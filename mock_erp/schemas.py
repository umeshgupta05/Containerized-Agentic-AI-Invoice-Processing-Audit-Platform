from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict


class ORMResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class VendorResponse(ORMResponse):
    vendor_id: str
    vendor_name: str
    country: Optional[str] = None
    currency: Optional[str] = None


class SKUResponse(ORMResponse):
    item_code: str
    category: Optional[str] = None
    uom: Optional[str] = None
    gst_rate: Optional[Decimal] = None


class PurchaseOrderLineResponse(ORMResponse):
    id: str
    po_number: str
    item_code: Optional[str] = None
    description: Optional[str] = None
    qty: Optional[Decimal] = None
    unit_price: Optional[Decimal] = None
    currency: Optional[str] = None


class PurchaseOrderResponse(BaseModel):
    po_number: str
    vendor_id: str
    line_items: list[PurchaseOrderLineResponse]
