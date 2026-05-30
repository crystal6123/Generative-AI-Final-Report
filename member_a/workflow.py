"""Workflow orchestration for member A.

This module keeps the node shape close to LangGraph:
tour_guide -> budget -> reviewer -> conditional edge -> tour_guide/final.
"""

from __future__ import annotations

from .agents import BudgetAgent, ReviewerAgent, TourGuideAgent
from .data_gateway import TravelDataGateway
from .models import CorrectionMarker, TravelRequest, WorkflowResult, WorkflowState


def run_workflow(
    request: TravelRequest,
    *,
    gateway: TravelDataGateway | None = None,
    llm_planner=None,
    max_corrections: int = 2,
) -> WorkflowResult:
    data_gateway = gateway or TravelDataGateway()
    state = WorkflowState(request=request, max_corrections=max_corrections)
    tour_guide = TourGuideAgent(data_gateway, llm_planner=llm_planner)
    budget_agent = BudgetAgent()
    reviewer = ReviewerAgent(data_gateway)

    while True:
        state.history.append(f"round_{state.correction_round}:tour_guide")
        state.draft = tour_guide.generate(state)

        state.history.append(f"round_{state.correction_round}:budget_agent")
        state.budget_report = budget_agent.calculate(state)

        state.history.append(f"round_{state.correction_round}:reviewer_agent")
        state.review_report = reviewer.review(state)

        if state.review_report.passed:
            state.history.append("final:accepted")
            return WorkflowResult(state=state, accepted=True)

        markers = {issue.marker for issue in state.review_report.issues}
        state.markers.update(markers)
        state.history.append(f"conditional_edge:reject:{','.join(sorted(marker.value for marker in markers))}")

        if state.correction_round >= state.max_corrections:
            state.manual_review_required.extend(issue.message for issue in state.review_report.issues)
            state.history.append("final:manual_review_required")
            return WorkflowResult(state=state, accepted=False)

        state.correction_round += 1


def marker_labels(markers: set[CorrectionMarker]) -> list[str]:
    labels = {
        CorrectionMarker.BUDGET_DOWNSHIFT: "調降預算級別",
        CorrectionMarker.TIME_CONFLICT: "時間衝突",
        CorrectionMarker.IMPROVE_DIVERSITY: "提高行程豐富度",
        CorrectionMarker.MISSING_DATA: "補齊資料欄位",
    }
    return [labels[marker] for marker in markers]
