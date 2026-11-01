import json
import uuid
from pathlib import Path

from database import Base, SessionLocal, engine
from models import SKU, PurchaseOrder, PurchaseOrderLine, Vendor

DATA_DIR = Path("/app/data/ERP_mockdata")


def seed_db():
    Base.metadata.create_all(bind=engine)
    if not DATA_DIR.exists():
        return
    db = SessionLocal()
    try:
        if db.query(Vendor).first() or db.query(PurchaseOrder).first():
            return
        vendors_path = DATA_DIR / "vendors.json"
        skus_path = DATA_DIR / "sku_master.json"
        po_path = DATA_DIR / "PO Records.json"
        for p in (vendors_path, skus_path, po_path):
            if not p.exists():
                return
        with open(vendors_path, encoding="utf-8") as f:
            vendors = json.load(f)
        db.add_all([Vendor(**v) for v in vendors])
        db.flush()
        with open(skus_path, encoding="utf-8") as f:
            skus = json.load(f)
        db.add_all([SKU(**s) for s in skus])
        db.flush()
        with open(po_path, encoding="utf-8") as f:
            purchase_orders = json.load(f)
        for record in purchase_orders:
            line_items = record.pop("line_items", [])
            po = PurchaseOrder(**record)
            db.add(po)
            db.flush()
            for item in line_items:
                db.add(
                    PurchaseOrderLine(
                        id=str(uuid.uuid4()),
                        po_number=po.po_number,
                        **item,
                    )
                )
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
