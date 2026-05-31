"""
Unit tests for _generate_alerts and _make_alert_id in app.api.alerts.

Architecture note: alerts are generated on-the-fly from PortfolioComposition rows
(not from a separate alert_generator service — that was removed). No database
required — rows are MagicMock instances with the required attributes.
"""
import uuid
from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from app.api.alerts import _generate_alerts, _make_alert_id, _THRESHOLD

# ─── helpers ────────────────────────────────────────────────────────────────

SUBFUND = "PKO Akcji Plus"
FUND_ID = uuid.uuid4()
UUID_MAP = {SUBFUND: FUND_ID}

DATE_OLD = date(2024, 1, 1)
DATE_NEW = date(2024, 2, 1)


def make_row(
    company_name: str = "Allegro",
    snapshot_date=DATE_NEW,
    subfund_name: str = SUBFUND,
    umbrella_name: str | None = None,
    isin: str | None = None,
    weight_pct=None,
) -> MagicMock:
    r = MagicMock()
    r.subfund_name = subfund_name
    r.umbrella_name = umbrella_name
    r.snapshot_date = snapshot_date
    r.company_name = company_name
    r.isin = isin
    r.weight_pct = Decimal(str(weight_pct)) if weight_pct is not None else None
    return r


# ─── basic alert types ───────────────────────────────────────────────────────

class TestAlertTypes:
    def test_new_position_detected(self):
        rows = [
            make_row("Existing", DATE_OLD, weight_pct=2.0),
            make_row("Existing", DATE_NEW, weight_pct=2.0),
            make_row("NewCo", DATE_NEW, weight_pct=5.0),
        ]
        alerts = _generate_alerts(rows, UUID_MAP, limit=100)
        assert any(a.alert_type == "new_position" and a.company_name == "NewCo" for a in alerts)

    def test_closed_position_detected(self):
        rows = [
            make_row("OldCo", DATE_OLD, weight_pct=3.0),
            make_row("Anchor", DATE_OLD, weight_pct=1.0),
            make_row("Anchor", DATE_NEW, weight_pct=1.0),
        ]
        alerts = _generate_alerts(rows, UUID_MAP, limit=100)
        assert any(a.alert_type == "closed_position" and a.company_name == "OldCo" for a in alerts)

    def test_position_increase_above_threshold(self):
        rows = [
            make_row("X", DATE_OLD, weight_pct=2.0),
            make_row("X", DATE_NEW, weight_pct=4.0),  # +2pp > _THRESHOLD
        ]
        alerts = _generate_alerts(rows, UUID_MAP, limit=100)
        assert len(alerts) == 1
        assert alerts[0].alert_type == "position_increase"

    def test_position_decrease_above_threshold(self):
        rows = [
            make_row("X", DATE_OLD, weight_pct=5.0),
            make_row("X", DATE_NEW, weight_pct=2.0),  # −3pp
        ]
        alerts = _generate_alerts(rows, UUID_MAP, limit=100)
        assert len(alerts) == 1
        assert alerts[0].alert_type == "position_decrease"

    def test_change_below_threshold_no_alert(self):
        # _THRESHOLD = 0.005 → change of 0.001 is silent
        rows = [
            make_row("X", DATE_OLD, weight_pct=5.000),
            make_row("X", DATE_NEW, weight_pct=5.001),
        ]
        alerts = _generate_alerts(rows, UUID_MAP, limit=100)
        assert alerts == []

    def test_unchanged_position_no_alert(self):
        rows = [
            make_row("X", DATE_OLD, weight_pct=3.0),
            make_row("X", DATE_NEW, weight_pct=3.0),
        ]
        alerts = _generate_alerts(rows, UUID_MAP, limit=100)
        assert alerts == []


# ─── edge cases ──────────────────────────────────────────────────────────────

class TestEdgeCases:
    def test_empty_rows_returns_empty(self):
        assert _generate_alerts([], UUID_MAP, limit=100) == []

    def test_only_one_date_no_diff_possible(self):
        rows = [make_row("X", DATE_NEW, weight_pct=5.0)]
        assert _generate_alerts(rows, UUID_MAP, limit=100) == []

    def test_null_snapshot_date_skipped(self):
        rows = [
            make_row("X", None, weight_pct=5.0),
            make_row("X", DATE_NEW, weight_pct=5.0),
        ]
        assert _generate_alerts(rows, UUID_MAP, limit=100) == []

    def test_subfund_not_in_uuid_map_skipped(self):
        rows = [
            make_row("X", DATE_OLD, subfund_name="Unknown Fund", weight_pct=2.0),
            make_row("X", DATE_NEW, subfund_name="Unknown Fund", weight_pct=5.0),
        ]
        assert _generate_alerts(rows, UUID_MAP, limit=100) == []

    def test_umbrella_name_used_when_subfund_name_none(self):
        fund_id = uuid.uuid4()
        rows = [
            make_row("X", DATE_OLD, subfund_name=None, umbrella_name="UmbrellaFund", weight_pct=2.0),
            make_row("X", DATE_NEW, subfund_name=None, umbrella_name="UmbrellaFund", weight_pct=5.0),
        ]
        alerts = _generate_alerts(rows, {"UmbrellaFund": fund_id}, limit=100)
        assert len(alerts) == 1
        assert alerts[0].fund_id == fund_id

    def test_null_weight_pct_treated_as_zero(self):
        # New position with weight_pct=None → treated as 0 old weight → change_pct is None
        rows = [
            make_row("Existing", DATE_OLD, weight_pct=1.0),
            make_row("Existing", DATE_NEW, weight_pct=1.0),
            make_row("NewCo", DATE_NEW, weight_pct=None),
        ]
        alerts = _generate_alerts(rows, UUID_MAP, limit=100)
        new_alerts = [a for a in alerts if a.alert_type == "new_position"]
        assert len(new_alerts) == 1

    def test_limit_caps_result(self):
        rows = []
        for i in range(30):
            rows.append(make_row(f"Co{i}", DATE_OLD, weight_pct=2.0))
            rows.append(make_row(f"Co{i}", DATE_NEW, weight_pct=6.0))
        alerts = _generate_alerts(rows, UUID_MAP, limit=5)
        assert len(alerts) == 5


