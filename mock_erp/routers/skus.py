from database import get_db
from fastapi import APIRouter, Depends, HTTPException
from models import SKU
from schemas import SKUResponse
from sqlalchemy.orm import Session

router = APIRouter(tags=["SKUs"])


@router.get("/sku/{item_code}", response_model=SKUResponse)
def get_sku(item_code: str, db: Session = Depends(get_db)):
    sku = db.query(SKU).filter(SKU.item_code == item_code).first()
    if sku is None:
        raise HTTPException(status_code=404, detail=f"SKU '{item_code}' not found")
    return sku
