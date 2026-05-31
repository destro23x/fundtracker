"""
Excel parser with heuristic column detection.
Handles common Polish TFI report formats.
"""
import io
import re
from decimal import Decimal, InvalidOperation
from datetime import date
from dataclasses import dataclass, field

import pandas as pd
import openpyxl


COMPANY_HINTS = {"spółka", "emitent", "nazwa", "company", "issuer", "instrument", "papier"}
TICKER_HINTS = {"ticker", "symbol", "kod", "skrót"}
ISIN_HINTS = {"isin", "kod isin"}
SHARES_HINTS = {"liczba", "sztuk", "wolumen", "quantity", "shares", "units", "ilość"}
VALUE_HINTS = {"wartość", "value", "wycena", "kwota"}
WEIGHT_HINTS = {"udział", "waga", "weight", "%", "procent", "udział w portfelu", "% portfela"}


@dataclass
class ParsedPosition:
    company_name: str
    ticker: str | None = None
    isin: str | None = None
    shares: Decimal | None = None
    value: Decimal | None = None
    weight_pct: Decimal | None = None
    currency: str = "PLN"
    asset_type: str | None = None
    country: str | None = None        # Kraj emitenta


@dataclass
class ParsedPortfolio:
    positions: list[ParsedPosition] = field(default_factory=list)
    snapshot_date: date | None = None
    total_value: Decimal | None = None
    currency: str = "PLN"
    raw_headers: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    subfund_name: str | None = None  # wypełniane przez dedykowane parsery (np. Goldman Sachs)
    umbrella_name: str | None = None  # Nazwa Parasola → poziom Funduszu
    fund_type: str | None = None      # Typ funduszu (SFIO, FIO, FIZ, …)
    fund_id: str | None = None        # Identyfikator funduszu (KNF ID / IZFIA ID)
    izfia_id: str | None = None       # Kod IZFiA funduszu (np. NOB003, ALR010, PZU001)


def _normalize_header(h: str) -> str:
    return str(h).strip().lower().replace("\n", " ").replace("  ", " ")


def _score_column(header: str, hints: set[str]) -> int:
    h = _normalize_header(header)
    return sum(1 for hint in hints if hint in h)


def _detect_columns(headers: list[str]) -> dict[str, int | None]:
    mapping: dict[str, int | None] = {
        "company": None, "ticker": None, "isin": None,
        "shares": None, "value": None, "weight": None,
    }
    scored = {
        "company": [(i, _score_column(h, COMPANY_HINTS)) for i, h in enumerate(headers)],
        "ticker": [(i, _score_column(h, TICKER_HINTS)) for i, h in enumerate(headers)],
        "isin": [(i, _score_column(h, ISIN_HINTS)) for i, h in enumerate(headers)],
        "shares": [(i, _score_column(h, SHARES_HINTS)) for i, h in enumerate(headers)],
        "value": [(i, _score_column(h, VALUE_HINTS)) for i, h in enumerate(headers)],
        "weight": [(i, _score_column(h, WEIGHT_HINTS)) for i, h in enumerate(headers)],
    }
    for key, candidates in scored.items():
        best = max(candidates, key=lambda x: x[1], default=None)
        if best and best[1] > 0:
            mapping[key] = best[0]
    return mapping


def _to_decimal(val) -> Decimal | None:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None
    s = str(val).strip().replace(" ", "").replace(",", ".").replace("%", "").replace("\xa0", "")
    try:
        return Decimal(s)
    except InvalidOperation:
        return None


def _find_header_row(df: pd.DataFrame) -> int:
    """Find the row index that looks like a header (most string cells with keywords)."""
    for i, row in df.iterrows():
        cells = [str(c).lower() for c in row if pd.notna(c)]
        joined = " ".join(cells)
        if any(h in joined for h in COMPANY_HINTS | TICKER_HINTS | ISIN_HINTS | VALUE_HINTS):
            return int(i)
    return 0


def _extract_date_from_filename(filename: str) -> date | None:
    patterns = [
        r"(\d{4})[-_.](\d{2})[-_.](\d{2})",
        r"(\d{2})[-_.](\d{2})[-_.](\d{4})",
        r"(\d{4})(\d{2})(\d{2})",
    ]
    for p in patterns:
        m = re.search(p, filename)
        if m:
            g = m.groups()
            try:
                if len(g[0]) == 4:
                    return date(int(g[0]), int(g[1]), int(g[2]))
                else:
                    return date(int(g[2]), int(g[1]), int(g[0]))
            except ValueError:
                continue
    return None


def parse_excel(file_bytes: bytes, filename: str = "") -> ParsedPortfolio:
    result = ParsedPortfolio()
    result.snapshot_date = _extract_date_from_filename(filename)

    try:
        xl = pd.ExcelFile(io.BytesIO(file_bytes))
    except Exception as e:
        result.warnings.append(f"Cannot open file: {e}")
        return result

    # Use first sheet by default, or the one with most data
    sheet_name = xl.sheet_names[0]
    for name in xl.sheet_names:
        if any(k in name.lower() for k in ["portfel", "portfolio", "pozycj", "składnik"]):
            sheet_name = name
            break

    raw_df = pd.read_excel(io.BytesIO(file_bytes), sheet_name=sheet_name, header=None)
    header_row = _find_header_row(raw_df)

    df = pd.read_excel(io.BytesIO(file_bytes), sheet_name=sheet_name, header=header_row)
    df.columns = [str(c) for c in df.columns]
    result.raw_headers = list(df.columns)

    col_map = _detect_columns(df.columns.tolist())

    if col_map["company"] is None:
        result.warnings.append("Could not detect company name column; falling back to first column.")
        col_map["company"] = 0

    for _, row in df.iterrows():
        company_val = row.iloc[col_map["company"]]
        if pd.isna(company_val) or str(company_val).strip() == "":
            continue
        company_name = str(company_val).strip()
        # Skip obvious header/total rows
        if any(kw in company_name.lower() for kw in ["razem", "suma", "total", "łącznie", "ogółem"]):
            # Try to extract total value
            if col_map["value"] is not None:
                result.total_value = _to_decimal(row.iloc[col_map["value"]]) or result.total_value
            continue

        pos = ParsedPosition(company_name=company_name)
        if col_map["ticker"] is not None:
            pos.ticker = str(row.iloc[col_map["ticker"]]).strip() if pd.notna(row.iloc[col_map["ticker"]]) else None
        if col_map["isin"] is not None:
            isin_val = str(row.iloc[col_map["isin"]]).strip() if pd.notna(row.iloc[col_map["isin"]]) else None
            pos.isin = isin_val if isin_val and re.match(r"[A-Z]{2}[A-Z0-9]{10}", isin_val or "") else None
        if col_map["shares"] is not None:
            pos.shares = _to_decimal(row.iloc[col_map["shares"]])
        if col_map["value"] is not None:
            pos.value = _to_decimal(row.iloc[col_map["value"]])
        if col_map["weight"] is not None:
            w = _to_decimal(row.iloc[col_map["weight"]])
            # Normalize: if stored as 0-100, keep; if 0-1, multiply
            if w is not None and w <= Decimal("1"):
                w = w * Decimal("100")
            pos.weight_pct = w

        result.positions.append(pos)

    return result
