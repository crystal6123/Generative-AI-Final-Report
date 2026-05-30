"""Validate member A itinerary quality across preference_master entries."""

from __future__ import annotations

from dataclasses import dataclass
import argparse
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


from member_a.api import run_member_a_json
from member_a.gemini_client import load_env_file
from member_a.llm_planner import GeminiItineraryPlanner
from member_a.local_llm_client import LocalLLMClient
from member_a.sqlite_data_gateway import SQLiteTravelDataGateway


REPRESENTATIVE_LLM_PREFERENCES = (
    "culture",
    "night_market",
    "local_food",
    "low_budget",
    "elderly_friendly",
    "rainy_day_backup",
    "adventure",
    "relaxed_pace",
    "family_friendly",
    "evening_activity",
)


@dataclass
class ValidationCase:
    preference: str
    mode: str
    status: str
    issues: list[str]
    total_cost_twd: float | None
    item_count: int


def main() -> None:
    args = _parse_args()
    load_env_file(ROOT / ".env")

    db_path = _find_full_db()
    gateway = SQLiteTravelDataGateway(db_path)
    preferences = gateway.preference_names()

    print(f"專案根目錄：{ROOT}")
    print(f"資料庫：{db_path}")
    print(f"偏好數量：{len(preferences)}")

    sqlite_cases = [
        _run_case(preference, db_path=db_path, llm_planner=None, mode="sqlite")
        for preference in preferences
    ]

    llm_cases: list[ValidationCase] = []
    if args.include_llm:
        llm_planner = GeminiItineraryPlanner(LocalLLMClient())
        llm_cases = [
            _run_case(
                preference,
                db_path=db_path,
                llm_planner=llm_planner,
                mode="local_llm",
            )
            for preference in REPRESENTATIVE_LLM_PREFERENCES
            if preference in preferences
        ]

    report = _render_report(sqlite_cases, llm_cases, include_llm=args.include_llm)
    report_path = ROOT / "docs" / "成員A_preferences驗證報告.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(report, encoding="utf-8")

    print(f"報告已產生：{report_path}")
    print(_summary_line("SQLite/API", sqlite_cases))
    if args.include_llm:
        print(_summary_line("Local LLM", llm_cases))


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--include-llm",
        action="store_true",
        help="Also run representative local LLM validation cases. Default is false for faster deterministic checks.",
    )
    return parser.parse_args()


def _run_case(preference: str, *, db_path: Path, llm_planner, mode: str) -> ValidationCase:
    payload = {
        "days": 3,
        "nights": 2,
        "people": 2,
        "budget_amount": _budget_for(preference),
        "budget_currency": "TWD",
        "cities": ["Bangkok"],
        "preferences": [preference],
        "user_text": "",
        "daily_start_time": "09:00",
        "daily_end_time": "21:00",
        "last_day_start_time": "10:00",
        "last_day_end_time": "17:00",
        "use_llm": llm_planner is not None,
    }

    try:
        result = run_member_a_json(payload, db_path=db_path, llm_planner=llm_planner)
        issues = _quality_issues(result, preference)
        status = "PASS" if not issues else "WARN"
        total_cost_twd = result["total_cost"]["twd"] if result.get("total_cost") else None
        item_count = sum(len(day.get("items", [])) for day in result.get("itinerary", []))
        return ValidationCase(preference, mode, status, issues, total_cost_twd, item_count)
    except Exception as exc:
        return ValidationCase(preference, mode, "FAIL", [str(exc)], None, 0)


