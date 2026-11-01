import html

import pandas as pd
import streamlit as st
from db import query
from ui_helpers import fmt_currency, severity_badge, status_badge


def detail_card(label: str, value: str) -> None:
    safe_label = html.escape(label)
    safe_value = html.escape(value or "-")
    st.markdown(
        f"""
        <div style="
            min-height: 112px;
            padding: 14px 16px;
            border: 1px solid rgba(148, 163, 184, 0.22);
            border-radius: 16px;
            background: linear-gradient(135deg, rgba(248, 250, 252, 0.95), rgba(241, 245, 249, 0.8));
            box-shadow: 0 6px 18px rgba(15, 23, 42, 0.05);
            display: flex;
            flex-direction: column;
            justify-content: center;
        ">
            <div style="
                color: #000000;
                font-size: 0.78rem;
                line-height: 1.1;
                margin-bottom: 8px;
            ">{safe_label}</div>
            <div style="
                color: #000000;
                font-size: clamp(0.78rem, 1.1vw, 1.05rem);
                line-height: 1.2;
                font-weight: 600;
                white-space: normal;
                overflow-wrap: anywhere;
                word-break: break-word;
            ">{safe_value}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def report_html(invoice_id: str) -> str:
    invoice_rows = query(
        """
        SELECT *
        FROM audit.invoice_audit
        WHERE invoice_id = :iid
        LIMIT 1
        """,
        {"iid": invoice_id},
    )
    invoice = invoice_rows[0] if invoice_rows else None
    if invoice is None:
        return "<p>No invoice found.</p>"
    line_items = query(
        """
        SELECT line_number, item_code, description, quantity, unit_price, line_total
        FROM audit.invoice_line_items
        WHERE invoice_id = :iid
        ORDER BY line_number
        """,
        {"iid": invoice_id},
    )
    discrepancies = query(
        """
        SELECT field_name, invoice_value, erp_value, deviation_pct, severity, detected_at
        FROM audit.discrepancies
        WHERE invoice_id = :iid
        ORDER BY detected_at
        """,
        {"iid": invoice_id},
    )
    feedback_rows = query(
        """
        SELECT field_name, original_value, corrected_value, corrected_by, corrected_at, revalidated
        FROM audit.human_feedback
        WHERE invoice_id = :iid
        ORDER BY corrected_at DESC
        """,
        {"iid": invoice_id},
    )

    def table(rows: list[dict], columns: list[str]) -> str:
        if not rows:
            return "<p class='empty'>None recorded.</p>"
        header = "".join(
            f"<th>{html.escape(col.replace('_', ' ').title())}</th>" for col in columns
        )
        body = []
        for row in rows:
            cells = []
            for col in columns:
                value = row.get(col)
                if hasattr(value, "isoformat"):
                    value = value.isoformat()
                cells.append(
                    f"<td>{html.escape(str(value) if value is not None else '-')}</td>"
                )
            body.append(f"<tr>{''.join(cells)}</tr>")
        return f"<table><thead><tr>{header}</tr></thead><tbody>{''.join(body)}</tbody></table>"

    invoice_rows = [
        {"field": key, "value": value}
        for key, value in invoice.items()
        if value is not None and key not in {"raw_extracted_text", "translated_text"}
    ]
    summary_rows = [
        {"field": "invoice_number", "value": invoice.get("invoice_number")},
        {"field": "vendor_name", "value": invoice.get("vendor_name")},
        {"field": "validation_status", "value": invoice.get("validation_status")},
        {"field": "recommendation", "value": invoice.get("recommendation")},
        {"field": "feedback_count", "value": len(feedback_rows)},
    ]
    report_html = f"""
    <!doctype html>
    <html lang="en">
    <head>
      <meta charset="utf-8">
      <style>
        body {{font-family: Arial, sans-serif; margin: 0; padding: 24px; background: #f6f7fb; color: #1f2937; }}
        .sheet {{max-width: 1200px; margin: 0 auto; background: white; border-radius: 16px; padding: 28px; box-shadow: 0 12px 30px rgba(15, 23, 42, 0.08); }}
        h1, h2 {{margin: 0 0 12px; }}
        h1 {{font-size: 30px; }}
        h2 {{margin-top: 28px; font-size: 20px; border-bottom: 1px solid #e5e7eb; padding-bottom: 8px; }}
        table {{width: 100%; border-collapse: collapse; margin-top: 10px; background: white; }}
        th, td {{border: 1px solid #e5e7eb; padding: 10px 12px; text-align: left; vertical-align: top; }}
        th {{background: #f3f4f6; font-size: 13px; text-transform: capitalize; }}
        .empty {{color: #6b7280; font-style: italic; }}
      </style>
    </head>
    <body>
      <main class="sheet">
        <h1>Invoice Audit Report</h1>
        <p><strong>Invoice:</strong> {html.escape(str(invoice.get("invoice_number") or "-"))}</p>
        <p><strong>Vendor:</strong> {html.escape(str(invoice.get("vendor_name") or "-"))}</p>
        <p><strong>Status:</strong> {html.escape(str(invoice.get("validation_status") or "-"))}</p>
        <p><strong>Recommendation:</strong> {html.escape(str(invoice.get("recommendation") or "-"))}</p>
        <h2>Summary</h2>
        {table(summary_rows, ["field", "value"])}
        <h2>Invoice Fields</h2>
        {table(invoice_rows, ["field", "value"])}
        <h2>Line Items</h2>
        {table(line_items, ["line_number", "item_code", "description", "quantity", "unit_price", "line_total"])}
        <h2>Discrepancies</h2>
        {table(discrepancies, ["field_name", "invoice_value", "erp_value", "deviation_pct", "severity", "detected_at"])}
        <h2>Human Feedback</h2>
        {table(feedback_rows, ["field_name", "original_value", "corrected_value", "corrected_by", "corrected_at", "revalidated"])}
      </main>
    </body>
    </html>
    """
    return report_html


top_left, top_right = st.columns([3, 1])
top_left.title("Invoice Detail")
if top_right.button("Refresh detail", use_container_width=True):
    st.rerun()
invoice_rows = query(
    """
    SELECT invoice_id, invoice_number, vendor_name, processed_at
    FROM audit.invoice_audit
    ORDER BY processed_at DESC
    """
)
if not invoice_rows:
    st.info("No invoices are available yet.")
    st.stop()
label_map = {
    str(row["invoice_id"]): (
        f"{row.get('invoice_number') or '(no number)'} | "
        f"{row.get('vendor_name') or '(no vendor)'} | {str(row['invoice_id'])}"
    )
    for row in invoice_rows
}
active_invoice_id = st.session_state.get("active_invoice_id")
index = 0
if active_invoice_id in label_map:
    index = list(label_map.keys()).index(active_invoice_id)
selected_invoice_id = st.selectbox(
    "Select invoice",
    list(label_map.keys()),
    index=index,
    format_func=lambda value: label_map[value],
    key="detail_invoice_selector",
)
st.session_state["active_invoice_id"] = selected_invoice_id
invoice_id = str(selected_invoice_id)
invoice_rows = query(
    """
    SELECT *
    FROM audit.invoice_audit
    WHERE invoice_id = :iid
    LIMIT 1
    """,
    {"iid": invoice_id},
)
inv = invoice_rows[0] if invoice_rows else None
if inv is None:
    st.warning("No invoice found with that ID or invoice number.")
    st.stop()
st.subheader(f"Invoice {inv.get('invoice_number') or '(no number)'}")
with st.container(border=True):
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        detail_card("Vendor", inv.get("vendor_name") or "-")
    with col2:
        detail_card("Date", str(inv.get("invoice_date") or "-"))
    with col3:
        detail_card(
            "Amount", fmt_currency(inv.get("total_amount"), inv.get("currency"))
        )
    with col4:
        detail_card("PO Number", inv.get("po_number") or "-")
    col5, col6, col7 = st.columns(3)
    col5.markdown(
        f"**Validation Status:** {status_badge(inv.get('validation_status'))}"
    )
    col6.markdown(f"**Recommendation:** {status_badge(inv.get('recommendation'))}")
    col7.markdown(f"**Source Language:** {inv.get('source_language') or '-'}")
    if inv.get("translation_confidence") is not None:
        st.caption(
            f"Translation confidence: {float(inv['translation_confidence']):.1%}"
        )
tab_items, tab_disc, tab_text, tab_report, tab_raw = st.tabs(
    [
        "Line Items",
        "Discrepancies",
        "Extracted Text",
        "Complete Report",
        "Raw Audit Record",
    ]
)
with tab_items:
    try:
        items = query(
            """
            SELECT line_number, item_code, description, quantity, unit_price, line_total
            FROM audit.invoice_line_items
            WHERE invoice_id = :iid
            ORDER BY line_number
            """,
            {"iid": invoice_id},
        )
    except Exception as exc:
        st.error(f"Database error: {exc}")
        items = []
    if items:
        df = pd.DataFrame(items)
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.info("No line items recorded for this invoice.")
with tab_disc:
    try:
        discs = query(
            """
            SELECT field_name, invoice_value, erp_value, deviation_pct, severity, detected_at
            FROM audit.discrepancies
            WHERE invoice_id = :iid
            ORDER BY detected_at
            """,
            {"iid": invoice_id},
        )
    except Exception as exc:
        st.error(f"Database error: {exc}")
        discs = []
    if discs:
        for d in discs:
            with st.expander(f"{d['field_name']} - {d.get('severity') or 'unknown'}"):
                c1, c2, c3, c4 = st.columns([2, 2, 2, 1])
                c1.markdown(f"**Field:** `{d['field_name']}`")
                c2.markdown(f"**Invoice:** {d.get('invoice_value') or '-'}")
                c3.markdown(f"**ERP:** {d.get('erp_value') or '-'}")
                dev = d.get("deviation_pct")
                dev_str = f"{float(dev):.2f}%" if dev is not None else "-"
                c4.markdown(
                    f"**Deviation:** {dev_str}  \n**Severity:** {severity_badge(d.get('severity'))}"
                )
    else:
        st.success("No discrepancies recorded for this invoice.")
with tab_text:
    raw_text = inv.get("raw_extracted_text") or ""
    translated_text = inv.get("translated_text") or ""
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**Original Extracted Text**")
        st.text_area(
            "",
            raw_text,
            height=350,
            key=f"raw_t_{invoice_id}",
            disabled=True,
        )
    with c2:
        st.markdown("**Translated Text (English)**")
        st.text_area(
            "",
            translated_text,
            height=350,
            key=f"trans_t_{invoice_id}",
            disabled=True,
        )
with tab_report:
    st.components.v1.html(report_html(invoice_id), height=1100, scrolling=True)
with tab_raw:
    display = {
        k: v
        for k, v in inv.items()
        if k not in ("raw_extracted_text", "translated_text")
    }
    for k, v in display.items():
        if hasattr(v, "isoformat"):
            display[k] = str(v)
        elif v is not None and not isinstance(v, (str, int, float, bool, dict, list)):
            display[k] = str(v)
    st.json(display)
