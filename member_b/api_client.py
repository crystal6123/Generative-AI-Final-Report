"""Client for member B Streamlit UI to call member A local HTTP API."""

from __future__ import annotations

from typing import Any

import requests


MEMBER_A_PLAN_URL = "http://127.0.0.1:8765/member-a/plan"
MEMBER_A_CHAT_URL = "http://127.0.0.1:8765/member-a/chat"


def request_trip_plan(payload: dict[str, Any], *, timeout: int = 120) -> dict[str, Any]:
    """Call member A itinerary planning API."""
    response = requests.post(MEMBER_A_PLAN_URL, json=payload, timeout=timeout)
    try:
        data = response.json()
    except ValueError as exc:
        raise RuntimeError(f"member A API 回傳不是 JSON：{response.text}") from exc

    if response.status_code != 200:
        raise RuntimeError(data.get("error", f"HTTP {response.status_code}"))

    return data


def request_ai_chat(payload: dict[str, Any], *, timeout: int = 90) -> dict[str, Any]:
    """Call member A Gemini chatbot API."""
    response = requests.post(MEMBER_A_CHAT_URL, json=payload, timeout=timeout)
    try:
        data = response.json()
    except ValueError as exc:
        raise RuntimeError(f"AI chat API 回傳不是 JSON：{response.text}") from exc

    if response.status_code != 200:
        raise RuntimeError(data.get("error", f"HTTP {response.status_code}"))

    return data
