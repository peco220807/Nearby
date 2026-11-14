import copy
import re
from datetime import date

import pytest

from app.eligibility.screen import NEEDS_CHECK, POSSIBLE, UNLIKELY, load_rules, screen

TODAY = date(2026, 11, 14)  # суммы VA действуют до 2026-11-30
OFFICIAL_HOSTS = ("www.va.gov", "www.medicaid.gov", "www.cms.gov", "www.irs.gov", "www.medicare.gov")


def by_id(result):
    return {p["id"]: p for p in result["programs"]}


VETERAN_LOW_INCOME = {
    "state": "TX",
    "age": 82,
    "is_veteran": True,
    "is_surviving_spouse_of_veteran": False,
    "wartime_service": True,
    "has_spouse": False,
    "needs_help_daily_activities": True,
    "in_nursing_home": False,
    "annual_income_cents": 1_500_000,   # $15,000 < MAPR $29,093
    "net_worth_cents": 5_000_000,       # $50,000 < $163,699
}


# --- ветеран с низким доходом ----------------------------------------------

def test_veteran_low_income_va_possible():
    va = by_id(screen(VETERAN_LOW_INCOME, today=TODAY))["va_aid_attendance"]
    assert va["status"] == POSSIBLE
    assert va["reasons"] == []
    assert va["to_check"] == []
    assert va["source_url"].startswith("https://www.va.gov/")


def test_veteran_income_above_mapr_needs_check_not_rejected():
    answers = {**VETERAN_LOW_INCOME, "annual_income_cents": 3_000_000}  # > $29,093
    va = by_id(screen(answers, today=TODAY))["va_aid_attendance"]
    assert va["status"] == NEEDS_CHECK
    assert any("MAPR" in c for c in va["to_check"])


def test_veteran_with_spouse_uses_higher_mapr():
    answers = {**VETERAN_LOW_INCOME, "has_spouse": True, "annual_income_cents": 3_000_000}  # < $34,488
    assert by_id(screen(answers, today=TODAY))["va_aid_attendance"]["status"] == POSSIBLE


def test_veteran_net_worth_above_limit_unlikely():
    answers = {**VETERAN_LOW_INCOME, "net_worth_cents": 20_000_000}
    va = by_id(screen(answers, today=TODAY))["va_aid_attendance"]
    assert va["status"] == UNLIKELY
    assert any("Чистые активы" in r for r in va["reasons"])


def test_surviving_spouse_low_income_possible():
    answers = {**VETERAN_LOW_INCOME, "is_veteran": False, "is_surviving_spouse_of_veteran": True,
               "annual_income_cents": 1_000_000}  # < $18,697
    assert by_id(screen(answers, today=TODAY))["va_aid_attendance"]["status"] == POSSIBLE


def test_va_amounts_expired_need_check():
    va = by_id(screen(VETERAN_LOW_INCOME, today=date(2026, 12, 1)))["va_aid_attendance"]
    assert va["status"] == NEEDS_CHECK


# --- не ветеран ------------------------------------------------------------

def test_not_veteran_va_unlikely():
    answers = {**VETERAN_LOW_INCOME, "is_veteran": False, "is_surviving_spouse_of_veteran": False}
    result = by_id(screen(answers, today=TODAY))
    va = result["va_aid_attendance"]
    assert va["status"] == UNLIKELY
    assert any("ветеран" in r for r in va["reasons"])
    # остальные программы при этом показываются
    assert {"medicaid_ltc", "dependent_care_credit"} <= result.keys()


def test_not_veteran_spouse_unknown_needs_check():
    answers = {**VETERAN_LOW_INCOME, "is_veteran": False, "is_surviving_spouse_of_veteran": None}
    assert by_id(screen(answers, today=TODAY))["va_aid_attendance"]["status"] == NEEDS_CHECK


# --- штат без программы ----------------------------------------------------

STATE_RULE = {
    "id": "ca_only", "name": "Программа штата CA", "summary": "Тест", "state": "CA",
    "source_url": "https://www.ca.gov/", "amounts_source_urls": [], "last_verified": "2026-11-14",
    "amounts_valid_until": None, "amounts": {}, "amounts_note": "", "input_fields": [],
    "conditions": [{"id": "c", "on_fail": "unlikely", "check": "Нужна помощь", "fail_text": "Помощь не нужна.",
                    "field": "needs_help_daily_activities", "op": "eq", "value": True}],
    "result_description": "Возможно.", "unlikely_description": "Скорее всего, не подойдёт.", "documents": [],
}


