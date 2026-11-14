import re

import pytest

from app.scenarios.calculator import (
    STATUS_INDEFINITE,
    STATUS_LESS_THAN_MONTH,
    calculate,
    home_care_monthly_cost,
    load_defaults,
    monthly_gap,
    months_covered,
)

SCENARIOS = load_defaults()["scenarios"]


def by_id(results):
    return {r["id"]: r for r in results}


# --- обычный случай ----------------------------------------------------------

def test_assisted_living_100k_savings_2k_income():
    results = by_id(calculate(10_000_000, 200_000, SCENARIOS))
    al = results["assisted_living"]
    assert al["monthly_cost_cents"] == 620_000
    assert al["monthly_gap_cents"] == 420_000
    assert al["months_covered"] == 23  # 100 000 // 4 200
    assert al["status"] == "covers about 23 months"
    assert al["kind"] == "survey"
    assert al["as_of"] == "2025"
    assert al["source_url"].startswith("https://investor.genworth.com/")


def test_months_rounds_down():
    assert months_covered(10_000_000, 420_000) == 23
    assert months_covered(420_000 * 23 + 419_999, 420_000) == 23
    assert months_covered(420_000 * 24, 420_000) == 24


# --- доход выше стоимости ---------------------------------------------------

def test_income_covers_cost_no_gap():
    assert monthly_gap(620_000, 620_000) == 0
    assert monthly_gap(620_000, 900_000) == 0
    assert months_covered(10_000_000, 0) is None


def test_income_above_cost_in_calculate():
    al = by_id(calculate(10_000_000, 1_000_000, SCENARIOS))["assisted_living"]
    assert al["monthly_gap_cents"] == 0
    assert al["months_covered"] is None
    assert al["status"] == STATUS_INDEFINITE


# --- накопления 0 ------------------------------------------------------------

def test_zero_savings_zero_months():
    assert months_covered(0, 420_000) == 0
    al = by_id(calculate(0, 200_000, SCENARIOS))["assisted_living"]
    assert al["months_covered"] == 0
    assert al["status"] == STATUS_LESS_THAN_MONTH


def test_zero_savings_and_no_gap_is_indefinite():
    assert months_covered(0, 0) is None


# --- отрицательные значения --------------------------------------------------

@pytest.mark.parametrize("fn, args", [
    (monthly_gap, (-1, 0)),
    (monthly_gap, (0, -1)),
    (months_covered, (-1, 100)),
    (months_covered, (100, -1)),
    (home_care_monthly_cost, (-1, 10)),
    (home_care_monthly_cost, (3000, -1)),
])
def test_negative_values_rejected(fn, args):
    with pytest.raises(ValueError):
        fn(*args)


def test_calculate_rejects_negative():
    with pytest.raises(ValueError):
        calculate(-1, 0, SCENARIOS)
    with pytest.raises(ValueError):
        calculate(0, -1, SCENARIOS)


# --- уход дома ----------------------------------------------------------------

def test_home_care_default_formula():
    # 20 ч/нед × 52 / 12 × 30 $ = 2 600 $ ровно
    assert home_care_monthly_cost(3000, 20) == 260_000
    hc = by_id(calculate(10_000_000, 200_000, SCENARIOS))["home_care"]
    assert hc["monthly_cost_cents"] == 260_000
    assert hc["hourly_cents"] == 3000
    assert hc["hours_per_week"] == 20
    assert hc["kind"] == "user_estimate"
    assert hc["months_covered"] == 10_000_000 // 60_000  # дефицит 600 $


def test_home_care_rounds_down_to_cent():
    # 1 ч/нед × 52 / 12 × 29.99 $ = 129.9566… $ → 129.95 $
    assert home_care_monthly_cost(2999, 1) == 12_995
    # 12.5 часов считаются точно: 12.5 × 52 / 12 × 30 = 1 625 $
    assert home_care_monthly_cost(3000, 12.5) == 162_500
    # 0.1 часа: 0.1 × 52 / 12 × 30 = 13 $ ровно (с float было бы 12.999…)
    assert home_care_monthly_cost(3000, 0.1) == 1_300


def test_home_care_user_values_override_defaults():
    hc = by_id(calculate(10_000_000, 0, SCENARIOS, home_care_hourly_cents=4000, home_care_hours_per_week=40))["home_care"]
    assert hc["monthly_cost_cents"] == 40 * 52 * 4000 // 12  # 693 333.33 → 69_333_33 центов
    assert hc["monthly_cost_cents"] == 693_333
    assert hc["hourly_cents"] == 4000 and hc["hours_per_week"] == 40


def test_home_care_zero_hours_costs_nothing():
    assert home_care_monthly_cost(3000, 0) == 0


# --- сценарии по умолчанию -----------------------------------------------------

def test_memory_care_hidden_unless_requested():
    ids = by_id(calculate(10_000_000, 200_000, SCENARIOS)).keys()
    assert "memory_care" not in ids  # в CareScout 2025 нет данных по memory care
    assert set(ids) == {"home_care", "assisted_living", "nursing_home_private_room"}


def test_memory_care_shown_when_requested():
    results = by_id(calculate(10_000_000, 200_000, SCENARIOS, include_disabled=True))
    mc = results["memory_care"]
    assert mc["monthly_cost_cents"] == 669_000
    assert "Needs verification" in mc["note"]
    assert mc["kind"] == "estimate"


def test_nursing_home_private_room_from_carescout():
    nh = by_id(calculate(10_000_000, 200_000, SCENARIOS))["nursing_home_private_room"]
    assert nh["monthly_cost_cents"] == 355 * 365 * 100 // 12  # 129 575 $/год → 10 797,91 $/мес, вниз
    assert nh["monthly_cost_cents"] == 1_079_791
    assert nh["kind"] == "survey" and nh["as_of"] == "2025"
    assert nh["source_url"].startswith("https://investor.genworth.com/")
    assert nh["monthly_gap_cents"] == 879_791
    assert nh["months_covered"] == 10_000_000 // 879_791 == 11


@pytest.mark.parametrize("scenario", SCENARIOS, ids=lambda s: s["id"])
def test_defaults_well_formed(scenario):
    for key in ("id", "name", "monthly_cost_cents", "source_url", "source_name", "as_of", "kind", "note", "enabled_by_default"):
        assert key in scenario, key
    assert scenario["kind"] in ("survey", "estimate", "user_estimate")
    if scenario["id"] == "home_care":
        assert scenario["monthly_cost_cents"] is None
        assert isinstance(scenario["hourly_cents_default"], int)
    else:
        assert isinstance(scenario["monthly_cost_cents"], int)  # центы, не float
        assert scenario["source_url"].startswith("https://")
    if scenario["kind"] == "survey":
        assert scenario["as_of"], "survey data must have a year"


def test_no_guarantee_words():
    defaults = load_defaults()
    results = calculate(10_000_000, 200_000, SCENARIOS, include_disabled=True)
    texts = [defaults["disclaimer"]] + [f'{r["name"]} {r["status"]} {r["note"]} {r["source_name"]}' for r in results]
    joined = " ".join(texts).lower()
    for word in ("guaranteed", "you will receive", "definitely", "you qualify"):
        assert not re.search(rf"\b{word}", joined), word
