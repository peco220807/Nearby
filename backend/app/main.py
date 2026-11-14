import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from app.db import Base, engine, SessionLocal
from app import models
from app.balance import ExpenseData, split_equal, compute_balances, compute_transfers, help_shares
from app.eligibility.screen import screen
from app.scenarios.calculator import calculate, load_defaults
from app.schemas import (
    HouseholdCreate, HouseholdOut, ExpenseCreate, HelpHoursCreate, BalanceOut, ScreeningAnswers, ScreeningResult,
    ScenarioRequest, ScenariosResponse,
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(title="Nearby API", lifespan=lifespan)

# Фронтенд (Vite) работает на другом порту — разрешаем ему обращаться к API
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("FRONTEND_ORIGINS", "http://localhost:5173").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_household_or_404(token: str, db: Session) -> models.Household:
    household = db.query(models.Household).filter_by(share_token=token).first()
    if household is None:
        raise HTTPException(status_code=404, detail="Household not found")
    return household


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/households", response_model=HouseholdOut, status_code=201)
def create_household(data: HouseholdCreate, db: Session = Depends(get_db)):
    household = models.Household(name=data.name, parent_name=data.parent_name)
    household.members = [models.Member(name=n) for n in data.member_names]
    db.add(household)
    db.commit()
    db.refresh(household)
    return household


@app.get("/households/{token}", response_model=HouseholdOut)
def get_household(token: str, db: Session = Depends(get_db)):
    return get_household_or_404(token, db)


@app.post("/households/{token}/expenses", status_code=201)
def add_expense(token: str, data: ExpenseCreate, db: Session = Depends(get_db)):
    household = get_household_or_404(token, db)
    member_ids = sorted(m.id for m in household.members)
    if data.paid_by_id not in member_ids:
        raise HTTPException(status_code=400, detail="Member does not belong to this household")

    expense = models.Expense(
        household_id=household.id,
        paid_by_id=data.paid_by_id,
        amount_cents=data.amount_cents,
        category=data.category,
        description=data.description,
        expense_date=data.expense_date,
        split_mode="equal",
    )
    db.add(expense)
    db.flush()

    # Делим поровну; остаток в центах отдаём тому, кто заплатил
    for mid, share in split_equal(data.amount_cents, member_ids, data.paid_by_id).items():
        db.add(models.ExpenseShare(expense_id=expense.id, member_id=mid, share_cents=share))

    db.commit()
    return {"id": expense.id}


@app.post("/households/{token}/help-hours", status_code=201)
def add_help_hours(token: str, data: HelpHoursCreate, db: Session = Depends(get_db)):
    household = get_household_or_404(token, db)
    if data.member_id not in {m.id for m in household.members}:
        raise HTTPException(status_code=400, detail="Member does not belong to this household")

    entry = models.CareEntry(
        household_id=household.id,
        member_id=data.member_id,
        hours=data.hours,
        entry_date=data.entry_date,
        note=data.note,
    )
    db.add(entry)
    db.commit()
    return {"id": entry.id}


@app.get("/households/{token}/balance", response_model=BalanceOut)
def get_balance(token: str, db: Session = Depends(get_db)):
    household = get_household_or_404(token, db)
    names = {m.id: m.name for m in household.members}

    expense_rows = db.query(models.Expense).filter_by(household_id=household.id).all()
    shares: dict[int, dict[int, int]] = {e.id: {} for e in expense_rows}
    share_rows = (
        db.query(models.ExpenseShare)
        .join(models.Expense, models.Expense.id == models.ExpenseShare.expense_id)
        .filter(models.Expense.household_id == household.id)
        .all()
    )
    for s in share_rows:
        shares[s.expense_id][s.member_id] = s.share_cents
    expenses = [ExpenseData(e.paid_by_id, e.amount_cents, shares[e.id]) for e in expense_rows]

    help_rows = db.query(models.CareEntry).filter_by(household_id=household.id).all()

    balances = compute_balances(names, expenses)
    return {
        "members": [{**vars(b), "name": names[b.member_id]} for b in balances],
        "transfers": [vars(t) for t in compute_transfers(balances)],
        "help_share_percent": help_shares(names, [(c.member_id, c.hours) for c in help_rows]),
    }


@app.post("/eligibility/screen", response_model=ScreeningResult)
def eligibility_screen(answers: ScreeningAnswers):
    return screen(answers.model_dump())


@app.post("/scenarios/calculate", response_model=ScenariosResponse)
def scenarios_calculate(data: ScenarioRequest):
    defaults = load_defaults()
    return {
        "disclaimer": defaults["disclaimer"],
        "scenarios": calculate(
            savings_cents=data.savings_cents,
            monthly_income_cents=data.monthly_income_cents,
            scenarios=defaults["scenarios"],
            home_care_hourly_cents=data.home_care_hourly_cents,
            home_care_hours_per_week=data.home_care_hours_per_week,
            include_disabled=data.include_disabled,
        ),
    }