def test_state_without_program_hides_it():
    rules = load_rules()["rules"] + [STATE_RULE]
    ids = by_id(screen({**VETERAN_LOW_INCOME, "state": "TX"}, rules=rules, today=TODAY)).keys()
    assert "ca_only" not in ids
    assert "va_aid_attendance" in ids  # федеральные программы остаются


def test_state_with_program_shows_it():
    result = by_id(screen({"state": "CA", "needs_help_daily_activities": True}, rules=[STATE_RULE], today=TODAY))
    assert result["ca_only"]["status"] == POSSIBLE


def test_state_unknown_state_program_needs_check():
    result = by_id(screen({"needs_help_daily_activities": True}, rules=[STATE_RULE], today=TODAY))
    assert result["ca_only"]["status"] == NEEDS_CHECK
    assert any("штат" in c for c in result["ca_only"]["to_check"])


def test_medicaid_never_possible_without_state_limits():
    assert by_id(screen(VETERAN_LOW_INCOME, today=TODAY))["medicaid_ltc"]["status"] == NEEDS_CHECK


# --- пустые поля -----------------------------------------------------------

def test_empty_answers_all_need_check():
    result = screen({}, today=TODAY)
    assert len(result["programs"]) == len(load_rules()["rules"])
    for p in result["programs"]:
        assert p["status"] == NEEDS_CHECK, p["id"]
        assert p["reasons"] == []
        assert p["to_check"]
        assert p["documents"]


def test_all_none_same_as_empty():
    keys = ["state", "age", "is_veteran", "wartime_service", "annual_income_cents", "net_worth_cents"]
    assert screen(dict.fromkeys(keys), today=TODAY) == screen({}, today=TODAY)


# --- налоговый кредит ------------------------------------------------------

def test_tax_credit_possible_still_asks_tax_professional():
    answers = {"needs_help_daily_activities": True, "lives_with_caregiver_over_half_year": True,
               "caregiver_provides_over_half_support": True, "caregiver_works": True}
    tax = by_id(screen(answers, today=TODAY))["dependent_care_credit"]
    assert tax["status"] == POSSIBLE
    assert any("налогового специалиста" in c for c in tax["to_check"])


def test_tax_credit_support_under_half_unlikely():
    answers = {"caregiver_provides_over_half_support": False}
    assert by_id(screen(answers, today=TODAY))["dependent_care_credit"]["status"] == UNLIKELY


# --- данные правил ---------------------------------------------------------

@pytest.mark.parametrize("rule", load_rules()["rules"], ids=lambda r: r["id"])
def test_rule_data_is_well_formed(rule):
    for key in ("id", "name", "summary", "input_fields", "conditions", "result_description",
                "source_url", "last_verified", "state", "documents"):
        assert key in rule
    date.fromisoformat(rule["last_verified"])
    for url in [rule["source_url"], *rule["amounts_source_urls"]]:
        assert re.match(r"https://([^/]+)/", url).group(1) in OFFICIAL_HOSTS, url
    for value in rule["amounts"].values():
        assert value is None or isinstance(value, int)  # только центы, без float
    if any(v is not None for v in rule["amounts"].values()):
        assert rule["amounts_source_urls"] and rule["amounts_valid_until"]


def test_no_guarantees_in_texts():
    texts = []
    for p in screen(VETERAN_LOW_INCOME, today=TODAY)["programs"] + screen({}, today=TODAY)["programs"]:
        texts += [p["summary"], p["result_description"], *p["reasons"], *p["to_check"]]
    joined = " ".join(texts).lower()
    for word in ("гарантированно", "гарантир", "вы получите", "точно", "одобрен"):
        assert word not in joined


def test_screen_does_not_mutate_rules():
    before = copy.deepcopy(load_rules())
    screen(VETERAN_LOW_INCOME, today=TODAY)
    assert load_rules() == before


def test_amounts_valid_until_returned():
    result = by_id(screen({}, today=TODAY))
    assert result["va_aid_attendance"]["amounts_valid_until"] == "2026-11-30"
    assert result["medicaid_ltc"]["amounts_valid_until"] is None


# --- VA PCAFC: поддержка семейных ухаживающих ------------------------------

PCAFC_VETERAN = {"is_veteran": True, "va_service_rating_70_plus": True, "needs_help_daily_activities": True}


def test_pcafc_veteran_70_needs_help_not_rejected():
    pcafc = by_id(screen(PCAFC_VETERAN, today=TODAY))["va_caregiver_pcafc"]
    assert pcafc["status"] in (POSSIBLE, NEEDS_CHECK)
    assert pcafc["reasons"] == []
    # 6 месяцев ухода, VA health care и ухаживающий опрос не спрашивает — их надо проверить
    assert pcafc["status"] == NEEDS_CHECK
    assert any("6 месяцев" in c for c in pcafc["to_check"])
    assert any("18 лет" in c for c in pcafc["to_check"])


