from pydantic import BaseModel, Field
from datetime import date


class HouseholdCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    parent_name: str | None = Field(default=None, max_length=120)
    member_names: list[str] = Field(min_length=1, max_length=10)


class MemberOut(BaseModel):
    id: int
    name: str
    model_config = {"from_attributes": True}


class HouseholdOut(BaseModel):
    id: int
    name: str
    parent_name: str | None
    share_token: str
    members: list[MemberOut]
    model_config = {"from_attributes": True}

class ExpenseCreate(BaseModel):
    paid_by_id: int
    amount_cents: int = Field(gt=0)
    category: str = Field(pattern="^(medication|care|transport|other)$")
    description: str | None = Field(default=None, max_length=200)
    expense_date: date


class CareEntryCreate(BaseModel):
    member_id: int
    hours: float = Field(gt=0, le=24)
    entry_date: date
    note: str | None = Field(default=None, max_length=200)