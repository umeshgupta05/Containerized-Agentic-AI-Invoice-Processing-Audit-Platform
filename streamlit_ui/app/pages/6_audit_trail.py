import pandas as pd
import streamlit as st
from db import query


top_left, top_right = st.columns([3, 1])
top_left.title("Processing Audit Trail")
if top_right.button("Refresh audit trail", use_container_width=True):
    st.rerun()
status_filter = st.selectbox(
    "Status",
    ["all", "success", "failed"],
    index=0,
)
try:
    filters = []
    if status_filter != "all":
        filters.append(f"status = '{status_filter}'")
    where_clause = f" WHERE {' AND '.join(filters)}" if filters else ""
    rows = query(
        f"""
        SELECT
            id,
            filename,
            CAST(invoice_id AS text) AS invoice_id,
            status,
            reason,
            report,
            detected_at
        FROM audit.processing_audit_log
        {where_clause}
        ORDER BY detected_at DESC
        LIMIT 200
        """
    )
except Exception as exc:
    st.warning(f"Could not load audit trail: {exc}")
    rows = []
if not rows:
    st.info("No processing events recorded yet.")
    st.stop()
frame = pd.DataFrame(rows)
if "invoice_id" in frame.columns:
    frame["invoice_id"] = frame["invoice_id"].map(
        lambda value: None if value is None else str(value)
    )
if "report" in frame.columns:
    frame["report_preview"] = frame["report"].apply(
        lambda value: "stored" if value is not None else "-"
    )
    frame = frame.drop(columns=["report"], errors="ignore")
st.dataframe(frame, use_container_width=True, hide_index=True)
selected = st.selectbox(
    "Select an audit record to inspect",
    options=[row["id"] for row in rows],
    index=0,
)
selected_row = next((row for row in rows if row["id"] == selected), None)
if selected_row:
    st.subheader(f"Audit Record #{selected_row['id']}")
    st.json(
        {
            "filename": selected_row.get("filename"),
            "invoice_id": str(selected_row.get("invoice_id"))
            if selected_row.get("invoice_id") is not None
            else None,
            "status": selected_row.get("status"),
            "reason": selected_row.get("reason") or "",
            "detected_at": selected_row.get("detected_at"),
            "report": selected_row.get("report"),
        }
    )
