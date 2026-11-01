import threading
import time
import uuid as uuid_mod
from contextlib import asynccontextmanager
from datetime import date, datetime

import httpx
from app.db.db import get_db, initialize_audit_tables, wait_for_database
from app.models.models import (
    HumanFeedback,
    InvoiceAudit,
)
from app.services import cache
from app.services.cache import get_redis_client
from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

QDRANT_URL = __import__("os").getenv("QDRANT_URL", "http://qdrant:6333")
MOCK_ERP_URL = __import__("os").getenv("MOCK_ERP_URL", "http://mock-erp:8000")
COLLECTION_NAME = __import__("os").getenv("QDRANT_COLLECTION", "invoices")


def ensure_qdrant_collection() -> None:
    try:
        from qdrant_client import QdrantClient
        from qdrant_client.models import Distance, VectorParams

        client = QdrantClient(url=QDRANT_URL)
        existing = {c.name for c in client.get_collections().collections}
        if COLLECTION_NAME not in existing:
            client.create_collection(
                collection_name=COLLECTION_NAME,
                vectors_config=VectorParams(size=1536, distance=Distance.COSINE),
            )
        if client.count(collection_name=COLLECTION_NAME).count == 0:
            from app.rag.indexing import rebuild_index

            rebuild_index()
    except Exception as exc:
        raise RuntimeError(
            f"Qdrant unreachable or collection creation failed: {exc}"
        ) from exc


def check_erp(retries: int = 10, delay: float = 2.0) -> None:
    last_exc: Exception | None = None
    for attempt in range(retries):
        try:
            resp = httpx.get(f"{MOCK_ERP_URL}/health", timeout=5)
            resp.raise_for_status()
            return
        except Exception as exc:
            last_exc = exc
            time.sleep(delay)
    raise RuntimeError(f"mock-erp unreachable after {retries} attempts: {last_exc}")


def start_watcher() -> None:
    from app.agents.monitor import run_monitor

    threading.Thread(target=run_monitor, daemon=True, name="folder-watcher").start()


@asynccontextmanager
async def lifespan(app_instance: FastAPI):
    wait_for_database()
    initialize_audit_tables()
    ensure_qdrant_collection()
    check_erp()
    start_watcher()
    yield


app = FastAPI(
    title="Containerized Agentic AI Invoice Processing & Audit Platform",
    lifespan=lifespan,
)


@app.get("/health")
def health() -> JSONResponse:
    result: dict[str, str] = {}
    try:
        from app.db.db import engine
        from sqlalchemy import text

        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        result["postgres"] = "ok"
    except Exception as exc:
        result["postgres"] = f"error: {exc}"
    try:
        from qdrant_client import QdrantClient

        QdrantClient(url=QDRANT_URL).get_collections()
        result["qdrant"] = "ok"
    except Exception as exc:
        result["qdrant"] = f"error: {exc}"
    try:
        client = get_redis_client()
        if client:
            client.ping()
        result["redis"] = "ok"
    except Exception as exc:
        result["redis"] = f"warning: {exc}"
    return JSONResponse(result)


