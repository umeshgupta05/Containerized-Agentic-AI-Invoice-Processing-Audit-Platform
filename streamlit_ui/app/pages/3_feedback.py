import html

import streamlit as st
from api import post
from db import query


def small_card(label: str, value: str) -> None:
    st.markdown(
        f"""
        <div style="
            min-height: 92px;
            padding: 12px 14px;
            border: 1px solid rgba(148, 163, 184, 0.22);
            border-radius: 16px;
            background: linear-gradient(135deg, rgba(248, 250, 252, 0.95), rgba(241, 245, 249, 0.8));
            box-shadow: 0 6px 18px rgba(15, 23, 42, 0.05);
            display: flex;
            flex-direction: column;
            justify-content: center;
        ">
            <div style="color:#475569; font-size:0.76rem; margin-bottom:8px;">{html.escape(label)}</div>
            <div style="color:#000; font-size:0.95rem; line-height:1.2; font-weight:600; overflow-wrap:anywhere;">
                {html.escape(str(value or "-"))}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def notice_card(title: str, message: str, tone: str) -> None:
    colors = {
        "success": ("#dcfce7", "#166534", "#86efac"),
        "warning": ("#fff7ed", "#9a3412", "#fdba74"),
        "info": ("#eff6ff", "#1d4ed8", "#93c5fd"),
    }
    bg, fg, border = colors.get(tone, colors["info"])
    st.markdown(
        f"""
        <div style="
            padding: 16px 18px;
            border-radius: 16px;
            border: 1px solid {border};
            background: {bg};
            color: {fg};
            margin: 8px 0 14px 0;
        ">
            <div style="font-weight:700; margin-bottom:4px;">{html.escape(title)}</div>
            <div style="font-size:0.95rem; line-height:1.35;">{html.escape(message)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


top_left, top_right = st.columns([3, 1])
top_left.title("Human Feedback")
if top_right.button("Refresh feedback", use_container_width=True):
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
with st.container(border=True):
    st.markdown("**Choose invoice to review**")
    selected_invoice_id = st.selectbox(
        "Select invoice",
        list(label_map.keys()),
        index=index,
        format_func=lambda value: label_map[value],
        key="feedback_invoice_selector",
        label_visibility="collapsed",
    )
st.session_state["active_invoice_id"] = selected_invoice_id
full_rows = query(
    """
    SELECT *
    FROM audit.invoice_audit
    WHERE invoice_id = :iid
    LIMIT 1
    """,
    {"iid": selected_invoice_id},
)
full_inv = full_rows[0] if full_rows else None
if full_inv is None:
    st.warning("No invoice found with that ID or invoice number.")
    st.stop()
invoice_id = str(full_inv["invoice_id"])
try:
    rows = query(
        """
        SELECT invoice_number, vendor_name, invoice_date, recommendation, validation_status
        FROM audit.invoice_audit
        WHERE invoice_id = :iid
        LIMIT 1
        """,
        {"iid": invoice_id},
    )
except Exception as exc:
    st.error(f"Database error: {exc}")
    st.stop()
if not rows:
    st.warning("No invoice found with that ID or invoice number.")
    st.stop()
inv = rows[0]
recommendation = str(inv.get("recommendation") or "").lower()
with st.container(border=True):
    st.markdown("**Selected invoice**")
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        small_card("Invoice", inv.get("invoice_number") or "?")
    with c2:
        small_card("Vendor", inv.get("vendor_name") or "?")
    with c3:
        small_card("Date", str(inv.get("invoice_date") or "?"))
    with c4:
        small_card("Recommendation", inv.get("recommendation") or "?")
if recommendation != "manual_review":
    notice_card(
        "Feedback not required",
        "This invoice is already approved or does not require manual review.",
        "success" if recommendation == "approve" else "warning",
    )
    notice_card(
        "Need to submit a correction?",
        "Select an invoice whose recommendation is manual_review.",
        "info",
    )
else:
    CORRECTABLE_FIELDS = [
        "invoice_number",
        "invoice_date",
        "vendor_name",
        "vendor_id",
        "po_number",
        "currency",
        "subtotal",
        "tax_amount",
        "total_amount",
        "recommendation",
        "validation_status",
    ]
    with st.container(border=True):
        st.subheader("Submit a Correction")
        with st.form("correction_form", clear_on_submit=True):
            field_name = st.selectbox(
                "Field to correct",
                CORRECTABLE_FIELDS,
                help="Select the invoice field you want to correct.",
            )
            current_value = full_inv.get(field_name)
            st.info(f"Current value for {field_name}: {current_value or '-'}")
            original_value = st.text_input(
                "Original value",
                value=str(current_value or ""),
                disabled=True,
                help="Captured automatically from the current invoice record and stored for history.",
            )
            corrected_value = st.text_input(
                "Corrected value",
                placeholder="Type the correct value here",
                help="Enter the correct value as it should be. This is saved permanently.",
            )
            corrected_by = st.text_input(
                "Your name or ID",
                placeholder="Example: auditor1",
                help="Identifies who submitted this correction in the audit trail.",
            )
            revalidate = st.checkbox(
                "Trigger re-validation after saving",
                value=True,
                help="Runs validation using the correction, but does not save changes to the original audit row.",
            )
            submit = st.form_submit_button("Save Correction")
    if submit:
        if not corrected_value.strip():
            st.warning("Corrected value must not be empty.")
        else:
            with st.spinner("Saving correction..."):
                result = post(
                    f"/invoices/{invoice_id}/feedback",
                    {
                        "field_name": field_name,
                        "original_value": original_value.strip() or None,
                        "corrected_value": corrected_value.strip(),
                        "corrected_by": corrected_by.strip() or None,
                    },
                )
            if result:
                st.success(
                    f"Correction saved for field '{field_name}'. "
                    "The original extracted value has not been changed."
                )
                if revalidate:
                    with st.spinner("Requesting re-validation..."):
                        rv = post(
                            f"/invoices/{invoice_id}/revalidate",
                            {"invoice_id": invoice_id},
                        )
                    if rv:
                        st.info(
                            "Re-validation complete. The original audit row was not changed."
                        )
st.subheader("Correction History")
st.caption("Newest corrections appear first.")
try:
    feedback_rows = query(
        """
        SELECT field_name, original_value, corrected_value, corrected_by, corrected_at, revalidated
        FROM audit.human_feedback
        WHERE invoice_id = :iid
        ORDER BY corrected_at DESC
        """,
        {"iid": invoice_id},
    )
except Exception as exc:
    st.error(f"Database error: {exc}")
    feedback_rows = []
if feedback_rows:
    for fb in feedback_rows:
        with st.expander(
            f"{fb['field_name']} corrected by {fb.get('corrected_by') or 'anonymous'}"
        ):
            c1, c2, c3, c4 = st.columns([2, 2, 2, 1])
            c1.markdown(f"**Field:** `{fb['field_name']}`")
            c2.markdown(f"**Was:** {fb.get('original_value') or '-'}")
            c3.markdown(f"**Corrected to:** {fb.get('corrected_value') or '-'}")
            rv_label = "Yes" if fb.get("revalidated") else "No"
            c4.markdown(
                f"**By:** {fb.get('corrected_by') or 'anonymous'}  \n"
                f"**Revalidated:** {rv_label}  \n"
                f"**At:** {str(fb.get('corrected_at') or '')[:19]}"
            )
else:
    st.info("No corrections submitted yet for this invoice.")
