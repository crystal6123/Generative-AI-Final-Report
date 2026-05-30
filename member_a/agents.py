"""Agent node implementations for the member A workflow."""

from __future__ import annotations

from collections import Counter
from itertools import cycle

from .currency import request_budget_to_money, thb_to_money
from .data_gateway import TravelDataGateway
from .models import (
    BudgetReport,
    CorrectionMarker,
    DayPlan,
    ItineraryDraft,
    ItineraryItem,
    ReviewIssue,
    ReviewReport,
    TravelRequest,
    WorkflowState,
)


def _item(day: int, start_time: str, record_id: str, gateway: TravelDataGateway) -> ItineraryItem:
    record = gateway.by_id(record_id)
    return ItineraryItem(
        day=day,
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
        note=f"Source: {record.source_name}; updated {record.updated_at}",
    )


class TourGuideAgent:
    def __init__(self, gateway: TravelDataGateway, llm_planner=None):
        self.gateway = gateway
        self.llm_planner = llm_planner

    def generate(self, state: WorkflowState) -> ItineraryDraft:
        request = state.request
        if self.llm_planner is not None:
            try:
                return self.llm_planner.generate(state, self.gateway)
            except Exception as exc:
                fallback = self._search_based_plan(state) if getattr(self.gateway, "prefers_search_results", False) else None
                if fallback is not None:
                    fallback.notes.append(_gemini_fallback_note(exc))
                    return fallback
                raise
        if getattr(self.gateway, "prefers_search_results", False):
            return self._search_based_plan(state)
        if (
            state.request.days == 5
            and "Bangkok" in request.cities
            and "Ayutthaya" in request.cities
        ):
            return self._bangkok_ayutthaya_five_day_plan(state)
        if len(request.cities) > 1:
            return self._default_multi_city_plan(state)
        if _has_preference(request, "nightlife", "market"):
            return self._nightlife_market_plan(state)
        if _has_preference(request, "history", "culture", "religion"):
            return self._culture_plan(state)
        if _has_preference(request, "artsy", "instagram", "cafe"):
            return self._artsy_plan(state)
        return self._default_multi_city_plan(state)

    def _search_based_plan(self, state: WorkflowState) -> ItineraryDraft:
        request = state.request
        records = self.gateway.search(cities=request.cities, tags=request.preferences)
        records = _filter_records_for_request(_rank_records_for_request(records, request), request)
        target_items = _target_item_count(request)
        if len(records) < target_items:
            supplemental = _filter_records_for_request(
                _rank_records_for_request(self.gateway.search(cities=request.cities, tags=()), request),
                request,
            )
            records = _merge_records(records, supplemental)
        if not records:
            return self._default_multi_city_plan(state)

        used_ids: set[str] = set()
        record_cycle = cycle(records)
        days: list[DayPlan] = []
        cities = request.cities or ("Bangkok",)
        for day_number in range(1, request.days + 1):
            city = _city_for_day(cities, day_number, request.days)
            day_items: list[ItineraryItem] = []
            for period in _periods_for_day(day_number, request):
                record = _next_record(record_cycle, used_ids, city, records)
                if record is None:
                    continue
                start_time = _next_start_time(day_items, period, self.gateway, record, request, day_number)
                day_items.append(
                    ItineraryItem(
                        day=day_number,
                        start_time=start_time,
                        title=record.content,
                        city=record.city or city,
                        data_id=record.record_id,
                        category=record.category,
                        cost_thb=record.cost_thb,
                        cost_note=record.cost_note,
                        area_id=record.area_id,
                        duration_min=record.duration_min,
                        tags=record.tags,
                        note=_record_reason(record, period, request),
                    )
                )
                used_ids.add(record.record_id)
            days.append(DayPlan(day=day_number, city=city, items=day_items))

        return ItineraryDraft(days=days, notes=_sqlite_plan_notes(request))

    def _nightlife_market_plan(self, state: WorkflowState) -> ItineraryDraft:
        use_budget_version = CorrectionMarker.BUDGET_DOWNSHIFT in state.markers
        day_1_ids = ["H005", "H006"] if use_budget_version else ["D001", "H006"]
        day_1 = DayPlan(
            day=1,
            city="Bangkok",
            items=[_item(1, "18:00", record_id, self.gateway) for record_id in day_1_ids],
        )
        notes = ["Applied lower-budget nightlife choices."] if use_budget_version else []
        return ItineraryDraft(days=[day_1], notes=notes)

    def _culture_plan(self, state: WorkflowState) -> ItineraryDraft:
        fixed_time = CorrectionMarker.TIME_CONFLICT in state.markers
        palace_time = "09:00" if fixed_time else "16:00"
        day_1 = DayPlan(
            day=1,
            city="Bangkok",
            items=[
                _item(1, palace_time, "A001", self.gateway),
                _item(1, "11:00", "A002", self.gateway),
                _item(1, "14:00", "A003", self.gateway),
            ],
        )
        notes = ["Moved Grand Palace to the morning after schedule review."] if fixed_time else []
        return ItineraryDraft(days=[day_1], notes=notes)

    def _artsy_plan(self, state: WorkflowState) -> ItineraryDraft:
        diversify = CorrectionMarker.IMPROVE_DIVERSITY in state.markers
        record_ids = (
            ["B002", "B003", "B004", "PENDING-13-001", "A003"]
            if diversify
            else ["B002", "B003", "B004"]
        )
        day_1 = DayPlan(
            day=1,
            city="Bangkok",
            items=[_item(1, f"{10 + index}:00", record_id, self.gateway) for index, record_id in enumerate(record_ids)],
        )
        notes = ["Added pending category 13 activity experience for diversity."] if diversify else []
        return ItineraryDraft(days=[day_1], notes=notes)

    def _bangkok_ayutthaya_five_day_plan(self, state: WorkflowState) -> ItineraryDraft:
        days = [
            DayPlan(
                day=1,
                city="Bangkok",
                items=[
                    _item(1, "16:00", "A002", self.gateway),
                    _item(1, "19:00", "D005", self.gateway),
                ],
            ),
            DayPlan(
                day=2,
                city="Bangkok",
                items=[
                    _item(2, "09:00", "A001", self.gateway),
                    _item(2, "14:00", "H001", self.gateway),
                    _item(2, "18:00", "H002", self.gateway),
                ],
            ),
            DayPlan(
                day=3,
                city="Ayutthaya",
                items=[
                    _item(3, "08:00", "D004", self.gateway),
                    _item(3, "10:00", "A005", self.gateway),
                    _item(3, "11:30", "A006", self.gateway),
                    _item(3, "15:00", "A007", self.gateway),
                ],
            ),
            DayPlan(
                day=4,
                city="Bangkok",
                items=[
                    _item(4, "10:00", "A008", self.gateway),
                    _item(4, "14:00", "B002", self.gateway),
                    _item(4, "20:00", "PENDING-13-003", self.gateway),
                ],
            ),
            DayPlan(
                day=5,
                city="Bangkok",
                items=[
                    _item(5, "10:00", "A009", self.gateway),
                    _item(5, "13:00", "D006", self.gateway),
                ],
            ),
        ]
        return ItineraryDraft(
            days=days,
            notes=["Generated from docs/泰國5天4夜行程草案.md with Ayutthaya and rooftop bar retained."],
        )

    def _default_multi_city_plan(self, state: WorkflowState) -> ItineraryDraft:
        days: list[DayPlan] = []
        cities = state.request.cities or ("Bangkok",)
        for day_number, city in enumerate(cities[: state.request.days], start=1):
            record_id = "A101" if city == "Chiang Mai" else "A001"
            days.append(
                DayPlan(
                    day=day_number,
                    city=city,
                    items=[_item(day_number, "09:00", record_id, self.gateway)],
                )
            )
        return ItineraryDraft(days=days, notes=["Generated multi-city skeleton plan."])


