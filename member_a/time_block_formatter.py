"""Strict time-block output formatting for itinerary demos and UI."""

from __future__ import annotations

from .models import DayPlan, ItineraryItem, TravelRequest


def format_day_time_blocks(day: DayPlan, request: TravelRequest) -> list[str]:
    if not day.items:
        return []
    items = sorted(day.items, key=lambda item: item.start_time)
    blocks: list[str] = []
    day_end = _parse_time(_effective_end_time(request, day.day))
    for index, item in enumerate(items):
        start = _round_to_half_hour(_parse_time(item.start_time))
        if index == len(items) - 1:
            end = max(start + 30, _round_to_half_hour(day_end))
        else:
            next_start = _round_to_half_hour(_parse_time(items[index + 1].start_time))
            end = max(start + 30, next_start - 30)
        blocks.append(_item_block(start, end, item, index == len(items) - 1))
        if index < len(items) - 1:
            next_start = _round_to_half_hour(_parse_time(items[index + 1].start_time))
            if next_start > end:
                blocks.append(f"- {_format_time(end)} - {_format_time(next_start)} 交通與移動")
    return blocks


def _item_block(start: int, end: int, item: ItineraryItem, is_last: bool) -> str:
    tail = "，行程結束/返回飯店" if is_last else ""
    label = "活動與用餐" if item.category in {"food", "market", "activity"} else "活動"
    return (
        f"- {_format_time(start)} - {_format_time(end)} "
        f"{item.title} [{item.data_id}]（{label}{tail}）"
    )


def _parse_time(value: str) -> int:
    hour, minute = value.split(":", 1)
    return int(hour) * 60 + int(minute)


def _format_time(total_minutes: int) -> str:
    hour = total_minutes // 60
    minute = total_minutes % 60
    return f"{hour:02d}:{minute:02d}"


def _round_to_half_hour(total_minutes: int) -> int:
    return int(round(total_minutes / 30) * 30)


def _effective_end_time(request: TravelRequest, day_number: int) -> str:
    if day_number == request.days:
        return request.last_day_end_time or "17:00"
    return request.daily_end_time
