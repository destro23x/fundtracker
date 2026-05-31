"""
Unit tests for pure helper functions in app.services.excel_parser.

No file I/O required — all helpers are pure (or close to it) and can be
tested with lightweight in-process inputs.
"""
from datetime import date
from decimal import Decimal

import pandas as pd
import pytest

from app.services.excel_parser import (
    _normalize_header,
    _score_column,
    _detect_columns,
    _to_decimal,
    _find_header_row,
    _extract_date_from_filename,
)


# ─── _normalize_header ────────────────────────────────────────────────────────

class TestNormalizeHeader:
    def test_strips_whitespace(self):
        assert _normalize_header("  Spółka  ") == "spółka"

    def test_lowercases(self):
        assert _normalize_header("ISIN") == "isin"

    def test_replaces_newline_with_space(self):
        assert _normalize_header("Udział\nw portfelu") == "udział w portfelu"

    def test_collapses_double_space(self):
        assert _normalize_header("wartość  netto") == "wartość netto"

    def test_empty_string(self):
        assert _normalize_header("") == ""

    def test_non_string_converts_via_str(self):
        # column names can be numbers in raw DataFrames
        assert _normalize_header(42) == "42"

    def test_mixed_case_and_spaces(self):
        assert _normalize_header("  Liczba Sztuk  ") == "liczba sztuk"

    def test_newline_becomes_single_space(self):
        result = _normalize_header("Udział\nportfela")
        assert "\n" not in result
        assert " " in result


# ─── _score_column ────────────────────────────────────────────────────────────

class TestScoreColumn:
    def test_exact_hint_match_scores_1(self):
        assert _score_column("ISIN", {"isin"}) == 1

    def test_partial_match_scores_1(self):
        # "wartość" is contained in "Wartość netto"
        assert _score_column("Wartość netto", {"wartość"}) == 1

    def test_no_match_scores_0(self):
        assert _score_column("random column", {"isin", "ticker"}) == 0

    def test_multiple_hints_matched(self):
        # Header matches two distinct hints
        score = _score_column("Udział w portfelu %", {"udział", "%"})
        assert score == 2

    def test_case_insensitive_due_to_normalize(self):
        # _score_column calls _normalize_header internally → case insensitive
        assert _score_column("TICKER", {"ticker"}) == 1

    def test_empty_hints_scores_0(self):
        assert _score_column("anything", set()) == 0


# ─── _detect_columns ─────────────────────────────────────────────────────────

class TestDetectColumns:
    def test_standard_polish_headers(self):
        headers = ["Emitent", "ISIN", "Liczba sztuk", "Wartość", "Udział %"]
        col = _detect_columns(headers)
        assert col["company"] == 0   # "emitent" in COMPANY_HINTS
        assert col["isin"] == 1
        assert col["shares"] == 2
        assert col["value"] == 3
        assert col["weight"] == 4

    def test_all_none_for_unrecognised_headers(self):
        headers = ["Alpha", "Beta", "Gamma", "Delta"]
        col = _detect_columns(headers)
        assert all(v is None for v in col.values())

    def test_english_headers(self):
        headers = ["Company", "Ticker", "ISIN", "Shares", "Value", "Weight"]
        col = _detect_columns(headers)
        assert col["company"] == 0
        assert col["ticker"] == 1
        assert col["isin"] == 2
        assert col["shares"] == 3
        assert col["value"] == 4
        assert col["weight"] == 5

    def test_returns_dict_with_all_keys(self):
        col = _detect_columns(["X"])
        assert set(col.keys()) == {"company", "ticker", "isin", "shares", "value", "weight"}

    def test_best_candidate_wins(self):
        # "Kod ISIN" scores higher than "Kod" for the isin key
        headers = ["Kod", "Kod ISIN", "Emitent"]
        col = _detect_columns(headers)
        assert col["isin"] == 1   # "isin" hint matched

    def test_single_column(self):
        col = _detect_columns(["Spółka"])
        assert col["company"] == 0


# ─── _to_decimal ─────────────────────────────────────────────────────────────

