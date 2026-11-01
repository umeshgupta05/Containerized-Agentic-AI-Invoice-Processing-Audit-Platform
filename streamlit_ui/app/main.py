import streamlit as st
from ui_helpers import apply_global_styles

st.set_page_config(
    page_title="Containerized Agentic AI Invoice Processing & Audit Platform",
    layout="wide",
    initial_sidebar_state="expanded",
)
apply_global_styles()
st.sidebar.title("Containerized Agentic AI Invoice Processing & Audit Platform")
st.sidebar.write("Review invoices, add corrections, and ask questions.")
if st.sidebar.button("Refresh current page", use_container_width=True):
    st.rerun()
dashboard = st.Page("pages/1_dashboard.py", title="Dashboard")
detail = st.Page("pages/2_invoice.py", title="Invoice Detail")
feedback = st.Page("pages/3_feedback.py", title="Human Feedback")
rag = st.Page("pages/4_invoice_q_a.py", title="Invoice Q & A")
admin = st.Page("pages/5_admin.py", title="Admin")
audit = st.Page("pages/6_audit_trail.py", title="Audit")
pg = st.navigation([dashboard, detail, feedback, rag, admin, audit])
pg.run()
