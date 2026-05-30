"""Local Ollama-compatible JSON client for member A."""

from __future__ import annotations

import json
import os
import re
from urllib import error, request


class LocalLLMClient:
    def __init__(
        self,
        *,
        model: str | None = None,
        url: str | None = None,
        timeout_seconds: int = 180,
    ):
        self.model = model or os.environ.get("LOCAL_LLM_MODEL", "deepseek-r1:8b")
        self.url = url or os.environ.get("LOCAL_LLM_URL", "http://localhost:11434/api/generate")
        self.timeout_seconds = timeout_seconds

    def generate_json(self, *, prompt: str, schema: dict) -> dict:
        payload = {
            "model": self.model,
            "prompt": self._json_prompt(prompt, schema),
            "stream": False,
            "format": "json",
            "options": {
                "temperature": 0.2,
            },
        }
        body = json.dumps(payload).encode("utf-8")
        req = request.Request(
            self.url,
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with request.urlopen(req, timeout=self.timeout_seconds) as response:
                response_data = json.loads(response.read().decode("utf-8"))
        except error.HTTPError as exc:
            details = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Local LLM request failed: {exc.code} {details}") from exc
        except error.URLError as exc:
            raise RuntimeError(f"Local LLM request failed: {exc.reason}") from exc

        text = str(response_data.get("response", ""))
        return parse_json_text(text)

    @staticmethod
    def _json_prompt(prompt: str, schema: dict) -> str:
        return f"""
{prompt}

你必須只輸出 JSON 物件，不要輸出 Markdown，不要輸出說明文字。
JSON schema 參考：
{json.dumps(schema, ensure_ascii=False)}
"""


def parse_json_text(text: str) -> dict:
    cleaned = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise ValueError(f"Local LLM returned invalid JSON: {text}")
        return json.loads(cleaned[start : end + 1])
