import json
import os
from typing import Any

from redis import Redis

DEFAULT_TTL_SECONDS = 60 * 60
CACHE_URL = os.getenv("REDIS_URL", "redis://redis:6379/1")


def get_redis_client() -> Any | None:
    try:
        return Redis.from_url(CACHE_URL, decode_responses=True)
    except Exception:
        return None


def get(key: str) -> Any:
    client = get_redis_client()
    if client is None:
        return None
    try:
        value = client.get(key)
    except Exception:
        return None
    if value is None:
        return None
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return value


def set(key: str, value: Any, ttl: int | None = DEFAULT_TTL_SECONDS) -> bool:
    payload = (
        value
        if isinstance(value, (str, bytes))
        else json.dumps(value, ensure_ascii=False)
    )
    client = get_redis_client()
    if client is None:
        return False
    try:
        return bool(client.set(key, payload, ex=ttl or DEFAULT_TTL_SECONDS))
    except Exception:
        return False


def delete(key: str) -> bool:
    client = get_redis_client()
    if client is None:
        return False
    try:
        return bool(client.delete(key))
    except Exception:
        return False
