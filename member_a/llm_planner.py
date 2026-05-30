"""LLM itinerary planning for member A's Tour Guide Agent."""

from __future__ import annotations

import json
from typing import Protocol

from .models import DataRecord, DayPlan, ItineraryDraft, ItineraryItem, TravelRequest, WorkflowState


class JsonGenerator(Protocol):
    def generate_json(self, *, prompt: str, schema: dict) -> dict:
        ...


class GeminiItineraryPlanner:
    def __init__(self, client: JsonGenerator, *, max_candidates: int = 60):
        self.client = client
        self.max_candidates = max_candidates

    def generate(self, state: WorkflowState, gateway) -> ItineraryDraft:
        records = gateway.search(cities=state.request.cities, tags=state.request.preferences)
        records = _filter_candidates(_rank_candidates(records, state.request), state.request)
        if len(records) < _target_item_count(state.request):
            supplemental = _filter_candidates(
                _rank_candidates(gateway.search(cities=state.request.cities, tags=()), state.request),
                state.request,
            )
            records = _merge_records(records, supplemental)
        candidates = records[: self.max_candidates]
        if not candidates:
            raise ValueError("No SQLite candidate records are available for Gemini planning.")

        payload = self.client.generate_json(
            prompt=self._prompt(state, candidates),
            schema=_itinerary_schema(),
        )
        return self._to_draft(payload, state.request, candidates)

    def _prompt(self, state: WorkflowState, candidates: list[DataRecord]) -> str:
        request = state.request
        candidate_text = json.dumps([_candidate(record) for record in candidates], ensure_ascii=False)
        marker_text = ", ".join(marker.value for marker in state.markers) or "none"
        issue_text = []
        if state.review_report:
            issue_text = [issue.message for issue in state.review_report.issues]
        return f"""
你是成員 A 的導遊 Agent，負責根據使用者需求與資料庫候選資料產生可執行行程。

規則：
1. 只能使用 candidates 裡存在的 data_id，不可以自行發明景點、餐廳或活動。
2. 需要排滿 request.days 天；一般天可排上午、下午、晚上。最後一天依 last_day_start_time / last_day_end_time 決定可安排區間。
3. 避開 request.unavailable_slots，例如 day1_morning 表示第 1 天上午不要排。
4. 優先符合 cities 的順序與 preferences。
5. 若 state_markers 有 budget_downshift，選擇低成本或免費項目。
6. 若 state_markers 有 time_conflict，避免太晚安排寺廟、皇室建築或博物館。
7. 若 state_markers 有 improve_diversity，避免同類型連續過多，加入不同 category。
8. notes 用繁體中文，reason 也用繁體中文。

request:
{json.dumps(_request_payload(request), ensure_ascii=False)}

state_markers: {marker_text}
review_issues:
{json.dumps(issue_text, ensure_ascii=False)}

candidates:
{candidate_text}
"""

    @staticmethod
    def _to_draft(payload: dict, request: TravelRequest, candidates: list[DataRecord]) -> ItineraryDraft:
        records_by_id = {record.record_id: record for record in candidates}
        days: list[DayPlan] = []
        seen_ids: set[str] = set()
        for raw_day in payload.get("days", []):
            day_number = int(raw_day.get("day", 0))
            if day_number < 1 or day_number > request.days:
                continue
            items: list[ItineraryItem] = []
            max_items = _target_count_for_day(request, day_number)
            for raw_item in raw_day.get("items", [])[:max_items]:
                data_id = str(raw_item.get("data_id", "")).strip()
                if not data_id or data_id in seen_ids or data_id not in records_by_id:
                    continue
                record = records_by_id[data_id]
                items.append(
                    ItineraryItem(
                        day=day_number,
                        start_time=str(raw_item.get("start_time", "09:00")),
                        title=record.content,
                        city=record.city,
                        data_id=record.record_id,
                        category=record.category,
                        cost_thb=record.cost_thb,
                        cost_note=record.cost_note,
                        area_id=record.area_id,
                        duration_min=record.duration_min,
                        tags=record.tags,
                        note=str(raw_item.get("reason", "")),
                    )
                )
                seen_ids.add(data_id)
            days.append(DayPlan(day=day_number, city=str(raw_day.get("city", "")), items=items))

        present_days = {day.day for day in days}
        for day_number in range(1, request.days + 1):
            if day_number not in present_days:
                city = request.cities[min(day_number - 1, len(request.cities) - 1)] if request.cities else ""
                days.append(DayPlan(day=day_number, city=city, items=[]))
        days.sort(key=lambda day: day.day)
        if not any(day.items for day in days):
            raise ValueError("Gemini produced no valid itinerary items from the candidate list.")
        _fill_sparse_days(days, request, candidates, seen_ids)
        _reschedule_items(days, request)
        _clamp_times_to_range(days, request)
        for day in days:
            day.items.sort(key=lambda item: item.start_time)
        return ItineraryDraft(days=days, notes=list(payload.get("notes", [])))


