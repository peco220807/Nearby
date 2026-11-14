"""Скрининг льгот: правила — данные (rules.json), здесь только их вычисление.

Каждое условие даёт True / False / None (не хватает данных или сумма не подтверждена).
Статус программы:
- «скорее не подходит» — нарушено условие с on_fail="unlikely" (в reasons идёт его fail_text,
  описание — unlikely_description);
- «нужна проверка»    — есть неизвестные или условие с on_fail="check" не выполнено;
- «возможно»          — все условия выполнены. Гарантий нет никогда.
"""
import json
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Any

POSSIBLE = "возможно"
UNLIKELY = "скорее не подходит"
NEEDS_CHECK = "нужна проверка"

RULES_PATH = Path(__file__).with_name("rules.json")


@lru_cache
def load_rules() -> dict:
    with RULES_PATH.open(encoding="utf-8") as f:
        return json.load(f)


def _amount(rule: dict, key: str, today: date) -> int | None:
    """Сумма из правила; None, если не подтверждена или срок её действия истёк."""
    valid_until = rule.get("amounts_valid_until")
    if valid_until and today > date.fromisoformat(valid_until):
        return None
    return rule.get("amounts", {}).get(key)


def _evaluate(cond: dict, answers: dict[str, Any], rule: dict, today: date) -> bool | None:
    if cond.get("manual"):
        return None  # условие, о котором опрос не спрашивает: всегда «проверить»
    if "all" in cond:
        results = [_evaluate(c, answers, rule, today) for c in cond["all"]]
        if False in results:
            return False
        return None if None in results else True
    if "any" in cond:
        results = [_evaluate(c, answers, rule, today) for c in cond["any"]]
        if True in results:
            return True
        return None if None in results else False

    actual = answers.get(cond["field"])
    expected = _amount(rule, cond["ref"], today) if "ref" in cond else cond["value"]
    if actual is None or expected is None:
        return None
    op = cond["op"]
    if op == "eq":
        return actual == expected
    if op == "lte":
        return actual <= expected
    if op == "gte":
        return actual >= expected
    raise ValueError(f"Неизвестная операция: {op}")


def _applies_to_state(rule: dict, state: str | None) -> bool:
    return rule["state"] is None or state is None or rule["state"] == state


def screen_rule(rule: dict, answers: dict[str, Any], today: date) -> dict:
    status = POSSIBLE
    reasons: list[str] = []   # что уже говорит против
    to_check: list[str] = []  # что проверить

    if rule["state"] is not None and answers.get("state") is None:
        status = NEEDS_CHECK
        to_check.append(f"Программа действует в штате {rule['state']}. Укажите штат родителя.")

    for cond in rule["conditions"]:
        result = _evaluate(cond, answers, rule, today)
        if result is True:
            continue
        if result is False and cond["on_fail"] == "unlikely":
            status = UNLIKELY
            reasons.append(cond["fail_text"])  # отрицательная формулировка, не требование
        else:
            if status == POSSIBLE:
                status = NEEDS_CHECK
            to_check.append(cond["check"])

    to_check.extend(rule.get("always_check", []))

    return {
        "id": rule["id"],
        "name": rule["name"],
        "summary": rule["summary"],
        "status": status,
        "result_description": rule["unlikely_description"] if status == UNLIKELY else rule["result_description"],
        "reasons": reasons,
        "to_check": to_check,
        "documents": rule["documents"],
        "source_url": rule["source_url"],
        "amounts_source_urls": rule["amounts_source_urls"],
        "amounts_note": rule["amounts_note"],
        "amounts_valid_until": rule.get("amounts_valid_until"),
        "last_verified": rule["last_verified"],
    }


def screen(answers: dict[str, Any], rules: list[dict] | None = None, today: date | None = None) -> dict:
    """Ответы опроса → список программ со статусом. Программы чужого штата не показываются."""
    data = load_rules()
    rules = data["rules"] if rules is None else rules
    today = today or date.today()
    state = answers.get("state")
    return {
        "disclaimer": data["disclaimer"],
        "programs": [screen_rule(r, answers, today) for r in rules if _applies_to_state(r, state)],
    }
