"""Output formatting helpers for demos and UI integration."""

from .workflow import marker_labels
from .models import WorkflowResult


def format_result(result: WorkflowResult) -> str:
    state = result.state
    lines = [
        f"accepted: {result.accepted}",
        f"correction_rounds_used: {state.correction_round}",
        f"state_markers: {', '.join(marker_labels(state.markers)) or 'none'}",
    ]

    if state.budget_report:
        report = state.budget_report
        lines.append(f"total_cost: {report.total.thb} THB / {report.total.twd} TWD")
        if report.budget:
            lines.append(f"budget: {report.budget.thb} THB / {report.budget.twd} TWD")

    if state.draft:
        lines.append("itinerary:")
        for day in state.draft.days:
            lines.append(f"  day {day.day} - {day.city}")
            for item in day.items:
                lines.append(
                    f"    {item.start_time} {item.title} [{item.data_id}] "
                    f"{item.cost_thb} THB"
                )
        if state.draft.notes:
            lines.append("notes:")
            lines.extend(f"  - {note}" for note in state.draft.notes)

    if state.manual_review_required:
        lines.append("manual_review_required:")
        lines.extend(f"  - {issue}" for issue in state.manual_review_required)

    lines.append("history:")
    lines.extend(f"  - {entry}" for entry in state.history)
    return "\n".join(lines)
