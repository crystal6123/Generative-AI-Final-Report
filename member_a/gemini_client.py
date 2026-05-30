"""Minimal Gemini REST client used by member A's LLM planner."""

from __future__ import annotations

import json
import os
from pathlib import Path
from urllib import error, request


def load_env_file(path: str | Path) -> None:
    env_path = Path(path)
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


class GeminiClient:
    def __init__(
        self,
        *,
        api_key: str | None = None,
        model: str | None = None,
        timeout_seconds: int = 60,
    ):
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY is required to use Gemini.")
        self.model = model or os.environ.get("GEMINI_MODEL", "gemini-3.5-flash")
        self.timeout_seconds = timeout_seconds

    def generate_json(self, *, prompt: str, schema: dict) -> dict:
        payload = {
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": prompt}],
                }
            ],
            "generationConfig": {
                "temperature": 0.3,
                "responseMimeType": "application/json",
                "responseSchema": schema,
            },
        }
        body = json.dumps(payload).encode("utf-8")
        req = request.Request(
            f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent",
            data=body,
            headers={
                "Content-Type": "application/json",
                "x-goog-api-key": self.api_key,
            },
            method="POST",
        )
        try:
            with request.urlopen(req, timeout=self.timeout_seconds) as response:
                response_data = json.loads(response.read().decode("utf-8"))
        except error.HTTPError as exc:
            details = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Gemini API request failed: {exc.code} {details}") from exc
        except error.URLError as exc:
            raise RuntimeError(f"Gemini API request failed: {exc.reason}") from exc

        text = self._extract_text(response_data)
        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Gemini returned invalid JSON: {text}") from exc

    @staticmethod
    def _extract_text(response_data: dict) -> str:
        candidates = response_data.get("candidates") or []
        if not candidates:
            raise ValueError("Gemini returned no candidates.")
        parts = candidates[0].get("content", {}).get("parts") or []
        texts = [part.get("text", "") for part in parts if part.get("text")]
        if not texts:
            raise ValueError("Gemini returned no text parts.")
        return "".join(texts)
