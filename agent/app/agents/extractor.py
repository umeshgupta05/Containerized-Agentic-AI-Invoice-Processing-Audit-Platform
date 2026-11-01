import os
from pathlib import Path
from typing import Any
from uuid import UUID

import pdfplumber
import pytesseract
from app.models.models import InvoiceAudit
from docx import Document as WordDocument
from langchain_community.document_loaders import PyPDFLoader
from PIL import Image
from sqlalchemy.orm import Session

TESSERACT_LANG = os.getenv("TESSERACT_LANG", "eng+spa+deu")
OCR_SCANNED_PDF = os.getenv("OCR_SCANNED_PDF", "true").lower() == "true"


def extract_pdf_with_pdfplumber(file_path: Path) -> tuple[str, str]:
    page_texts = []
    with pdfplumber.open(str(file_path)) as pdf:
        for page_number, page in enumerate(pdf.pages, start=1):
            sections = []
            tables = page.extract_tables(
                table_settings={
                    "vertical_strategy": "lines",
                    "horizontal_strategy": "lines",
                    "snap_tolerance": 3,
                    "join_tolerance": 3,
                    "intersection_tolerance": 3,
                }
            )
            table_text = []
            for table in tables or []:
                for row in table:
                    if not row:
                        continue
                    cells = [" ".join((cell or "").split()) for cell in row]
                    if any(cells):
                        table_text.append(" | ".join(cells))
            raw_text = page.extract_text(layout=True) or ""
            raw_text = "\n".join(
                line.rstrip() for line in raw_text.splitlines()
            ).strip()
            if table_text:
                sections.append("EXTRACTED TABLES:")
                sections.extend(table_text)
            if raw_text:
                sections.append("PAGE TEXT:")
                sections.append(raw_text)
            if not raw_text and not table_text:
                words = page.extract_words(
                    x_tolerance=2,
                    y_tolerance=3,
                    keep_blank_chars=False,
                )
                if words:
                    sections.append(" ".join(word["text"] for word in words))
            page_content = "\n".join(sections).strip()
            if page_content:
                page_texts.append(f"--- Page {page_number} ---\n{page_content}")
    extracted_text = "\n\n".join(page_texts).strip()
    if extracted_text:
        return extracted_text, "pdfplumber"
    raise ValueError(f"pdfplumber extracted no text from {file_path.name}")


def extract_pdf_with_pypdf(file_path: Path) -> tuple[str, str]:
    loader = PyPDFLoader(str(file_path))
    documents = loader.load()
    page_texts = [
        f"--- Page {index + 1} ---\n{document.page_content.strip()}"
        for index, document in enumerate(documents)
        if document.page_content and document.page_content.strip()
    ]
    extracted_text = "\n\n".join(page_texts).strip()
    if not extracted_text:
        raise ValueError(f"PyPDFLoader extracted no text from {file_path.name}")
    return extracted_text, "pypdfloader"


def ocr_pdf(file_path: Path) -> tuple[str, str]:
    try:
        from pdf2image import convert_from_path
    except ImportError as exc:
        raise RuntimeError("Scanned PDF OCR requires pdf2image and Poppler.") from exc
    images = convert_from_path(str(file_path))
    page_texts = []
    for page_number, image in enumerate(images, start=1):
        text = pytesseract.image_to_string(
            image,
            lang=TESSERACT_LANG,
        ).strip()
        if text:
            page_texts.append(f"--- Page {page_number} (OCR) ---\n{text}")
    extracted_text = "\n\n".join(page_texts).strip()
    if not extracted_text:
        raise ValueError(f"OCR extracted no text from scanned PDF {file_path.name}")
    return extracted_text, "tesseract_pdf_ocr"


def extract_pdf(file_path: Path) -> tuple[str, str]:
    errors = []
    try:
        return extract_pdf_with_pdfplumber(file_path)
    except Exception as exc:
        errors.append(f"pdfplumber: {type(exc).__name__}: {exc}")
    try:
        return extract_pdf_with_pypdf(file_path)
    except Exception as exc:
        errors.append(f"PyPDFLoader: {type(exc).__name__}: {exc}")
    if OCR_SCANNED_PDF:
        try:
            return ocr_pdf(file_path)
        except Exception as exc:
            errors.append(f"OCR: {type(exc).__name__}: {exc}")
    raise RuntimeError(
        f"All PDF extraction methods failed for {file_path.name}: " + " | ".join(errors)
    )


def extract_docx(file_path: Path) -> tuple[str, str]:
    document = WordDocument(str(file_path))
    sections = []
    for paragraph in document.paragraphs:
        text = paragraph.text.strip()
        if text:
            sections.append(text)
    for table_index, table in enumerate(document.tables, start=1):
        sections.append(f"TABLE {table_index}:")
        for row in table.rows:
            cells = [" ".join(cell.text.split()) for cell in row.cells]
            if any(cells):
                sections.append(" | ".join(cells))
    extracted_text = "\n".join(sections).strip()
    if not extracted_text:
        raise ValueError(f"No text could be extracted from DOCX {file_path.name}")
    return extracted_text, "python-docx"


def extract_image(file_path: Path) -> tuple[str, str]:
    with Image.open(file_path) as image:
        extracted_text = pytesseract.image_to_string(
            image,
            lang=TESSERACT_LANG,
        ).strip()
    if not extracted_text:
        raise ValueError(f"Tesseract extracted no text from {file_path.name}")
    return extracted_text, "tesseract"


def extract_document(file_path: str | Path) -> tuple[str, str]:
    path = Path(file_path)
    if not path.is_file():
        raise FileNotFoundError(f"File not found: {path}")
    extension = path.suffix.lower()
    if extension == ".pdf":
        return extract_pdf(path)
    if extension == ".docx":
        return extract_docx(path)
    if extension == ".png":
        return extract_image(path)
    raise ValueError(f"Unsupported document format: {extension}")


def find_audit_record(db: Session, audit_id: UUID):
    columns = InvoiceAudit.__table__.columns.keys()
    if "id" in columns:
        id_column = InvoiceAudit.id
    elif "invoice_id" in columns:
        id_column = InvoiceAudit.invoice_id
    else:
        raise RuntimeError("InvoiceAudit has neither id nor invoice_id column")
    return db.query(InvoiceAudit).filter(id_column == audit_id).first()


def extract_invoice(
    file_path: str | Path,
    invoice_id: str | UUID,
    db: Session,
) -> dict[str, Any]:
    try:
        audit_id = UUID(str(invoice_id))
    except (ValueError, TypeError, AttributeError):
        return {
            "invoice_id": str(invoice_id),
            "extraction_status": "failed",
            "message": "Invalid invoice ID",
        }
    try:
        audit_record = find_audit_record(db, audit_id)
    except Exception as exc:
        db.rollback()
        return {
            "invoice_id": str(audit_id),
            "extraction_status": "failed",
            "message": f"Database lookup failed: {type(exc).__name__}: {exc}",
        }
    if audit_record is None:
        return {
            "invoice_id": str(audit_id),
            "extraction_status": "failed",
            "message": "Audit record not found",
        }
    try:
        raw_text, method = extract_document(file_path)
        audit_record.raw_extracted_text = raw_text
        audit_record.extraction_method = method
        db.commit()
        return {
            "invoice_id": str(audit_id),
            "extraction_status": "success",
            "extraction_method": method,
            "raw_extracted_text": raw_text,
        }
    except Exception as exc:
        db.rollback()
        return {
            "invoice_id": str(audit_id),
            "extraction_status": "failed",
            "message": f"{type(exc).__name__}: {exc}",
        }
