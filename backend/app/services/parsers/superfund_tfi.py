"""
Parser dla PDF SUPERFUND TFI — „YYYYMMDD_Zestawienie_Portfeli_SUPERFUND*.pdf".

Format linii danych (tekst bez spacji wewnątrz pól, tokeny oddzielone spacją):
  SUBFUND_NAME INSTRUMENT_NAME ISIN EMITENT ASSET_TYPE CURRENCY QTY VALUE WEIGHT%

Przykład (akcje):
  SUPERFUNDAKCYJNYFUNDUSZINWESTYCYJNYOTWARTYPORTFELOWY SYNEKTIK PLSNKTK00019 SYNEKTIKS.A. AKCJE PLN 1624,00 476156,80 4,15%

Linie z pozycjami gotówkowymi (8 tokenów, bez poprawnego ISIN) są pomijane.
Data snapshotów jest wyciągana z nazwy pliku (YYYYMMDD_...).
"""

from __future__ import annotations

import io
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Optional

DETECTION_TEXT = "NAZWAPEŁNAINSTRUMENTU"

_ISIN_RE = re.compile(r"^[A-Z]{2}[A-Z0-9]{10}$")
_DATE_IN_FILENAME_RE = re.compile(r"(\d{8})")
_DECIMAL_RE = re.compile(r"^-?\d[\d,]*$")

# Nagłówek PDF (pierwsza linia) — pomijamy
_HEADER_LINE = "NAZWAPEŁNAINSTRUMENTU ISIN EMITENT TYPINSTRUMENTU WALUTA ILOŚĆ WARTOŚĆCAŁKOWITA UDZIAŁWAKTYWACHNETTO"


# ---------------------------------------------------------------------------
# Typy danych
# ---------------------------------------------------------------------------

@dataclass
class SuperfundPosition:
    company_name: str
    instrument_name: str
    isin: Optional[str]
    asset_type: Optional[str]
    currency: str
    shares: Optional[Decimal]
    value: Optional[Decimal]
    weight_pct: Optional[Decimal]


@dataclass
class SuperfundSubfundSnapshot:
    subfund_name: str
    snapshot_date: date
    positions: list[SuperfundPosition] = field(default_factory=list)
    total_value: Optional[Decimal] = None


# ---------------------------------------------------------------------------
# Pomocnicze
# ---------------------------------------------------------------------------

def _to_decimal(s: str) -> Optional[Decimal]:
    if not s:
        return None
    try:
        return Decimal(s.replace(",", "."))
    except InvalidOperation:
        return None


def _date_from_filename(filename: str) -> Optional[date]:
    m = _DATE_IN_FILENAME_RE.search(filename)
    if m:
        try:
            return datetime.strptime(m.group(1), "%Y%m%d").date()
        except ValueError:
            pass
    return None


def _pretty_subfund_name(raw: str) -> str:
    """
    Próbuje dodać spacje do CamelCase/UpperCase ciągu bez spacji.
    Np. "SUPERFUNDAKCYJNYFIO" pozostaje bez zmian — pole jest czytelne jako skrót.
    """
    return raw  # Na razie zwracamy tak jak jest — nazwy są unikalne


# ---------------------------------------------------------------------------
# Główna funkcja parsowania
# ---------------------------------------------------------------------------

def parse_superfund_tfi(
    file_bytes: bytes,
    filename: str = "",
    subfund_filter: str | None = None,
) -> list[SuperfundSubfundSnapshot]:
    import pdfplumber

    snapshot_date = _date_from_filename(filename) or date.today()
    subfunds: dict[str, SuperfundSubfundSnapshot] = {}

    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            for line in text.split("\n"):
                line = line.strip()
                if not line:
                    continue

                # Pomiń nagłówek
                if "NAZWAPEŁNAINSTRUMENTU" in line or line.startswith("NAZWAPEŁNA"):
                    continue

                tokens = line.split()

                # Oczekujemy 9 tokenów dla pozycji z ISIN:
                #  [0] subfund  [1] instr_name  [2] isin  [3] emitent
                #  [4] type     [5] currency    [6] qty   [7] value   [8] pct%
                if len(tokens) != 9:
                    continue

                isin_candidate = tokens[2]
                if not _ISIN_RE.match(isin_candidate):
                    continue  # Pomijamy gotówkę i inne wiersze bez poprawnego ISIN

                subfund_raw = tokens[0]
                instrument_name = tokens[1]
                isin = isin_candidate
                company_name = tokens[3]
                asset_type = tokens[4]
                currency = tokens[5]
                qty_str = tokens[6]
                value_str = tokens[7]
                pct_str = tokens[8].rstrip("%")

                if not _DECIMAL_RE.match(qty_str):
                    continue

                shares = _to_decimal(qty_str)
                value = _to_decimal(value_str)
                weight_pct = _to_decimal(pct_str)

                subfund_name = subfund_raw
                if subfund_filter and subfund_name != subfund_filter:
                    continue

                if subfund_name not in subfunds:
                    subfunds[subfund_name] = SuperfundSubfundSnapshot(
                        subfund_name=subfund_name,
                        snapshot_date=snapshot_date,
                    )

                subfunds[subfund_name].positions.append(
                    SuperfundPosition(
                        company_name=company_name,
                        instrument_name=instrument_name,
                        isin=isin,
                        asset_type=asset_type,
                        currency=currency,
                        shares=shares,
                        value=value,
                        weight_pct=weight_pct,
                    )
                )

    return list(subfunds.values())


def list_subfunds(file_bytes: bytes) -> list[str]:
    """Zwraca listę nazw subfunduszy w pliku."""
    snapshots = parse_superfund_tfi(file_bytes)
    return [s.subfund_name for s in snapshots]