def test_pcafc_rating_unknown_needs_check():
    answers = {**PCAFC_VETERAN, "va_service_rating_70_plus": None}
    pcafc = by_id(screen(answers, today=TODAY))["va_caregiver_pcafc"]
    assert pcafc["status"] == NEEDS_CHECK
    assert any("70%" in c for c in pcafc["to_check"])


def test_pcafc_rating_below_70_unlikely():
    answers = {**PCAFC_VETERAN, "va_service_rating_70_plus": False}
    pcafc = by_id(screen(answers, today=TODAY))["va_caregiver_pcafc"]
    assert pcafc["status"] == UNLIKELY
    assert any("70%" in r for r in pcafc["reasons"])


def test_pcafc_not_veteran_unlikely():
    answers = {**PCAFC_VETERAN, "is_veteran": False}
    assert by_id(screen(answers, today=TODAY))["va_caregiver_pcafc"]["status"] == UNLIKELY


def test_pcafc_has_no_amounts():
    pcafc = by_id(screen({}, today=TODAY))["va_caregiver_pcafc"]
    assert pcafc["amounts_valid_until"] is None
    assert pcafc["amounts_source_urls"] == []
    assert "va.gov" in pcafc["amounts_note"]
    assert any("10-10CG" in d for d in pcafc["documents"])


# --- Medicare Savings Programs и Extra Help --------------------------------

def test_medicare_with_income_and_assets_unknown_needs_check():
    msp = by_id(screen({"has_medicare": True}, today=TODAY))["medicare_savings_extra_help"]
    assert msp["status"] == NEEDS_CHECK
    assert msp["reasons"] == []


def test_medicare_limits_unverified_even_with_low_income():
    answers = {"has_medicare": True, "annual_income_cents": 100_000, "net_worth_cents": 100_000}
    msp = by_id(screen(answers, today=TODAY))["medicare_savings_extra_help"]
    assert msp["status"] == NEEDS_CHECK  # лимиты не вписаны → нельзя сказать «возможно»


def test_no_medicare_unlikely():
    msp = by_id(screen({"has_medicare": False}, today=TODAY))["medicare_savings_extra_help"]
    assert msp["status"] == UNLIKELY


def test_medicare_limits_are_null():
    rule = next(r for r in load_rules()["rules"] if r["id"] == "medicare_savings_extra_help")
    assert rule["amounts"] == {"income_limit_cents": None, "asset_limit_cents": None}
    assert rule["state"] is None
    assert "medicare.gov" in rule["amounts_note"]


# --- тексты причин «против» и описания ------------------------------------

def test_reasons_are_negative_not_requirements():
    answers = {"is_veteran": False, "va_service_rating_70_plus": False, "needs_help_daily_activities": True}
    pcafc = by_id(screen(answers, today=TODAY))["va_caregiver_pcafc"]
    assert pcafc["reasons"] == [
        "Родитель не является ветераном (по вашим ответам).",
        "Рейтинг нарушения здоровья VA ниже 70% (по вашим ответам).",
    ]


def test_tax_unlikely_reason_and_description_are_negative():
    tax = by_id(screen({"caregiver_provides_over_half_support": False}, today=TODAY))["dependent_care_credit"]
    assert tax["status"] == UNLIKELY
    assert tax["reasons"] == ["Вы обеспечиваете не больше 50% поддержки родителя (по вашим ответам)."]
    assert tax["result_description"].startswith("Скорее всего, кредит не подойдёт")
    assert "Возможно" not in tax["result_description"]


def test_description_positive_when_not_unlikely():
    tax = by_id(screen({}, today=TODAY))["dependent_care_credit"]
    assert tax["status"] == NEEDS_CHECK
    assert tax["result_description"].startswith("Возможно")


def test_unlikely_descriptions_never_say_possible():
    answers = {"is_veteran": False, "is_surviving_spouse_of_veteran": False, "has_medicare": False,
               "caregiver_works": False}
    for p in screen(answers, today=TODAY)["programs"]:
        if p["status"] == UNLIKELY:
            assert p["result_description"].startswith("Скорее всего"), p["id"]
            assert p["reasons"]


@pytest.mark.parametrize("rule", load_rules()["rules"], ids=lambda r: r["id"])
def test_unlikely_conditions_have_fail_text(rule):
    assert rule["unlikely_description"].startswith("Скорее всего")
    for cond in rule["conditions"]:
        if cond["on_fail"] == "unlikely":
            assert cond.get("fail_text"), f"{rule['id']}.{cond['id']}"
            assert cond["fail_text"] != cond["check"]
            assert "(по вашим ответам)" in cond["fail_text"]
