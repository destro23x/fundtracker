import uuid
from datetime import datetime, date
from decimal import Decimal
from pydantic import BaseModel


# --- Auth ---

class UserCreate(BaseModel):
    email: str
    password: str


class UserLogin(BaseModel):
    email: str
    password: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    id: str
    email: str

    model_config = {"from_attributes": True}


# --- Subfund (subfundusz / leaf) ---

class SubfundCreate(BaseModel):
    name: str
    ticker: str | None = None
    description: str | None = None


class SubfundUpdate(BaseModel):
    name: str | None = None
    ticker: str | None = None
    description: str | None = None


class SubfundOut(BaseModel):
    id: uuid.UUID
    name: str
    ticker: str | None
    description: str | None
    tfi_id: uuid.UUID | None = None
    fund_id: uuid.UUID | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


# --- Alert ---

class AlertOut(BaseModel):
    id: uuid.UUID
    fund_id: uuid.UUID
    alert_type: str
    company_name: str | None
    ticker: str | None
    change_pct: Decimal | None
    old_weight: Decimal | None
    new_weight: Decimal | None
    message: str
    is_read: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class AlertMarkRead(BaseModel):
    ids: list[uuid.UUID]


# --- Alert Rules ---

class AlertRuleCreate(BaseModel):
    name: str
    is_active: bool = True
    track_new: bool = True
    track_closed: bool = True
    track_increases: bool = True
    track_decreases: bool = True
    min_weight_pp: Decimal = Decimal("2.0")
    min_rel_pct: Decimal = Decimal("20.0")
    fund_id: uuid.UUID | None = None


class AlertRuleUpdate(BaseModel):
    name: str | None = None
    is_active: bool | None = None
    track_new: bool | None = None
    track_closed: bool | None = None
    track_increases: bool | None = None
    track_decreases: bool | None = None
    min_weight_pp: Decimal | None = None
    min_rel_pct: Decimal | None = None
    fund_id: uuid.UUID | None = None


class AlertRuleOut(BaseModel):
    id: uuid.UUID
    name: str
    is_active: bool
    track_new: bool
    track_closed: bool
    track_increases: bool
    track_decreases: bool
    min_weight_pp: Decimal
    min_rel_pct: Decimal
    fund_id: uuid.UUID | None
    created_at: datetime

    model_config = {"from_attributes": True}


# --- Upload-all (bulk import subfunds) ---

class UploadedSubfund(BaseModel):
    fund_id: uuid.UUID
    fund_name: str
    snapshot_id: uuid.UUID
    snapshot_date: date
    position_count: int
    fund_created: bool  # True jeśli fundusz został auto-utworzony


class SkippedSubfund(BaseModel):
    fund_name: str
    reason: str


class UploadAllResult(BaseModel):
    parser_detected: str
    total_subfunds: int
    created: list[UploadedSubfund]
    skipped: list[SkippedSubfund]


# --- Wyszukiwanie po spółce (agregacja across funduszy) ---

class HoldingPerFund(BaseModel):
    fund_id: uuid.UUID
    fund_name: str
    snapshot_id: uuid.UUID
    snapshot_date: date
    shares: Decimal | None
    value: Decimal | None
    weight_pct: Decimal | None
    currency: str


class CompanyHoldings(BaseModel):
    company_name: str
    isin: str | None
    ticker: str | None
    total_shares: Decimal | None
    total_value: Decimal | None
    currency: str  # waluta sumowania (PLN jeśli mieszane)
    fund_count: int
    funds: list[HoldingPerFund]


class TopAsset(BaseModel):
    rank: int
    company_name: str
    isin: str | None
    ticker: str | None
    total_value: Decimal
    total_shares: Decimal | None
    fund_count: int
    currency: str


# --- Fund (fundusz parasolowy / umbrella) ---

class FundCreate(BaseModel):
    name: str
    tfi_id: uuid.UUID | None = None


class FundOut(BaseModel):
    id: uuid.UUID
    name: str
    tfi_id: uuid.UUID | None
    created_at: datetime
    subfund_count: int = 0

    model_config = {"from_attributes": True}


# --- TFI ---

class TFICreate(BaseModel):
    name: str


class TFIOut(BaseModel):
    id: uuid.UUID
    name: str
    created_at: datetime
    subfund_count: int = 0

    model_config = {"from_attributes": True}


# --- Artykuły ---

class ArticleCreate(BaseModel):
    title: str
    content: str
    published_at: datetime | None = None


class ArticleOut(BaseModel):
    id: uuid.UUID
    title: str
    content: str
    author: str | None
    published_at: datetime
    created_at: datetime

    model_config = {"from_attributes": True}