def _candidate(record: DataRecord) -> dict:
    return {
        "data_id": record.record_id,
        "title": record.content,
        "city": record.city,
        "category": record.category,
        "cost_thb": record.cost_thb,
        "cost_note": record.cost_note,
        "area_id": record.area_id,
        "duration_min": record.duration_min,
        "tags": list(record.tags[:12]),
    }


def _rank_candidates(records: list[DataRecord], request: TravelRequest) -> list[DataRecord]:
    prefs = set(request.preferences)

    def score(record: DataRecord) -> tuple[int, float, str]:
        value = 0
        if prefs.intersection(record.tags):
            value -= 20
        if "culture" in prefs and record.record_id == "A001":
            value -= 30
        if {"street_food", "night_market", "local_food"}.intersection(prefs):
            if record.category == "market":
                value -= 12
            if record.category == "food":
                value -= 10
            if record.category == "activity":
                value -= 4
            if record.cost_thb >= 1500 and "luxury_budget" not in prefs:
                value += 25
            if "fine_dining" in record.tags and "fine_dining" not in prefs:
                value += 20
        return (value, record.cost_thb, record.record_id)

    return sorted(records, key=score)


def _filter_candidates(records: list[DataRecord], request: TravelRequest) -> list[DataRecord]:
    prefs = set(request.preferences)
    if not {"street_food", "night_market", "local_food"}.intersection(prefs):
        return records
    if {"luxury_budget", "fine_dining"}.intersection(prefs):
        return records

    filtered = [
        record
        for record in records
        if not (
            record.category == "food"
            and (record.cost_thb > 1000 or "fine_dining" in record.tags)
        )
    ]
    return filtered or records


def _request_payload(request: TravelRequest) -> dict:
    return {
        "days": request.days,
        "nights": request.nights,
        "people": request.people,
        "budget_amount": request.budget_amount,
        "budget_currency": request.budget_currency,
        "cities": list(request.cities),
        "preferences": list(request.preferences),
        "must_visit": list(request.must_visit),
        "avoid": list(request.avoid),
        "transport_preference": list(request.transport_preference),
        "unavailable_slots": list(request.unavailable_slots),
        "daily_start_time": request.daily_start_time,
        "daily_end_time": request.daily_end_time,
        "time_flex_minutes": request.time_flex_minutes,
        "last_day_start_time": request.last_day_start_time,
        "last_day_end_time": request.last_day_end_time,
    }