class BudgetAgent:
    def calculate(self, state: WorkflowState) -> BudgetReport:
        if state.draft is None:
            raise ValueError("BudgetAgent requires an itinerary draft.")

        reasons: list[str] = []
        total_thb = 0.0
        estimated_items: list[str] = []
        free_items: list[str] = []

        for item in state.draft.items:
            cost, cost_note = _cost_for_budget(item)
            if item.cost_thb <= 0 and cost > 0:
                item.cost_thb = cost
                item.cost_note = cost_note
                estimated_items.append(f"{item.title} [{item.data_id}] {cost:g} THB")
            elif cost <= 0:
                free_items.append(f"{item.title} [{item.data_id}]")
            total_thb += cost

        total_thb *= max(1, state.request.people)
        total = thb_to_money(total_thb)
        budget = request_budget_to_money(state.request.budget_amount, state.request.budget_currency)
        over_budget = budget is not None and total.thb > budget.thb

        if estimated_items:
            reasons.append("部分資料庫項目缺少明確費用，已用類別 fallback 合理估價：" + "; ".join(estimated_items))
        if state.draft.items and total.thb == 0 and free_items:
            reasons.append("所有已選項目皆判定為免費或無需門票，因此總費用為 0。")
        if over_budget:
            reasons.append(f"Total cost {total.thb} THB exceeds budget {budget.thb} THB.")
        return BudgetReport(total=total, budget=budget, over_budget=over_budget, reasons=reasons)