# ─── ISIN keying ─────────────────────────────────────────────────────────────

class TestIsinKeying:
    def test_isin_used_as_key_when_present(self):
        rows = [
            make_row("Allegro", DATE_OLD, isin="PL0001", weight_pct=2.0),
            make_row("Allegro", DATE_NEW, isin="PL0001", weight_pct=5.0),
        ]
        alerts = _generate_alerts(rows, UUID_MAP, limit=100)
        assert any(a.alert_type == "position_increase" for a in alerts)

    def test_isin_case_insensitive(self):
        rows = [
            make_row("X", DATE_OLD, isin="pl0001", weight_pct=2.0),
            make_row("X", DATE_NEW, isin="PL0001", weight_pct=5.0),  # upper vs lower
        ]
        alerts = _generate_alerts(rows, UUID_MAP, limit=100)
        assert any(a.alert_type == "position_increase" for a in alerts)


# ─── alert fields ────────────────────────────────────────────────────────────

class TestAlertFields:
    def test_fund_id_correct(self):
        rows = [make_row("X", DATE_OLD, weight_pct=2.0), make_row("X", DATE_NEW, weight_pct=5.0)]
        alerts = _generate_alerts(rows, UUID_MAP, limit=100)
        assert alerts[0].fund_id == FUND_ID

    def test_message_contains_company_name(self):
        rows = [make_row("KGHM", DATE_OLD, weight_pct=2.0), make_row("KGHM", DATE_NEW, weight_pct=5.0)]
        alerts = _generate_alerts(rows, UUID_MAP, limit=100)
        assert "KGHM" in alerts[0].message

    def test_new_position_change_pct_none(self):
        """New position: old_weight=0 → division by zero avoided → change_pct=None."""
        rows = [
            make_row("Anchor", DATE_OLD, weight_pct=1.0),
            make_row("Anchor", DATE_NEW, weight_pct=1.0),
            make_row("NewCo", DATE_NEW, weight_pct=5.0),
        ]
        alerts = _generate_alerts(rows, UUID_MAP, limit=100)
        new_alert = next(a for a in alerts if a.alert_type == "new_position")
        assert new_alert.change_pct is None

    def test_increase_weights_stored(self):
        rows = [make_row("X", DATE_OLD, weight_pct=2.0), make_row("X", DATE_NEW, weight_pct=5.0)]
        alerts = _generate_alerts(rows, UUID_MAP, limit=100)
        assert alerts[0].old_weight == Decimal("2.0")
        assert alerts[0].new_weight == Decimal("5.0")

    def test_is_read_always_false(self):
        rows = [make_row("X", DATE_OLD, weight_pct=2.0), make_row("X", DATE_NEW, weight_pct=5.0)]
        alerts = _generate_alerts(rows, UUID_MAP, limit=100)
        assert all(not a.is_read for a in alerts)

    def test_ticker_set_from_isin(self):
        rows = [
            make_row("X", DATE_OLD, isin="PLISIN1", weight_pct=2.0),
            make_row("X", DATE_NEW, isin="PLISIN1", weight_pct=5.0),
        ]
        alerts = _generate_alerts(rows, UUID_MAP, limit=100)
        assert alerts[0].ticker == "PLISIN1"


# ─── multiple subfunds ────────────────────────────────────────────────────────

class TestMultipleSubfunds:
    def test_two_subfunds_independent(self):
        fund_a = uuid.uuid4()
        fund_b = uuid.uuid4()
        uuid_map = {"FundA": fund_a, "FundB": fund_b}

        rows = [
            make_row("X", DATE_OLD, subfund_name="FundA", weight_pct=2.0),
            make_row("X", DATE_NEW, subfund_name="FundA", weight_pct=5.0),
            make_row("Y", DATE_OLD, subfund_name="FundB", weight_pct=1.0),
            make_row("Y", DATE_NEW, subfund_name="FundB", weight_pct=1.0),
        ]
        alerts = _generate_alerts(rows, uuid_map, limit=100)
        assert len(alerts) == 1
        assert alerts[0].fund_id == fund_a


# ─── _make_alert_id ───────────────────────────────────────────────────────────

class TestMakeAlertId:
    def test_deterministic(self):
        id1 = _make_alert_id("subfund", "company", "new_position")
        id2 = _make_alert_id("subfund", "company", "new_position")
        assert id1 == id2

    def test_different_type_different_id(self):
        id1 = _make_alert_id("s", "c", "new_position")
        id2 = _make_alert_id("s", "c", "closed_position")
        assert id1 != id2

    def test_different_company_different_id(self):
        id1 = _make_alert_id("s", "CompanyA", "new_position")
        id2 = _make_alert_id("s", "CompanyB", "new_position")
        assert id1 != id2

    def test_returns_uuid(self):
        result = _make_alert_id("s", "c", "t")
        assert isinstance(result, uuid.UUID)


