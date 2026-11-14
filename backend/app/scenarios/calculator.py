"""Care scenario calculator. Pure functions; money is always integer cents."""
import json
from fractions import Fraction
from functools import lru_cache
from pathlib import Path

DEFAULTS_PATH = Path(__file__).with_name("defaults.json")

STATUS_INDEFINITE = "no gap: indefinite"
STATUS_LESS_THAN_MONTH = "less than one month"


@lru_cache
def load_defaults() -> dict:
    with DEFAULTS_PATH.open(encoding="utf-8") as f:
        return json.load(f)


def _non_negative(**values: int | float) -> None:
    for name, value in values.items():
        if value < 0:
            raise ValueError(f"{name} must not be negative")


def home_care_monthly_cost(hourly_cents: int, hours_per_week: int | float) -> int:
    """Hours per week × 52 / 12 × hourly rate, rounded down to the cent."""
    _non_negative(hourly_cents=hourly_cents, hours_per_week=hours_per_week)
    # Fraction(str(...)) keeps 12.5 hours exact instead of a binary float approximation
    monthly = Fraction(str(hours_per_week)) * 52 * hourly_cents / 12
    return int(monthly)  # int() of a non-negative Fraction rounds down


def monthly_gap(monthly_cost_cents: int, monthly_income_cents: int) -> int:
    """Monthly gap. 0 when income covers the cost."""
    _non_negative(monthly_cost_cents=monthly_cost_cents, monthly_income_cents=monthly_income_cents)
    return max(monthly_cost_cents - monthly_income_cents, 0)


def months_covered(savings_cents: int, gap_cents: int) -> int | None:
    """How many full months the savings cover. None when there is no gap."""
    _non_negative(savings_cents=savings_cents, gap_cents=gap_cents)
    if gap_cents == 0:
        return None
    return savings_cents // gap_cents


def status_text(months: int | None) -> str:
    if months is None:
        return STATUS_INDEFINITE
    if months == 0:
        return STATUS_LESS_THAN_MONTH
    return f"covers about {months} month{'s' if months != 1 else ''}"


def calculate(
    savings_cents: int,
    monthly_income_cents: int,
    scenarios: list[dict],
    home_care_hourly_cents: int | None = None,
    home_care_hours_per_week: int | float | None = None,
    include_disabled: bool = False,
) -> list[dict]:
    """Run every scenario. Scenarios with enabled_by_default=false appear only on explicit request."""
    _non_negative(savings_cents=savings_cents, monthly_income_cents=monthly_income_cents)
    results = []
    for s in scenarios:
        if not s["enabled_by_default"] and not include_disabled:
            continue
        extra: dict = {}
        if s["id"] == "home_care":
            hourly = s["hourly_cents_default"] if home_care_hourly_cents is None else home_care_hourly_cents
            hours = s["hours_per_week_default"] if home_care_hours_per_week is None else home_care_hours_per_week
            cost = home_care_monthly_cost(hourly, hours)
            extra = {"hourly_cents": hourly, "hours_per_week": hours}
        else:
            cost = s["monthly_cost_cents"]
        gap = monthly_gap(cost, monthly_income_cents)
        months = months_covered(savings_cents, gap)
        results.append({
            "id": s["id"],
            "name": s["name"],
            "monthly_cost_cents": cost,
            "monthly_gap_cents": gap,
            "months_covered": months,
            "status": status_text(months),
            "source_url": s["source_url"],
            "source_name": s["source_name"],
            "as_of": s["as_of"],
            "kind": s["kind"],
            "note": s["note"],
            **extra,
        })
    return results
