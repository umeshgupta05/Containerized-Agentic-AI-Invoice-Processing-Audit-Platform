import os
from typing import Any

import httpx
import streamlit as st

AGENT_URL = os.getenv("AGENT_URL", "http://agent:8000")
TIMEOUT = 300


def get(path: str, params: dict | None = None) -> Any | None:
    try:
        resp = httpx.get(f"{AGENT_URL}{path}", params=params, timeout=TIMEOUT)
        resp.raise_for_status()
        return resp.json()
    except httpx.HTTPStatusError as exc:
        st.error(
            f"Agent API error {exc.response.status_code}: {exc.response.text[:300]}"
        )
        return None
    except Exception as exc:
        st.error(f"Cannot reach agent ({AGENT_URL}): {exc}")
        return None


def post(path: str, payload: dict) -> Any | None:
    try:
        resp = httpx.post(f"{AGENT_URL}{path}", json=payload, timeout=TIMEOUT)
        resp.raise_for_status()
        return resp.json()
    except httpx.HTTPStatusError as exc:
        st.error(
            f"Agent API error {exc.response.status_code}: {exc.response.text[:300]}"
        )
        return None
    except Exception as exc:
        st.error(f"Cannot reach agent ({AGENT_URL}): {exc}")
        return None