class ReviewerAgent:
    def __init__(self, gateway: TravelDataGateway):
        self.gateway = gateway

    def review(self, state: WorkflowState) -> ReviewReport:
        if state.draft is None or state.budget_report is None:
            raise ValueError("ReviewerAgent requires draft and budget report.")

        issues: list[ReviewIssue] = []
        if state.budget_report.over_budget:
            issues.append(
                ReviewIssue(
                    code="OVER_BUDGET",
                    severity="high",
                    message="TotalCost > Budget; lower the budget tier.",
                    marker=CorrectionMarker.BUDGET_DOWNSHIFT,
                )
            )

        if state.draft.items and state.budget_report.total.thb <= 0 and not _all_items_explicitly_free(state.draft.items):
            issues.append(
                ReviewIssue(
                    code="MISSING_COST",
                    severity="high",
                    message="Itinerary has items but total cost is 0; add cost estimation or mark all items as explicitly free.",
                    marker=CorrectionMarker.MISSING_DATA,
                )
            )

        issues.extend(self._schedule_issues(state))
        issues.extend(self._diversity_issues(state))
        return ReviewReport(passed=not issues, issues=issues)

    def _schedule_issues(self, state: WorkflowState) -> list[ReviewIssue]:
        issues: list[ReviewIssue] = []
        for item in state.draft.items if state.draft else []:
            record = self.gateway.get_schedule_record(item.title)
            if record and record.closes_at and item.start_time > record.closes_at:
                issues.append(
                    ReviewIssue(
                        code="TIME_CONFLICT",
                        severity="high",
                        message=f"{item.title} is scheduled at {item.start_time}, after closing time {record.closes_at}.",
                        marker=CorrectionMarker.TIME_CONFLICT,
                    )
                )
        return issues

    def _diversity_issues(self, state: WorkflowState) -> list[ReviewIssue]:
        if state.draft is None:
            return []
        category_counts = Counter(item.category for item in state.draft.items)
        cafe_count = sum(1 for item in state.draft.items if "cafe" in item.tags)
        if cafe_count >= 3 and category_counts["activity"] == 0:
            return [
                ReviewIssue(
                    code="LOW_DIVERSITY",
                    severity="medium",
                    message="Too many similar cafe/photo spots; add a category 13 activity experience.",
                    marker=CorrectionMarker.IMPROVE_DIVERSITY,
                )
            ]
        return []


def _cost_for_budget(item: ItineraryItem) -> tuple[float, str]:
    """Return a usable per-person THB cost for budget calculation.

    SQLite records sometimes contain 0 because the exact fee is missing, not because
    the item is truly free. This helper keeps explicitly-free items at 0, but assigns
    a conservative fallback estimate for missing prices so the UI will not show an
    unrealistic total_cost = 0.
    """
    raw_cost = float(item.cost_thb or 0)
    if raw_cost > 0:
        return raw_cost, item.cost_note

    if _is_explicitly_free(item):
        if item.cost_note:
            return 0.0, item.cost_note
        return 0.0, "此項目判定為免費或無需門票。"

    fallback = _fallback_cost_thb(item)
    if fallback <= 0:
        return 0.0, item.cost_note or "此項目目前判定為免費或無需門票。"

    return fallback, (
        item.cost_note
        or f"資料庫尚無明確費用，系統依 {item.category} 類別自動估算為 {fallback:g} THB / 人。"
    )


def _fallback_cost_thb(item: ItineraryItem) -> float:
    category = (item.category or "").lower()
    tags = {tag.lower() for tag in item.tags}
    title = item.title.lower()

    if category == "food":
        if "fine_dining" in tags or "luxury" in tags:
            return 1500.0
        if {"street_food", "local_food", "night_market"}.intersection(tags):
            return 200.0
        return 300.0
    if category == "market":
        # 市集通常不用門票，但旅遊預算應估餐飲/購物支出。
        return 300.0
    if category == "activity":
        if "spa" in tags or "massage" in tags or "relax_spa" in tags:
            return 800.0
        if "workshop" in tags or "class" in tags:
            return 1200.0
        return 600.0
    if category == "transport":
        return 250.0
    if category == "cost":
        return 300.0
    if category == "attraction":
        if any(keyword in title for keyword in ("mall", "market", "park", "bacc")):
            return 0.0
        return 200.0
    return 200.0


