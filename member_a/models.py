"""Shared data models for the member A workflow."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Literal


Currency = Literal["THB", "TWD"]


class CorrectionMarker(str, Enum):
    BUDGET_DOWNSHIFT = "budget_downshift"
    TIME_CONFLICT = "time_conflict"
    IMPROVE_DIVERSITY = "improve_diversity"
    MISSING_DATA = "missing_data"


@dataclass(frozen=True)
class Money:
    thb: float
    twd: float


@dataclass(frozen=True)
class DataRecord:
    record_id: str
    category: str
    content: str
    source_name: str
    url: str
    updated_at: str
    is_structured: bool
    city: str
    area_id: str = ""
    cost_thb: float = 0
    cost_note: str = ""
    opens_at: str | None = None
    closes_at: str | None = None
    duration_min: int = 90
    tags: tuple[str, ...] = ()


@dataclass(frozen=True)
class TravelRequest:
    days: int
    nights: int
    people: int
    budget_amount: float | None
    budget_currency: Currency
    cities: tuple[str, ...]
    preferences: tuple[str, ...]
    must_visit: tuple[str, ...] = ()
    avoid: tuple[str, ...] = ()
    transport_preference: tuple[str, ...] = ()
    unavailable_slots: tuple[str, ...] = ()
    daily_start_time: str = "09:00"
    daily_end_time: str = "21:00"
    time_flex_minutes: int = 30
    last_day_start_time: str | None = None
    last_day_end_time: str | None = None
    # "low" | "medium" | "comfort" | "luxury" | None (auto-derive from budget)
    accommodation_level: str | None = None


@dataclass
class ItineraryItem:
    day: int
    start_time: str
    title: str
    city: str
    data_id: str
    category: str
    cost_thb: float
    cost_note: str = ""
    area_id: str = ""
    duration_min: int = 90
    tags: tuple[str, ...] = ()
    note: str = ""


@dataclass
class DayPlan:
    day: int
    city: str
    items: list[ItineraryItem] = field(default_factory=list)


@dataclass
class ItineraryDraft:
    days: list[DayPlan]
    notes: list[str] = field(default_factory=list)

    @property
    def items(self) -> list[ItineraryItem]:
        return [item for day in self.days for item in day.items]


@dataclass
class BudgetReport:
    total: Money
    budget: Money | None
    over_budget: bool
    reasons: list[str] = field(default_factory=list)
    accommodation_thb: float = 0.0
    accommodation_level: str = ""
    accommodation_per_night_thb: float = 0.0


@dataclass(frozen=True)
class ReviewIssue:
    code: str
    severity: Literal["low", "medium", "high"]
    message: str
    marker: CorrectionMarker


@dataclass
class ReviewReport:
    passed: bool
    issues: list[ReviewIssue] = field(default_factory=list)


@dataclass
class WorkflowState:
    request: TravelRequest
    correction_round: int = 0
    max_corrections: int = 2
    markers: set[CorrectionMarker] = field(default_factory=set)
    history: list[str] = field(default_factory=list)
    manual_review_required: list[str] = field(default_factory=list)
    draft: ItineraryDraft | None = None
    budget_report: BudgetReport | None = None
    review_report: ReviewReport | None = None


@dataclass
class WorkflowResult:
    state: WorkflowState
    accepted: bool
