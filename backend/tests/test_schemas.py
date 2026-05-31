"""
Unit tests for Pydantic schemas in app.schemas.
No database required.
"""
import uuid
from datetime import datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.schemas import (
    UserCreate,
    UserLogin,
    TokenOut,
    AlertOut,
    AlertMarkRead,
    SubfundCreate,
    SubfundUpdate,
    SubfundOut,
    FundCreate,
    FundOut,
    TFICreate,
    TFIOut,
    AlertRuleCreate,
    AlertRuleUpdate,
    AlertRuleOut,
)


# ─── Auth schemas ─────────────────────────────────────────────────────────────

class TestUserCreate:
    def test_valid(self):
        u = UserCreate(email="user@example.com", password="secret")
        assert u.email == "user@example.com"
        assert u.password == "secret"

    def test_local_domain_accepted(self):
        # admin@fundtracker.local must not be rejected (str, not EmailStr)
        u = UserCreate(email="admin@fundtracker.local", password="admin123")
        assert u.email == "admin@fundtracker.local"

    def test_missing_password_raises(self):
        with pytest.raises(ValidationError):
            UserCreate(email="x@y.com")

    def test_missing_email_raises(self):
        with pytest.raises(ValidationError):
            UserCreate(password="secret")


class TestUserLogin:
    def test_valid(self):
        u = UserLogin(email="u@e.pl", password="pw")
        assert u.password == "pw"


class TestTokenOut:
    def test_default_token_type(self):
        t = TokenOut(access_token="abc123")
        assert t.token_type == "bearer"

    def test_custom_token_type(self):
        t = TokenOut(access_token="abc", token_type="other")
        assert t.token_type == "other"


# ─── AlertOut ─────────────────────────────────────────────────────────────────

def _make_alert_out(**overrides):
    base = dict(
        id=uuid.uuid4(),
        fund_id=uuid.uuid4(),
        alert_type="new_position",
        company_name="Allegro",
        ticker=None,
        change_pct=None,
        old_weight=Decimal("0"),
        new_weight=Decimal("5.0"),
        message="Nowa pozycja: Allegro (5.00%)",
        is_read=False,
        created_at=datetime.utcnow(),
    )
    base.update(overrides)
    return AlertOut(**base)


class TestAlertOut:
    def test_valid(self):
        a = _make_alert_out()
        assert a.alert_type == "new_position"

    def test_is_read_defaults_false(self):
        assert _make_alert_out().is_read is False

    def test_nullable_fields_accept_none(self):
        a = _make_alert_out(ticker=None, change_pct=None, old_weight=None, new_weight=None)
        assert a.ticker is None

    def test_decimal_weights_preserved(self):
        a = _make_alert_out(old_weight=Decimal("2.5"), new_weight=Decimal("7.0"))
        assert a.old_weight == Decimal("2.5")
        assert a.new_weight == Decimal("7.0")

    def test_missing_required_field_raises(self):
        with pytest.raises(ValidationError):
            AlertOut(fund_id=uuid.uuid4(), alert_type="new_position")  # missing id, message, etc.


class TestAlertMarkRead:
    def test_empty_ids(self):
        a = AlertMarkRead(ids=[])
        assert a.ids == []

    def test_uuid_list(self):
        ids = [uuid.uuid4(), uuid.uuid4()]
        a = AlertMarkRead(ids=ids)
        assert len(a.ids) == 2


# ─── Subfund schemas ──────────────────────────────────────────────────────────

class TestSubfundCreate:
    def test_name_only(self):
        s = SubfundCreate(name="PKO Akcji")
        assert s.ticker is None
        assert s.description is None

    def test_full(self):
        s = SubfundCreate(name="PKO Akcji", ticker="PKO1", description="Fundusz akcji")
        assert s.ticker == "PKO1"

    def test_missing_name_raises(self):
        with pytest.raises(ValidationError):
            SubfundCreate()


class TestSubfundUpdate:
    def test_all_optional(self):
        s = SubfundUpdate()
        assert s.name is None
        assert s.ticker is None

    def test_partial_update(self):
        s = SubfundUpdate(ticker="NEW")
        assert s.ticker == "NEW"
        assert s.name is None


