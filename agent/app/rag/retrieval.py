from rank_bm25 import BM25Okapi

from app.rag.embeddings import embed
from app.rag.vector_store import vector_search


def hybrid_retrieve(
    question: str,
    invoice_id: str | None = None,
    top_k: int = 5,
) -> list[dict]:
    vector = embed(question)
    candidates = vector_search(vector, limit=top_k * 3, invoice_id=invoice_id)
    if not candidates:
        return []
    corpus = [c["payload"].get("text", "") for c in candidates]
    bm25 = BM25Okapi([text.lower().split() for text in corpus])
    bm25_scores = bm25.get_scores(question.lower().split())
    max_bm25 = max(bm25_scores) if max(bm25_scores) > 0 else 1.0
    for doc, bm25_score in zip(candidates, bm25_scores):
        doc["hybrid_score"] = doc["score"] + float(bm25_score) / max_bm25
    candidates.sort(key=lambda x: x["hybrid_score"], reverse=True)
    return candidates[:top_k]
