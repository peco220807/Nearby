from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db import Base, engine, SessionLocal
from app import models
from app.schemas import HouseholdCreate, HouseholdOut, ExpenseCreate, CareEntryCreate

app = FastAPI(title="Nearby API")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_household_or_404(token: str, db: Session) -> models.Household:
    household = db.query(models.Household).filter_by(share_token=token).first()
    if household is None:
        raise HTTPException(status_code=404, detail="Семья не найдена")
    return household


@app.on_event("startup")
def create_tables():
    Base.metadata.create_all(bind=engine)


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
        raise HTTPException(status_code=400, detail="Участник не из этой семьи")

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
    base, remainder = divmod(data.amount_cents, len(member_ids))
    for mid in member_ids:
        share = base + (remainder if mid == data.paid_by_id else 0)
        db.add(models.ExpenseShare(expense_id=expense.id, member_id=mid, share_cents=share))

    db.commit()
    return {"id": expense.id}


@app.post("/households/{token}/care-entries", status_code=201)
def add_care_entry(token: str, data: CareEntryCreate, db: Session = Depends(get_db)):
    household = get_household_or_404(token, db)
    if data.member_id not in {m.id for m in household.members}:
        raise HTTPException(status_code=400, detail="Участник не из этой семьи")

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