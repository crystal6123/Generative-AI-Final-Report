"""Small JSON HTTP API for member B to call member A locally."""

from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from member_a.api import run_member_a_json
from member_a.gemini_client import load_env_file
from member_a.llm_planner import GeminiItineraryPlanner
from member_a.local_llm_client import LocalLLMClient


class MemberAHandler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:
        if self.path != "/member-a/plan":
            self.send_error(404, "Use POST /member-a/plan")
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
            result = run_member_a_json(
                payload,
                db_path=_find_full_db(),
                llm_planner=GeminiItineraryPlanner(LocalLLMClient()) if payload.get("use_llm", True) else None,
            )
            self._send_json(200, result)
        except Exception as exc:
            self._send_json(500, {"error": str(exc)})

    def _send_json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main() -> None:
    load_env_file(ROOT / ".env")
    server = ThreadingHTTPServer(("127.0.0.1", 8765), MemberAHandler)
    print("成員 A API 已啟動：http://127.0.0.1:8765/member-a/plan")
    print("停止服務請按 Ctrl+C")
    server.serve_forever()


def _find_full_db() -> Path:
    candidates = sorted(ROOT.glob("**/thailand_trip_full.db"))
    if not candidates:
        raise FileNotFoundError("Cannot find thailand_trip_full.db under the project folder.")
    return candidates[0]


if __name__ == "__main__":
    main()
