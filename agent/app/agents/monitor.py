import hashlib
import os
import time
from pathlib import Path
from uuid import UUID, uuid4

from app.db.db import SessionLocal
from app.models.models import InvoiceAudit, ProcessingAuditLog

INCOMING_DIR = Path(os.getenv("INCOMING_DIR", "/data/incoming"))
SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".png"}


def sha256(file_path: Path) -> str:
    h = hashlib.sha256()
    with file_path.open("rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def get_invoice_by_id(db, invoice_id):
    invoice_model_id = getattr(InvoiceAudit, "id", None)
    invoice_model_invoice_id = getattr(InvoiceAudit, "invoice_id", None)
    if invoice_model_id is not None:
        return db.query(InvoiceAudit).filter(invoice_model_id == invoice_id).first()
    if invoice_model_invoice_id is not None:
        return (
            db.query(InvoiceAudit)
            .filter(invoice_model_invoice_id == invoice_id)
            .first()
        )
    raise AttributeError("InvoiceAudit must define either an id or invoice_id column")


def mark_failed(invoice_id) -> None:
    db = SessionLocal()
    try:
        invoice = get_invoice_by_id(db, invoice_id)
        if invoice is None:
            return
        invoice.validation_status = "failed"
        db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()


def record_processing_result(
    filename: str,
    invoice_id: UUID | str | None,
    status: str,
    reason: str | None = None,
    report: dict | None = None,
) -> ProcessingAuditLog | None:
    db = SessionLocal()
    try:
        normalized_status = str(status).lower()
        if normalized_status not in {"success", "failed"}:
            normalized_status = "failed"
        parsed_invoice_id = None
        if invoice_id is not None:
            try:
                parsed_invoice_id = UUID(str(invoice_id))
            except (ValueError, TypeError, AttributeError):
                parsed_invoice_id = None
        record = ProcessingAuditLog(
            filename=str(filename),
            invoice_id=parsed_invoice_id,
            report=report,
            status=normalized_status,
            reason=reason or "",
        )
        db.add(record)
        db.commit()
        db.refresh(record)
        return record
    except Exception:
        db.rollback()
        return None
    finally:
        db.close()


def create_audit_record(file_path: Path, checksum: str):
    db = SessionLocal()
    try:
        existing = (
            db.query(InvoiceAudit)
            .filter(InvoiceAudit.file_checksum == checksum)
            .first()
        )
        if existing:
            return None
        invoice_id = uuid4()
        model_columns = InvoiceAudit.__table__.columns.keys()
        values = {
            "file_path": str(file_path),
            "file_checksum": checksum,
            "validation_status": "pending",
        }
        if "id" in model_columns:
            values["id"] = invoice_id
        elif "invoice_id" in model_columns:
            values["invoice_id"] = invoice_id
        else:
            raise AttributeError(
                "InvoiceAudit has neither an id nor an invoice_id column"
            )
        invoice = InvoiceAudit(**values)
        db.add(invoice)
        db.commit()
        return invoice_id
    except Exception:
        db.rollback()
        return None
    finally:
        db.close()


def process_file(file_path: Path) -> None:
    try:
        checksum = sha256(file_path)
    except Exception as exc:
        record_processing_result(
            filename=file_path.name,
            invoice_id=None,
            status="failed",
            reason=f"checksum calculation failed: {exc}",
            report=None,
        )
        return
    invoice_id = create_audit_record(file_path, checksum)
    if invoice_id is None:
        record_processing_result(
            filename=file_path.name,
            invoice_id=None,
            status="failed",
            reason="duplicate or database error while creating audit record",
            report=None,
        )
        return
    try:
        from app.graph.workflow import graph

        initial_state = {
            "invoice_id": str(invoice_id),
            "file_path": str(file_path),
            "status": "running",
            "current_stage": "starting",
            "errors": [],
        }
        final_state = graph.invoke(initial_state)
        if final_state.get("status") == "failed":
            reason = (
                "; ".join(
                    f"{item.get('stage', 'unknown')}: {item.get('message', 'unknown error')}"
                    for item in final_state.get("errors", [])
                )
                or "workflow failed"
            )
            mark_failed(invoice_id)
            record_processing_result(
                filename=file_path.name,
                invoice_id=invoice_id,
                status="failed",
                reason=reason,
                report=None,
            )
            return
        report = final_state.get("report")
        record_processing_result(
            filename=file_path.name,
            invoice_id=invoice_id,
            status="success",
            reason="",
            report=report,
        )
    except Exception as exc:
        mark_failed(invoice_id)
        record_processing_result(
            filename=file_path.name,
            invoice_id=invoice_id,
            status="failed",
            reason=f"workflow exception: {exc}",
            report=None,
        )


def run_monitor(poll_interval: int = 5) -> None:
    INCOMING_DIR.mkdir(parents=True, exist_ok=True)
    processed: set[Path] = set()
    while True:
        try:
            files = list(INCOMING_DIR.iterdir())
        except Exception:
            time.sleep(poll_interval)
            continue
        for file_path in files:
            if not file_path.is_file():
                continue
            if file_path in processed:
                continue
            if file_path.suffix.lower() not in SUPPORTED_EXTENSIONS:
                record_processing_result(
                    filename=file_path.name,
                    invoice_id=None,
                    status="failed",
                    reason=f"unsupported extension: {file_path.suffix or 'unknown'}",
                    report=None,
                )
                processed.add(file_path)
                continue
            try:
                first_size = file_path.stat().st_size
                time.sleep(1)
                if file_path.stat().st_size != first_size:
                    continue
                process_file(file_path)
                processed.add(file_path)
            except FileNotFoundError:
                continue
            except Exception:
                record_processing_result(
                    filename=file_path.name,
                    invoice_id=None,
                    status="failed",
                    reason=f"monitor error: {file_path.name}",
                    report=None,
                )
        time.sleep(poll_interval)