def _itinerary_schema() -> dict:
    item_schema = {
        "type": "object",
        "properties": {
            "start_time": {"type": "string", "description": "HH:MM local start time."},
            "data_id": {"type": "string", "description": "Must be one of the candidate data_id values."},
            "reason": {"type": "string", "description": "Traditional Chinese reason for this choice."},
        },
        "required": ["start_time", "data_id", "reason"],
        "additionalProperties": False,
    }
    return {
        "type": "object",
        "properties": {
            "days": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "day": {"type": "integer"},
                        "city": {"type": "string"},
                        "items": {"type": "array", "items": item_schema},
                    },
                    "required": ["day", "city", "items"],
                    "additionalProperties": False,
                },
            },
            "notes": {
                "type": "array",
                "items": {"type": "string"},
            },
        },
        "required": ["days", "notes"],
        "additionalProperties": False,
    }


def _fill_sparse_days(
    days: list[DayPlan],
    request: TravelRequest,
    candidates: list[DataRecord],
    seen_ids: set[str],
) -> None:
    candidate_iter = iter(candidates)
    for day in days:
        target_count = _target_count_for_day(request, day.day)
        while len(day.items) < target_count:
            record = _next_unused_candidate(candidate_iter, candidates, seen_ids, day.city)
            if record is None:
                break
            start_time = _completion_start_time(day.items, request, day.day)
            period = _period_label(start_time)
            day.items.append(
                ItineraryItem(
                    day=day.day,
                    start_time=start_time,
                    title=record.content,
                    city=record.city,
                    data_id=record.record_id,
                    category=record.category,
                    cost_thb=record.cost_thb,
                    cost_note=record.cost_note,
                    area_id=record.area_id,
                    duration_min=record.duration_min,
                    tags=record.tags,
                    note=f"依使用者偏好加入此{_category_label(record.category)}，安排在{period}讓行程更完整。",
                )
            )
            seen_ids.add(record.record_id)


def _reschedule_items(days: list[DayPlan], request: TravelRequest) -> None:
    for day in days:
        _prioritize_day_items(day, request)
        slots = _day_slots(request, day.items, day.day)
        for item, start_time in zip(day.items, slots, strict=False):
            item.start_time = start_time
            _align_note_period(item)
    _ensure_evening_item(days, request)


def _prioritize_day_items(day: DayPlan, request: TravelRequest) -> None:
    prefs = set(request.preferences)
    if not {"night_market", "street_food", "local_food", "evening_activity"}.intersection(prefs):
        return

    def score(item: ItineraryItem) -> tuple[int, str]:
        if item.category in {"market", "activity"} or {"night_market", "evening_activity"}.intersection(item.tags):
            return (2, item.data_id)
        if item.category == "food":
            return (1, item.data_id)
        return (0, item.data_id)

    day.items.sort(key=score)


def _next_unused_candidate(
    candidate_iter,
    candidates: list[DataRecord],
    seen_ids: set[str],
    city: str,
) -> DataRecord | None:
    for record in candidate_iter:
        if record.record_id not in seen_ids and (not city or record.city == city):
            return record
    for record in candidates:
        if record.record_id not in seen_ids:
            return record
    return None


def _completion_start_time(items: list[ItineraryItem], request: TravelRequest, day_number: int) -> str:
    slots = _time_slots(request, day_number)
    return slots[min(len(items), len(slots) - 1)]


def _period_label(start_time: str) -> str:
    hour = int(start_time.split(":", 1)[0])
    if hour < 12:
        return "上午"
    if hour < 18:
        return "下午"
    return "晚上"


def _ensure_evening_item(days: list[DayPlan], request: TravelRequest) -> None:
    prefs = set(request.preferences)
    if not {"night_market", "evening_activity"}.intersection(prefs):
        return
    if any(_hour(item.start_time) >= 18 for day in days for item in day.items):
        return
    for day in days:
        for item in reversed(day.items):
            if item.category in {"market", "activity", "food"}:
                item.start_time = _end_aligned_start_time(request, item.duration_min, day.day)
                if "晚上" not in item.note and "夜" not in item.note:
                    item.note = f"{item.note}（調整至晚上以符合夜市/晚間活動偏好。）"
                return


