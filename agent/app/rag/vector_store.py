import os

from app.rag.embeddings import EMBEDDING_DIM
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchValue,
    PointStruct,
    VectorParams,
)

QDRANT_URL = os.getenv("QDRANT_URL", "http://qdrant:6333")
COLLECTION = os.getenv("QDRANT_COLLECTION", "invoices")


def get_client() -> QdrantClient:
    return QdrantClient(url=QDRANT_URL)


def ensure_collection() -> None:
    client = get_client()
    existing = {c.name for c in client.get_collections().collections}
    if COLLECTION not in existing:
        client.create_collection(
            collection_name=COLLECTION,
            vectors_config=VectorParams(size=EMBEDDING_DIM, distance=Distance.COSINE),
        )


def upsert(points: list[PointStruct]) -> None:
    get_client().upsert(collection_name=COLLECTION, points=points)


def vector_search(
    vector: list[float],
    limit: int = 10,
    invoice_id: str | None = None,
) -> list[dict]:
    filt = None
    if invoice_id:
        filt = Filter(
            must=[FieldCondition(key="invoice_id", match=MatchValue(value=invoice_id))]
        )
    response = get_client().query_points(
        collection_name=COLLECTION,
        query=vector,
        limit=limit,
        query_filter=filt,
        with_payload=True,
    )
    results = getattr(response, "points", [])
    return [{"id": str(r.id), "score": r.score, "payload": r.payload} for r in results]
