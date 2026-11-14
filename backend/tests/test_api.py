import os

os.environ.setdefault("DATABASE_URL", "sqlite://")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base
from app.main import app, get_db


@pytest.fixture
def client():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)

    def override():
        db = Session()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def create_family(client, names):
    r = client.post("/households", json={"name": "Family", "member_names": names})
    assert r.status_code == 201
    data = r.json()
    return data["share_token"], [m["id"] for m in data["members"]]


def test_balance_endpoint(client):
    token, (a, b, c) = create_family(client, ["A", "B", "C"])
    for payer, amount in ((a, 1000), (b, 200)):
        r = client.post(f"/households/{token}/expenses", json={
            "paid_by_id": payer, "amount_cents": amount, "category": "medication", "expense_date": "2026-11-14",
        })
        assert r.status_code == 201
    for member, hours in ((a, 3), (c, 1)):
        r = client.post(f"/households/{token}/help-hours", json={
            "member_id": member, "hours": hours, "entry_date": "2026-11-14",
        })
        assert r.status_code == 201

    r = client.get(f"/households/{token}/balance")
    assert r.status_code == 200
    body = r.json()
    # 1000 → 333/333/334 (остаток плательщику А); 200 → 66/68/66 (остаток Б)
    assert body["members"] == [
        {"member_id": a, "name": "A", "paid_cents": 1000, "owed_cents": 400, "net_cents": 600},
        {"member_id": b, "name": "B", "paid_cents": 200, "owed_cents": 401, "net_cents": -201},
        {"member_id": c, "name": "C", "paid_cents": 0, "owed_cents": 399, "net_cents": -399},
    ]
    assert body["transfers"] == [
        {"from_id": c, "to_id": a, "amount_cents": 399},
        {"from_id": b, "to_id": a, "amount_cents": 201},
    ]
    assert body["help_share_percent"] == {str(a): 75.0, str(b): 0.0, str(c): 25.0}


def test_balance_endpoint_without_hours(client):
    token, _ = create_family(client, ["A", "B"])
    body = client.get(f"/households/{token}/balance").json()
    assert body["help_share_percent"] == {}
    assert body["transfers"] == []
    assert all(m["net_cents"] == 0 for m in body["members"])


def test_old_care_entries_path_removed(client):
    token, (a, _) = create_family(client, ["A", "B"])
    r = client.post(f"/households/{token}/care-entries", json={"member_id": a, "hours": 1, "entry_date": "2026-11-14"})
    assert r.status_code == 404


def test_balance_unknown_token(client):
    assert client.get("/households/nope/balance").status_code == 404


def test_eligibility_screen_endpoint(client):
    r = client.post("/eligibility/screen", json={"state": "TX", "is_veteran": False, "is_surviving_spouse_of_veteran": False})
    assert r.status_code == 200
    body = r.json()
    assert "disclaimer" in body
    va = next(p for p in body["programs"] if p["id"] == "va_aid_attendance")
    assert va["status"] == "unlikely"
    assert {"status", "to_check", "documents", "source_url", "last_verified"} <= va.keys()


def test_eligibility_screen_empty_body(client):
    r = client.post("/eligibility/screen", json={})
    assert r.status_code == 200
    assert all(p["status"] == "needs review" for p in r.json()["programs"])


def test_eligibility_screen_rejects_bad_state(client):
    assert client.post("/eligibility/screen", json={"state": "XX"}).status_code == 422
    assert client.post("/eligibility/screen", json={"net_worth_cents": -1}).status_code == 422


def test_scenarios_calculate_endpoint(client):
    r = client.post("/scenarios/calculate", json={"savings_cents": 10_000_000, "monthly_income_cents": 200_000})
    assert r.status_code == 200
    body = r.json()
    assert body["disclaimer"] == "This is a planning estimate. Actual prices depend on the city and the facility."
    by_id = {s["id"]: s for s in body["scenarios"]}
    assert by_id["assisted_living"]["months_covered"] == 23
    assert by_id["assisted_living"]["monthly_gap_cents"] == 420_000
    assert "memory_care" not in by_id
    assert "nursing_home_private_room" in by_id
    assert {"id", "name", "monthly_cost_cents", "monthly_gap_cents", "months_covered", "status",
            "source_url", "source_name", "as_of", "kind", "note"} <= by_id["assisted_living"].keys()


def test_scenarios_calculate_include_disabled(client):
    r = client.post("/scenarios/calculate", json={"savings_cents": 0, "monthly_income_cents": 0, "include_disabled": True})
    assert "memory_care" in {s["id"] for s in r.json()["scenarios"]}


def test_scenarios_calculate_rejects_negative(client):
    for body in (
        {"savings_cents": -1, "monthly_income_cents": 0},
        {"savings_cents": 0, "monthly_income_cents": -1},
        {"savings_cents": 0, "monthly_income_cents": 0, "home_care_hourly_cents": -1},
        {"savings_cents": 0, "monthly_income_cents": 0, "home_care_hours_per_week": -1},
        {"savings_cents": 0, "monthly_income_cents": 0, "home_care_hours_per_week": 169},
    ):
        assert client.post("/scenarios/calculate", json=body).status_code == 422, body
    assert client.post("/scenarios/calculate", json={}).status_code == 422