def _align_note_period(item: ItineraryItem) -> None:
    period = _period_label(item.start_time)
    for old_period in ("上午", "下午", "晚上"):
        if old_period in item.note and old_period != period:
            item.note = item.note.replace(old_period, period)


def _clamp_times_to_range(days: list[DayPlan], request: TravelRequest) -> None:
    for day in days:
        start = _parse_time(_effective_start_time(request, day.day)) - request.time_flex_minutes
        end = _parse_time(_effective_end_time(request, day.day)) + request.time_flex_minutes
        for item in day.items:
            minutes = _parse_time(item.start_time)
            if minutes < start:
                item.start_time = _effective_start_time(request, day.day)
            elif minutes > end:
                item.start_time = _effective_end_time(request, day.day)


def _hour(start_time: str) -> int:
    return int(start_time.split(":", 1)[0])


def _time_slots(request: TravelRequest, day_number: int) -> tuple[str, str, str, str]:
    start = _parse_time(_effective_start_time(request, day_number))
    end = _parse_time(_effective_end_time(request, day_number))
    span = max(1, end - start)
    return (
        _format_time(_round_to_nice_minutes(start)),
        _format_time(_round_to_nice_minutes(start + int(span * 0.4))),
        _format_time(_round_to_nice_minutes(start + int(span * 0.65))),
        _format_time(_round_to_nice_minutes(start + int(span * 0.8))),
    )


def _day_slots(request: TravelRequest, items: list[ItineraryItem], day_number: int) -> tuple[str, ...]:
    item_count = len(items)
    start = _parse_time(_effective_start_time(request, day_number))
    end = _parse_time(_effective_end_time(request, day_number))
    if item_count <= 1:
        return (_format_time(start),)
    elif item_count == 2:
        return (
            _format_time(start),
            _end_aligned_start_time(request, items[-1].duration_min, day_number),
        )
    else:
        middle = _round_to_nice_minutes(start + int((end - start) * 0.45))
        return (
            _format_time(start),
            _format_time(middle),
            _end_aligned_start_time(request, items[-1].duration_min, day_number),
        )


def _end_aligned_start_time(request: TravelRequest, duration_min: int, day_number: int) -> str:
    start = _parse_time(_effective_start_time(request, day_number))
    end = _parse_time(_effective_end_time(request, day_number))
    latest_start = max(start, end - max(30, duration_min))
    return _format_time(_round_to_nice_minutes(latest_start))


def _parse_time(value: str) -> int:
    hour, minute = value.split(":", 1)
    return int(hour) * 60 + int(minute)


def _format_time(total_minutes: int) -> str:
    hour = total_minutes // 60
    minute = total_minutes % 60
    return f"{hour:02d}:{minute:02d}"


def _round_to_nice_minutes(total_minutes: int) -> int:
    return int(round(total_minutes / 30) * 30)


def _category_label(category: str) -> str:
    return {
        "attraction": "景點",
        "food": "餐飲",
        "market": "市集/商圈",
        "activity": "活動",
    }.get(category, "安排")


def _target_item_count(request: TravelRequest) -> int:
    if request.days <= 0:
        return 0
    return sum(_target_count_for_day(request, day_number) for day_number in range(1, request.days + 1))


def _target_count_for_day(request: TravelRequest, day_number: int) -> int:
    if day_number == request.days and _effective_end_time(request, day_number) <= "17:00":
        return 2
    return 3


def _effective_start_time(request: TravelRequest, day_number: int) -> str:
    if day_number == request.days and request.last_day_start_time:
        return request.last_day_start_time
    return request.daily_start_time


def _effective_end_time(request: TravelRequest, day_number: int) -> str:
    if day_number == request.days:
        return request.last_day_end_time or "17:00"
    return request.daily_end_time


def _merge_records(primary: list[DataRecord], supplemental: list[DataRecord]) -> list[DataRecord]:
    by_id = {record.record_id: record for record in primary}
    for record in supplemental:
        by_id.setdefault(record.record_id, record)
    return list(by_id.values())