class TestSubfundOut:
    def test_from_attributes(self):
        from unittest.mock import MagicMock
        m = MagicMock()
        m.id = uuid.uuid4()
        m.name = "Test Fund"
        m.ticker = "TF"
        m.description = None
        m.tfi_id = None
        m.fund_id = None
        m.created_at = datetime.utcnow()

        s = SubfundOut.model_validate(m)
        assert s.name == "Test Fund"
        assert s.ticker == "TF"

    def test_optional_fields_default_none(self):
        from unittest.mock import MagicMock
        m = MagicMock()
        m.id = uuid.uuid4()
        m.name = "F"
        m.ticker = None
        m.description = None
        m.tfi_id = None
        m.fund_id = None
        m.created_at = datetime.utcnow()

        s = SubfundOut.model_validate(m)
        assert s.tfi_id is None
        assert s.fund_id is None


# ─── Fund schemas ─────────────────────────────────────────────────────────────

class TestFundCreate:
    def test_without_tfi(self):
        f = FundCreate(name="PKO TFI")
        assert f.tfi_id is None

    def test_with_tfi(self):
        tid = uuid.uuid4()
        f = FundCreate(name="PKO TFI", tfi_id=tid)
        assert f.tfi_id == tid

    def test_missing_name_raises(self):
        with pytest.raises(ValidationError):
            FundCreate()


class TestFundOut:
    def test_default_subfund_count(self):
        f = FundOut(id=uuid.uuid4(), name="F", tfi_id=None, created_at=datetime.utcnow())
        assert f.subfund_count == 0


# ─── TFI schemas ─────────────────────────────────────────────────────────────

class TestTFICreate:
    def test_valid(self):
        t = TFICreate(name="PKO TFI SA")
        assert t.name == "PKO TFI SA"

    def test_missing_name_raises(self):
        with pytest.raises(ValidationError):
            TFICreate()


class TestTFIOut:
    def test_default_subfund_count(self):
        t = TFIOut(id=uuid.uuid4(), name="T", created_at=datetime.utcnow())
        assert t.subfund_count == 0


# ─── AlertRule schemas ────────────────────────────────────────────────────────

class TestAlertRuleCreate:
    def test_defaults(self):
        r = AlertRuleCreate(name="Duże zmiany")
        assert r.is_active is True
        assert r.track_new is True
        assert r.track_closed is True
        assert r.track_increases is True
        assert r.track_decreases is True
        assert r.min_weight_pp == Decimal("2.0")
        assert r.min_rel_pct == Decimal("20.0")
        assert r.fund_id is None

    def test_custom_thresholds(self):
        r = AlertRuleCreate(name="R", min_weight_pp=Decimal("5.0"), min_rel_pct=Decimal("50.0"))
        assert r.min_weight_pp == Decimal("5.0")

    def test_scoped_to_fund(self):
        fid = uuid.uuid4()
        r = AlertRuleCreate(name="R", fund_id=fid)
        assert r.fund_id == fid

    def test_missing_name_raises(self):
        with pytest.raises(ValidationError):
            AlertRuleCreate()


class TestAlertRuleUpdate:
    def test_all_optional(self):
        r = AlertRuleUpdate()
        assert r.name is None
        assert r.is_active is None

    def test_partial(self):
        r = AlertRuleUpdate(is_active=False)
        assert r.is_active is False
        assert r.name is None


class TestAlertRuleOut:
    def _make(self, **overrides):
        base = dict(
            id=uuid.uuid4(),
            name="Duże zmiany",
            is_active=True,
            track_new=True,
            track_closed=True,
            track_increases=True,
            track_decreases=True,
            min_weight_pp=Decimal("2.0"),
            min_rel_pct=Decimal("20.0"),
            fund_id=None,
            created_at=datetime.utcnow(),
        )
        base.update(overrides)
        return AlertRuleOut(**base)

    def test_valid(self):
        r = self._make()
        assert r.name == "Duże zmiany"
        assert r.is_active is True

    def test_fund_id_optional(self):
        assert self._make(fund_id=None).fund_id is None
        fid = uuid.uuid4()
        assert self._make(fund_id=fid).fund_id == fid

    def test_decimal_thresholds_preserved(self):
        r = self._make(min_weight_pp=Decimal("5.5"), min_rel_pct=Decimal("33.3"))
        assert r.min_weight_pp == Decimal("5.5")
        assert r.min_rel_pct == Decimal("33.3")

    def test_from_attributes(self):
        from unittest.mock import MagicMock
        m = MagicMock()
        m.id = uuid.uuid4()
        m.name = "Rule"
        m.is_active = False
        m.track_new = True
        m.track_closed = False
        m.track_increases = True
        m.track_decreases = False
        m.min_weight_pp = Decimal("1.0")
        m.min_rel_pct = Decimal("10.0")
        m.fund_id = None
        m.created_at = datetime.utcnow()
        r = AlertRuleOut.model_validate(m)
        assert r.is_active is False
        assert r.track_closed is False