def _is_explicitly_free(item: ItineraryItem) -> bool:
    note = (item.cost_note or "").lower()
    title = (item.title or "").lower()
    free_keywords = (
        "免費",
        "不收門票",
        "無需門票",
        "免門票",
        "free",
        "free entry",
        "no admission",
    )
    missing_keywords = (
        "尚無",
        "未在",
        "需人工確認",
        "需依",
        "另計",
        "資料庫",
        "missing",
        "unknown",
    )
    if any(keyword in note for keyword in missing_keywords):
        return False
    if any(keyword in note for keyword in free_keywords):
        return True
    if item.category == "attraction" and any(keyword in title for keyword in ("park", "mall", "bacc")):
        return True
    return False


def _all_items_explicitly_free(items: list[ItineraryItem]) -> bool:
    return bool(items) and all(float(item.cost_thb or 0) <= 0 and _is_explicitly_free(item) for item in items)


def _has_preference(request: TravelRequest, *keywords: str) -> bool:
    prefs = {pref.lower() for pref in request.preferences}
    return bool(prefs.intersection(keywords))


def _city_for_day(cities: tuple[str, ...], day_number: int, total_days: int) -> str:
    if len(cities) == 1:
        return cities[0]
    if day_number == total_days:
        return cities[-1]
    index = min(day_number - 1, len(cities) - 1)
    return cities[index]


def _periods_for_day(day_number: int, request: TravelRequest) -> tuple[str, ...]:
    periods = ("morning", "afternoon", "evening")
    if day_number == request.days and _effective_end_time(request, day_number) <= "17:00":
        periods = periods[:2]
    return tuple(
        period
        for period in periods
        if not _slot_is_unavailable(request, day_number, period)
    )


def _slot_is_unavailable(request: TravelRequest, day_number: int, period: str) -> bool:
    tokens = {slot.lower().strip() for slot in request.unavailable_slots}
    day_tokens = {
        period,
        f"day{day_number}_{period}",
        f"day_{day_number}_{period}",
        f"d{day_number}_{period}",
        f"{day_number}_{period}",
    }
    return bool(tokens.intersection(day_tokens))


def _next_record(
    record_cycle,
    used_ids: set[str],
    city: str,
    records,
):
    fallback = None
    for _ in range(len(records)):
        record = next(record_cycle)
        if record.record_id in used_ids:
            continue
        if fallback is None:
            fallback = record
        if record.city == city:
            return record
    return fallback


def _rank_records_for_request(records, request: TravelRequest):
    prefs = set(request.preferences)

    def score(record) -> tuple[int, float, str]:
        value = 0
        if prefs.intersection(record.tags):
            value -= 20
        if "culture" in prefs and record.record_id == "A001":
            value -= 30
        if {"street_food", "night_market", "local_food"}.intersection(prefs):
            if record.category == "market":
                value -= 14
            if record.category == "food":
                value -= 12
            if record.category == "activity":
                value -= 4
        if "rainy_day_backup" in prefs and {"shopping_mall", "museum", "cafe_dessert", "relax_spa"}.intersection(record.tags):
            value -= 10
        if "family_friendly" in prefs and {"family_friendly", "親子友善"}.intersection(record.tags):
            value -= 10
        if "low_budget" in prefs and record.cost_thb > 500:
            value += 10
        return (value, record.cost_thb, record.record_id)

    return sorted(records, key=score)


def _filter_records_for_request(records, request: TravelRequest):
    prefs = set(request.preferences)
    if {"street_food", "night_market", "local_food"}.intersection(prefs) and not {"luxury_budget", "fine_dining"}.intersection(prefs):
        records = [
            record
            for record in records
            if not (record.category == "food" and (record.cost_thb > 1000 or "fine_dining" in record.tags))
        ]
    if "low_budget" in prefs:
        affordable = [record for record in records if record.cost_thb <= 500]
        if affordable:
            records = affordable
    return list(records)


def _merge_records(primary, supplemental):
    by_id = {record.record_id: record for record in primary}
    for record in supplemental:
        by_id.setdefault(record.record_id, record)
    return list(by_id.values())


