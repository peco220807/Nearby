import pytest

from app.balance import (
    ExpenseData,
    MemberBalance,
    Transfer,
    help_shares,
    compute_balances,
    compute_transfers,
    split_equal,
)


def expense(payer, amount, members):
    return ExpenseData(payer, amount, split_equal(amount, members, payer))


# --- split_equal -----------------------------------------------------------

def test_split_even():
    assert split_equal(900, [1, 2, 3], 1) == {1: 300, 2: 300, 3: 300}


def test_split_remainder_goes_to_payer():
    shares = split_equal(1000, [1, 2, 3], 2)
    assert shares == {1: 333, 2: 334, 3: 333}
    assert sum(shares.values()) == 1000


def test_split_amount_smaller_than_members():
    assert split_equal(2, [1, 2, 3], 3) == {1: 0, 2: 0, 3: 2}


def test_split_empty_members_raises():
    with pytest.raises(ValueError):
        split_equal(100, [], 1)


def test_split_foreign_payer_raises():
    with pytest.raises(ValueError):
        split_equal(100, [1, 2], 99)


# --- compute_balances ------------------------------------------------------

def test_balances_single_expense():
    result = compute_balances([1, 2, 3], [expense(1, 900, [1, 2, 3])])
    assert result == [
        MemberBalance(1, 900, 300, 600),
        MemberBalance(2, 0, 300, -300),
        MemberBalance(3, 0, 300, -300),
    ]


def test_balances_with_remainder_sum_to_zero():
    members = [1, 2, 3]
    result = compute_balances(members, [expense(1, 1000, members), expense(2, 101, members)])
    by_id = {b.member_id: b for b in result}
    assert by_id[1] == MemberBalance(1, 1000, 334 + 33, 1000 - 367)
    assert by_id[2] == MemberBalance(2, 101, 333 + 35, 101 - 368)
    assert by_id[3] == MemberBalance(3, 0, 333 + 33, -366)
    assert sum(b.net_cents for b in result) == 0


def test_balances_no_expenses():
    assert compute_balances([1, 2], []) == [MemberBalance(1, 0, 0, 0), MemberBalance(2, 0, 0, 0)]


def test_balances_empty_household():
    assert compute_balances([], []) == []


# --- compute_transfers -----------------------------------------------------

def apply(balances, transfers):
    net = {b.member_id: b.net_cents for b in balances}
    for t in transfers:
        assert t.amount_cents > 0
        net[t.from_id] += t.amount_cents
        net[t.to_id] -= t.amount_cents
    return net


def test_transfers_two_debtors_one_creditor():
    balances = compute_balances([1, 2, 3], [expense(1, 900, [1, 2, 3])])
    assert compute_transfers(balances) == [Transfer(2, 1, 300), Transfer(3, 1, 300)]


def test_transfers_greedy_largest_first():
    balances = [
        MemberBalance(1, 0, 0, 500),
        MemberBalance(2, 0, 0, 200),
        MemberBalance(3, 0, 0, -600),
        MemberBalance(4, 0, 0, -100),
    ]
    transfers = compute_transfers(balances)
    assert transfers == [Transfer(3, 1, 500), Transfer(3, 2, 100), Transfer(4, 2, 100)]
    assert all(v == 0 for v in apply(balances, transfers).values())


def test_transfers_with_remainder_settle_to_zero():
    members = [1, 2, 3]
    balances = compute_balances(members, [expense(1, 1000, members), expense(2, 101, members)])
    transfers = compute_transfers(balances)
    assert all(v == 0 for v in apply(balances, transfers).values())
    assert len(transfers) <= len(members) - 1


def test_transfers_all_settled():
    assert compute_transfers([MemberBalance(1, 0, 0, 0), MemberBalance(2, 0, 0, 0)]) == []


def test_transfers_empty_household():
    assert compute_transfers([]) == []


def test_transfers_unbalanced_raises():
    with pytest.raises(ValueError):
        compute_transfers([MemberBalance(1, 0, 0, 100)])


# --- help_shares -----------------------------------------------------------

def test_help_shares_percent():
    assert help_shares([1, 2, 3], [(1, 3.0), (2, 1.0), (1, 4.0)]) == {1: 87.5, 2: 12.5, 3: 0.0}


def test_help_shares_rounding():
    assert help_shares([1, 2, 3], [(1, 1), (2, 1), (3, 1)]) == {1: 33.3, 2: 33.3, 3: 33.3}


def test_help_shares_no_hours_returns_empty():
    assert help_shares([1, 2], []) == {}


def test_help_shares_empty_household():
    assert help_shares([], []) == {}


# --- несколько расходов от разных участников -------------------------------

def test_multiple_payers_balances_and_transfers():
    members = [1, 2, 3, 4]
    expenses = [
        expense(1, 10_000, members),  # 2500 каждому
        expense(2, 3_001, members),   # 750 ×3, плательщику 751
        expense(3, 999, members),     # 249 ×3, плательщику 252
    ]
    balances = compute_balances(members, expenses)
    by_id = {b.member_id: b for b in balances}
    assert by_id[1] == MemberBalance(1, 10_000, 2500 + 750 + 249, 10_000 - 3499)
    assert by_id[2] == MemberBalance(2, 3_001, 2500 + 751 + 249, 3_001 - 3500)
    assert by_id[3] == MemberBalance(3, 999, 2500 + 750 + 252, 999 - 3502)
    assert by_id[4] == MemberBalance(4, 0, 2500 + 750 + 249, -3499)
    assert sum(b.net_cents for b in balances) == 0

    transfers = compute_transfers(balances)
    assert transfers == [Transfer(4, 1, 3499), Transfer(3, 1, 2503), Transfer(2, 1, 499)]
    assert all(v == 0 for v in apply(balances, transfers).values())
