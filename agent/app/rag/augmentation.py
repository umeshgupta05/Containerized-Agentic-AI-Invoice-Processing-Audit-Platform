def format_context(docs: list[dict]) -> str:
    if not docs:
        return "No relevant invoice data found."
    parts = []
    for i, doc in enumerate(docs, 1):
        payload = doc.get("payload", {})
        meta = []
        if payload.get("invoice_number"):
            meta.append(f"Invoice #{payload['invoice_number']}")
        if payload.get("vendor_name"):
            meta.append(f"Vendor: {payload['vendor_name']}")
        if payload.get("validation_status"):
            meta.append(f"Status: {payload['validation_status']}")
        header = f"[Document {i}] " + " | ".join(meta) if meta else f"[Document {i}]"
        block = payload.get("text", "")
        report_json = payload.get("report_json")
        if report_json:
            block = (
                f"{block}\n\nReport JSON:\n{report_json}"
                if block
                else f"Report JSON:\n{report_json}"
            )
        parts.append(f"{header}\n{block}")
    return "\n\n---\n\n".join(parts)
