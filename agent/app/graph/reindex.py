from typing import Any, TypedDict

from app.rag.indexing import rebuild_index
from langgraph.graph import END, START, StateGraph


class ReindexState(TypedDict, total=False):
    force: bool
    indexed_count: int
    status: str
    message: str


def rebuild_index_node(state: ReindexState) -> dict[str, Any]:
    try:
        count = rebuild_index()
        return {"status": "completed", "indexed_count": count, "message": ""}
    except Exception as exc:
        return {"status": "failed", "indexed_count": 0, "message": str(exc)}


def build() -> Any:
    builder = StateGraph(ReindexState)
    builder.add_node("rebuild_index", rebuild_index_node)
    builder.add_edge(START, "rebuild_index")
    builder.add_edge("rebuild_index", END)
    return builder.compile()


graph = build()
