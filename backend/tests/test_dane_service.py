"""
Unit tests for DaneRow dataclass and parse_file_to_dane_rows in app.services.dane_service.

No file I/O required — parse_file_to_dane_rows is tested via mocked detect_parser
and parse_with_parser. DaneRow tests are pure dataclass/logic tests.
"""
from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from app.services.dane_service import DaneRow, parse_file_to_dane_rows


# ─── helpers ─────────────────────────────────────────────────────────────────

def _make_row(**overrides) -> DaneRow:
    defaults = dict(
        umbrella_name="PKO TFI",
        subfund_name="PKO Akcji Plus",
        fund_type="SFIO",
        fund_id="PLFIO000001",
        izfia_id="PKO001",
        company_name="Allegro",
        country="PL",
        isin="PLALGR000010",
        asset_type="Akcje",
        shares=Decimal("1000"),
        currency_fund="PLN",
        currency_instrument="PLN",
        value=Decimal("50000.00"),
        weight_pct=Decimal("5.25"),
        snapshot_date=date(2024, 3, 31),
        currency_flag=False,
    )
    defaults.update(overrides)
    return DaneRow(**defaults)


def _make_mock_portfolio(
    subfund_name: str = "Fund A",
    umbrella_name: str = "Umbrella",
    currency: str = "PLN",
    positions: list | None = None,
) -> MagicMock:
    pos = MagicMock()
    pos.company_name = "Allegro"
    pos.country = "PL"
    pos.isin = "PLALGR000010"
    pos.asset_type = "Akcje"
    pos.shares = Decimal("100")
    pos.currency = "PLN"
    pos.value = Decimal("10000.00")
    pos.weight_pct = Decimal("5.0")

    portfolio = MagicMock()
    portfolio.subfund_name = subfund_name
    portfolio.umbrella_name = umbrella_name
    portfolio.currency = currency
    portfolio.fund_type = "SFIO"
    portfolio.fund_id = "PL001"
    portfolio.izfia_id = "PKO001"
    portfolio.snapshot_date = date(2024, 3, 31)
    portfolio.positions = positions if positions is not None else [pos]
    return portfolio


# ─── DaneRow.to_dict ─────────────────────────────────────────────────────────

class TestDaneRowToDict:
    def test_all_keys_present(self):
        d = _make_row().to_dict()
        expected = {
            "umbrella_name", "subfund_name", "fund_type", "fund_id", "izfia_id",
            "company_name", "country", "isin", "asset_type", "shares",
            "currency_fund", "currency_instrument", "value", "weight_pct",
            "snapshot_date", "currency_flag",
        }
        assert expected == set(d.keys())

    def test_decimal_shares_converted_to_float(self):
        d = _make_row(shares=Decimal("1234.5678")).to_dict()
        assert isinstance(d["shares"], float)
        assert d["shares"] == pytest.approx(1234.5678)

    def test_decimal_value_converted_to_float(self):
        d = _make_row(value=Decimal("99999.99")).to_dict()
        assert isinstance(d["value"], float)

    def test_decimal_weight_pct_converted_to_float(self):
        d = _make_row(weight_pct=Decimal("12.34")).to_dict()
        assert isinstance(d["weight_pct"], float)
        assert d["weight_pct"] == pytest.approx(12.34)

    def test_snapshot_date_formatted_as_iso(self):
        d = _make_row(snapshot_date=date(2024, 3, 31)).to_dict()
        assert d["snapshot_date"] == "2024-03-31"

    def test_snapshot_date_none(self):
        d = _make_row(snapshot_date=None).to_dict()
        assert d["snapshot_date"] is None

    def test_none_shares_stays_none(self):
        d = _make_row(shares=None).to_dict()
        assert d["shares"] is None

    def test_none_value_stays_none(self):
        d = _make_row(value=None).to_dict()
        assert d["value"] is None

    def test_none_weight_pct_stays_none(self):
        d = _make_row(weight_pct=None).to_dict()
        assert d["weight_pct"] is None

    def test_string_fields_pass_through(self):
        d = _make_row(company_name="KGHM", isin="PLKGHM000017", country="PL").to_dict()
        assert d["company_name"] == "KGHM"
        assert d["isin"] == "PLKGHM000017"
        assert d["country"] == "PL"

    def test_currency_flag_true_preserved(self):
        d = _make_row(currency_fund="EUR", currency_flag=True).to_dict()
        assert d["currency_flag"] is True

    def test_currency_flag_false_preserved(self):
        d = _make_row(currency_fund="PLN", currency_flag=False).to_dict()
        assert d["currency_flag"] is False

    def test_none_optional_fields_stay_none(self):
        d = _make_row(
            umbrella_name=None,
            subfund_name=None,
            fund_type=None,
            fund_id=None,
            izfia_id=None,
            country=None,
            isin=None,
            asset_type=None,
        ).to_dict()
        assert d["umbrella_name"] is None
        assert d["subfund_name"] is None
        assert d["isin"] is None

    def test_zero_shares_converted_to_zero_float(self):
        d = _make_row(shares=Decimal("0")).to_dict()
        assert d["shares"] == pytest.approx(0.0)
        assert isinstance(d["shares"], float)


# ─── DaneRow currency_flag field ─────────────────────────────────────────────