# ─── UserOut ──────────────────────────────────────────────────────────────────

from app.schemas import UserOut  # noqa: E402


class TestUserOut:
    def test_valid(self):
        u = UserOut(id=str(uuid.uuid4()), email="user@example.com")
        assert u.email == "user@example.com"

    def test_from_attributes(self):
        from unittest.mock import MagicMock
        m = MagicMock()
        m.id = str(uuid.uuid4())  # UserOut.id is str, not UUID
        m.email = "admin@fundtracker.local"
        u = UserOut.model_validate(m)
        assert u.email == "admin@fundtracker.local"

    def test_id_is_string(self):
        u = UserOut(id="dev-user", email="dev@local")
        assert u.id == "dev-user"

    def test_missing_email_raises(self):
        with pytest.raises(ValidationError):
            UserOut(id="x")

    def test_missing_id_raises(self):
        with pytest.raises(ValidationError):
            UserOut(email="x@y.com")


# ─── Upload / bulk schemas ────────────────────────────────────────────────────

from app.schemas import UploadedSubfund, SkippedSubfund, UploadAllResult  # noqa: E402


class TestUploadedSubfund:
    def test_valid(self):
        s = UploadedSubfund(
            fund_id=uuid.uuid4(),
            fund_name="PKO Akcji Plus",
            snapshot_id=uuid.uuid4(),
            snapshot_date=datetime.utcnow().date(),
            position_count=42,
            fund_created=True,
        )
        assert s.fund_name == "PKO Akcji Plus"
        assert s.position_count == 42
        assert s.fund_created is True

    def test_fund_not_created(self):
        s = UploadedSubfund(
            fund_id=uuid.uuid4(),
            fund_name="F",
            snapshot_id=uuid.uuid4(),
            snapshot_date=datetime.utcnow().date(),
            position_count=0,
            fund_created=False,
        )
        assert s.fund_created is False

    def test_missing_required_raises(self):
        with pytest.raises(ValidationError):
            UploadedSubfund(fund_name="F")


class TestSkippedSubfund:
    def test_valid(self):
        s = SkippedSubfund(fund_name="PKO", reason="Duplicate snapshot date")
        assert s.fund_name == "PKO"
        assert s.reason == "Duplicate snapshot date"

    def test_missing_reason_raises(self):
        with pytest.raises(ValidationError):
            SkippedSubfund(fund_name="F")


class TestUploadAllResult:
    def test_empty_lists(self):
        r = UploadAllResult(
            parser_detected="pko_tfi",
            total_subfunds=0,
            created=[],
            skipped=[],
        )
        assert r.total_subfunds == 0
        assert r.created == []
        assert r.skipped == []

    def test_with_items(self):
        created = [
            UploadedSubfund(
                fund_id=uuid.uuid4(),
                fund_name="F",
                snapshot_id=uuid.uuid4(),
                snapshot_date=datetime.utcnow().date(),
                position_count=10,
                fund_created=True,
            )
        ]
        skipped = [SkippedSubfund(fund_name="X", reason="dup")]
        r = UploadAllResult(
            parser_detected="pko_tfi",
            total_subfunds=2,
            created=created,
            skipped=skipped,
        )
        assert len(r.created) == 1
        assert len(r.skipped) == 1


# ─── Search / rankings schemas ────────────────────────────────────────────────

from app.schemas import HoldingPerFund, CompanyHoldings, TopAsset  # noqa: E402


