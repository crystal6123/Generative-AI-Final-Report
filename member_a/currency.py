"""Currency helpers.

The exchange rate is a demo default for deterministic validation. In production,
replace it with the rate source agreed by the team.
"""

from .models import Money


DEFAULT_THB_TO_TWD = 0.91


def thb_to_money(thb: float, thb_to_twd: float = DEFAULT_THB_TO_TWD) -> Money:
    return Money(thb=round(thb, 2), twd=round(thb * thb_to_twd, 2))


def request_budget_to_money(
    amount: float | None,
    currency: str,
    thb_to_twd: float = DEFAULT_THB_TO_TWD,
) -> Money | None:
    if amount is None:
        return None
    if currency == "THB":
        return thb_to_money(amount, thb_to_twd)
    if currency == "TWD":
        return Money(thb=round(amount / thb_to_twd, 2), twd=round(amount, 2))
    raise ValueError(f"Unsupported currency: {currency}")