@app.get("/invoices")
def list_invoices(
    status: str | None = Query(None),
    vendor: str | None = Query(None),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> JSONResponse:
    q = db.query(InvoiceAudit)
    if status:
        q = q.filter(InvoiceAudit.validation_status == status)
    if vendor:
        q = q.filter(InvoiceAudit.vendor_name.ilike(f"%{vendor}%"))
    total = q.count()
    rows = (
        q.order_by(InvoiceAudit.processed_at.desc()).offset(offset).limit(limit).all()
    )
    invoices = []
    for r in rows:
        invoices.append(
            {
                "invoice_id": str(r.invoice_id),
                "invoice_number": r.invoice_number,
                "vendor_name": r.vendor_name,
                "po_number": r.po_number,
                "invoice_date": r.invoice_date.isoformat() if r.invoice_date else None,
                "currency": r.currency,
                "total_amount": float(r.total_amount)
                if r.total_amount is not None
                else None,
                "validation_status": r.validation_status,
                "recommendation": r.recommendation,
                "processed_at": r.processed_at.isoformat() if r.processed_at else None,
            }
        )
    return JSONResponse({"total": total, "items": invoices})


@app.get("/invoices/{invoice_id}")
def get_invoice(invoice_id: str, db: Session = Depends(get_db)) -> JSONResponse:
    try:
        uid = uuid_mod.UUID(invoice_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid invoice_id format")
    row = db.query(InvoiceAudit).filter(InvoiceAudit.invoice_id == uid).first()
    if not row:
        raise HTTPException(status_code=404, detail="Invoice not found")
    line_items = [
        {
            "id": li.id,
            "line_number": li.line_number,
            "item_code": li.item_code,
            "description": li.description,
            "quantity": float(li.quantity) if li.quantity is not None else None,
            "unit_price": float(li.unit_price) if li.unit_price is not None else None,
            "line_total": float(li.line_total) if li.line_total is not None else None,
        }
        for li in row.line_items
    ]
    discrepancies = [
        {
            "id": d.id,
            "field_name": d.field_name,
            "invoice_value": d.invoice_value,
            "erp_value": d.erp_value,
            "deviation_pct": float(d.deviation_pct)
            if d.deviation_pct is not None
            else None,
            "severity": d.severity,
            "detected_at": d.detected_at.isoformat() if d.detected_at else None,
        }
        for d in row.discrepancies
    ]
    return JSONResponse(
        {
            "invoice_id": str(row.invoice_id),
            "invoice_number": row.invoice_number,
            "vendor_name": row.vendor_name,
            "po_number": row.po_number,
            "invoice_date": row.invoice_date.isoformat() if row.invoice_date else None,
            "currency": row.currency,
            "total_amount": float(row.total_amount)
            if row.total_amount is not None
            else None,
            "validation_status": row.validation_status,
            "recommendation": row.recommendation,
            "raw_extracted_text": row.raw_extracted_text,
            "translated_text": row.translated_text,
            "source_language": row.source_language,
            "extraction_method": row.extraction_method,
            "processed_at": row.processed_at.isoformat() if row.processed_at else None,
            "thread_id": row.thread_id,
            "line_items": line_items,
            "discrepancies": discrepancies,
        }
    )


class FeedbackRequest(BaseModel):
    field_name: str
    original_value: str | None = None
    corrected_value: str
    corrected_by: str = "auditor"


@app.post("/invoices/{invoice_id}/feedback")
def submit_feedback(
    invoice_id: str,
    body: FeedbackRequest,
    db: Session = Depends(get_db),
) -> JSONResponse:
    try:
        uid = uuid_mod.UUID(invoice_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid invoice_id format")
    invoice = db.query(InvoiceAudit).filter(InvoiceAudit.invoice_id == uid).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    recommendation = str(invoice.recommendation or "").strip().lower()
    if recommendation != "manual_review":
        raise HTTPException(
            status_code=409,
            detail=(
                "Human feedback is only allowed when manual review is required. "
                f"Current recommendation: {invoice.recommendation or 'not set'}"
            ),
        )
    original_value = (body.original_value or "").strip() or None
    if original_value is None:
        current_value = getattr(invoice, body.field_name, None)
        if isinstance(current_value, (date, datetime)):
            original_value = current_value.isoformat()
        elif current_value is not None:
            original_value = str(current_value).strip() or None
    record = HumanFeedback(
        invoice_id=uid,
        field_name=body.field_name,
        original_value=original_value,
        corrected_value=body.corrected_value,
        corrected_by=body.corrected_by,
    )
    db.add(record)
    db.flush()
    db.commit()
    db.refresh(record)
    return JSONResponse({"id": record.id, "status": "recorded"}, status_code=201)


@app.post("/invoices/{invoice_id}/revalidate")
def revalidate_invoice(invoice_id: str, db: Session = Depends(get_db)) -> JSONResponse:
    try:
        uid = uuid_mod.UUID(invoice_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid invoice_id format")
    invoice = db.query(InvoiceAudit).filter(InvoiceAudit.invoice_id == uid).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    try:
        from app.graph.revalidate import graph as revalidate_graph

        result = revalidate_graph.invoke({"invoice_id": str(uid)})
        return JSONResponse({"status": "revalidated", "result": result})
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Revalidation failed: {exc}")


class RagQueryRequest(BaseModel):
    query: str
    invoice_id: str | None = None
    top_k: int = 5


class RagScoreRequest(BaseModel):
    query: str
    answer: str
    invoice_id: str | None = None


def resolve_invoice_id(invoice_id: str | None) -> str | None:
    if not invoice_id:
        return None
    try:
        uuid_mod.UUID(invoice_id)
        return invoice_id
    except ValueError:
        row = (
            get_db()
            .__next__()
            .query(InvoiceAudit)
            .filter(InvoiceAudit.invoice_number == invoice_id)
            .first()
        )
        return str(row.invoice_id) if row is not None else None


@app.post("/rag/answer")
def rag_answer(body: RagQueryRequest) -> JSONResponse:
    try:
        invoice_id = resolve_invoice_id(body.invoice_id)
        import os

        llm = os.getenv("LITELLM_MODEL", "amazon.nova-lite-v1:0")
        prompt_key = f"answer:{llm}:{body.query.strip()}:{invoice_id or ''}"
        cached = cache.get(prompt_key)
        if cached is not None:
            payload = dict(cached)
            payload["cache_hit"] = True
            payload["cache_key"] = prompt_key
            return JSONResponse(payload)

        from app.rag.generation import generate
        from app.rag.query_router import classify_query
        from app.rag.retrieval import hybrid_retrieve
        from app.rag.sql_agent import route_sql_question

        query_type = classify_query(body.query)
        if query_type == "sql":
            result = route_sql_question(body.query)
            if result is not None:
                payload = {
                    "question": body.query,
                    "invoice_id": invoice_id,
                    "answer": result.get("answer"),
                    "sources": result.get("sources", []),
                    "query_type": "sql",
                    "sql_result": result,
                    "score_pending": False,
                    "cache_hit": False,
                    "cache_key": prompt_key,
                }
                payload = jsonable_encoder(payload)
                cache.set(prompt_key, payload, ttl=60 * 60)
                return JSONResponse(payload)

        docs = hybrid_retrieve(
            question=body.query,
            invoice_id=invoice_id,
            top_k=body.top_k,
        )
        answer = generate(question=body.query, docs=docs)
        sources = [
            d["payload"].get("invoice_number") or d["payload"].get("invoice_id", "")
            for d in docs
            if d.get("payload")
        ]
        payload = {
            "question": body.query,
            "invoice_id": invoice_id,
            "answer": answer,
            "sources": list(dict.fromkeys(sources)),
            "query_type": "rag",
            "score_pending": True,
            "cache_hit": False,
            "cache_key": prompt_key,
        }
        payload = jsonable_encoder(payload)
        cache.set(prompt_key, payload, ttl=60 * 60)
        return JSONResponse(payload)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"RAG answer failed: {exc}")


@app.post("/rag/score")
def rag_score(body: RagScoreRequest) -> JSONResponse:
    try:
        invoice_id = resolve_invoice_id(body.invoice_id)
        from app.rag.reflection import reflect
        from app.rag.retrieval import hybrid_retrieve

        docs = hybrid_retrieve(
            question=body.query,
            invoice_id=invoice_id,
            top_k=5,
        )
        result = reflect(
            question=body.query,
            answer=body.answer,
            docs=docs,
        )
        return JSONResponse(jsonable_encoder(result))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"RAG score failed: {exc}")


@app.post("/rag/query")
def rag_query(body: RagQueryRequest) -> JSONResponse:
    try:
        invoice_id = body.invoice_id
        if invoice_id:
            try:
                uuid_mod.UUID(invoice_id)
            except ValueError:
                row = (
                    get_db()
                    .__next__()
                    .query(InvoiceAudit)
                    .filter(InvoiceAudit.invoice_number == invoice_id)
                    .first()
                )
                if row is not None:
                    invoice_id = str(row.invoice_id)
                else:
                    invoice_id = None
        try:
            from qdrant_client import QdrantClient

            qclient = QdrantClient(url=QDRANT_URL)
            if qclient.count(collection_name=COLLECTION_NAME).count == 0:
                from app.rag.indexing import rebuild_index

                rebuild_index()
        except Exception:
            pass
        import os

        llm = os.getenv("LITELLM_MODEL", "amazon.nova-lite-v1:0")
        prompt_key = f"{llm}:{body.query.strip()}"
        cached = cache.get(prompt_key)
        if cached is not None:
            payload = dict(cached)
            payload["cache_hit"] = True
            payload["cache_key"] = prompt_key
            return JSONResponse(payload)
        from app.rag.rag_graph import graph as rag_graph

        result = rag_graph.invoke(
            {
                "question": body.query,
                "invoice_id": invoice_id,
            }
        )
        result["cache_hit"] = False
        result["cache_key"] = prompt_key
        result = jsonable_encoder(result)
        cache.set(prompt_key, result, ttl=60 * 60)
        return JSONResponse(result)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"RAG query failed: {exc}")


@app.post("/reindex")
def trigger_reindex() -> JSONResponse:
    try:
        from app.graph.reindex import graph as reindex_graph

        result = reindex_graph.invoke({})
        return JSONResponse({"status": "reindexed", "result": result})
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Reindex failed: {exc}")
