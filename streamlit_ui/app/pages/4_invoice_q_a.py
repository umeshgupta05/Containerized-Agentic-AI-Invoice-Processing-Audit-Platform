import streamlit as st
from api import post

st.title("Invoice Q & A")
st.caption("Ask questions about processed invoices.")
if "invoice_chat_history" not in st.session_state:
    st.session_state.invoice_chat_history = []
top_left, top_right = st.columns([3, 1])
top_left.write("")
if top_right.button("Clear chat", use_container_width=True):
    st.session_state.invoice_chat_history = []
    st.rerun()

question = st.chat_input("Ask a question about the invoices...")
if question:
    st.session_state.invoice_chat_history.append(
        {
            "question": question,
            "answer": "Thinking...",
            "loading": True,
        }
    )

for entry in st.session_state.invoice_chat_history:
    with st.chat_message("user"):
        st.write(entry["question"])
    with st.chat_message("assistant"):
        st.write(entry.get("answer", ""))
        if entry.get("loading"):
            continue
        if entry.get("score_loading"):
            st.info("RAGAS score is calculating...")
        scores = entry.get("scores")
        if isinstance(scores, dict) and not entry.get("score_loading"):
            s1, s2, s3 = st.columns(3)
            s1.metric("Relevance", f"{scores.get('relevance', 0):.2f}")
            s2.metric("Groundedness", f"{scores.get('groundedness', 0):.2f}")
            s3.metric("Context Relevance", f"{scores.get('context_relevance', 0):.2f}")
        elif scores is not None and not entry.get("score_loading"):
            st.metric("RAGAS Score", f"{float(scores):.2f}")
        if entry.get("score") is not None and not entry.get("score_loading"):
            st.caption(f"Overall score: {float(entry['score']):.2f}")
        if entry.get("score_error"):
            st.warning(entry["score_error"])
        if entry.get("sources"):
            st.caption("Sources: " + ", ".join(entry["sources"]))
        if "cache_hit" in entry:
            cache_text = "hit" if entry.get("cache_hit") else "miss"
            st.caption(f"Cache: {cache_text}")
        retries = entry.get("retries", 0)
        if retries:
            st.caption(f"Reflection retries: {retries}")

for entry in st.session_state.invoice_chat_history:
    if not entry.get("loading"):
        continue
    payload: dict = {"query": entry["question"]}
    with st.spinner("Retrieving and generating answer..."):
        result = post("/rag/answer", payload)
    if result:
        entry["answer"] = result.get("answer") or str(result)
        entry["sources"] = result.get("sources") or []
        entry["invoice_id"] = result.get("invoice_id")
        entry["query_type"] = result.get("query_type")
        entry["cache_hit"] = result.get("cache_hit", False)
        entry["score_loading"] = bool(result.get("score_pending"))
    else:
        entry["answer"] = "Sorry, I could not get an answer."
    entry["loading"] = False
    st.rerun()

for entry in st.session_state.invoice_chat_history:
    if not entry.get("score_loading"):
        continue
    payload = {
        "query": entry["question"],
        "answer": entry.get("answer", ""),
        "invoice_id": entry.get("invoice_id"),
    }
    with st.spinner("Calculating RAGAS score..."):
        result = post("/rag/score", payload)
    if result:
        entry["scores"] = result.get("metrics")
        entry["score"] = result.get("score")
        entry["reflection_ok"] = result.get("ok")
        entry["reflection_reason"] = result.get("reason")
        if not result.get("ok") and result.get("reason"):
            entry["score_error"] = result["reason"]
    else:
        entry["score_error"] = "RAGAS score could not be calculated."
    entry["score_loading"] = False
    st.rerun()