class TestHoldingPerFund:
    def test_valid(self):
        h = HoldingPerFund(
            fund_id=uuid.uuid4(),
            fund_name="PKO Akcji",
            snapshot_id=uuid.uuid4(),
            snapshot_date=datetime.utcnow().date(),
            shares=Decimal("100"),
            value=Decimal("5000.00"),
            weight_pct=Decimal("3.5"),
            currency="PLN",
        )
        assert h.currency == "PLN"
        assert h.weight_pct == Decimal("3.5")

    def test_nullable_fields(self):
        h = HoldingPerFund(
            fund_id=uuid.uuid4(),
            fund_name="F",
            snapshot_id=uuid.uuid4(),
            snapshot_date=datetime.utcnow().date(),
            shares=None,
            value=None,
            weight_pct=None,
            currency="PLN",
        )
        assert h.shares is None
        assert h.value is None
        assert h.weight_pct is None


class TestCompanyHoldings:
    def test_valid_empty_funds(self):
        c = CompanyHoldings(
            company_name="Allegro",
            isin="PLALGR000010",
            ticker="ALE",
            total_shares=Decimal("500"),
            total_value=Decimal("25000"),
            currency="PLN",
            fund_count=2,
            funds=[],
        )
        assert c.company_name == "Allegro"
        assert c.fund_count == 2

    def test_isin_ticker_optional(self):
        c = CompanyHoldings(
            company_name="Unknown",
            isin=None,
            ticker=None,
            total_shares=None,
            total_value=Decimal("1000"),
            currency="PLN",
            fund_count=1,
            funds=[],
        )
        assert c.isin is None
        assert c.ticker is None

    def test_missing_company_name_raises(self):
        with pytest.raises(ValidationError):
            CompanyHoldings(isin="X", fund_count=0, total_value=Decimal("0"), currency="PLN", funds=[])


class TestTopAsset:
    def test_valid(self):
        t = TopAsset(
            rank=1,
            company_name="Allegro",
            isin="PLALGR000010",
            ticker="ALE",
            total_value=Decimal("100000"),
            total_shares=Decimal("2000"),
            fund_count=5,
            currency="PLN",
        )
        assert t.rank == 1
        assert t.total_value == Decimal("100000")

    def test_optional_isin_ticker_shares(self):
        t = TopAsset(
            rank=3,
            company_name="X",
            isin=None,
            ticker=None,
            total_value=Decimal("1000"),
            total_shares=None,
            fund_count=1,
            currency="PLN",
        )
        assert t.isin is None
        assert t.total_shares is None


# ─── Article schemas ──────────────────────────────────────────────────────────

from app.schemas import ArticleCreate, ArticleOut  # noqa: E402


class TestArticleCreate:
    def test_valid_minimal(self):
        a = ArticleCreate(title="Tytuł", content="Treść artykułu")
        assert a.title == "Tytuł"
        assert a.published_at is None

    def test_with_published_at(self):
        now = datetime.utcnow()
        a = ArticleCreate(title="T", content="C", published_at=now)
        assert a.published_at == now

    def test_missing_title_raises(self):
        with pytest.raises(ValidationError):
            ArticleCreate(content="C")

    def test_missing_content_raises(self):
        with pytest.raises(ValidationError):
            ArticleCreate(title="T")


class TestArticleOut:
    def test_valid(self):
        a = ArticleOut(
            id=uuid.uuid4(),
            title="Tytuł",
            content="Treść",
            author="Jan Kowalski",
            published_at=datetime.utcnow(),
            created_at=datetime.utcnow(),
        )
        assert a.title == "Tytuł"
        assert a.author == "Jan Kowalski"

    def test_author_optional(self):
        a = ArticleOut(
            id=uuid.uuid4(),
            title="T",
            content="C",
            author=None,
            published_at=datetime.utcnow(),
            created_at=datetime.utcnow(),
        )
        assert a.author is None

    def test_from_attributes(self):
        from unittest.mock import MagicMock
        m = MagicMock()
        m.id = uuid.uuid4()
        m.title = "Test Article"
        m.content = "Body"
        m.author = None
        m.published_at = datetime.utcnow()
        m.created_at = datetime.utcnow()
        a = ArticleOut.model_validate(m)
        assert a.title == "Test Article"