class TestDaneRowCurrencyFlag:
    def test_pln_no_flag(self):
        row = _make_row(currency_fund="PLN", currency_flag=False)
        assert row.currency_flag is False

    def test_eur_flag_set(self):
        row = _make_row(currency_fund="EUR", currency_flag=True)
        assert row.currency_flag is True

    def test_usd_flag_set(self):
        row = _make_row(currency_fund="USD", currency_flag=True)
        assert row.currency_flag is True


# ─── parse_file_to_dane_rows ─────────────────────────────────────────────────

class TestParseFileToDaneRows:
    def test_returns_list_of_dane_rows(self):
        with patch("app.services.dane_service.detect_parser", return_value="pko_tfi"), \
             patch("app.services.dane_service.parse_with_parser",
                   return_value=[_make_mock_portfolio()]):
            rows = parse_file_to_dane_rows(b"fake content", "test.xlsx")
        assert isinstance(rows, list)
        assert len(rows) == 1
        assert isinstance(rows[0], DaneRow)

    def test_row_fields_populated_correctly(self):
        with patch("app.services.dane_service.detect_parser", return_value="pko_tfi"), \
             patch("app.services.dane_service.parse_with_parser",
                   return_value=[_make_mock_portfolio("Fund A", "Umbrella X")]):
            rows = parse_file_to_dane_rows(b"fake", "test.xlsx")
        row = rows[0]
        assert row.company_name == "Allegro"
        assert row.subfund_name == "Fund A"
        assert row.umbrella_name == "Umbrella X"
        assert row.currency_fund == "PLN"

    def test_unknown_format_raises_value_error(self):
        with patch("app.services.dane_service.detect_parser", return_value=None):
            with pytest.raises(ValueError, match="Nierozpoznany"):
                parse_file_to_dane_rows(b"junk bytes", "unknown_format.pdf")

    def test_empty_parser_result_raises_value_error(self):
        with patch("app.services.dane_service.detect_parser", return_value="pko_tfi"), \
             patch("app.services.dane_service.parse_with_parser", return_value=[]):
            with pytest.raises(ValueError, match="Parser"):
                parse_file_to_dane_rows(b"fake", "test.xlsx")

    def test_non_pln_currency_sets_flag(self):
        with patch("app.services.dane_service.detect_parser", return_value="pko_tfi"), \
             patch("app.services.dane_service.parse_with_parser",
                   return_value=[_make_mock_portfolio(currency="EUR")]):
            rows = parse_file_to_dane_rows(b"fake", "test.xlsx")
        assert rows[0].currency_flag is True
        assert rows[0].currency_fund == "EUR"

    def test_pln_currency_no_flag(self):
        with patch("app.services.dane_service.detect_parser", return_value="pko_tfi"), \
             patch("app.services.dane_service.parse_with_parser",
                   return_value=[_make_mock_portfolio(currency="PLN")]):
            rows = parse_file_to_dane_rows(b"fake", "test.xlsx")
        assert rows[0].currency_flag is False

    def test_currency_case_normalized_to_upper(self):
        with patch("app.services.dane_service.detect_parser", return_value="pko_tfi"), \
             patch("app.services.dane_service.parse_with_parser",
                   return_value=[_make_mock_portfolio(currency="pln")]):
            rows = parse_file_to_dane_rows(b"fake", "test.xlsx")
        assert rows[0].currency_fund == "PLN"

    def test_multiple_portfolios_all_rows_included(self):
        p1 = _make_mock_portfolio("FundA")
        p2 = _make_mock_portfolio("FundB")
        with patch("app.services.dane_service.detect_parser", return_value="pko_tfi"), \
             patch("app.services.dane_service.parse_with_parser", return_value=[p1, p2]):
            rows = parse_file_to_dane_rows(b"fake", "test.xlsx")
        assert len(rows) == 2
        subfunds = {r.subfund_name for r in rows}
        assert subfunds == {"FundA", "FundB"}

    def test_portfolio_with_multiple_positions(self):
        pos1 = MagicMock()
        pos1.company_name = "Allegro"
        pos1.country = "PL"
        pos1.isin = "PLALGR000010"
        pos1.asset_type = "Akcje"
        pos1.shares = Decimal("100")
        pos1.currency = "PLN"
        pos1.value = Decimal("5000.00")
        pos1.weight_pct = Decimal("5.0")

        pos2 = MagicMock()
        pos2.company_name = "CD Projekt"
        pos2.country = "PL"
        pos2.isin = "PLCDPRT000019"
        pos2.asset_type = "Akcje"
        pos2.shares = Decimal("50")
        pos2.currency = "PLN"
        pos2.value = Decimal("3000.00")
        pos2.weight_pct = Decimal("3.0")

        portfolio = _make_mock_portfolio(positions=[pos1, pos2])
        with patch("app.services.dane_service.detect_parser", return_value="pko_tfi"), \
             patch("app.services.dane_service.parse_with_parser", return_value=[portfolio]):
            rows = parse_file_to_dane_rows(b"fake", "multi_pos.xlsx")
        assert len(rows) == 2
        names = {r.company_name for r in rows}
        assert names == {"Allegro", "CD Projekt"}

    def test_snapshot_date_propagated(self):
        portfolio = _make_mock_portfolio()
        portfolio.snapshot_date = date(2024, 6, 30)
        with patch("app.services.dane_service.detect_parser", return_value="pko_tfi"), \
             patch("app.services.dane_service.parse_with_parser", return_value=[portfolio]):
            rows = parse_file_to_dane_rows(b"fake", "test.xlsx")
        assert rows[0].snapshot_date == date(2024, 6, 30)
