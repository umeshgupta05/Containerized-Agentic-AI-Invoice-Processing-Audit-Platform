import os
import time
from collections.abc import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, declarative_base, sessionmaker

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+pg8000://postgres:postgres@postgres:5432/invoice_auditor",
)
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
    pool_timeout=30,
)
SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
)
Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def wait_for_database(
    retries: int = 15,
    delay_seconds: int = 2,
) -> None:
    last_error = None
    for attempt in range(retries):
        try:
            with engine.connect() as connection:
                connection.execute(text("SELECT 1"))
            return
        except Exception as exc:
            last_error = exc
            if attempt < retries - 1:
                time.sleep(delay_seconds)
    raise RuntimeError(
        f"PostgreSQL was not ready after {retries} attempts"
    ) from last_error


def initialize_audit_tables() -> None:
    with engine.begin() as connection:
        connection.execute(text("CREATE SCHEMA IF NOT EXISTS audit"))
    tables = [
        Base.metadata.tables["audit.invoice_audit"],
        Base.metadata.tables["audit.invoice_line_items"],
        Base.metadata.tables["audit.discrepancies"],
        Base.metadata.tables["audit.human_feedback"],
        Base.metadata.tables["audit.processing_audit_log"],
    ]
    Base.metadata.create_all(
        bind=engine,
        tables=tables,
    )
