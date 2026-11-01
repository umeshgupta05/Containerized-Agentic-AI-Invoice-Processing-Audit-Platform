import hashlib
import json
import os
import re
from typing import Any
from uuid import UUID

import litellm
from app.models.models import InvoiceAudit
from app.services import cache
from langchain_core.messages import HumanMessage, SystemMessage
from sqlalchemy.orm import Session

TARGET_LANGUAGE = "English"
LITELLM_MODEL = os.getenv(
    "LITELLM_MODEL",
    "bedrock/anthropic.claude-3-haiku-20240307-v1:0",
)
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
PROMPT_VERSION = "v2"


def cache_key(text: str) -> str:
    value = "|".join(
        [
            LITELLM_MODEL,
            AWS_REGION,
            TARGET_LANGUAGE,
            PROMPT_VERSION,
            text,
        ]
    )
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()
    return f"invoice-translation:{digest}"


def detect_and_translate(text: str) -> dict[str, Any]:
    messages = [
        SystemMessage(
            content=(
                "You are an invoice language detection and translation "
                "assistant. Detect the primary language of the invoice text. "
                "Translate the text into English only if it is not already "
                "English. If it is English, return the original text "
                "unchanged.\n\n"
                "Preserve invoice numbers, purchase order numbers, SKU codes, "
                "vendor names, product names, dates, numeric values, decimal "
                "separators, currencies, tax rates, and line-item order. "
                "Do not calculate, correct, infer, or alter invoice values. "
                "Do not omit content, even if it appears repetitive.\n\n"
                "Return only a valid JSON object with exactly these keys: "
                "source_language, detection_confidence, translated_text, "
                "translation_confidence. Confidence values must be numeric "
                "values between 0 and 1. Use the language name in "
                "source_language."
            )
        ),
        HumanMessage(content=f"Invoice text:\n{text}"),
    ]
    lite_messages = [
        {"role": "system", "content": messages[0].content},
        {"role": "user", "content": messages[1].content},
    ]
    raw_response = litellm.completion(
        model=LITELLM_MODEL,
        messages=lite_messages,
        temperature=0,
        max_tokens=4096,
    )
    content = raw_response.choices[0].message.content
    if isinstance(content, list):
        content = "\n".join(
            str(item.get("text", "")) if isinstance(item, dict) else str(item)
            for item in content
        )
    cleaned = re.sub(
        r"\A```(?:json)?\s*|\s*```\Z",
        "",
        str(content).strip(),
        flags=re.IGNORECASE,
    ).strip()
    try:
        result = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise ValueError("Bedrock returned invalid JSON.") from exc
    if not isinstance(result, dict):
        raise ValueError("Bedrock response must be a JSON object.")
    try:
        source_language = str(result["source_language"]).strip()
        translated_text = result["translated_text"]
        detection_confidence = float(result["detection_confidence"])
        translation_confidence = float(result["translation_confidence"])
    except KeyError as exc:
        raise ValueError(
            f"Missing required Bedrock response field: {exc.args[0]}"
        ) from exc
    except (TypeError, ValueError) as exc:
        raise ValueError("Bedrock returned invalid confidence values.") from exc
    if not 0 <= detection_confidence <= 1 or not 0 <= translation_confidence <= 1:
        raise ValueError("Bedrock confidence values must be between 0 and 1.")
    if not source_language:
        raise ValueError("Source language was not detected.")
    if not isinstance(translated_text, str) or not translated_text.strip():
        raise ValueError("Bedrock returned empty translated text.")
    is_english = source_language.casefold() in {
        "english",
        "en",
        "eng",
    }
    return {
        "source_language": source_language,
        "translated_text": translated_text.strip(),
        "detection_confidence": round(detection_confidence, 4),
        "translation_confidence": round(translation_confidence, 4),
        "translated": not is_english,
    }


def translate_text(text: str) -> dict[str, Any]:
    if not text or not text.strip():
        raise ValueError("Invoice text is empty.")
    key = cache_key(text)
    try:
        cached = cache.get(key)
        if isinstance(cached, bytes):
            cached = cached.decode("utf-8")
        if isinstance(cached, str) and cached.strip():
            cached = json.loads(cached)
        if isinstance(cached, dict):
            required_keys = {
                "source_language",
                "translated_text",
                "detection_confidence",
                "translation_confidence",
                "translated",
            }
            if required_keys.issubset(cached):
                return {
                    **cached,
                    "cache_hit": True,
                }
    except Exception:
        pass
    result = detect_and_translate(text)
    try:
        cache.set(key, json.dumps(result, ensure_ascii=False), ttl=60 * 60)
    except Exception:
        pass
    return {
        **result,
        "cache_hit": False,
    }


def translate_invoice(
    invoice_id: UUID | str,
    db: Session,
) -> dict[str, Any]:
    try:
        parsed_id = (
            invoice_id if isinstance(invoice_id, UUID) else UUID(str(invoice_id))
        )
    except (ValueError, TypeError, AttributeError):
        return {
            "status": "failed",
            "invoice_id": str(invoice_id),
            "error": "Invalid invoice ID.",
        }
    invoice = (
        db.query(InvoiceAudit).filter(InvoiceAudit.invoice_id == parsed_id).first()
    )
    if invoice is None:
        return {
            "status": "failed",
            "invoice_id": str(parsed_id),
            "error": "Invoice audit record not found.",
        }
    raw_text = invoice.raw_extracted_text
    if not raw_text or not raw_text.strip():
        return {
            "status": "failed",
            "invoice_id": str(parsed_id),
            "error": "No extracted text is available.",
        }
    try:
        result = translate_text(raw_text)
        invoice.source_language = result["source_language"]
        invoice.translated_text = result["translated_text"]
        invoice.translation_confidence = result["translation_confidence"]
        db.commit()
        return {
            "status": "success",
            "invoice_id": str(invoice.invoice_id),
            **result,
        }
    except Exception as exc:
        db.rollback()
        return {
            "status": "failed",
            "invoice_id": str(parsed_id),
            "error": str(exc),
        }
