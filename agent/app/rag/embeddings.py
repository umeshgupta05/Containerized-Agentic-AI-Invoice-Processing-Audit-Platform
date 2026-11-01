import os

import litellm

EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "bedrock/amazon.titan-embed-text-v1")
EMBEDDING_DIM = int(os.getenv("EMBEDDING_DIM", "1536"))


def embed(text: str) -> list[float]:
    response = litellm.embedding(model=EMBEDDING_MODEL, input=[text])
    return response.data[0]["embedding"]


def embed_batch(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    response = litellm.embedding(model=EMBEDDING_MODEL, input=texts)
    return [item["embedding"] for item in response.data]
