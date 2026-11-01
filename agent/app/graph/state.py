from typing import Any, TypedDict


class InvoiceAuditState(TypedDict, total=False):
    invoice_id: str
    file_path: str
    extraction_result: dict[str, Any]
    translation_result: dict[str, Any]
    data_validation_result: dict[str, Any]
    business_validation_result: dict[str, Any]
    report: dict[str, Any]
    report_file: str
    status: str
    current_stage: str
    errors: list[dict[str, str]]
