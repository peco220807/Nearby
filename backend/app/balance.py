"""Household balance. Pure functions: no database, integer cents only."""
from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class ExpenseData:
    paid_by_id: int
    amount_cents: int
    shares: dict[int, int]  # member_id -> доля в центах


@dataclass(frozen=True)
class MemberBalance:
    member_id: int
    paid_cents: int   # сколько заплатил
    owed_cents: int   # сколько должен по долям
    net_cents: int    # > 0 — ему должны, < 0 — он должен


@dataclass(frozen=True)
class Transfer:
    from_id: int
    to_id: int
    amount_cents: int


def split_equal(amount_cents: int, member_ids: Iterable[int], payer_id: int) -> dict[int, int]:
    """Splits an amount equally; the payer gets the leftover cents."""
    ids = sorted(member_ids)
    if not ids:
        raise ValueError("No members to split between")
    if payer_id not in ids:
        raise ValueError("Payer is not a member of this household")
    base, remainder = divmod(amount_cents, len(ids))
    return {mid: base + (remainder if mid == payer_id else 0) for mid in ids}


def compute_balances(member_ids: Iterable[int], expenses: Iterable[ExpenseData]) -> list[MemberBalance]:
    ids = sorted(member_ids)
    paid = dict.fromkeys(ids, 0)
    owed = dict.fromkeys(ids, 0)
    for e in expenses:
        paid[e.paid_by_id] += e.amount_cents
        for mid, share in e.shares.items():
            owed[mid] += share
    return [MemberBalance(mid, paid[mid], owed[mid], paid[mid] - owed[mid]) for mid in ids]


def compute_transfers(balances: Iterable[MemberBalance]) -> list[Transfer]:
    """Greedy: the largest debtor pays the largest creditor."""
    balances = list(balances)
    if sum(b.net_cents for b in balances) != 0:
        raise ValueError("Balances do not sum to zero")

    debtors = {b.member_id: -b.net_cents for b in balances if b.net_cents < 0}
    creditors = {b.member_id: b.net_cents for b in balances if b.net_cents > 0}
    transfers: list[Transfer] = []
    while debtors:
        # при равных суммах берём меньший id — результат детерминирован
        d = min(debtors, key=lambda m: (-debtors[m], m))
        c = min(creditors, key=lambda m: (-creditors[m], m))
        amount = min(debtors[d], creditors[c])
        transfers.append(Transfer(d, c, amount))
        for pool, mid in ((debtors, d), (creditors, c)):
            pool[mid] -= amount
            if pool[mid] == 0:
                del pool[mid]
    return transfers


def help_shares(member_ids: Iterable[int], entries: Iterable[tuple[int, float]]) -> dict[int, float]:
    """Share of help hours per member in percent (1 decimal). No hours -> empty dict."""
    hours = dict.fromkeys(sorted(member_ids), 0.0)
    for mid, h in entries:
        hours[mid] += h
    total = sum(hours.values())
    if total <= 0:
        return {}
    return {mid: round(h * 100 / total, 1) for mid, h in hours.items()}
