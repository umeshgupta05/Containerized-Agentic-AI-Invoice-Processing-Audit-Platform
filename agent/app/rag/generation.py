import os
from pathlib import Path

import litellm
import yaml
from app.rag.augmentation import format_context

PERSONA_PATH = Path(__file__).resolve().parents[1] / "configs" / "rag_persona.yaml"
DEFAULT_PERSONA = {
    "name": "Invoice Context QA Assistant",
    "role": "invoice audit and retrieval assistant",
    "tone": "precise, factual, and concise",
    "objective": "Answer questions only from the supplied invoice context and stay within the invoice scope.",
    "instructions": [
        "Use only the provided invoice context as the source of truth.",
        "Do not answer irrelevant, off-topic, or unsupported questions.",
        "If the answer is not present in the context, say: 'I cannot answer this from the provided invoice context.'",
        "Do not invent values, dates, amounts, vendors, or policy details.",
        "Keep responses brief, factual, and directly tied to the invoice data.",
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
        f"You are {persona.get('name', 'Invoice Context QA Assistant')}. "
        f"Your role is {persona.get('role', 'invoice audit and retrieval assistant')}. "
        f"Tone: {persona.get('tone', 'precise, factual, and concise')}. "
        f"Objective: {persona.get('objective', 'Answer questions only from the supplied invoice context and stay within the invoice scope.')}\n\n"
        "Strict response rules:\n"
        "- Answer only using the provided invoice context.\n"
        "- Do not answer irrelevant, off-topic, or unsupported questions.\n"
        "- If the context does not contain the answer, respond exactly with: 'I cannot answer this from the provided invoice context.'\n"
        "- Do not invent values, dates, amounts, vendors, or policy details.\n"
        "- Keep the response brief, factual, and directly tied to the invoice data.\n"
        f"{persona_suffix}"
    )


SYSTEM = build_system_prompt()


def litellm_model() -> str:
    return os.getenv("LITELLM_MODEL", "bedrock/anthropic.claude-3-haiku-20240307-v1:0")


def generate(question: str, docs: list[dict]) -> str:
    context = format_context(docs)
    messages = [
        {"role": "system", "content": build_system_prompt()},
        {"role": "user", "content": f"Context:\n{context}\n\nQuestion: {question}"},
    ]
    response = litellm.completion(
        model=litellm_model(),
        messages=messages,
        temperature=0,
        max_tokens=2048,
    )
    return response.choices[0].message.content
