import json

from app.db.db import SessionLocal
from app.models.models import InvoiceAudit
from app.rag.embeddings import embed
from app.rag.vector_store import ensure_collection, upsert
from qdrant_client.models import PointStruct


def invoice_to_report(invoice: InvoiceAudit) -> dict:
    line_items = [
        {
            "line_number": item.line_number,
            "item_code": item.item_code,
            "description": item.description,
            "quantity": item.quantity,
            "unit_price": item.unit_price,
            "line_total": item.line_total,
        }
        for item in getattr(invoice, "line_items", [])
    ]
    discrepancies = [
        {
            "field_name": item.field_name,
            "invoice_value": item.invoice_value,
            "erp_value": item.erp_value,
            "deviation_pct": item.deviation_pct,
            "severity": item.severity,
            "detected_at": item.detected_at.isoformat() if item.detected_at else None,
        }
        for item in getattr(invoice, "discrepancies", [])
    ]
    feedback = [
        {
            "field_name": item.field_name,
            "original_value": item.original_value,
            "corrected_value": item.corrected_value,
            "corrected_by": item.corrected_by,
            "corrected_at": item.corrected_at.isoformat()
            if item.corrected_at
            else None,
            "revalidated": item.revalidated,
        }
        for item in getattr(invoice, "feedback", [])
    ]
    report = {
        "report_type": "invoice_audit_report",
        "generated_at": None,
        "invoice": {
            "invoice_id": str(invoice.invoice_id),
            "invoice_number": invoice.invoice_number,
            "vendor_name": invoice.vendor_name,
            "invoice_date": str(invoice.invoice_date) if invoice.invoice_date else None,
            "currency": invoice.currency,
            "total_amount": str(invoice.total_amount)
            if invoice.total_amount is not None
            else None,
            "validation_status": invoice.validation_status,
            "recommendation": invoice.recommendation,
            "raw_extracted_text": invoice.raw_extracted_text,
            "translated_text": invoice.translated_text,
        },
        "line_items": line_items,
        "discrepancies": discrepancies,
        "human_feedback": feedback,
        "summary": {
            "invoice_id": str(invoice.invoice_id),
            "invoice_number": invoice.invoice_number,
            "vendor_name": invoice.vendor_name,
            "validation_status": invoice.validation_status,
            "recommendation": invoice.recommendation,
            "missing_fields": [],
            "missing_field_count": 0,
            "feedback_count": len(feedback),
        },
    }
    return report


def report_to_text(report: dict) -> str:
    invoice = report.get("invoice", {}) or {}
    summary = report.get("summary", {}) or {}
    line_items = report.get("line_items", []) or []
    discrepancies = report.get("discrepancies", []) or []
    feedback = report.get("human_feedback", []) or []
    parts = [
        "Invoice audit report",
        f"Invoice number: {summary.get('invoice_number') or invoice.get('invoice_number') or 'unknown'}",
        f"Vendor: {summary.get('vendor_name') or invoice.get('vendor_name') or 'unknown'}",
        f"Date: {invoice.get('invoice_date') or 'unknown'}",
        f"Amount: {invoice.get('total_amount') or 'unknown'} {invoice.get('currency') or ''}",
        f"Status: {summary.get('validation_status') or invoice.get('validation_status') or 'unknown'}",
        f"Recommendation: {summary.get('recommendation') or 'unknown'}",
        f"Feedback count: {len(feedback)}",
        f"Line item count: {len(line_items)}",
        f"Discrepancy count: {len(discrepancies)}",
        "Report JSON:",
        json.dumps(report, ensure_ascii=False, default=str),
    ]
    return "\n".join(parts)


def index_report(report: dict) -> None:
    invoice = report.get("invoice", {}) or {}
    summary = report.get("summary", {}) or {}
    invoice_id = invoice.get("invoice_id") or summary.get("invoice_id")
    if invoice_id is None:
        raise ValueError("Report payload is missing invoice_id")
    text = report_to_text(report)
    vector = embed(text)
    point = PointStruct(
        id=str(invoice_id),
        vector=vector,
        payload={
            "invoice_id": str(invoice_id),
            "invoice_number": invoice.get("invoice_number")
            or summary.get("invoice_number"),
            "vendor_name": invoice.get("vendor_name") or summary.get("vendor_name"),
            "invoice_date": invoice.get("invoice_date") or summary.get("invoice_date"),
            "validation_status": invoice.get("validation_status")
            or summary.get("validation_status"),
            "recommendation": invoice.get("recommendation")
            or summary.get("recommendation"),
            "report_json": json.dumps(report, ensure_ascii=False, default=str),
            "text": text,
        },
    )
    ensure_collection()
    upsert([point])


def index_invoice(invoice: InvoiceAudit) -> None:
    report = invoice_to_report(invoice)
    index_report(report)


def rebuild_index() -> int:
    ensure_collection()
    db = SessionLocal()
    try:
        invoices = db.query(InvoiceAudit).all()
        for invoice in invoices:
            try:
                index_invoice(invoice)
            except Exception:
                pass
        return len(invoices)
    finally:
        db.close()
