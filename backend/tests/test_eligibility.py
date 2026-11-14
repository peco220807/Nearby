import copy
import re
from datetime import date

import pytest

from app.eligibility.screen import NEEDS_CHECK, POSSIBLE, UNLIKELY, load_rules, screen

TODAY = date(2026, 11, 14)  # VA amounts are valid until 2026-11-30
OFFICIAL_HOSTS = ("www.va.gov", "www.medicaid.gov", "www.cms.gov", "www.irs.gov", "www.medicare.gov", "www.ssa.gov")
FORBIDDEN_WORDS = ("guaranteed", "guarantee", "you will receive", "you'll receive", "definitely", "you qualify",
                   "you will qualify", "going to be fine", "approved")


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


# --- status values are machine strings ---------------------------------------

def test_status_constants():
    assert (POSSIBLE, NEEDS_CHECK, UNLIKELY) == ("possible", "needs review", "unlikely")


# --- veteran with low income ---------------------------------------------------

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
    assert any("net worth is above" in r.lower() for r in va["reasons"])


def test_surviving_spouse_low_income_possible():
    answers = {**VETERAN_LOW_INCOME, "is_veteran": False, "is_surviving_spouse_of_veteran": True,
               "annual_income_cents": 1_000_000}  # < $18,697
    assert by_id(screen(answers, today=TODAY))["va_aid_attendance"]["status"] == POSSIBLE


def test_va_amounts_expired_need_check():
    va = by_id(screen(VETERAN_LOW_INCOME, today=date(2026, 12, 1)))["va_aid_attendance"]
    assert va["status"] == NEEDS_CHECK


# --- not a veteran ---------------------------------------------------------------

def test_not_veteran_va_unlikely():
    answers = {**VETERAN_LOW_INCOME, "is_veteran": False, "is_surviving_spouse_of_veteran": False}
    result = by_id(screen(answers, today=TODAY))
    va = result["va_aid_attendance"]
    assert va["status"] == UNLIKELY
    assert any("not a veteran" in r for r in va["reasons"])
    # other programs are still shown
    assert {"medicaid_ltc", "dependent_care_credit"} <= result.keys()


def test_not_veteran_spouse_unknown_needs_check():
    answers = {**VETERAN_LOW_INCOME, "is_veteran": False, "is_surviving_spouse_of_veteran": None}
    assert by_id(screen(answers, today=TODAY))["va_aid_attendance"]["status"] == NEEDS_CHECK


# --- state without the program ------------------------------------------------------

STATE_RULE = {
    "id": "ca_only", "name": "California program", "summary": "Test", "state": "CA",
    "source_url": "https://www.ca.gov/", "amounts_source_urls": [], "last_verified": "2026-11-14",
    "amounts_valid_until": None, "amounts": {}, "amounts_note": "", "input_fields": [],
    "conditions": [{"id": "c", "on_fail": "unlikely", "check": "Needs help", "fail_text": "Does not need help.",
                    "field": "needs_help_daily_activities", "op": "eq", "value": True}],
    "result_description": "Possibly.", "unlikely_description": "Unlikely: does not fit.", "documents": [],
}


def test_state_without_program_hides_it():
    rules = load_rules()["rules"] + [STATE_RULE]
    ids = by_id(screen({**VETERAN_LOW_INCOME, "state": "TX"}, rules=rules, today=TODAY)).keys()
    assert "ca_only" not in ids
    assert "va_aid_attendance" in ids  # federal programs stay


def test_state_with_program_shows_it():
    result = by_id(screen({"state": "CA", "needs_help_daily_activities": True}, rules=[STATE_RULE], today=TODAY))
    assert result["ca_only"]["status"] == POSSIBLE


def test_state_unknown_state_program_needs_check():
    result = by_id(screen({"needs_help_daily_activities": True}, rules=[STATE_RULE], today=TODAY))
    assert result["ca_only"]["status"] == NEEDS_CHECK
    assert any("state" in c for c in result["ca_only"]["to_check"])


def test_medicaid_never_possible_without_state_limits():
    assert by_id(screen(VETERAN_LOW_INCOME, today=TODAY))["medicaid_ltc"]["status"] == NEEDS_CHECK


# --- empty answers ----------------------------------------------------------------

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


# --- dependent care credit ------------------------------------------------------------

