from database import get_db
from fastapi import APIRouter, Depends, HTTPException
from models import PurchaseOrder, PurchaseOrderLine
from schemas import PurchaseOrderLineResponse, PurchaseOrderResponse
from sqlalchemy.orm import Session

router = APIRouter(tags=["Purchase Orders"])


@router.get("/po/{po_number}", response_model=PurchaseOrderResponse)
def get_purchase_order(po_number: str, db: Session = Depends(get_db)):
    po = db.query(PurchaseOrder).filter(PurchaseOrder.po_number == po_number).first()
    if po is None:
        raise HTTPException(
            status_code=404, detail=f"Purchase order '{po_number}' not found"
        )
    lines = (
        db.query(PurchaseOrderLine)
        .filter(PurchaseOrderLine.po_number == po_number)
        .all()
    )
    return PurchaseOrderResponse(
        po_number=po.po_number,
        vendor_id=po.vendor_id,
        line_items=[PurchaseOrderLineResponse.model_validate(line) for line in lines],
    )
