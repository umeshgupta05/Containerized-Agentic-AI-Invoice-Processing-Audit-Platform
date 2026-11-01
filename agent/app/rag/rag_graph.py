from typing import Any, TypedDict

from app.rag.generation import generate
from app.rag.query_router import classify_query
from app.rag.reflection import reflect
from app.rag.retrieval import hybrid_retrieve
from app.rag.sql_agent import route_sql_question
from langgraph.graph import END, START, StateGraph

MAX_RETRIES = 3


class RAGState(TypedDict, total=False):
    question: str
    invoice_id: str | None
    route: str
    docs: list[dict]
    answer: str
    sources: list[str]
    reflection_ok: bool
    reflection_reason: str
    reflection_retryable: bool
    retries: int
    score: float | None
    scores: dict[str, float] | None
    sql_result: dict[str, Any] | None
    query_type: str | None


def router_node(state: RAGState) -> dict[str, Any]:
    query_type = classify_query(state["question"])
    return {
        "query_type": query_type,
        "retries": 0,
        "reflection_ok": False,
    }


def decide_query_path(state: RAGState) -> str:
    return "sql" if state.get("query_type") == "sql" else "retrieve"


def sql_node(state: RAGState) -> dict[str, Any]:
    result = route_sql_question(state["question"])
    if result is None:
        return {
            "query_type": "rag",
            "sql_result": None,
            "answer": "",
            "sources": [],
        }
    return {
        "query_type": "sql",
        "sql_result": result,
        "answer": result.get("answer"),
        "sources": result.get("sources", []),
    }


def after_sql(state: RAGState) -> str:
    if state.get("sql_result") is not None:
        return "done"
    return "retrieve"


def retrieval_node(state: RAGState) -> dict[str, Any]:
    docs = hybrid_retrieve(
        question=state["question"],
        invoice_id=state.get("invoice_id"),
        top_k=5,
    )
    sources = [
        d["payload"].get("invoice_number") or d["payload"].get("invoice_id", "")
        for d in docs
        if d.get("payload")
    ]
    return {"docs": docs, "sources": list(dict.fromkeys(sources))}


def generation_node(state: RAGState) -> dict[str, Any]:
    answer = generate(question=state["question"], docs=state.get("docs", []))
    return {"answer": answer}


def reflection_node(state: RAGState) -> dict[str, Any]:
    result = reflect(
        question=state["question"],
        answer=state.get("answer", ""),
        docs=state.get("docs", []),
    )
    return {
        "reflection_ok": result["ok"],
        "reflection_reason": result["reason"],
        "reflection_retryable": result.get("retryable", False),
        "retries": state.get("retries", 0) + 1,
        "score": result.get("score"),
        "scores": result.get("metrics"),
    }


def after_reflection(state: RAGState) -> str:
    if state.get("reflection_ok"):
        return "done"
    if not state.get("reflection_retryable"):
        return "done"
    if state.get("retries", 0) >= MAX_RETRIES:
        return "done"
    return "retry"


def build() -> Any:
    builder = StateGraph(RAGState)
    builder.add_node("router", router_node)
    builder.add_node("sql", sql_node)
    builder.add_node("retrieve", retrieval_node)
    builder.add_node("generate", generation_node)
    builder.add_node("reflect", reflection_node)
    builder.add_edge(START, "router")
    builder.add_conditional_edges(
        "router",
        decide_query_path,
        {"sql": "sql", "retrieve": "retrieve"},
    )
    builder.add_conditional_edges(
        "sql",
        after_sql,
        {"done": END, "retrieve": "retrieve"},
    )
    builder.add_edge("retrieve", "generate")
    builder.add_edge("generate", "reflect")
    builder.add_conditional_edges(
        "reflect",
        after_reflection,
        {"done": END, "retry": "retrieve"},
    )
    return builder.compile()


graph = build()
