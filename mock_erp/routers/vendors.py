from database import get_db
from fastapi import APIRouter, Depends, HTTPException
from models import Vendor
from schemas import VendorResponse
from sqlalchemy.orm import Session

router = APIRouter(tags=["Vendors"])


@router.get("/vendor/{vendor_id}", response_model=VendorResponse)
def get_vendor(vendor_id: str, db: Session = Depends(get_db)):
    vendor = db.query(Vendor).filter(Vendor.vendor_id == vendor_id).first()
    if vendor is None:
        raise HTTPException(status_code=404, detail=f"Vendor '{vendor_id}' not found")
    return vendor
