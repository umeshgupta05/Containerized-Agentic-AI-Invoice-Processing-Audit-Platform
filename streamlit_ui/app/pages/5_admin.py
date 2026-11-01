import streamlit as st
from api import get, post
from db import query

top_left, top_right = st.columns([3, 1])
top_left.title("Admin")
if top_right.button("Refresh admin", use_container_width=True):
    st.rerun()
st.subheader("Service Health")
health = get("/health")
if health:
    for svc, status in health.items():
        color = "green" if status == "ok" else "red"
        st.markdown(f"- **{svc.capitalize()}**: :{color}[{status}]")
else:
    st.warning("Could not reach the agent health endpoint.")
st.divider()
st.subheader("Audit Statistics")
try:
    stats = query(
        """
        SELECT
            COUNT(*)                                           AS total_invoices,
            COUNT(*) FILTER (WHERE recommendation = 'approve')       AS approved,
            COUNT(*) FILTER (WHERE recommendation = 'manual_review') AS manual_review,
            COUNT(*) FILTER (WHERE recommendation = 'reject')        AS rejected,
            COUNT(*) FILTER (WHERE validation_status = 'failed')     AS failed,
            COUNT(DISTINCT vendor_name)                        AS unique_vendors,
            MIN(processed_at)                                  AS first_processed,
            MAX(processed_at)                                  AS last_processed
        FROM audit.invoice_audit
        """
    )
    if stats:
        s = stats[0]
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Total Invoices", s.get("total_invoices") or 0)
        c2.metric("Unique Vendors", s.get("unique_vendors") or 0)
        c3.metric("First Processed", str(s.get("first_processed") or "-")[:10])
        c4.metric("Last Processed", str(s.get("last_processed") or "-")[:10])
        c5, c6, c7, c8 = st.columns(4)
        c5.metric("Approved", s.get("approved") or 0)
        c6.metric("Manual Review", s.get("manual_review") or 0)
        c7.metric("Rejected", s.get("rejected") or 0)
        c8.metric("Failed", s.get("failed") or 0)
except Exception as exc:
    st.warning(f"Could not load statistics: {exc}")
st.divider()
st.subheader("Rebuild Vector Index")
st.write(
    "Rebuilds the Qdrant vector index from all invoice records currently in PostgreSQL. "
    "Run this after a database restore or if the RAG Q&A returns stale or missing results. "
    "The vector index is a derived store; rebuilding it does not affect the audit trail."
)
force = st.checkbox(
    "Force full rebuild",
    help="Re-embed every invoice, even those already indexed.",
)
if st.button("Start Reindex"):
    with st.spinner(
        "Rebuilding index — this may take a few minutes for large datasets..."
    ):
        result = post("/reindex", {"force": force})
    if result:
        status_val = result.get("status", "unknown")
        count = result.get("indexed_count", "?")
        msg = result.get("message", "")
        if status_val == "completed":
            st.success(f"Reindex complete. {count} invoice(s) indexed.")
        else:
            st.error(f"Reindex status: {status_val}. {msg}")
st.divider()
st.subheader("Recent Human Corrections")
try:
    fb_rows = query(
        """
        SELECT
            hf.invoice_id,
            ia.invoice_number,
            ia.vendor_name,
            hf.field_name,
            hf.original_value,
            hf.corrected_value,
            hf.corrected_by,
            hf.corrected_at,
            hf.revalidated
        FROM audit.human_feedback hf
        JOIN audit.invoice_audit ia USING (invoice_id)
        ORDER BY hf.corrected_at DESC
        LIMIT 20
        """
    )
except Exception as exc:
    st.warning(f"Could not load feedback history: {exc}")
    fb_rows = []
if fb_rows:
    import pandas as pd

    fb_df = pd.DataFrame(fb_rows).drop(columns=["invoice_id"], errors="ignore")
    st.dataframe(fb_df, use_container_width=True, hide_index=True)
else:
    st.info("No human corrections recorded yet.")
