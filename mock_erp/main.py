from database import engine
from fastapi import FastAPI
from routers import health, purchase_orders, skus, vendors
from seed_db import seed_db

seed_db()
app = FastAPI(
    title="Mock ERP API",
    description=(
        "Read-only ERP lookup API for the Containerized Agentic AI Invoice "
        "Processing & Audit Platform."
    ),
    version="1.0.0",
)
app.include_router(health.router)
app.include_router(vendors.router)
app.include_router(skus.router)
app.include_router(purchase_orders.router)


@app.on_event("startup")
def verify_database_connection():
    with engine.connect():
        pass
