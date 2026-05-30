"""Validate member A itinerary quality across preference_master entries."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

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
    load_env_file(ROOT / ".env")
    db_path = _find_full_db()
    gateway = SQLiteTravelDataGateway(db_path)
    preferences = gateway.preference_names()

    sqlite_cases = [
        _run_case(preference, db_path=db_path, llm_planner=None, mode="sqlite")
        for preference in preferences
    ]
    llm_cases = [
        _run_case(
            preference,
            db_path=db_path,
            llm_planner=GeminiItineraryPlanner(LocalLLMClient()),
            mode="local_llm",
        )
        for preference in REPRESENTATIVE_LLM_PREFERENCES
        if preference in preferences
    ]

    report = _render_report(sqlite_cases, llm_cases)
    report_path = ROOT / "docs" / "成員A_preferences驗證報告.md"
    report_path.write_text(report, encoding="utf-8")
    print(f"報告已產生：{report_path}")
    print(_summary_line("SQLite/API", sqlite_cases))
    print(_summary_line("Local LLM", llm_cases))


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
        "use_llm": llm_planner is not None,
    }
    try:
        result = run_member_a_json(payload, db_path=db_path, llm_planner=llm_planner)
        issues = _quality_issues(result, preference)
        status = "PASS" if not issues else "WARN"
        total_cost_twd = result["total_cost"]["twd"] if result.get("total_cost") else None
        item_count = sum(len(day["items"]) for day in result["itinerary"])
        return ValidationCase(preference, mode, status, issues, total_cost_twd, item_count)
    except Exception as exc:
        return ValidationCase(preference, mode, "FAIL", [str(exc)], None, 0)


def _quality_issues(result: dict, preference: str) -> list[str]:
    issues: list[str] = []
    itinerary = result.get("itinerary", [])
    if len(itinerary) != 3:
        issues.append(f"expected 3 days, got {len(itinerary)}")
    empty_days = [day["day"] for day in itinerary if not day.get("items")]
    if empty_days:
        issues.append(f"empty days: {empty_days}")
    for day in itinerary:
        max_items = 2 if day["day"] == 3 else 3
        if len(day.get("items", [])) > max_items:
            issues.append(f"day {day['day']} has too many items: {len(day['items'])}")
        times = [item["start_time"] for item in day.get("items", [])]
        if times != sorted(times):
            issues.append(f"day {day['day']} times are not sorted")
        for item in day.get("items", []):
            if item.get("duration_min", 0) <= 0:
                issues.append(f"{item.get('data_id')} missing duration")
            if "cost_note" not in item:
                issues.append(f"{item.get('data_id')} missing cost_note")
    if preference in {"night_market", "evening_activity"} and not _has_evening_item(itinerary):
        issues.append("night/evening preference has no item after 18:00")
    if preference in {"street_food", "local_food", "night_market"}:
        expensive_food = [
            item["data_id"]
            for day in itinerary
            for item in day.get("items", [])
            if item.get("category") == "food" and item.get("cost_thb", 0) > 1000
        ]
        if expensive_food:
            issues.append(f"street/local food preference includes expensive food: {expensive_food}")
    return issues


def _has_evening_item(itinerary: list[dict]) -> bool:
    for day in itinerary:
        for item in day.get("items", []):
            hour = int(str(item.get("start_time", "00:00")).split(":", 1)[0])
            if hour >= 18:
                return True
    return False


def _budget_for(preference: str) -> int:
    if preference == "luxury_budget":
        return 120000
    if preference in {"low_budget", "street_food", "night_market"}:
        return 15000
    return 30000


def _render_report(sqlite_cases: list[ValidationCase], llm_cases: list[ValidationCase]) -> str:
    lines = [
        "# 成員A preferences 驗證報告",
        "",
        "## Summary",
        "",
        f"- {_summary_line('SQLite/API', sqlite_cases)}",
        f"- {_summary_line('Local LLM', llm_cases)}",
        "",
        "## SQLite/API 全量驗證",
        "",
        "| Preference | Status | Items | Total TWD | Issues |",
        "|---|---:|---:|---:|---|",
    ]
    lines.extend(_case_rows(sqlite_cases))
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
    counts = {status: sum(1 for case in cases if case.status == status) for status in ("PASS", "WARN", "FAIL")}
    return f"{label}: PASS {counts['PASS']} / WARN {counts['WARN']} / FAIL {counts['FAIL']}"


def _find_full_db() -> Path:
    candidates = sorted(ROOT.glob("**/thailand_trip_full.db"))
    if not candidates:
        raise FileNotFoundError("Cannot find thailand_trip_full.db under the project folder.")
    return candidates[0]


if __name__ == "__main__":
    main()
