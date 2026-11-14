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
    r = client.post("/households", json={"name": "Семья", "member_names": names})
    assert r.status_code == 201
    data = r.json()
    return data["share_token"], [m["id"] for m in data["members"]]


def test_balance_endpoint(client):
    token, (a, b, c) = create_family(client, ["А", "Б", "В"])
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
        {"member_id": a, "name": "А", "paid_cents": 1000, "owed_cents": 400, "net_cents": 600},
        {"member_id": b, "name": "Б", "paid_cents": 200, "owed_cents": 401, "net_cents": -201},
        {"member_id": c, "name": "В", "paid_cents": 0, "owed_cents": 399, "net_cents": -399},
    ]
    assert body["transfers"] == [
        {"from_id": c, "to_id": a, "amount_cents": 399},
        {"from_id": b, "to_id": a, "amount_cents": 201},
    ]
    assert body["help_share_percent"] == {str(a): 75.0, str(b): 0.0, str(c): 25.0}


def test_balance_endpoint_without_hours(client):
    token, _ = create_family(client, ["А", "Б"])
    body = client.get(f"/households/{token}/balance").json()
    assert body["help_share_percent"] == {}
    assert body["transfers"] == []
    assert all(m["net_cents"] == 0 for m in body["members"])


def test_old_care_entries_path_removed(client):
    token, (a, _) = create_family(client, ["А", "Б"])
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
    assert va["status"] == "скорее не подходит"
    assert {"status", "to_check", "documents", "source_url", "last_verified"} <= va.keys()


def test_eligibility_screen_empty_body(client):
    r = client.post("/eligibility/screen", json={})
    assert r.status_code == 200
    assert all(p["status"] == "нужна проверка" for p in r.json()["programs"])


def test_eligibility_screen_rejects_bad_state(client):
    assert client.post("/eligibility/screen", json={"state": "XX"}).status_code == 422
    assert client.post("/eligibility/screen", json={"net_worth_cents": -1}).status_code == 422
