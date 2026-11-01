from copy import copy
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, TypedDict
from uuid import UUID

from app.db.db import SessionLocal
from app.models.models import HumanFeedback, InvoiceAudit
from langgraph.graph import END, START, StateGraph


def apply_feedback_value(field_name: str, corrected_value: str | None) -> Any:
    field = (field_name or "").strip()
    if corrected_value is None:
        return None
    value = str(corrected_value).strip()
    if value == "" or value.lower() in {"none", "null"}:
        return None
    try:
        if field == "invoice_date":
            for candidate in (
                value,
                value.replace("T", " "),
                value.replace("/", "-"),
            ):
                try:
                    return date.fromisoformat(candidate[:10])
                except ValueError:
                    pass
                for fmt in (
                    "%d-%m-%Y",
                    "%d/%m/%Y",
                    "%d.%m.%Y",
                    "%d %B %Y",
                    "%d %b %Y",
                    "%Y/%m/%d",
                    "%Y-%m-%d",
                ):
                    try:
                        return datetime.strptime(candidate, fmt).date()
                    except ValueError:
                        continue
            raise ValueError(f"Unsupported invoice_date format: {value}")
        if field in {
            "total_amount",
            "subtotal",
            "tax_amount",
            "line_total",
            "unit_price",
        }:
            return Decimal(value.replace(",", ""))
        return value
    except (InvalidOperation, ValueError):
        return value


def apply_feedback_to_invoice(
    invoice: InvoiceAudit, field_name: str, corrected_value: str | None
) -> InvoiceAudit:
    if invoice is None:
        raise ValueError("invoice is required")
    field = (field_name or "").strip()
    if not field:
        raise ValueError("field_name is required")
    effective = copy(invoice)
    setattr(effective, field, apply_feedback_value(field, corrected_value))
    return effective


def apply_feedback_overrides(
    invoice: InvoiceAudit, feedback_rows: list[Any]
) -> InvoiceAudit:
    if invoice is None:
        return invoice
    ordered = sorted(
        feedback_rows,
        key=lambda item: (
            getattr(item, "corrected_at", None) or datetime.min.replace(tzinfo=None)
        ),
        reverse=True,
    )
    seen: dict[str, str] = {}
    for feedback in ordered:
        field_name = (getattr(feedback, "field_name", None) or "").strip()
        if not field_name or field_name in seen:
            continue
        corrected_value = getattr(feedback, "corrected_value", None)
        if corrected_value is None:
            continue
        seen[field_name] = str(corrected_value).strip()
    effective = copy(invoice)
    for field_name, corrected_value in seen.items():
        setattr(
            effective, field_name, apply_feedback_value(field_name, corrected_value)
        )
    return effective


class FeedbackState(TypedDict, total=False):
    invoice_id: str
    field_name: str
    original_value: str | None
    corrected_value: str | None
    corrected_by: str | None
    feedback_id: int | None
    status: str
    message: str


def add_feedback_node(state: FeedbackState) -> dict[str, Any]:
    field_name = (state.get("field_name") or "").strip()
    if not field_name:
        return {"status": "failed", "message": "field_name is required."}
    if len(field_name) > 255:
        return {"status": "failed", "message": "field_name exceeds 255 characters."}
    corrected_by = state.get("corrected_by")
    if corrected_by and len(corrected_by) > 128:
        return {"status": "failed", "message": "corrected_by exceeds 128 characters."}
    db = SessionLocal()
    try:
        parsed_id = UUID(state["invoice_id"])
    except (ValueError, TypeError):
        return {"status": "failed", "message": "Invalid invoice_id."}
    try:
        invoice = (
            db.query(InvoiceAudit).filter(InvoiceAudit.invoice_id == parsed_id).first()
        )
        if invoice is None:
            return {"status": "failed", "message": "Invoice not found."}
        feedback = HumanFeedback(
            invoice_id=parsed_id,
            field_name=field_name,
            original_value=state.get("original_value"),
            corrected_value=state.get("corrected_value"),
            corrected_by=corrected_by,
            revalidated=False,
        )
        db.add(feedback)
        db.flush()
        db.commit()
        db.refresh(feedback)
        return {
            "status": "success",
            "feedback_id": feedback.id,
            "message": "",
        }
    except Exception as exc:
        db.rollback()
        return {"status": "failed", "message": str(exc)}
    finally:
        db.close()


def build() -> Any:
    builder = StateGraph(FeedbackState)
    builder.add_node("add_feedback", add_feedback_node)
    builder.add_edge(START, "add_feedback")
    builder.add_edge("add_feedback", END)
    return builder.compile()


graph = build()