def _target_item_count(request: TravelRequest) -> int:
    if request.days <= 0:
        return 0
    total = 0
    for day_number in range(1, request.days + 1):
        total += len(_periods_for_day(day_number, request))
    return max(1, total)


def _next_start_time(
    day_items: list[ItineraryItem],
    period: str,
    gateway: TravelDataGateway,
    next_record,
    request: TravelRequest | None = None,
    day_number: int = 1,
) -> str:
    anchors = _time_anchors(request, day_number)
    if not day_items:
        fallback_start = _parse_time(_effective_start_time(request, day_number)) if request else 9 * 60
        return _format_time(_round_to_nice_minutes(anchors.get(period, fallback_start)))
    previous = day_items[-1]
    previous_end = _parse_time(previous.start_time) + previous.duration_min + _travel_buffer_min(
        previous,
        period,
        gateway,
        next_record.area_id,
    )
    start = max(previous_end, anchors.get(period, previous_end))
    if request is not None:
        start = min(start, _parse_time(_effective_end_time(request, day_number)) + request.time_flex_minutes)
    return _format_time(_round_to_nice_minutes(start))


def _travel_buffer_min(
    previous: ItineraryItem,
    next_period: str,
    gateway: TravelDataGateway,
    next_area_id: str,
) -> int:
    if hasattr(gateway, "travel_time_minutes"):
        travel_time = gateway.travel_time_minutes(previous.area_id, next_area_id)
        if travel_time is not None:
            return travel_time + 15
    if next_period == "afternoon":
        return 30
    if next_period == "evening":
        return 45
    if previous.category in {"market", "activity"}:
        return 45
    return 30


def _parse_time(value: str) -> int:
    hour, minute = value.split(":", 1)
    return int(hour) * 60 + int(minute)


def _format_time(total_minutes: int) -> str:
    hour = total_minutes // 60
    minute = total_minutes % 60
    return f"{hour:02d}:{minute:02d}"


def _round_to_nice_minutes(total_minutes: int) -> int:
    return int(round(total_minutes / 30) * 30)


def _time_anchors(request: TravelRequest | None, day_number: int = 1) -> dict[str, int]:
    if request is None:
        return {
            "morning": 9 * 60,
            "afternoon": 12 * 60 + 30,
            "evening": 18 * 60,
        }
    start = _parse_time(_effective_start_time(request, day_number))
    end = _parse_time(_effective_end_time(request, day_number))
    span = max(1, end - start)
    return {
        "morning": start,
        "afternoon": start + int(span * 0.4),
        "evening": start + int(span * 0.75),
    }


def _effective_start_time(request: TravelRequest, day_number: int) -> str:
    if day_number == request.days and request.last_day_start_time:
        return request.last_day_start_time
    return request.daily_start_time


def _effective_end_time(request: TravelRequest, day_number: int) -> str:
    if day_number == request.days:
        return request.last_day_end_time or "17:00"
    return request.daily_end_time


def _sqlite_plan_notes(request: TravelRequest) -> list[str]:
    notes = ["此行程由成員 C 的 SQLite 資料庫候選資料產生。"]
    if request.unavailable_slots:
        notes.append(f"已避開使用者不想安排的時段：{', '.join(request.unavailable_slots)}。")
    return notes


def _record_reason(record, period: str, request: TravelRequest) -> str:
    period_labels = {
        "morning": "上午",
        "afternoon": "下午",
        "evening": "晚上",
    }
    category_labels = {
        "attraction": "景點",
        "food": "餐飲",
        "market": "市集/商圈",
        "activity": "活動體驗",
        "cost": "費用項目",
        "transport": "交通",
    }
    matched_preferences = [
        preference
        for preference in request.preferences
        if preference.lower() in {tag.lower() for tag in record.tags}
    ]
    category = category_labels.get(record.category, record.category)
    period_label = period_labels.get(period, period)
    if matched_preferences:
        preference_text = "、".join(matched_preferences)
        return f"安排在{period_label}，預估停留 {record.duration_min} 分鐘，因為這個{category}符合使用者偏好：{preference_text}。"
    if record.cost_thb == 0:
        return f"安排在{period_label}，預估停留 {record.duration_min} 分鐘，作為低成本的{category}選項，能控制整體預算。"
    return f"安排在{period_label}，預估停留 {record.duration_min} 分鐘，作為本日{category}重點，讓行程節奏更完整。"


def _gemini_fallback_note(exc: Exception) -> str:
    return "Gemini 暫時無法產生有效行程，已改用 SQLite 規則版排程。"
