"""Gemini client utilities for member A.

This file supports both:
1. GeminiItineraryPlanner usage through generate_json-like calls if your planner
   already expects text generation.
2. The website chatbot through generate_text().

Place this file at:
    member_a/gemini_client.py
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


def load_env_file(path: str | Path) -> None:
    """Load simple KEY=VALUE pairs from a .env file without overriding env vars."""
    env_path = Path(path)
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")

        if key and key not in os.environ:
            os.environ[key] = value


class GeminiClient:
    def __init__(self, model_name: str | None = None) -> None:
        api_key = os.environ.get("GEMINI_API_KEY", "").strip()
        self.model_name = model_name or os.environ.get("GEMINI_MODEL", "gemini-2.5-flash").strip()

        if not api_key:
            raise RuntimeError("找不到 GEMINI_API_KEY，請確認專案根目錄 .env 是否已設定。")

        try:
            import google.generativeai as genai
        except ImportError as exc:
            raise RuntimeError(
                "找不到 google-generativeai，請先執行：python -m pip install google-generativeai"
            ) from exc

        genai.configure(api_key=api_key)
        self._model = genai.GenerativeModel(self.model_name)

    def generate_text(self, prompt: str) -> str:
        """Generate plain text from Gemini."""
        response = self._model.generate_content(prompt)
        text = getattr(response, "text", "") or ""
        return text.strip()

    def generate_json(self, prompt: str) -> dict[str, Any]:
        """Generate JSON from Gemini and parse it into a dict.

        This method is useful if other member_a modules expect a JSON response.
        """
        text = self.generate_text(prompt)
        return _parse_json_from_text(text)

    def complete(self, prompt: str) -> str:
        """Compatibility alias for local/LLM clients that call complete()."""
        return self.generate_text(prompt)


def _parse_json_from_text(text: str) -> dict[str, Any]:
    cleaned = text.strip()

    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`").strip()
        if cleaned.lower().startswith("json"):
            cleaned = cleaned[4:].strip()

    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start != -1 and end != -1 and end > start:
        cleaned = cleaned[start : end + 1]

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Gemini 回傳內容不是合法 JSON：{text}") from exc

    if not isinstance(data, dict):
        raise RuntimeError("Gemini JSON 回傳必須是 object/dict。")
    return data
