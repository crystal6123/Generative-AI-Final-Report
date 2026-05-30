"""Run member A's three-agent workflow with member C's SQLite database."""

from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from member_a.models import TravelRequest
from member_a.sqlite_data_gateway import SQLiteTravelDataGateway
from member_a.workflow import run_workflow


def main() -> None:
    db_path = _find_full_db()
    gateway = SQLiteTravelDataGateway(db_path)
    request = TravelRequest(
        days=3,
        nights=2,
        people=2,
        budget_amount=20000,
        budget_currency="TWD",
        cities=("Bangkok",),
        preferences=("culture", "history", "religion"),
        unavailable_slots=(),
        daily_start_time="09:00",
        daily_end_time="21:00",
    )

    result = run_workflow(request, gateway=gateway)
    print("=== 成員 A SQLite 資料庫模擬 ===")
    print(f"資料庫：{db_path}")
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
            for item in day.items:
                print(
                    f"    {item.start_time} {item.title} [{item.data_id}] "
                    f"{item.cost_thb} THB / 停留 {item.duration_min} 分鐘"
                )
                if item.note:
                    print(f"      理由：{item.note}")
                if item.cost_note:
                    print(f"      費用說明：{item.cost_note}")

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