def test_tax_credit_possible_still_asks_tax_professional():
    answers = {"needs_help_daily_activities": True, "lives_with_caregiver_over_half_year": True,
               "caregiver_provides_over_half_support": True, "caregiver_works": True}
    tax = by_id(screen(answers, today=TODAY))["dependent_care_credit"]
    assert tax["status"] == POSSIBLE
    assert any("tax professional" in c for c in tax["to_check"])


def test_tax_credit_support_under_half_unlikely():
    answers = {"caregiver_provides_over_half_support": False}
    assert by_id(screen(answers, today=TODAY))["dependent_care_credit"]["status"] == UNLIKELY


# --- rule data -----------------------------------------------------------------------

@pytest.mark.parametrize("rule", load_rules()["rules"], ids=lambda r: r["id"])
def test_rule_data_is_well_formed(rule):
    for key in ("id", "name", "summary", "input_fields", "conditions", "result_description",
                "source_url", "last_verified", "state", "documents"):
        assert key in rule
    date.fromisoformat(rule["last_verified"])
    for url in [rule["source_url"], *rule["amounts_source_urls"]]:
        assert re.match(r"https://([^/]+)/", url).group(1) in OFFICIAL_HOSTS, url
    for value in rule["amounts"].values():
        assert value is None or isinstance(value, int)  # cents only, never float
    if any(v is not None for v in rule["amounts"].values()):
        assert rule["amounts_source_urls"] and rule["amounts_valid_until"]


def test_official_program_names_kept():
    names = {r["id"]: r["name"] for r in load_rules()["rules"]}
    assert names["va_aid_attendance"] == "VA Aid and Attendance"
    assert names["medicaid_ltc"] == "Medicaid long-term care"
    assert names["dependent_care_credit"] == "Dependent Care Credit (IRS)"
    assert names["va_caregiver_pcafc"] == "VA Program of Comprehensive Assistance for Family Caregivers"
    assert "Medicare Savings Programs" in names["medicare_savings_extra_help"]
    assert "Extra Help" in names["medicare_savings_extra_help"]


def test_no_guarantees_in_texts():
    texts = [load_rules()["disclaimer"]]
    for rule in load_rules()["rules"]:
        texts += [rule["name"], rule["summary"], rule["result_description"], rule["unlikely_description"],
                  rule["amounts_note"], *rule["documents"], *rule.get("always_check", [])]
        for cond in rule["conditions"]:
            texts += [cond["check"], cond.get("fail_text", "")]
    joined = " ".join(texts).lower()
    for word in FORBIDDEN_WORDS:
        assert word not in joined, word


def test_no_cyrillic_in_rules():
    assert not re.search(r"[А-Яа-яЁё]", load_rules.__wrapped__.__globals__["RULES_PATH"].read_text(encoding="utf-8"))


def test_screen_does_not_mutate_rules():
    before = copy.deepcopy(load_rules())
    screen(VETERAN_LOW_INCOME, today=TODAY)
    assert load_rules() == before


def test_amounts_valid_until_returned():
    result = by_id(screen({}, today=TODAY))
    assert result["va_aid_attendance"]["amounts_valid_until"] == "2026-11-30"
    assert result["medicaid_ltc"]["amounts_valid_until"] is None


# --- VA PCAFC: family caregiver support -----------------------------------------------

PCAFC_VETERAN = {"is_veteran": True, "va_service_rating_70_plus": True, "needs_help_daily_activities": True}


def test_pcafc_veteran_70_needs_help_not_rejected():
    pcafc = by_id(screen(PCAFC_VETERAN, today=TODAY))["va_caregiver_pcafc"]
    assert pcafc["status"] in (POSSIBLE, NEEDS_CHECK)
    assert pcafc["reasons"] == []
    # 6 months of care, VA health care and the caregiver are not asked in the survey -> review
    assert pcafc["status"] == NEEDS_CHECK
    assert any("6 months" in c for c in pcafc["to_check"])
    assert any("at least 18" in c for c in pcafc["to_check"])


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


# --- Medicare Savings Programs and Extra Help ------------------------------------------

def test_medicare_with_income_and_assets_unknown_needs_check():
    msp = by_id(screen({"has_medicare": True}, today=TODAY))["medicare_savings_extra_help"]
    assert msp["status"] == NEEDS_CHECK
    assert msp["reasons"] == []


def test_medicare_limits_unverified_even_with_low_income():
    answers = {"has_medicare": True, "annual_income_cents": 100_000, "net_worth_cents": 100_000}
    msp = by_id(screen(answers, today=TODAY))["medicare_savings_extra_help"]
    assert msp["status"] == NEEDS_CHECK  # limits are not entered -> cannot say "possible"