class TestToDecimal:
    def test_integer_string(self):
        assert _to_decimal("1000") == Decimal("1000")

    def test_float_string_with_dot(self):
        assert _to_decimal("1234.56") == Decimal("1234.56")

    def test_float_string_with_comma(self):
        assert _to_decimal("1 234,56") == Decimal("1234.56")

    def test_percent_sign_stripped(self):
        assert _to_decimal("12.5%") == Decimal("12.5")

    def test_non_breaking_space_stripped(self):
        # \xa0 is a non-breaking space used in Polish number formatting
        assert _to_decimal("10\xa0000") == Decimal("10000")

    def test_none_returns_none(self):
        assert _to_decimal(None) is None

    def test_nan_float_returns_none(self):
        import math
        assert _to_decimal(float("nan")) is None

    def test_empty_string_returns_none(self):
        assert _to_decimal("") is None

    def test_non_numeric_string_returns_none(self):
        assert _to_decimal("N/A") is None

    def test_zero_string(self):
        assert _to_decimal("0") == Decimal("0")

    def test_negative_value(self):
        assert _to_decimal("-500.25") == Decimal("-500.25")

    def test_integer_value(self):
        assert _to_decimal(42) == Decimal("42")

    def test_float_value(self):
        result = _to_decimal(3.14)
        assert result == pytest.approx(Decimal("3.14"), abs=Decimal("0.01"))

    def test_spaces_stripped(self):
        assert _to_decimal("  500  ") == Decimal("500")


# ─── _find_header_row ────────────────────────────────────────────────────────

class TestFindHeaderRow:
    def _df(self, rows: list[list]) -> pd.DataFrame:
        return pd.DataFrame(rows)

    def test_first_row_is_header(self):
        df = self._df([
            ["Emitent", "ISIN", "Wartość"],
            ["Allegro", "PLALGR000010", "5000"],
        ])
        assert _find_header_row(df) == 0

    def test_header_on_second_row(self):
        df = self._df([
            ["Report title", None, None],
            ["Spółka", "ISIN", "Liczba"],
            ["Allegro", "PLALGR000010", "100"],
        ])
        assert _find_header_row(df) == 1

    def test_header_on_third_row(self):
        df = self._df([
            [None, None, None],
            ["Data:", "2024-03-31", None],
            ["Emitent", "Ticker", "Wartość"],
            ["KGHM", "KGH", "10000"],
        ])
        assert _find_header_row(df) == 2

    def test_no_header_defaults_to_zero(self):
        # DataFrame with no recognisable keywords → falls back to 0
        df = self._df([["foo", "bar"], ["baz", "qux"]])
        assert _find_header_row(df) == 0

    def test_english_value_keyword_detected(self):
        df = self._df([
            ["Company", "Value"],
            ["Allegro", "5000"],
        ])
        assert _find_header_row(df) == 0


# ─── _extract_date_from_filename ─────────────────────────────────────────────

class TestExtractDateFromFilename:
    def test_yyyy_mm_dd_with_dashes(self):
        assert _extract_date_from_filename("portfel_2024-03-31.xlsx") == date(2024, 3, 31)

    def test_yyyy_mm_dd_with_underscores(self):
        assert _extract_date_from_filename("PKO_2024_06_30.xlsx") == date(2024, 6, 30)

    def test_yyyy_mm_dd_with_dots(self):
        assert _extract_date_from_filename("raport.2024.12.31.xlsx") == date(2024, 12, 31)

    def test_dd_mm_yyyy_with_dots(self):
        assert _extract_date_from_filename("dane_31.03.2024.xlsx") == date(2024, 3, 31)

    def test_dd_mm_yyyy_with_dashes(self):
        assert _extract_date_from_filename("dane_31-03-2024.xlsx") == date(2024, 3, 31)

    def test_yyyymmdd_compact(self):
        assert _extract_date_from_filename("PKO20240331.xlsx") == date(2024, 3, 31)

    def test_no_date_returns_none(self):
        assert _extract_date_from_filename("portfel_brak_daty.xlsx") is None

    def test_empty_string_returns_none(self):
        assert _extract_date_from_filename("") is None

    def test_date_in_path(self):
        assert _extract_date_from_filename("/uploads/2024-03-31/portfel.xlsx") == date(2024, 3, 31)

    def test_invalid_date_digits_skipped(self):
        # 2024-13-99 is invalid — should not raise, returns None
        result = _extract_date_from_filename("report_2024-13-99.xlsx")
        assert result is None

    def test_compact_date_at_start(self):
        assert _extract_date_from_filename("20241231_raport.xlsx") == date(2024, 12, 31)
