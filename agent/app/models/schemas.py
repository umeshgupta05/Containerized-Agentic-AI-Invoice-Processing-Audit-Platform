from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class InvoiceLineItemRead(ORMModel):
    id: int
    invoice_id: UUID
    line_number: int | None = None
    item_code: str | None = None
    description: str | None = None
    quantity: Decimal | None = None
    unit_price: Decimal | None = None
    line_total: Decimal | None = None


class DiscrepancyRead(ORMModel):
    id: int
    invoice_id: UUID
    field_name: str
    invoice_value: str | None = None
    erp_value: str | None = None
    deviation_pct: Decimal | None = None
    severity: str | None = None
    detected_at: datetime


class HumanFeedbackCreate(BaseModel):
    field_name: str = Field(
        min_length=1,
        max_length=64,
    )
    original_value: str | None = None
    corrected_value: str | None = None
    corrected_by: str | None = Field(
        default=None,
        max_length=128,
    )


class HumanFeedbackRead(ORMModel):
    id: int
    invoice_id: UUID
    field_name: str
    original_value: str | None = None
    corrected_value: str | None = None
    corrected_by: str | None = None
    corrected_at: datetime
    revalidated: bool


class InvoiceAuditRead(ORMModel):
    invoice_id: UUID
    file_path: str | None = None
    file_checksum: str
    extraction_method: str | None = None
    raw_extracted_text: str | None = None
    translated_text: str | None = None
    source_language: str | None = None
    translation_confidence: Decimal | None = None
    invoice_number: str | None = None
    vendor_name: str | None = None
    po_number: str | None = None
    invoice_date: date | None = None
    currency: str | None = None
    total_amount: Decimal | None = None
    validation_status: str | None = None
    recommendation: str | None = None
    extracted_raw: dict[str, Any] | None = None
    thread_id: str | None = None
    processed_at: datetime
    line_items: list[InvoiceLineItemRead] = Field(default_factory=list)
    discrepancies: list[DiscrepancyRead] = Field(default_factory=list)


class InvoiceAuditListItem(ORMModel):
    invoice_id: UUID
    invoice_number: str | None = None
    vendor_name: str | None = None
    invoice_date: date | None = None
    currency: str | None = None
    total_amount: Decimal | None = None
    validation_status: str | None = None
    recommendation: str | None = None
    processed_at: datetime
