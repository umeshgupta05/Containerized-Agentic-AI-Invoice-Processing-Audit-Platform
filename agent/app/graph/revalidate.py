from typing import Any, TypedDict
from uuid import UUID

from app.agents.business_validation import validate_business
from app.agents.data_validation import validate_invoice
from app.db.db import SessionLocal
from app.graph.feedback import apply_feedback_overrides
from app.models.models import HumanFeedback, InvoiceAudit
from langgraph.graph import END, START, StateGraph


class RevalidateState(TypedDict, total=False):
    invoice_id: str
    status: str
    validation_status: str | None
    recommendation: str | None
    message: str


def get_invoice_node(state: RevalidateState) -> dict[str, Any]:
    db = SessionLocal()
    try:
        parsed_id = UUID(state["invoice_id"])
        invoice = (
            db.query(InvoiceAudit).filter(InvoiceAudit.invoice_id == parsed_id).first()
        )
        if invoice is None:
            return {"status": "failed", "message": "Invoice not found."}
        return {"status": "running", "message": ""}
    except (ValueError, TypeError):
        return {"status": "failed", "message": "Invalid invoice_id."}
    finally:
        db.close()


def run_validation_node(state: RevalidateState) -> dict[str, Any]:
    if state.get("status") == "failed":
        return {}
    db = SessionLocal()
    original_commit = db.commit
    db.commit = db.flush
    try:
        parsed_id = UUID(state["invoice_id"])
        invoice = (
            db.query(InvoiceAudit).filter(InvoiceAudit.invoice_id == parsed_id).first()
        )
        if invoice is None:
            return {"status": "failed", "message": "Invoice not found."}
        feedback_rows = (
            db.query(HumanFeedback)
            .filter(HumanFeedback.invoice_id == parsed_id)
            .order_by(HumanFeedback.corrected_at.desc())
            .all()
        )
        effective_invoice = apply_feedback_overrides(invoice, feedback_rows)
        for feedback in feedback_rows:
            field_name = (feedback.field_name or "").strip()
            if field_name:
                setattr(invoice, field_name, getattr(effective_invoice, field_name))
        data_result = validate_invoice(invoice_id=state["invoice_id"], db=db)
        if data_result.get("status") == "failed":
            return {"status": "failed", "message": data_result.get("message", "")}
        business_result = validate_business(invoice_id=state["invoice_id"], db=db)
        if business_result.get("status") == "failed":
            return {"status": "failed", "message": business_result.get("message", "")}
        return {
            "validation_status": business_result.get(
                "validation_status", data_result.get("validation_status")
            ),
            "recommendation": business_result.get(
                "recommendation", data_result.get("recommendation")
            ),
        }
    except Exception as exc:
        return {"status": "failed", "message": str(exc)}
    finally:
        db.rollback()
        db.commit = original_commit
        db.close()


def mark_revalidated_node(state: RevalidateState) -> dict[str, Any]:
    if state.get("status") == "failed":
        return {}
    db = SessionLocal()
    try:
        parsed_id = UUID(state["invoice_id"])
        db.query(HumanFeedback).filter(
            HumanFeedback.invoice_id == parsed_id,
            HumanFeedback.revalidated.is_(False),
        ).update({"revalidated": True})
        db.commit()
        return {"status": "completed", "message": "Revalidation complete."}
    except Exception as exc:
        db.rollback()
        return {"status": "failed", "message": str(exc)}
    finally:
        db.close()


def should_stop(state: RevalidateState) -> str:
    return "stop" if state.get("status") == "failed" else "continue"


def build() -> Any:
    builder = StateGraph(RevalidateState)
    builder.add_node("get_invoice", get_invoice_node)
    builder.add_node("run_validation", run_validation_node)
    builder.add_node("mark_revalidated", mark_revalidated_node)
    builder.add_edge(START, "get_invoice")
    builder.add_conditional_edges(
        "get_invoice", should_stop, {"continue": "run_validation", "stop": END}
    )
    builder.add_conditional_edges(
        "run_validation", should_stop, {"continue": "mark_revalidated", "stop": END}
    )
    builder.add_edge("mark_revalidated", END)
    return builder.compile()


graph = build()
