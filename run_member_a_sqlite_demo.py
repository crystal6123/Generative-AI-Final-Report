"""Run member A's three-agent workflow with member C's SQLite database."""

from __future__ import annotations

from pathlib import Path
import sys


def _project_root() -> Path:
    """Return the project root that contains member_a/.

    These scripts may be executed from the project root, from a scripts folder,
    or copied temporarily elsewhere during testing.
    """
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


from member_a.models import TravelRequest
from member_a.sqlite_data_gateway import SQLiteTravelDataGateway
from member_a.time_block_formatter import format_day_time_blocks
from member_a.workflow import run_workflow


def _sample_request() -> TravelRequest:
    return TravelRequest(
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
        time_flex_minutes=30,
        last_day_start_time="10:00",
        last_day_end_time="17:00",
    )


def main() -> None:
    db_path = _find_full_db()
    gateway = SQLiteTravelDataGateway(db_path)
    request = _sample_request()
    result = run_workflow(request, gateway=gateway)

    print("=== 成員 A SQLite 資料庫模擬 ===")
    print(f"專案根目錄：{ROOT}")
    print(f"資料庫：{db_path}")
    _print_result(result, show_time_blocks=True)


def _print_result(result, *, show_time_blocks: bool = False) -> None:
    print(f"是否通過審查：{'通過' if result.accepted else '未通過'}")
    print(f"已使用修正輪數：{result.state.correction_round}")

    if result.state.budget_report:
        report = result.state.budget_report
        print(f"預估總花費：{report.total.thb} THB / {report.total.twd} TWD")
        if report.budget:
            print(f"使用者預算：{report.budget.thb} THB / {report.budget.twd} TWD")
        if report.reasons:
            print("預算說明：")
            for reason in report.reasons:
                print(f"  - {reason}")

    if result.state.draft:
        print("行程：")
        for day in result.state.draft.days:
            print(f"  第 {day.day} 天 - {day.city}")
            if show_time_blocks:
                print("    行程時間：")
                for block in format_day_time_blocks(day, result.state.request):
                    print(f"      {block}")
            print("    行程明細：")
            for item in day.items:
                print(f"      {item.start_time} {item.title} [{item.data_id}]")
                print(f"        類型：{item.category}")
                print(f"        預估停留：{item.duration_min} 分鐘")
                print(f"        預估費用：{item.cost_thb} THB")
                if item.cost_note:
                    print(f"        費用說明：{item.cost_note}")
                if item.note:
                    print(f"        理由：{item.note}")
        if result.state.draft.notes:
            print("備註：")
            for note in result.state.draft.notes:
                print(f"  - {note}")

    if result.state.manual_review_required:
        print("需要人工檢查：")
        for issue in result.state.manual_review_required:
            print(f"  - {issue}")

    print("Agent 執行紀錄：")
    for entry in result.state.history:
        print(f"  - {entry}")


if __name__ == "__main__":
    main()
