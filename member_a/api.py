"""JSON-facing API helpers for member B integration."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .models import TravelRequest, WorkflowResult
from .preference_resolver import normalize_request_preferences
from .sqlite_data_gateway import SQLiteTravelDataGateway
from .workflow import marker_labels, run_workflow


def run_member_a_json(
    payload: dict[str, Any],
    *,
    db_path: str | Path,
    llm_planner=None,
) -> dict[str, Any]:
    gateway = SQLiteTravelDataGateway(db_path)
    request = normalize_request_preferences(
        _request_from_payload(payload),
        gateway=gateway,
        user_text=str(payload.get("user_text", "")),
    )
    result = run_workflow(request, gateway=gateway, llm_planner=llm_planner)
    return workflow_result_to_json(result)


def workflow_result_to_json(result: WorkflowResult) -> dict[str, Any]:
    state = result.state
    budget_report = state.budget_report
    return {
        "accepted": result.accepted,
        "correction_rounds_used": state.correction_round,
        "state_markers": [marker.value for marker in state.markers],
        "state_marker_labels": marker_labels(state.markers),
        "total_cost": _money_to_json(budget_report.total if budget_report else None),
        "budget": _money_to_json(budget_report.budget if budget_report and budget_report.budget else None),
        "住宿費用_THB": budget_report.accommodation_thb if budget_report else 0.0,
        "住宿等級": budget_report.accommodation_level if budget_report else "",
        "住宿每晚_THB": budget_report.accommodation_per_night_thb if budget_report else 0.0,
        "預估總費用_THB": budget_report.total.thb if budget_report else 0.0,
        "itinerary": [
            {
                "day": day.day,
                "city": day.city,
                "items": [
                    {
                        "start_time": item.start_time,
                        "title": item.title,
                        "data_id": item.data_id,
                        "category": item.category,
                        "cost_thb": item.cost_thb,
                        "cost_note": item.cost_note,
                        "duration_min": item.duration_min,
                        "note": item.note,
                    }
                    for item in day.items
                ],
            }
            for day in (state.draft.days if state.draft else [])
        ],
        "notes": list(state.draft.notes if state.draft else []),
        "manual_review_required": list(state.manual_review_required),
        "history": list(state.history),
        "resolved_preferences": list(state.request.preferences),
    }


def _request_from_payload(payload: dict[str, Any]) -> TravelRequest:
    return TravelRequest(
        days=int(payload["days"]),
        nights=int(payload["nights"]),
        people=int(payload.get("people", 1)),
        budget_amount=_optional_float(payload.get("budget_amount")),
        budget_currency=str(payload.get("budget_currency", "TWD")),
        cities=tuple(payload.get("cities") or ("Bangkok",)),
        preferences=tuple(payload.get("preferences") or ()),
        must_visit=tuple(payload.get("must_visit") or ()),
        avoid=tuple(payload.get("avoid") or ()),
        transport_preference=tuple(payload.get("transport_preference") or ()),
        unavailable_slots=tuple(payload.get("unavailable_slots") or ()),
        daily_start_time=str(payload.get("daily_start_time", "09:00")),
        daily_end_time=str(payload.get("daily_end_time", "21:00")),
        time_flex_minutes=int(payload.get("time_flex_minutes", 30)),
        last_day_start_time=payload.get("last_day_start_time"),
        last_day_end_time=payload.get("last_day_end_time"),
        accommodation_level=payload.get("accommodation_level") or None,
    )


def _optional_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    return float(value)


def _money_to_json(value) -> dict[str, float] | None:
    if value is None:
        return None
    return {"thb": value.thb, "twd": value.twd}