def _quality_issues(result: dict, preference: str) -> list[str]:
    issues: list[str] = []
    itinerary = result.get("itinerary", [])

    if not result.get("accepted", False):
        manual = result.get("manual_review_required") or []
        issues.append(f"workflow not accepted: {manual or result.get('state_marker_labels', [])}")

    if len(itinerary) != 3:
        issues.append(f"expected 3 days, got {len(itinerary)}")

    empty_days = [day.get("day") for day in itinerary if not day.get("items")]
    if empty_days:
        issues.append(f"empty days: {empty_days}")

    total_cost = result.get("total_cost") or {}
    if float(total_cost.get("thb") or 0) <= 0 and any(day.get("items") for day in itinerary):
        issues.append("total cost is 0 while itinerary has items")

    for day in itinerary:
        max_items = 2 if day.get("day") == 3 else 3
        items = day.get("items", [])
        if len(items) > max_items:
            issues.append(f"day {day.get('day')} has too many items: {len(items)}")

        times = [str(item.get("start_time", "")) for item in items]
        if times != sorted(times):
            issues.append(f"day {day.get('day')} times are not sorted")

        for item in items:
            data_id = item.get("data_id")
            if item.get("category") == "cost" or str(data_id).startswith("COST_MAP_"):
                issues.append(f"{data_id} is a cost record but appears as itinerary item")
            if item.get("duration_min", 0) <= 0:
                issues.append(f"{data_id} missing duration")
            if "cost_note" not in item:
                issues.append(f"{data_id} missing cost_note")
            if item.get("cost_thb", 0) < 0:
                issues.append(f"{data_id} has negative cost")

    if preference in {"night_market", "evening_activity"} and not _has_evening_item(itinerary):
        issues.append("night/evening preference has no item after 18:00")

    if preference in {"street_food", "local_food", "night_market"}:
        expensive_food = [
            item.get("data_id")
            for day in itinerary
            for item in day.get("items", [])
            if item.get("category") == "food" and float(item.get("cost_thb") or 0) > 1000
        ]
        if expensive_food:
            issues.append(f"street/local food preference includes expensive food: {expensive_food}")

    return issues


def _has_evening_item(itinerary: list[dict]) -> bool:
    for day in itinerary:
        for item in day.get("items", []):
            try:
                hour = int(str(item.get("start_time", "00:00")).split(":", 1)[0])
            except ValueError:
                continue
            if hour >= 18:
                return True
    return False


def _budget_for(preference: str) -> int:
    if preference == "luxury_budget":
        return 120000
    if preference in {"low_budget", "street_food", "night_market"}:
        return 15000
    return 30000


def _render_report(
    sqlite_cases: list[ValidationCase],
    llm_cases: list[ValidationCase],
    *,
    include_llm: bool,
) -> str:
    lines = [
        "# 成員A preferences 驗證報告",
        "",
        f"- Project root: `{ROOT}`",
        f"- Database: `{_find_full_db()}`",
        "",
        "## Summary",
        "",
        f"- {_summary_line('SQLite/API', sqlite_cases)}",
    ]

    if include_llm:
        lines.append(f"- {_summary_line('Local LLM', llm_cases)}")

    lines.extend([
        "",
        "## SQLite/API 全量驗證",
        "",
        "| Preference | Status | Items | Total TWD | Issues |",
        "|---|---:|---:|---:|---|",
    ])
    lines.extend(_case_rows(sqlite_cases))

    if include_llm:
        lines.extend([
            "",
            "## Local LLM 代表偏好驗證",
            "",
            "| Preference | Status | Items | Total TWD | Issues |",
            "|---|---:|---:|---:|---|",
        ])
        lines.extend(_case_rows(llm_cases))

    return "\n".join(lines) + "\n"


def _case_rows(cases: list[ValidationCase]) -> list[str]:
    rows = []
    for case in cases:
        issues = "<br>".join(case.issues) if case.issues else "-"
        total = f"{case.total_cost_twd:.1f}" if case.total_cost_twd is not None else "-"
        rows.append(f"| `{case.preference}` | {case.status} | {case.item_count} | {total} | {issues} |")
    return rows


def _summary_line(label: str, cases: list[ValidationCase]) -> str:
    counts = {
        status: sum(1 for case in cases if case.status == status)
        for status in ("PASS", "WARN", "FAIL")
    }
    return f"{label}: PASS {counts['PASS']} / WARN {counts['WARN']} / FAIL {counts['FAIL']}"


if __name__ == "__main__":
    main()