def test_no_medicare_unlikely():
    msp = by_id(screen({"has_medicare": False}, today=TODAY))["medicare_savings_extra_help"]
    assert msp["status"] == UNLIKELY


def test_medicare_limits_are_null():
    rule = next(r for r in load_rules()["rules"] if r["id"] == "medicare_savings_extra_help")
    assert rule["amounts"] == {"income_limit_cents": None, "asset_limit_cents": None}
    assert rule["state"] is None
    assert "medicare.gov" in rule["amounts_note"]


# --- reasons and descriptions wording -----------------------------------------------------

def test_reasons_are_negative_not_requirements():
    answers = {"is_veteran": False, "va_service_rating_70_plus": False, "needs_help_daily_activities": True}
    pcafc = by_id(screen(answers, today=TODAY))["va_caregiver_pcafc"]
    assert pcafc["reasons"] == [
        "Based on your answers, your parent is not a veteran, and this program is for veterans' caregivers.",
        "Based on your answers, the VA disability rating is below 70%, which this program requires.",
    ]


def test_tax_unlikely_reason_and_description_are_negative():
    tax = by_id(screen({"caregiver_provides_over_half_support": False}, today=TODAY))["dependent_care_credit"]
    assert tax["status"] == UNLIKELY
    assert tax["reasons"] == [
        "Based on your answers, you provide 50% or less of your parent's support, and this credit needs more than half."
    ]
    assert tax["result_description"].startswith("Unlikely to apply")
    assert "Possibly" not in tax["result_description"]


def test_description_positive_when_not_unlikely():
    tax = by_id(screen({}, today=TODAY))["dependent_care_credit"]
    assert tax["status"] == NEEDS_CHECK
    assert tax["result_description"].startswith("Possibly")


def test_unlikely_descriptions_never_say_possible():
    answers = {"is_veteran": False, "is_surviving_spouse_of_veteran": False, "has_medicare": False,
               "caregiver_works": False}
    for p in screen(answers, today=TODAY)["programs"]:
        if p["status"] == UNLIKELY:
            assert p["result_description"].startswith("Unlikely"), p["id"]
            assert p["reasons"]


@pytest.mark.parametrize("rule", load_rules()["rules"], ids=lambda r: r["id"])
def test_unlikely_conditions_have_fail_text(rule):
    assert rule["unlikely_description"].startswith("Unlikely")
    assert rule["result_description"].startswith("Possibly")
    for cond in rule["conditions"]:
        if cond["on_fail"] == "unlikely":
            assert cond.get("fail_text"), f"{rule['id']}.{cond['id']}"
            assert cond["fail_text"] != cond["check"]
            # a reason reads as what the answers showed, not as a requirement
            assert cond["fail_text"].startswith("Based on your answers")


# --- memory, diagnosis and "not sure" --------------------------------------------------

NO_HELP_VETERAN = {**VETERAN_LOW_INCOME, "needs_help_daily_activities": False, "in_nursing_home": False}


def test_memory_help_counts_as_need_for_help():
    answers = {**NO_HELP_VETERAN, "needs_daily_help_memory": True}
    assert by_id(screen(answers, today=TODAY))["va_aid_attendance"]["status"] == POSSIBLE


def test_memory_unknown_gives_needs_review_not_unlikely():
    answers = {**NO_HELP_VETERAN, "needs_daily_help_memory": None}
    va = by_id(screen(answers, today=TODAY))["va_aid_attendance"]
    assert va["status"] == NEEDS_CHECK
    assert va["reasons"] == []


def test_no_help_for_any_reason_is_unlikely():
    answers = {**NO_HELP_VETERAN, "needs_daily_help_memory": False}
    va = by_id(screen(answers, today=TODAY))["va_aid_attendance"]
    assert va["status"] == UNLIKELY
    assert any("memory" in r for r in va["reasons"])


def test_diagnosis_alone_does_not_change_any_status():
    base = screen({}, today=TODAY)
    with_dx = screen({"has_dementia_or_alzheimers": True}, today=TODAY)
    assert with_dx == base
    assert all(p["status"] == NEEDS_CHECK for p in with_dx["programs"])


