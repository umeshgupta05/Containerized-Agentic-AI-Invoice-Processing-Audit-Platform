import pandas as pd
import streamlit as st
from api import get
from db import query
from ui_helpers import fmt_currency

st.title("Invoice Audit Dashboard")
st.caption("Quick invoice status, filters, and review navigation.")
if "show_actual_invoice_table" not in st.session_state:
    st.session_state["show_actual_invoice_table"] = False
if st.button("Refresh dashboard", use_container_width=False):
    st.rerun()


health = get("/health")
if health:
    with st.expander("Service health", expanded=False):
        cols = st.columns(len(health))
        for col, (svc, status) in zip(cols, health.items()):
            color = "green" if status == "ok" else "red"
            label = "Running" if status == "ok" else status
            col.markdown(f"**{svc.capitalize()}**  \n:{color}[{label}]")
with st.container(border=True):
    st.markdown("**Find invoices**")
    col_f1, col_f2, col_f3 = st.columns([2, 2, 3])
    status_options = [
        "All",
        "assessed",
        "review_required",
        "passed",
        "failed",
        "partial",
    ]
    rec_options = ["All", "approve", "manual_review", "reject"]
    status_filter = col_f1.selectbox("Validation status", status_options)
    rec_filter = col_f2.selectbox("Recommendation", rec_options)
    search = col_f3.text_input(
        "Search vendor or invoice number", placeholder="INV-001 or vendor"
    )
where_clauses = []
params: dict = {}
if status_filter != "All":
    where_clauses.append("ia.validation_status = :status")
    params["status"] = status_filter
if rec_filter != "All":
    where_clauses.append("ia.recommendation = :rec")
    params["rec"] = rec_filter
if search.strip():
    where_clauses.append(
        "(ia.vendor_name ILIKE :search OR ia.invoice_number ILIKE :search)"
    )
    params["search"] = f"%{search.strip()}%"
where_sql = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""
try:
    if st.session_state["show_actual_invoice_table"]:
        invoices = query(
            f"""
            SELECT
                ia.invoice_id,
                ia.invoice_number,
                ia.vendor_name,
                ia.invoice_date,
                ia.currency,
                ia.total_amount,
                ia.validation_status,
                ia.recommendation,
                ia.source_language,
                ia.processed_at,
                COALESCE(fb.feedback_count, 0) AS feedback_count,
                fb.last_feedback_at
            FROM audit.invoice_audit ia
            LEFT JOIN (
                SELECT
                    invoice_id,
                    COUNT(*) AS feedback_count,
                    MAX(corrected_at) AS last_feedback_at
                FROM audit.human_feedback
                GROUP BY invoice_id
            ) fb ON fb.invoice_id = ia.invoice_id
            {where_sql}
            ORDER BY ia.processed_at DESC
            """,
            params,
        )
    else:
        invoices = query(
            f"""
            SELECT
                invoice_id,
                invoice_number,
                vendor_name,
                invoice_date,
                currency,
                total_amount,
                validation_status,
                recommendation,
                source_language,
                processed_at
            FROM audit.invoice_audit ia
            {where_sql}
            ORDER BY processed_at DESC
            """,
            params,
        )
except Exception as exc:
    st.error(f"Database error: {exc}")
    st.stop()
total = len(invoices)
approved = sum(1 for r in invoices if r.get("recommendation") == "approve")
review = sum(1 for r in invoices if r.get("recommendation") == "manual_review")
rejected = sum(1 for r in invoices if r.get("recommendation") == "reject")
m1, m2, m3, m4 = st.columns(4)
m1.metric("Total Invoices", total)
m2.metric("Approved", approved)
m3.metric("Manual Review", review)
m4.metric("Rejected", rejected)
st.progress(0 if total == 0 else approved / total, text="Approval progress")
if not invoices:
    st.info("No invoices match the selected filters.")
    st.stop()
toggle_label = (
    "Show actual invoice table"
    if not st.session_state["show_actual_invoice_table"]
    else "Show human feedback table"
)
left, right = st.columns([1, 2])
if left.button(toggle_label, use_container_width=True):
    st.session_state["show_actual_invoice_table"] = not st.session_state[
        "show_actual_invoice_table"
    ]
    st.rerun()
if st.session_state["show_actual_invoice_table"]:
    right.caption("Showing raw audit rows.")
    rows = []
    for inv in invoices:
        rows.append(
            {
                "Invoice Number": inv.get("invoice_number") or "-",
                "Vendor": inv.get("vendor_name") or "-",
                "Date": str(inv.get("invoice_date") or "-"),
                "Amount": fmt_currency(inv.get("total_amount"), inv.get("currency")),
                "Language": inv.get("source_language") or "-",
                "Status": inv.get("validation_status") or "-",
                "Recommendation": inv.get("recommendation") or "-",
                "Processed": str(inv.get("processed_at") or "-")[:19],
                "invoice_id_hidden": str(inv.get("invoice_id", "")),
            }
        )
else:
    right.caption("Showing latest human corrections.")
    rows = []
    for inv in invoices:
        feedback_rows = query(
            """
            SELECT field_name, corrected_value, corrected_at
            FROM audit.human_feedback
            WHERE invoice_id = :iid
            ORDER BY corrected_at DESC
            """,
            {"iid": str(inv.get("invoice_id", ""))},
        )
        overrides: dict[str, str] = {}
        for feedback in feedback_rows:
            field_name = feedback.get("field_name")
            corrected_value = feedback.get("corrected_value")
            if (
                field_name
                and field_name not in overrides
                and corrected_value not in (None, "")
            ):
                overrides[field_name] = str(corrected_value)
        amount = fmt_currency(inv.get("total_amount"), inv.get("currency"))
        if "total_amount" in overrides:
            currency = overrides.get("currency") or inv.get("currency") or ""
            amount = f"{currency} {overrides['total_amount']}".strip()
        rows.append(
            {
                "Invoice ID": str(inv.get("invoice_id", "")),
                "Invoice Number": overrides.get("invoice_number")
                or inv.get("invoice_number")
                or "-",
                "Vendor": overrides.get("vendor_name") or inv.get("vendor_name") or "-",
                "Date": overrides.get("invoice_date") or inv.get("invoice_date") or "-",
                "Amount": amount,
                "Language": overrides.get("source_language")
                or inv.get("source_language")
                or "-",
                "Status": overrides.get("validation_status")
                or inv.get("validation_status")
                or "-",
                "Recommendation": overrides.get("recommendation")
                or inv.get("recommendation")
                or "-",
                "Feedback Count": int(inv.get("feedback_count") or 0),
                "Last Feedback": str(inv.get("last_feedback_at") or "-")[:19],
                "Processed": str(inv.get("processed_at") or "-")[:19],
            }
        )
df = pd.DataFrame(rows)
if "invoice_id_hidden" in df.columns:
    display_df = df.drop(columns=["invoice_id_hidden"])
else:
    display_df = df
st.dataframe(display_df, use_container_width=True, hide_index=True)
with st.container(border=True):
    st.subheader("Open an Invoice")
    id_input = st.text_input("Invoice ID", placeholder="Paste invoice UUID")
    if id_input.strip():
        st.session_state["active_invoice_id"] = id_input.strip()
        st.success("Invoice ID saved. Open Detail, Feedback, or Q&A from the sidebar.")
