import uuid

from app.db.db import Base
from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship


class InvoiceAudit(Base):
    __tablename__ = "invoice_audit"
    __table_args__ = (
        UniqueConstraint(
            "file_checksum",
            name="uq_invoice_audit_file_checksum",
        ),
        Index(
            "ix_invoice_audit_invoice_number",
            "invoice_number",
        ),
        Index(
            "ix_invoice_audit_vendor_name",
            "vendor_name",
        ),
        Index(
            "ix_invoice_audit_invoice_date",
            "invoice_date",
        ),
        Index(
            "ix_invoice_audit_validation_status",
            "validation_status",
        ),
        {"schema": "audit"},
    )
    invoice_id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    file_path = Column(String(512), nullable=True)
    file_checksum = Column(String(64), nullable=False)
    extraction_method = Column(String(32), nullable=True)
    raw_extracted_text = Column(Text, nullable=True)
    translated_text = Column(Text, nullable=True)
    source_language = Column(String(32), nullable=True)
    translation_confidence = Column(Numeric(4, 3), nullable=True)
    invoice_number = Column(String(64), nullable=True)
    vendor_name = Column(String(255), nullable=True)
    po_number = Column(String(64), nullable=True)
    invoice_date = Column(Date, nullable=True)
    currency = Column(String(3), nullable=True)
    total_amount = Column(Numeric(14, 2), nullable=True)
    validation_status = Column(String(32), nullable=True)
    recommendation = Column(String(32), nullable=True)
    extracted_raw = Column(JSONB, nullable=True)
    thread_id = Column(String(128), nullable=True)
    processed_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    line_items = relationship(
        "InvoiceLineItem",
        back_populates="invoice",
        cascade="all, delete-orphan",
    )
    discrepancies = relationship(
        "Discrepancy",
        back_populates="invoice",
        cascade="all, delete-orphan",
    )
    feedback = relationship(
        "HumanFeedback",
        back_populates="invoice",
        cascade="all, delete-orphan",
    )


class InvoiceLineItem(Base):
    __tablename__ = "invoice_line_items"
    __table_args__ = (
        Index(
            "ix_invoice_line_items_invoice_id",
            "invoice_id",
        ),
        {"schema": "audit"},
    )
    id = Column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )
    invoice_id = Column(
        UUID(as_uuid=True),
        ForeignKey(
            "audit.invoice_audit.invoice_id",
            ondelete="CASCADE",
        ),
        nullable=False,
    )
    line_number = Column(Integer, nullable=True)
    item_code = Column(String(64), nullable=True)
    description = Column(Text, nullable=True)
    quantity = Column(Numeric(12, 3), nullable=True)
    unit_price = Column(Numeric(14, 4), nullable=True)
    line_total = Column(Numeric(14, 2), nullable=True)
    invoice = relationship(
        "InvoiceAudit",
        back_populates="line_items",
    )


class Discrepancy(Base):
    __tablename__ = "discrepancies"
    __table_args__ = (
        Index(
            "ix_discrepancies_invoice_id",
            "invoice_id",
        ),
        Index(
            "ix_discrepancies_detected_at",
            "detected_at",
        ),
        {"schema": "audit"},
    )
    id = Column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )
    invoice_id = Column(
        UUID(as_uuid=True),
        ForeignKey(
            "audit.invoice_audit.invoice_id",
            ondelete="CASCADE",
        ),
        nullable=False,
    )
    field_name = Column(String(64), nullable=False)
    invoice_value = Column(Text, nullable=True)
    erp_value = Column(Text, nullable=True)
    deviation_pct = Column(Numeric(8, 4), nullable=True)
    severity = Column(String(16), nullable=True)
    detected_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    invoice = relationship(
        "InvoiceAudit",
        back_populates="discrepancies",
    )


class HumanFeedback(Base):
    __tablename__ = "human_feedback"
    __table_args__ = (
        Index(
            "ix_human_feedback_invoice_id",
            "invoice_id",
        ),
        Index(
            "ix_human_feedback_corrected_at",
            "corrected_at",
        ),
        {"schema": "audit"},
    )
    id = Column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )
    invoice_id = Column(
        UUID(as_uuid=True),
        ForeignKey(
            "audit.invoice_audit.invoice_id",
            ondelete="CASCADE",
        ),
        nullable=False,
    )
    field_name = Column(String(255), nullable=False)
    original_value = Column(Text, nullable=True)
    corrected_value = Column(Text, nullable=True)
    corrected_by = Column(String(128), nullable=True)
    corrected_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    revalidated = Column(
        Boolean,
        nullable=False,
        server_default="false",
    )
    invoice = relationship(
        "InvoiceAudit",
        back_populates="feedback",
    )


class ProcessingAuditLog(Base):
    __tablename__ = "processing_audit_log"
    __table_args__ = (
        Index(
            "ix_processing_audit_log_invoice_id",
            "invoice_id",
        ),
        Index(
            "ix_processing_audit_log_status",
            "status",
        ),
        Index(
            "ix_processing_audit_log_detected_at",
            "detected_at",
        ),
        {"schema": "audit"},
    )
    id = Column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )
    filename = Column(String(512), nullable=False)
    invoice_id = Column(
        UUID(as_uuid=True),
        ForeignKey(
            "audit.invoice_audit.invoice_id",
            ondelete="SET NULL",
        ),
        nullable=True,
    )
    report = Column(JSONB, nullable=True)
    status = Column(String(16), nullable=False)
    reason = Column(Text, nullable=True)
    detected_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    invoice = relationship(
        "InvoiceAudit",
        foreign_keys=[invoice_id],
    )
