from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from app.services.llm_client import get_bedrock_converse_llm
from pydantic import BaseModel, Field

PERSONA_PATH = Path(__file__).resolve().parents[1] / "configs" / "query_router_persona.yaml"
DEFAULT_PERSONA = {
    "name": "Invoice Routing Assistant",
    "role": "invoice request router",
    "tone": "precise, factual, and concise",
    "objective": "Classify each user request as either rag or sql using only the request itself and the invoice context rules.",
    "instructions": [
        "Return exactly one category: 'rag' or 'sql'.",
        "Use 'sql' only for questions that can be answered directly from the PostgreSQL database, such as counts, lists, totals, statuses, recent records, and aggregate analytics.",
        "Use 'rag' for semantic, invoice-context, or document-based questions that need retrieval and generation.",
        "Do not answer off-topic or unsupported questions; route them conservatively to 'rag' if the intent is not clearly SQL.",
    ],
}


def load_persona() -> dict:
    if not PERSONA_PATH.exists():
        return DEFAULT_PERSONA.copy()

    with PERSONA_PATH.open("r", encoding="utf-8") as file:
        configured = yaml.safe_load(file) or {}

    return {
        **DEFAULT_PERSONA,
        **configured,
    }


def build_system_prompt() -> str:
    persona = load_persona()
    instructions = persona.get("instructions", [])
    if isinstance(instructions, str):
        instructions = [instructions]

    instruction_lines = "\n".join(f"- {line}" for line in instructions)
    persona_suffix = (
        f"Persona-specific instructions:\n{instruction_lines}"
        if instruction_lines
        else ""
    )
    return (
        f"You are {persona.get('name', 'Invoice Routing Assistant')}. "
        f"Your role is {persona.get('role', 'invoice request router')}. "
        f"Tone: {persona.get('tone', 'precise, factual, and concise')}. "
        f"Objective: {persona.get('objective', 'Classify each user request as either rag or sql using only the request itself and the invoice context rules.')}\n\n"
        "Strict routing rules:\n"
        "- Return exactly one category: 'rag' or 'sql'.\n"
        "- Use 'sql' only for questions that can be answered directly from the PostgreSQL database, such as counts, lists, totals, statuses, recent records, and aggregate analytics.\n"
        "- Use 'rag' for semantic, invoice-context, or document-based questions that need retrieval and generation.\n"
        "- If the request is unclear, off-topic, or not clearly a database query, prefer 'rag'.\n"
        f"{persona_suffix}"
    )


class QueryClassification(BaseModel):
    category: Literal["rag", "sql"] = Field(
        description="Classify the request into rag or sql."
    )


def classify_query(question: str) -> str:
    llm = get_bedrock_converse_llm(temperature=0, max_tokens=256)
    structured_llm = llm.with_structured_output(QueryClassification)
    response = structured_llm.invoke(
        [
            ("system", build_system_prompt()),
            ("human", question),
        ]
    )
    category = getattr(response, "category", None)
    if category not in {"rag", "sql"}:
        category = "rag"
    return category
