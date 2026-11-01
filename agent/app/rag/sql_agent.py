from __future__ import annotations

from typing import Any

from app.db.db import Base, engine
from app.rag.query_router import classify_query
from app.services.llm_client import get_bedrock_converse_llm
from pydantic import BaseModel, Field
from sqlalchemy import text


class QueryClassification(BaseModel):
    category: str = Field(description="Return either 'rag' or 'sql'.")


class GeneratedSql(BaseModel):
    sql: str = Field(
        description="A safe read-only SQL SELECT statement that answers the question."
    )


def get_database_schema() -> str:
    schema_lines: list[str] = []
    for table in sorted(
        Base.metadata.tables.values(),
        key=lambda item: (item.schema or "", item.name),
    ):
        columns = ", ".join(f"{column.name}: {column.type}" for column in table.columns)
        schema_lines.append(f"- {table.schema}.{table.name}: {columns}")
    return "\n".join(schema_lines)


def generate_sql_query(question: str) -> str:
    llm = get_bedrock_converse_llm(temperature=0, max_tokens=512)
    structured_llm = llm.with_structured_output(GeneratedSql)
    response = structured_llm.invoke(
        [
            (
                "system",
                "You are a SQL generation assistant. Use the schema exactly as provided. "
                "Generate a read-only SQL SELECT statement only. Do not use UPDATE, DELETE, "
                "INSERT, DROP, ALTER, or other DDL/DML. Keep the query safe and deterministic. "
                "Return only the SQL text, no markdown fences.",
            ),
            (
                "human",
                f"Database schema:\n{get_database_schema()}\n\nQuestion: {question}",
            ),
        ]
    )
    sql = getattr(response, "sql", None) or str(response).strip()
    if not sql:
        raise ValueError("SQL generation returned an empty query.")
    cleaned = sql.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("` ")
        if cleaned.lower().startswith("sql"):
            cleaned = cleaned[3:].strip()
    if not cleaned.lower().startswith("select"):
        raise ValueError("Generated SQL was not a SELECT statement.")
    return cleaned


def execute_sql_query(sql: str) -> list[dict[str, Any]]:
    with engine.connect() as connection:
        result = connection.execute(text(sql))
        rows = result.mappings().all()
        return [dict(row) for row in rows]


def format_label(name: str) -> str:
    return name.replace("_", " ").title()


def format_value(value: Any) -> str:
    if value is None:
        return "Not available"
    return str(value)


def format_sql_answer(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "No matching invoice records were found."

    lines = [f"Found {len(rows)} matching invoice record(s)."]
    for index, row in enumerate(rows, start=1):
        lines.append("")
        lines.append(f"Record {index}:")
        for key, value in row.items():
            lines.append(f"- {format_label(key)}: {format_value(value)}")
    return "\n".join(lines)


def sql_sources(rows: list[dict[str, Any]]) -> list[str]:
    sources = []
    for row in rows:
        source = row.get("invoice_number") or row.get("invoice_id")
        if source:
            sources.append(str(source))
    return list(dict.fromkeys(sources))


def route_sql_question(question: str) -> dict[str, Any] | None:
    try:
        if classify_query(question) != "sql":
            return None
        sql = generate_sql_query(question)
        rows = execute_sql_query(sql)
        return {
            "source": "sql",
            "query_type": "sql",
            "sql": sql,
            "rows": rows,
            "answer": format_sql_answer(rows),
            "sources": sql_sources(rows),
        }
    except Exception:
        return None
