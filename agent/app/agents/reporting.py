from __future__ import annotations

import html
import json
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import UUID

from app.models.models import Discrepancy, HumanFeedback, InvoiceAudit, InvoiceLineItem


def missing_fields(invoice: Any) -> list[str]:
    stored = getattr(invoice, "missing_fields", None)
    if isinstance(stored, list):
        return [str(field) for field in stored]
    required = (
        "invoice_number",
        "invoice_date",
        "vendor_name",
        "currency",
        "total_amount",
    )
    return [field for field in required if getattr(invoice, field, None) is None]


def summarize_discrepancies(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_severity: dict[str, int] = {}
    by_field: dict[str, int] = {}
    for row in rows:
        severity = str(row.get("severity") or row.get("level") or "unspecified").lower()
        field = str(
            row.get("field_name")
            or row.get("field")
            or row.get("discrepancy_type")
            or "unspecified"
        )
        by_severity[severity] = by_severity.get(severity, 0) + 1
        by_field[field] = by_field.get(field, 0) + 1
    return {"total": len(rows), "by_severity": by_severity, "by_field": by_field}


def table_rows(rows: list[dict[str, Any]], columns: list[str]) -> str:
    if not rows:
        return "<p class='empty'>None recorded.</p>"
    header = "".join(
        f"<th>{html.escape(column.replace('_', ' ').title())}</th>"
        for column in columns
    )
    body_rows = []
    for row in rows:
        cells = []
        for column in columns:
            value = row.get(column)
            if hasattr(value, "isoformat"):
                value = value.isoformat()
            cells.append(
                f"<td>{html.escape(str(value) if value is not None else '-')}</td>"
            )
        body_rows.append(f"<tr>{''.join(cells)}</tr>")
    return f"<table><thead><tr>{header}</tr></thead><tbody>{''.join(body_rows)}</tbody></table>"


def report_to_html(report: dict[str, Any]) -> str:
    invoice = report.get("invoice", {}) or {}
    summary = report.get("summary", {}) or {}
    line_items = [
        item for item in report.get("line_items", []) if isinstance(item, dict)
    ]
    discrepancies = [
        item for item in report.get("discrepancies", []) if isinstance(item, dict)
    ]
    feedback = [
        item for item in report.get("human_feedback", []) if isinstance(item, dict)
    ]
    summary_rows = [
        {"field": key, "value": value}
        for key, value in summary.items()
        if value is not None
    ]
    invoice_rows = [
        {"field": key, "value": value}
        for key, value in invoice.items()
        if value is not None
    ]
    line_columns = [
        "line_number",
        "item_code",
        "description",
        "quantity",
        "unit_price",
        "line_total",
    ]
    discrepancy_columns = [
        "field_name",
        "invoice_value",
        "erp_value",
        "deviation_pct",
        "severity",
        "detected_at",
    ]
    feedback_columns = [
        "field_name",
        "original_value",
        "corrected_value",
        "corrected_by",
        "corrected_at",
        "revalidated",
    ]
    template = """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Invoice Audit Report</title>
  <style>
    body { font-family: Arial, Helvetica, sans-serif; margin: 0; padding: 24px; background: #f6f7fb; color: #1f2937; }
    .sheet { max-width: 1200px; margin: 0 auto; background: #fff; border-radius: 16px; padding: 28px; box-shadow: 0 12px 30px rgba(15, 23, 42, 0.08); }
    h1, h2 { margin: 0 0 12px; }
    h1 { font-size: 30px; }
    h2 { margin-top: 28px; font-size: 20px; border-bottom: 1px solid #e5e7eb; padding-bottom: 8px; }
    p { line-height: 1.5; }
    .meta { color: #6b7280; margin-bottom: 18px; }
    .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 12px; margin: 16px 0 8px; }
    .card { border: 1px solid #e5e7eb; border-radius: 12px; padding: 14px; background: #fafafa; }
    .card label { display: block; font-size: 12px; text-transform: uppercase; letter-spacing: .06em; color: #6b7280; margin-bottom: 6px; }
    .card div { font-size: 15px; font-weight: 600; word-break: break-word; }
    table { width: 100%; border-collapse: collapse; margin-top: 10px; background: white; }
    th, td { border: 1px solid #e5e7eb; padding: 10px 12px; text-align: left; vertical-align: top; }
    th { background: #f3f4f6; font-size: 13px; text-transform: capitalize; }
    .empty { color: #6b7280; font-style: italic; }
    .section { margin-top: 24px; }
    .json { white-space: pre-wrap; background: #0f172a; color: #e2e8f0; padding: 16px; border-radius: 12px; overflow-x: auto; }
  </style>
</head>
<body>
  <main class="sheet">
    <h1>Invoice Audit Report</h1>
    <p class="meta">Generated at __GENERATED_AT__</p>

    <div class="grid">
      <div class="card"><label>Invoice Number</label><div>__INVOICE_NUMBER__</div></div>
      <div class="card"><label>Vendor</label><div>__VENDOR_NAME__</div></div>
      <div class="card"><label>Status</label><div>__VALIDATION_STATUS__</div></div>
      <div class="card"><label>Recommendation</label><div>__RECOMMENDATION__</div></div>
      <div class="card"><label>Missing Fields</label><div>__MISSING_FIELDS__</div></div>
      <div class="card"><label>Feedback Entries</label><div>__FEEDBACK_COUNT__</div></div>
    </div>

    <div class="section">
      <h2>Report Summary</h2>
      __SUMMARY_TABLE__
    </div>

    <div class="section">
      <h2>Invoice Fields</h2>
      __INVOICE_TABLE__
    </div>

    <div class="section">
      <h2>Line Items</h2>
      __LINE_ITEMS_TABLE__
    </div>

    <div class="section">
      <h2>Discrepancies</h2>
      __DISCREPANCY_TABLE__
    </div>

    <div class="section">
      <h2>Human Feedback</h2>
      __FEEDBACK_TABLE__
    </div>

    <div class="section">
      <h2>Report JSON</h2>
      <div class="json">__REPORT_JSON__</div>
    </div>
  </main>
</body>
</html>
"""
    return (
        template.replace(
            "__GENERATED_AT__", html.escape(str(report.get("generated_at", "")))
        )
        .replace(
            "__INVOICE_NUMBER__",
            html.escape(
                str(
                    summary.get("invoice_number")
                    or invoice.get("invoice_number")
                    or "-"
                )
            ),
        )
        .replace(
            "__VENDOR_NAME__",
            html.escape(
                str(summary.get("vendor_name") or invoice.get("vendor_name") or "-")
            ),
        )
        .replace(
            "__VALIDATION_STATUS__",
            html.escape(
                str(
                    summary.get("validation_status")
                    or invoice.get("validation_status")
                    or "-"
                )
            ),
        )
        .replace(
            "__RECOMMENDATION__",
            html.escape(
                str(
                    summary.get("recommendation")
                    or invoice.get("recommendation")
                    or "-"
                )
            ),
        )
        .replace(
            "__MISSING_FIELDS__",
            html.escape(
                ", ".join(map(str, summary.get("missing_fields", []))) or "None"
            ),
        )
        .replace("__FEEDBACK_COUNT__", html.escape(str(len(feedback))))
        .replace("__SUMMARY_TABLE__", table_rows(summary_rows, ["field", "value"]))
        .replace("__INVOICE_TABLE__", table_rows(invoice_rows, ["field", "value"]))
        .replace("__LINE_ITEMS_TABLE__", table_rows(line_items, line_columns))
        .replace(
            "__DISCREPANCY_TABLE__", table_rows(discrepancies, discrepancy_columns)
        )
        .replace("__FEEDBACK_TABLE__", table_rows(feedback, feedback_columns))
        .replace(
            "__REPORT_JSON__",
            html.escape(json.dumps(report, indent=2, ensure_ascii=False, default=str)),
        )
    )


def build_invoice_report(db: Any, invoice_id: str | UUID) -> dict[str, Any]:
    invoice = (
        db.query(InvoiceAudit).filter(InvoiceAudit.invoice_id == invoice_id).first()
    )
    if invoice is None:
        try:
            parsed_id = UUID(str(invoice_id))
            invoice = (
                db.query(InvoiceAudit)
                .filter(InvoiceAudit.invoice_id == parsed_id)
                .first()
            )
        except (ValueError, TypeError, AttributeError):
            invoice = None
    if invoice is None:
        raise ValueError(f"Invoice audit record not found: {invoice_id}")
    line_item_data = [
        {
            "id": row.id,
            "invoice_id": row.invoice_id,
            "line_number": row.line_number,
            "item_code": row.item_code,
            "description": row.description,
            "quantity": row.quantity,
            "unit_price": row.unit_price,
            "line_total": row.line_total,
        }
        for row in db.query(InvoiceLineItem)
        .filter(InvoiceLineItem.invoice_id == invoice.invoice_id)
        .all()
    ]
    discrepancy_data = [
        {
            "id": row.id,
            "invoice_id": row.invoice_id,
            "field_name": row.field_name,
            "invoice_value": row.invoice_value,
            "erp_value": row.erp_value,
            "deviation_pct": row.deviation_pct,
            "severity": row.severity,
            "detected_at": row.detected_at,
        }
        for row in db.query(Discrepancy)
        .filter(Discrepancy.invoice_id == invoice.invoice_id)
        .all()
    ]
    feedback_data = [
        {
            "id": row.id,
            "invoice_id": row.invoice_id,
            "field_name": row.field_name,
            "original_value": row.original_value,
            "corrected_value": row.corrected_value,
            "corrected_by": row.corrected_by,
            "corrected_at": row.corrected_at,
            "revalidated": row.revalidated,
        }
        for row in db.query(HumanFeedback)
        .filter(HumanFeedback.invoice_id == invoice.invoice_id)
        .all()
    ]
    missing = missing_fields(invoice)
    report = {
        "report_type": "invoice_audit_report",
        "generated_at": datetime.now().astimezone().isoformat(),
        "invoice": {
            "invoice_id": invoice.invoice_id,
            "file_path": invoice.file_path,
            "file_checksum": invoice.file_checksum,
            "extraction_method": invoice.extraction_method,
            "raw_extracted_text": invoice.raw_extracted_text,
            "translated_text": invoice.translated_text,
            "source_language": invoice.source_language,
            "translation_confidence": invoice.translation_confidence,
            "invoice_number": invoice.invoice_number,
            "vendor_name": invoice.vendor_name,
            "po_number": invoice.po_number,
            "invoice_date": invoice.invoice_date,
            "currency": invoice.currency,
            "total_amount": invoice.total_amount,
            "validation_status": invoice.validation_status,
            "recommendation": invoice.recommendation,
            "extracted_raw": invoice.extracted_raw,
            "thread_id": invoice.thread_id,
            "processed_at": invoice.processed_at,
        },
        "line_items": line_item_data,
        "discrepancies": discrepancy_data,
        "human_feedback": feedback_data,
        "summary": {
            "invoice_id": str(invoice.invoice_id),
            "invoice_number": getattr(invoice, "invoice_number", None),
            "vendor_name": getattr(invoice, "vendor_name", None),
            "validation_status": getattr(invoice, "validation_status", None),
            "recommendation": invoice.recommendation or "manual_review",
            "missing_fields": missing,
            "missing_field_count": len(missing),
            "feedback_count": len(feedback_data),
            "translation": {
                "source_language": getattr(invoice, "source_language", None),
                "translation_confidence": getattr(
                    invoice, "translation_confidence", None
                ),
                "translation_performed": getattr(invoice, "translated_text", None)
                is not None,
            },
            "discrepancy_summary": summarize_discrepancies(discrepancy_data),
        },
    }
    return json.loads(json.dumps(report, ensure_ascii=False, default=str))


def report_stem(
    report: dict[str, Any], timestamp: str | None = None
) -> tuple[str, str]:
    invoice_id = str(report.get("summary", {}).get("invoice_id", "unknown"))
    safe_id = "".join(
        ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in invoice_id
    )
    stamp = timestamp or datetime.now().strftime("%Y%m%d_%H%M%S")
    return safe_id, stamp


def save_invoice_report(
    report: dict[str, Any],
    output_dir: str | Path = "reports",
    timestamp: str | None = None,
) -> Path:
    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    safe_id, stamp = report_stem(report, timestamp=timestamp)
    path = directory / f"invoice_report_{safe_id}_{stamp}.json"
    with path.open("w", encoding="utf-8") as file:
        json.dump(report, file, indent=2, ensure_ascii=False, default=str)
    return path


def save_invoice_report_html(
    report: dict[str, Any],
    output_dir: str | Path = "reports",
    timestamp: str | None = None,
) -> Path:
    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    safe_id, stamp = report_stem(report, timestamp=timestamp)
    path = directory / f"invoice_report_{safe_id}_{stamp}.html"
    path.write_text(report_to_html(report), encoding="utf-8")
    return path


def generate_invoice_report(
    invoice_id: str | UUID,
    db: Any,
    output_dir: str | Path = "reports",
) -> dict[str, Any]:
    report = build_invoice_report(db=db, invoice_id=invoice_id)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    json_path = save_invoice_report(report, output_dir=output_dir, timestamp=timestamp)
    html_path = save_invoice_report_html(
        report, output_dir=output_dir, timestamp=timestamp
    )
    report["report_file"] = str(json_path)
    report["report_html_file"] = str(html_path)
    try:
        from app.rag.indexing import index_report

        index_report(report)
    except Exception:
        pass
    return report
