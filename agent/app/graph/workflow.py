from collections.abc import Callable
from typing import Any

from app.agents.business_validation import validate_business
from app.agents.data_validation import validate_invoice
from app.agents.extractor import extract_invoice
from app.agents.reporting import generate_invoice_report
from app.agents.translation import translate_invoice
from app.db.db import SessionLocal
from app.graph.state import InvoiceAuditState
from langgraph.graph import END, START, StateGraph


def open_session():
    return SessionLocal()


def record_error(
    state: InvoiceAuditState, stage: str, exc: Exception
) -> dict[str, Any]:
    errors = list(state.get("errors", []))
    errors.append(
        {"stage": stage, "error_type": type(exc).__name__, "message": str(exc)}
    )
    return {"status": "failed", "current_stage": stage, "errors": errors}


def run_stage(
    state: InvoiceAuditState,
    stage: str,
    result_key: str,
    operation: Callable[[Any], Any],
    completed: bool = False,
    failure_fields: tuple[str, ...] = ("status",),
) -> dict[str, Any]:
    db = open_session()
    try:
        result = operation(db)
        result_data = result if isinstance(result, dict) else {"result": result}
        if isinstance(result, dict) and any(
            result.get(field) in {"failed", "error"} for field in failure_fields
        ):
            return {
                result_key: result_data,
                "status": "failed",
                "current_stage": stage,
            }
        updates = {
            result_key: result_data,
            "status": "completed" if completed else "running",
            "current_stage": stage,
        }
        if result_key == "report":
            updates["report_file"] = str(result_data.get("report_file", ""))
        return updates
    except Exception as exc:
        return record_error(state, stage, exc)
    finally:
        db.close()


def extraction_node(state: InvoiceAuditState) -> dict[str, Any]:
    return run_stage(
        state,
        "extraction",
        "extraction_result",
        lambda db: extract_invoice(
            file_path=state["file_path"],
            invoice_id=state["invoice_id"],
            db=db,
        ),
        failure_fields=("status", "extraction_status"),
    )


def translation_node(state: InvoiceAuditState) -> dict[str, Any]:
    return run_stage(
        state,
        "translation",
        "translation_result",
        lambda db: translate_invoice(invoice_id=state["invoice_id"], db=db),
    )


def data_validation_node(state: InvoiceAuditState) -> dict[str, Any]:
    return run_stage(
        state,
        "data_validation",
        "data_validation_result",
        lambda db: validate_invoice(invoice_id=state["invoice_id"], db=db),
    )


def business_validation_node(state: InvoiceAuditState) -> dict[str, Any]:
    return run_stage(
        state,
        "business_validation",
        "business_validation_result",
        lambda db: validate_business(invoice_id=state["invoice_id"], db=db),
    )


def reporting_node(state: InvoiceAuditState) -> dict[str, Any]:
    return run_stage(
        state,
        "reporting",
        "report",
        lambda db: generate_invoice_report(invoice_id=state["invoice_id"], db=db),
        completed=True,
        failure_fields=(),
    )


def route_after_stage(state: InvoiceAuditState) -> str:
    return "stop" if state.get("status") == "failed" else "continue"


def build() -> Any:
    builder = StateGraph(InvoiceAuditState)
    builder.add_node("extract", extraction_node)
    builder.add_node("translate", translation_node)
    builder.add_node("data_validate", data_validation_node)
    builder.add_node("business_validate", business_validation_node)
    builder.add_node("report", reporting_node)
    builder.add_edge(START, "extract")
    builder.add_conditional_edges(
        "extract", route_after_stage, {"continue": "translate", "stop": END}
    )
    builder.add_conditional_edges(
        "translate", route_after_stage, {"continue": "data_validate", "stop": END}
    )
    builder.add_conditional_edges(
        "data_validate",
        route_after_stage,
        {"continue": "business_validate", "stop": END},
    )
    builder.add_conditional_edges(
        "business_validate", route_after_stage, {"continue": "report", "stop": END}
    )
    builder.add_edge("report", END)
    return builder.compile()


graph = build()
