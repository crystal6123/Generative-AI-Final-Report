"""Run member A with SQLite data and a local Ollama model."""

from __future__ import annotations

from pathlib import Path
import os
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from member_a.gemini_client import load_env_file
from member_a.models import TravelRequest
from member_a.sqlite_data_gateway import SQLiteTravelDataGateway
from member_a.time_block_formatter import format_day_time_blocks
from member_a.workflow import run_workflow


def main() -> None:
    load_env_file(ROOT / ".env")
    db_path = _find_full_db()
    gateway = SQLiteTravelDataGateway(db_path)
    request = TravelRequest(
        days=3,
        nights=2,
        people=2,
        budget_amount=20000,
        budget_currency="TWD",
        cities=("Bangkok",),
        preferences=("night_market", "street_food", "local_food"),
        unavailable_slots=(),
        daily_start_time="10:00",
        daily_end_time="22:00",
        time_flex_minutes=30,
        last_day_start_time="10:00",
        last_day_end_time="17:00",
    )

    result = run_workflow(request, gateway=gateway)
    print("=== 成員 A SQLite 規則版模擬（LLM 關閉） ===")
    print(f"資料庫：{db_path}")
    print("模型：LLM disabled")
    print(f"是否通過審查：{'通過' if result.accepted else '未通過'}")
    print(f"已使用修正輪數：{result.state.correction_round}")

    if result.state.budget_report:
        report = result.state.budget_report
        print(f"預估總花費：{report.total.thb} THB / {report.total.twd} TWD")
        if report.budget:
            print(f"使用者預算：{report.budget.thb} THB / {report.budget.twd} TWD")

    if result.state.draft:
        print("行程：")
        for day in result.state.draft.days:
            print(f"  第 {day.day} 天 - {day.city}")
            print("    行程時間：")
            for block in format_day_time_blocks(day, result.state.request):
                print(f"      {block}")
            print("    行程明細：")
            for item in day.items:
                print(
                    f"      [{item.data_id}] {item.title}"
                )
                print(f"        預估停留：{item.duration_min} 分鐘")
                print(f"        預估費用：{item.cost_thb} THB")
                if item.note:
                    print(f"        理由：{item.note}")
                if item.cost_note:
                    print(f"        費用說明：{item.cost_note}")
        if result.state.draft.notes:
            print("備註：")
            for note in result.state.draft.notes:
                print(f"  - {note}")

    print("Agent 執行紀錄：")
    for entry in result.state.history:
        print(f"  - {entry}")


def _find_full_db() -> Path:
    candidates = sorted(ROOT.glob("**/thailand_trip_full.db"))
    if not candidates:
        raise FileNotFoundError("Cannot find thailand_trip_full.db under the project folder.")
    return candidates[0]


if __name__ == "__main__":
    main()
