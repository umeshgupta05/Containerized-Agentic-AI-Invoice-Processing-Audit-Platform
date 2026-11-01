import os
from typing import Any

import httpx

MOCK_ERP_URL = os.getenv("MOCK_ERP_URL", "http://mock-erp:8000")


def get_vendor(vendor_id: str) -> dict[str, Any]:
    response = httpx.get(f"{MOCK_ERP_URL}/vendor/{vendor_id}", timeout=10)
    response.raise_for_status()
    return response.json()


def get_sku(sku_code: str) -> dict[str, Any]:
    response = httpx.get(f"{MOCK_ERP_URL}/sku/{sku_code}", timeout=10)
    response.raise_for_status()
    return response.json()


def get_purchase_order(po_number: str) -> dict[str, Any]:
    response = httpx.get(f"{MOCK_ERP_URL}/po/{po_number}", timeout=10)
    response.raise_for_status()
    return response.json()
