from __future__ import annotations

import math
import os
import sys
from typing import Any
from unittest.mock import MagicMock

sys.modules["langchain_community.chat_models.vertexai"] = MagicMock()
sys.modules["langchain_community.llms.vertexai"] = MagicMock()


def safe_float(value: Any) -> float:
    if value is None:
        return 0.0

    try:
        score = float(value)
    except (TypeError, ValueError):
        return 0.0

    if math.isnan(score) or score < 0.0:
        return 0.0
    if score > 1.0:
        return 1.0
    return score


def reflect(question: str, answer: str, docs: list[dict]) -> dict[str, Any]:
    empty_metrics = {
        "relevance": 0.0,
        "groundedness": 0.0,
        "context_relevance": 0.0,
    }
    answer_text = (answer or "").strip()
    if not answer_text or len(answer_text) < 15:
        return {
            "ok": False,
            "reason": "Answer is too short for evaluation.",
            "score": 0.0,
            "metrics": empty_metrics,
            "retryable": True,
        }
    try:
        from langchain_aws import BedrockEmbeddings, ChatBedrockConverse
        from ragas import EvaluationDataset, evaluate
        from ragas.embeddings import LangchainEmbeddingsWrapper
        from ragas.llms import LangchainLLMWrapper
        from ragas.metrics import (
            Faithfulness,
            LLMContextPrecisionWithoutReference,
            ResponseRelevancy,
        )
        from ragas.run_config import RunConfig

        from app.services.llm_client import get_model_name
    except Exception as exc:
        return {
            "ok": False,
            "reason": f"RAGAS evaluation unavailable: {exc}",
            "score": 0.0,
            "metrics": empty_metrics,
            "retryable": False,
        }
    try:
        contexts = []
        for doc in docs:
            payload = doc.get("payload") or {}
            text = payload.get("text") or doc.get("page_content") or ""
            if text:
                contexts.append(str(text))
        if not contexts:
            contexts = [""]
        embedding_model = os.getenv(
            "EMBEDDING_MODEL", "bedrock/amazon.titan-embed-text-v1"
        ).removeprefix("bedrock/")
        dataset = EvaluationDataset.from_list(
            [
                {
                    "user_input": question,
                    "response": answer_text,
                    "retrieved_contexts": contexts,
                }
            ]
        )
        eval_llm = LangchainLLMWrapper(
            ChatBedrockConverse(
                model=os.getenv("RAGAS_LLM_MODEL", get_model_name()).removeprefix(
                    "bedrock/"
                ),
                region_name=os.getenv("AWS_REGION", "us-east-1"),
                temperature=0,
                max_tokens=2048,
                max_retries=0,
            )
        )
        eval_embeddings = LangchainEmbeddingsWrapper(
            BedrockEmbeddings(
                model_id=embedding_model,
                region_name=os.getenv("AWS_REGION", "us-east-1"),
            )
        )
        result = evaluate(
            dataset=dataset,
            metrics=[
                ResponseRelevancy(llm=eval_llm, embeddings=eval_embeddings),
                Faithfulness(llm=eval_llm),
                LLMContextPrecisionWithoutReference(llm=eval_llm),
            ],
            llm=eval_llm,
            embeddings=eval_embeddings,
            run_config=RunConfig(
                max_retries=0,
                max_wait=1,
                max_workers=1,
            ),
            raise_exceptions=False,
            show_progress=False,
        )
        row = (
            result.to_pandas().iloc[0].to_dict() if hasattr(result, "to_pandas") else {}
        )
        metrics = {
            "relevance": safe_float(
                row.get("answer_relevancy", row.get("response_relevancy"))
            ),
            "groundedness": safe_float(row.get("faithfulness")),
            "context_relevance": safe_float(
                row.get("llm_context_precision_without_reference")
            ),
        }
        overall = round(
            (
                metrics["relevance"]
                + metrics["groundedness"]
                + metrics["context_relevance"]
            )
            / 3.0,
            4,
        )
        ok = overall > 0.7
        return {
            "ok": ok,
            "reason": "" if ok else "RAGAS triad score below the approval threshold.",
            "score": overall,
            "metrics": metrics,
            "retryable": not ok,
        }
    except Exception as exc:
        return {
            "ok": False,
            "reason": f"RAGAS evaluation failed: {exc}",
            "score": 0.0,
            "metrics": empty_metrics,
            "retryable": False,
        }
