"""Small JSON HTTP API for member B to call member A locally.

Run from the project root:
    python run_member_a_api.py

Default behavior is SQLite/rule-based planning because it is deterministic for
member B demos. To enable LLM planning, send use_llm=true in the POST payload.
Optional payload field llm_provider can be "local" or "gemini".
"""

from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import sys
from typing import Any


def _project_root() -> Path:
    here = Path(__file__).resolve()
    candidates = [
        here.parent,
        here.parent.parent,
        Path.cwd(),
        Path.cwd().parent,
    ]
    for candidate in candidates:
        if (candidate / "member_a").is_dir():
            return candidate
    raise FileNotFoundError(
        "Cannot locate project root. Please run this script inside the project folder "
        "that contains member_a/."
    )


ROOT = _project_root()
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from member_a.api import run_member_a_json
from member_a.gemini_client import GeminiClient, load_env_file
from member_a.llm_planner import GeminiItineraryPlanner
from member_a.local_llm_client import LocalLLMClient


class MemberAHandler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:
        if self.path != "/member-a/plan":
            self.send_error(404, "Use POST /member-a/plan")
            return

        try:
            length = int(self.headers.get("Content-Length", "0"))
            raw_body = self.rfile.read(length).decode("utf-8") if length else "{}"
            payload = json.loads(raw_body)

            result = run_member_a_json(
                payload,
                db_path=_find_full_db(),
                llm_planner=_build_llm_planner(payload),
            )
            self._send_json(200, result)

        except json.JSONDecodeError as exc:
            self._send_json(400, {"error": f"Invalid JSON payload: {exc}"})
        except FileNotFoundError as exc:
            self._send_json(500, {"error": str(exc), "hint": "確認 member_c/database/thailand_trip_full.db 是否存在。"})
        except Exception as exc:
            self._send_json(500, {"error": str(exc)})

    def do_GET(self) -> None:
        if self.path not in {"/", "/health"}:
            self.send_error(404, "Use POST /member-a/plan")
            return

        try:
            database = str(_find_full_db())
            ok = True
            error = ""
        except Exception as exc:
            database = ""
            ok = False
            error = str(exc)

        self._send_json(
            200 if ok else 500,
            {
                "ok": ok,
                "service": "member-a",
                "endpoint": "POST /member-a/plan",
                "project_root": str(ROOT),
                "database": database,
                "error": error,
            },
        )

    def _send_json(self, status: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:
        return


def main() -> None:
    load_env_file(ROOT / ".env")
    db_path = _find_full_db()

    server = ThreadingHTTPServer(("127.0.0.1", 8765), MemberAHandler)
    print("成員 A API 已啟動：http://127.0.0.1:8765/member-a/plan")
    print("健康檢查：http://127.0.0.1:8765/health")
    print(f"專案根目錄：{ROOT}")
    print(f"資料庫：{db_path}")
    print("預設模式：SQLite 規則版；payload use_llm=true 才啟用 LLM。")
    print("停止服務請按 Ctrl+C")
    server.serve_forever()


def _build_llm_planner(payload: dict[str, Any]):
    use_llm = bool(payload.get("use_llm", False))
    if not use_llm:
        return None

    provider = str(payload.get("llm_provider", "local")).lower().strip()
    if provider == "gemini":
        return GeminiItineraryPlanner(GeminiClient())
    if provider in {"local", "ollama"}:
        return GeminiItineraryPlanner(LocalLLMClient())

    raise ValueError("llm_provider must be 'local' or 'gemini'.")


def _find_full_db() -> Path:
    preferred = ROOT / "member_c" / "database" / "thailand_trip_full.db"
    if preferred.exists():
        return preferred

    candidates = sorted(ROOT.glob("**/thailand_trip_full.db"))
    if not candidates:
        raise FileNotFoundError(
            "Cannot find thailand_trip_full.db under the project folder. "
            "Expected path: member_c/database/thailand_trip_full.db"
        )
    return candidates[0]


if __name__ == "__main__":
    main()