def test_diagnosis_without_need_for_help_does_not_rescue_va():
    answers = {**NO_HELP_VETERAN, "needs_daily_help_memory": False, "has_dementia_or_alzheimers": True}
    assert by_id(screen(answers, today=TODAY))["va_aid_attendance"]["status"] == UNLIKELY


def test_medicaid_memory_help_and_disability_are_review_only():
    answers = {"age": 60, "has_disability": True, "needs_daily_help_memory": True}
    mc = by_id(screen(answers, today=TODAY))["medicaid_ltc"]
    assert mc["status"] == NEEDS_CHECK  # state limits are null -> never "possible"
    assert mc["reasons"] == []
    assert not any("65" in c for c in mc["to_check"])  # age/disability condition is satisfied by the disability


def test_unknown_values_never_produce_unlikely():
    keys = ["needs_daily_help_memory", "has_dementia_or_alzheimers", "has_disability", "needs_help_daily_activities",
            "has_medicare", "is_veteran", "is_surviving_spouse_of_veteran"]
    for p in screen(dict.fromkeys(keys), today=TODAY)["programs"]:
        assert p["status"] == NEEDS_CHECK, p["id"]


# --- disability: Medicare before 65 and SSI ------------------------------------------

def test_disability_never_gives_possible():
    answers = {"has_disability": True, "age": 60, "annual_income_cents": 0, "net_worth_cents": 0}
    dis = by_id(screen(answers, today=TODAY))["disability_medicare_ssi"]
    assert dis["status"] == NEEDS_CHECK  # SSI limits are null and the 24-month rule is manual
    assert dis["reasons"] == []
    assert any("24 months" in c for c in dis["to_check"])


def test_disability_unknown_is_needs_review():
    dis = by_id(screen({"has_disability": None, "age": 60}, today=TODAY))["disability_medicare_ssi"]
    assert dis["status"] == NEEDS_CHECK


def test_no_disability_under_65_unlikely():
    dis = by_id(screen({"has_disability": False, "age": 60}, today=TODAY))["disability_medicare_ssi"]
    assert dis["status"] == UNLIKELY
    assert dis["reasons"] and dis["reasons"][0].startswith("Based on your answers")


def test_no_disability_but_65_plus_still_review_for_ssi():
    dis = by_id(screen({"has_disability": False, "age": 80}, today=TODAY))["disability_medicare_ssi"]
    assert dis["status"] == NEEDS_CHECK


def test_disability_rule_sources_and_null_amounts():
    rule = next(r for r in load_rules()["rules"] if r["id"] == "disability_medicare_ssi")
    assert rule["source_url"].startswith("https://www.medicare.gov/")
    assert any("ssa.gov" in t for t in rule["always_check"]) and any("cms.gov" in t for t in rule["always_check"])
    assert set(rule["amounts"].values()) == {None}
    assert rule["last_verified"] == "2026-11-15"


def test_new_texts_have_no_promises():
    rule = next(r for r in load_rules()["rules"] if r["id"] == "disability_medicare_ssi")
    texts = [rule["summary"], rule["result_description"], rule["unlikely_description"], rule["amounts_note"],
             *rule["always_check"], *[c["check"] for c in rule["conditions"]],
             *[c.get("fail_text", "") for c in rule["conditions"]]]
    joined = " ".join(texts).lower()
    for word in ("guaranteed", "you will qualify", "you'll qualify", "you will receive", "definitely"):
        assert word not in joined, word


def test_memory_help_counts_for_tax_credit_and_pcafc():
    tax = by_id(screen({"needs_help_daily_activities": False, "needs_daily_help_memory": True,
                        "lives_with_caregiver_over_half_year": True, "caregiver_provides_over_half_support": True,
                        "caregiver_works": True}, today=TODAY))["dependent_care_credit"]
    assert tax["status"] == POSSIBLE
    pcafc = by_id(screen({**PCAFC_VETERAN, "needs_help_daily_activities": False, "needs_daily_help_memory": True},
                         today=TODAY))["va_caregiver_pcafc"]
    assert pcafc["status"] == NEEDS_CHECK and pcafc["reasons"] == []


@pytest.mark.parametrize("rule", load_rules()["rules"], ids=lambda r: r["id"])
def test_input_fields_list_every_field_used(rule):
    used = set()
    def walk(c):
        if "field" in c:
            used.add(c["field"])
        for sub in c.get("any", []) + c.get("all", []):
            walk(sub)
    for c in rule["conditions"]:
        walk(c)
    assert used <= set(rule["input_fields"]), used - set(rule["input_fields"])
