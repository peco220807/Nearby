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


class HelpHoursCreate(BaseModel):
    member_id: int
    hours: float = Field(gt=0, le=24)
    entry_date: date
    note: str | None = Field(default=None, max_length=200)

class MemberBalanceOut(BaseModel):
    member_id: int
    name: str
    paid_cents: int
    owed_cents: int
    net_cents: int


class TransferOut(BaseModel):
    from_id: int
    to_id: int
    amount_cents: int


class BalanceOut(BaseModel):
    members: list[MemberBalanceOut]
    transfers: list[TransferOut]
    help_share_percent: dict[int, float]


US_STATES = (
    "AL|AK|AZ|AR|CA|CO|CT|DE|DC|FL|GA|HI|ID|IL|IN|IA|KS|KY|LA|ME|MD|MA|MI|MN|MS|MO|MT|NE|NV|NH|NJ|NM|NY|"
    "NC|ND|OH|OK|OR|PA|RI|SC|SD|TN|TX|UT|VT|VA|WA|WV|WI|WY"
)


class ScreeningAnswers(BaseModel):
    """Ответы опроса о родителе. Любое поле можно не заполнять — тогда «нужна проверка»."""
    state: str | None = Field(default=None, pattern=f"^({US_STATES})$")
    age: int | None = Field(default=None, ge=0, le=130)
    is_veteran: bool | None = None
    is_surviving_spouse_of_veteran: bool | None = None
    wartime_service: bool | None = None
    has_spouse: bool | None = None
    needs_help_daily_activities: bool | None = None
    in_nursing_home: bool | None = None
    annual_income_cents: int | None = Field(default=None, ge=0)
    net_worth_cents: int | None = Field(default=None, ge=0)
    # про того, кто помогает родителю (для налогового кредита)
    lives_with_caregiver_over_half_year: bool | None = None
    caregiver_provides_over_half_support: bool | None = None
    caregiver_works: bool | None = None


class ProgramResult(BaseModel):
    id: str
    name: str
    summary: str
    status: str
    result_description: str
    reasons: list[str]
    to_check: list[str]
    documents: list[str]
    source_url: str
    amounts_source_urls: list[str]
    amounts_note: str
    last_verified: str


class ScreeningResult(BaseModel):
    disclaimer: str
    programs: list[ProgramResult]
