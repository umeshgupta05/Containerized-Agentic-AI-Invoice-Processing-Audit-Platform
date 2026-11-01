from database import Base
from sqlalchemy import Column, ForeignKey, Numeric, String
from sqlalchemy.orm import relationship


class Vendor(Base):
    __tablename__ = "vendors"
    vendor_id = Column(String(64), primary_key=True)
    vendor_name = Column(String(255), nullable=False)
    country = Column(String(64), nullable=True)
    currency = Column(String(3), nullable=True)


class SKU(Base):
    __tablename__ = "sku_master"
    item_code = Column(String(64), primary_key=True)
    category = Column(String(128), nullable=True)
    uom = Column(String(32), nullable=True)
    gst_rate = Column(Numeric(6, 2), nullable=True)


class PurchaseOrder(Base):
    __tablename__ = "purchase_orders"
    po_number = Column(String(64), primary_key=True)
    vendor_id = Column(String(64), ForeignKey("vendors.vendor_id"), nullable=False)
    line_items = relationship("PurchaseOrderLine", back_populates="po")


class PurchaseOrderLine(Base):
    __tablename__ = "po_line_items"
    id = Column(String(128), primary_key=True)
    po_number = Column(
        String(64), ForeignKey("purchase_orders.po_number"), nullable=False
    )
    item_code = Column(String(64), ForeignKey("sku_master.item_code"), nullable=True)
    description = Column(String(512), nullable=True)
    qty = Column(Numeric(12, 3), nullable=True)
    unit_price = Column(Numeric(14, 4), nullable=True)
    currency = Column(String(3), nullable=True)
    po = relationship("PurchaseOrder", back_populates="line_items")
