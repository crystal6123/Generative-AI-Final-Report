"""Small JSON HTTP API for member B to call member A locally.

Run from the project root:
    python run_member_a_api.py

Endpoints:
    GET  /health
    POST /member-a/plan
    POST /member-a/chat

Default behavior of /member-a/plan is SQLite/rule-based planning because it is
stable for demos. To enable LLM planning, send use_llm=true in the POST payload.
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
        if self.path == "/member-a/plan":
            self._handle_plan()
            return

        if self.path == "/member-a/chat":
            self._handle_chat()
            return

        self.send_error(404, "Use POST /member-a/plan or POST /member-a/chat")

    def do_GET(self) -> None:
        if self.path not in {"/", "/health"}:
            self.send_error(404, "Use POST /member-a/plan or POST /member-a/chat")
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
                "python_executable": sys.executable,
                "google_generativeai_available": _module_available("google.generativeai"),
                "endpoints": [
                    "GET /health",
                    "POST /member-a/plan",
                    "POST /member-a/chat",
                ],
                "project_root": str(ROOT),
                "database": database,
                "error": error,
            },
        )

    def _handle_plan(self) -> None:
        try:
            payload = self._read_json_body()
            result = run_member_a_json(
                payload,
                db_path=_find_full_db(),
                llm_planner=_build_llm_planner(payload),
            )
            self._send_json(200, result)

        except json.JSONDecodeError as exc:
            self._send_json(400, {"error": f"Invalid JSON payload: {exc}"})
        except FileNotFoundError as exc:
            self._send_json(
                500,
                {
                    "error": str(exc),
                    "hint": "確認 member_c/database/thailand_trip_full.db 是否存在。",
                },
            )
        except Exception as exc:
            self._send_json(500, {"error": str(exc)})

    def _handle_chat(self) -> None:
        """Gemini-powered AI travel chatbot endpoint.

        Expected payload:
        {
          "message": "第 2 天下雨怎麼辦？",
          "history": [{"role": "user", "content": "..."}],
          "current_itinerary": {... optional ...}
        }
        """
        try:
            payload = self._read_json_body()
            user_message = str(payload.get("message", "")).strip()
            history = payload.get("history", [])
            current_itinerary = payload.get("current_itinerary", None)

            if not user_message:
                self._send_json(400, {"error": "message is required"})
                return

            client = GeminiClient()
            prompt = _build_chat_prompt(
                user_message=user_message,
                history=history,
                current_itinerary=current_itinerary,
            )
            reply = client.generate_text(prompt)

            self._send_json(
                200,
                {
                    "reply": reply,
                    "provider": "gemini",
                },
            )

        except json.JSONDecodeError as exc:
            self._send_json(400, {"error": f"Invalid JSON payload: {exc}"})
        except Exception as exc:
            self._send_json(500, {"error": str(exc)})

    def _read_json_body(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        raw_body = self.rfile.read(length).decode("utf-8") if length else "{}"
        payload = json.loads(raw_body)
        if not isinstance(payload, dict):
            raise ValueError("JSON payload must be an object.")
        return payload

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
    print("AI 聊天 API：http://127.0.0.1:8765/member-a/chat")
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


def _build_chat_prompt(
    *,
    user_message: str,
    history: Any,
    current_itinerary: Any,
) -> str:
    safe_history = history if isinstance(history, list) else []

    return f"""
你是「泰國 AI 旅遊助手」，負責協助使用者規劃與調整泰國旅遊行程。

請遵守：
1. 一律使用繁體中文回答。
2. 回答要具體、可執行，不要只給空泛建議。
3. 若使用者問旅遊推薦，請依照城市、預算、天數、偏好給建議。
4. 若使用者提到突發狀況，例如班機延誤、下雨、太累、景點關閉，請說明應如何調整行程。
5. 若資訊不足，請列出你需要的欄位，但仍先給一個合理方向。
6. 不要編造精確營業時間、票價或交通費；若不確定，請標示「需再次確認」。
7. 若問題適合重新排行程，請在回答最後加上「建議重新產生或重排行程」。
8. 若使用者要求「詳細介紹」、「逐一介紹」、「推薦美食」、「附近美食」、「分析」或「交通建議」，請完整回答，不要只寫開場句。
9. 回覆景點時可依「特色、建議停留方式、注意事項、附近順遊或用餐」分段。
10. 若回答多天行程，至少涵蓋每一天；若內容太長，請優先保留每一天的重點，不要只回答第一天。

目前行程資料，可為空：
{json.dumps(current_itinerary, ensure_ascii=False, indent=2)}

對話紀錄：
{json.dumps(safe_history[-10:], ensure_ascii=False, indent=2)}

使用者最新問題：
{user_message}
""".strip()


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


def _module_available(module_name: str) -> bool:
    try:
        __import__(module_name)
        return True
    except ImportError:
        return False


if __name__ == "__main__":
    main()
