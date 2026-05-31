"""
Parser dla pliku XLSX Pekao TFI — „Skład portfela funduszy i subfunduszy zarządzanych przez Pekao TFI S.A.".

Struktura (arkusz „FI_Pekao_WSZYSTKIE"):
  Wiersz 0:  metadane (col E = data wyceny jako serial Excela, col G = tytuł)
  Wiersz 1:  nagłówki kolumn
  Wiersze 2+: dane — jeden wiersz = jedna pozycja

Kolumny (0-based, A=0):
  B  (1)   Identyfikator IZFiA funduszu lub subfunduszu  → izfia_id
  C  (2)   Kod ISIN funduszu lub subfunduszu             → fund_id
  D  (3)   Nazwa funduszu lub subfunduszu                → subfund_name
  F  (5)   Typ funduszu                                  → fund_type
  G  (6)   Waluta wyceny funduszu lub subfunduszu        → currency_fund
  I  (8)   Nazwa emitenta instrumentu                    → company_name
  J  (9)   Kod ISIN składnika portfela                   → isin
  M  (12)  Typ instrumentu                               → asset_type
  O  (14)  Kraj emitenta                                 → country
  Q  (16)  Waluta instrumentu                            → currency_instrument
  R  (17)  Ilość składnika lokat                         → shares
  S  (18)  Wartość składnika lokat w walucie funduszu    → value
  T  (19)  Procentowy udział (ułamek 0–1, ×100 = %)     → weight_pct

Umbrella name: zawsze „Pekao TFI".
Snapshot date: wyciągana z wiersza 0, col E (serial daty Excela).
"""

from __future__ import annotations

import io
import zipfile
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Optional

# ---------------------------------------------------------------------------
# Stałe
# ---------------------------------------------------------------------------

UMBRELLA_NAME = "Pekao TFI"
DETECTION_SHEET = "FI_Pekao_WSZYSTKIE"   # nazwa arkusza — klucz detekcji
DETECTION_HEADER_B = "Identyfikator IZFiA funduszu lub subfunduszu"

_NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"

# Indeksy kolumn (0-based)
COL_IZFIA     = 1   # B
COL_FUND_ISIN = 2   # C
COL_SUBFUND   = 3   # D
COL_FUND_TYPE = 5   # F
COL_CUR_FUND  = 6   # G
COL_COMPANY   = 8   # I
COL_ISIN      = 9   # J
COL_ASSET     = 12  # M
COL_COUNTRY   = 14  # O
COL_CUR_INST  = 16  # Q
COL_SHARES    = 17  # R
COL_VALUE     = 18  # S
COL_WEIGHT    = 19  # T
COL_DATE      = 4   # E (row 0 only)


# ---------------------------------------------------------------------------
# Modele
# ---------------------------------------------------------------------------

@dataclass
class PekaoPosition:
    company_name: Optional[str]
    isin: Optional[str]
    asset_type: Optional[str]
    country: Optional[str]
    currency: str
    shares: Optional[Decimal]
    value: Optional[Decimal]
    weight_pct: Optional[Decimal]


@dataclass
class PekaoSubfundSnapshot:
    subfund_name: str
    fund_id: Optional[str]      # ISIN subfunduszu
    izfia_code: Optional[str]   # identyfikator IZFiA (np. "PIO048")
    fund_type: Optional[str]
    currency_fund: str
    snapshot_date: date
    positions: list[PekaoPosition] = field(default_factory=list)
    total_value: Optional[Decimal] = None


# ---------------------------------------------------------------------------
# Pomocnicze
# ---------------------------------------------------------------------------

def _to_decimal(v) -> Optional[Decimal]:
    if v is None:
        return None
    try:
        return Decimal(str(v).replace(",", ".").strip())
    except InvalidOperation:
        return None


def _excel_date(serial) -> Optional[date]:
    """Konwertuje serial daty Excela na date (epoka 1899-12-30)."""
    try:
        return (datetime(1899, 12, 30) + timedelta(days=int(float(serial)))).date()
    except (TypeError, ValueError):
        return None


def _load_xlsx_raw(file_bytes: bytes) -> tuple[str, list[list]]:
    """
    Zwraca (sheet_name, rows).
    Odczytuje przez surowy ZIP/XML — niezawodne niezależnie od dimension ref.
    """
    with zipfile.ZipFile(io.BytesIO(file_bytes)) as zf:
        # Nazwa arkusza
        wb_root = ET.fromstring(zf.read("xl/workbook.xml"))
        sheets_el = wb_root.find(f"{_NS}sheets")
        sheet_name = ""
        if sheets_el is not None:
            first = list(sheets_el)
            if first:
                sheet_name = first[0].get("name", "")

        # Shared strings
        shared: list[str] = []
        if "xl/sharedStrings.xml" in zf.namelist():
            ss_root = ET.fromstring(zf.read("xl/sharedStrings.xml"))
            for si in ss_root.findall(f"{_NS}si"):
                parts = si.findall(f".//{_NS}t")
                shared.append("".join(p.text or "" for p in parts))

        sheet_files = sorted(
            n for n in zf.namelist()
            if n.startswith("xl/worksheets/sheet") and n.endswith(".xml")
        )
        if not sheet_files:
            return sheet_name, []

        ws_root = ET.fromstring(zf.read(sheet_files[0]))
        rows: list[list] = []
        for row_el in ws_root.findall(f".//{_NS}row"):
            cells: dict[int, object] = {}
            for cell_el in row_el.findall(f"{_NS}c"):
                ref = cell_el.get("r", "")
                col_letters = "".join(c for c in ref if c.isalpha())
                col_idx = 0
                for ch in col_letters:
                    col_idx = col_idx * 26 + (ord(ch.upper()) - ord("A") + 1)
                col_idx -= 1

                cell_type = cell_el.get("t", "n")
                v_el = cell_el.find(f"{_NS}v")
                val = None
                if v_el is not None and v_el.text is not None:
                    if cell_type == "s":
                        idx = int(v_el.text)
                        val = shared[idx] if idx < len(shared) else None
                    else:
                        try:
                            val = float(v_el.text)
                        except ValueError:
                            val = v_el.text
                cells[col_idx] = val

            if cells:
                max_col = max(cells.keys())
                rows.append([cells.get(i) for i in range(max_col + 1)])

    return sheet_name, rows


# ---------------------------------------------------------------------------
# Publiczne API
# ---------------------------------------------------------------------------

def list_subfunds(file_bytes: bytes) -> list[str]:
    """Zwraca unikalne nazwy subfunduszy (col D, z wiersza 2+)."""
    _, rows = _load_xlsx_raw(file_bytes)
    seen: list[str] = []
    for row in rows[2:]:   # row 0 = meta, row 1 = header
        if len(row) <= COL_SUBFUND or not row[COL_SUBFUND]:
            continue
        name = str(row[COL_SUBFUND]).strip()
        if name and name not in seen:
            seen.append(name)
    return seen


def parse_pekao_tfi(
    file_bytes: bytes,
    subfund_filter: Optional[str] = None,
) -> list[PekaoSubfundSnapshot]:
    """Parsuje plik Pekao TFI XLSX i zwraca listę PekaoSubfundSnapshot."""
    _, rows = _load_xlsx_raw(file_bytes)
    if len(rows) < 3:
        raise ValueError("Plik Pekao TFI nie zawiera danych.")

    # Data z wiersza 0, col E
    meta = rows[0]
    snapshot_date = (
        _excel_date(meta[COL_DATE])
        if len(meta) > COL_DATE and meta[COL_DATE] is not None
        else date.today()
    )

    subfunds: dict[str, PekaoSubfundSnapshot] = {}

    for row in rows[2:]:   # pomijamy wiersz meta (0) i nagłówkowy (1)
        def _get(idx: int):
            return row[idx] if len(row) > idx else None

        subfund_name = str(_get(COL_SUBFUND)).strip() if _get(COL_SUBFUND) else None
        if not subfund_name:
            continue
        if subfund_filter and subfund_name != subfund_filter:
            continue

        isin = str(_get(COL_ISIN)).strip() if _get(COL_ISIN) else None
        if not isin:
            continue

        if subfund_name not in subfunds:
            izfia_code  = str(_get(COL_IZFIA)).strip() if _get(COL_IZFIA) else None
            fund_id     = str(_get(COL_FUND_ISIN)).strip() if _get(COL_FUND_ISIN) else None
            fund_type   = str(_get(COL_FUND_TYPE)).strip() if _get(COL_FUND_TYPE) else None
            currency_fund = str(_get(COL_CUR_FUND)).strip() if _get(COL_CUR_FUND) else "PLN"
            subfunds[subfund_name] = PekaoSubfundSnapshot(
                subfund_name=subfund_name,
                fund_id=fund_id,
                izfia_code=izfia_code,
                fund_type=fund_type,
                currency_fund=currency_fund,
                snapshot_date=snapshot_date,
            )

        company_name = str(_get(COL_COMPANY)).strip() if _get(COL_COMPANY) else None
        asset_type   = str(_get(COL_ASSET)).strip() if _get(COL_ASSET) else None
        country      = str(_get(COL_COUNTRY)).strip() if _get(COL_COUNTRY) else None
        currency     = str(_get(COL_CUR_INST)).strip() if _get(COL_CUR_INST) else "PLN"

        shares = _to_decimal(_get(COL_SHARES))
        value  = _to_decimal(_get(COL_VALUE))
        # weight_pct jest ułamkiem (0–1) — konwertujemy na procenty
        weight_raw = _to_decimal(_get(COL_WEIGHT))
        weight_pct = weight_raw * 100 if weight_raw is not None else None

        subfunds[subfund_name].positions.append(
            PekaoPosition(
                company_name=company_name,
                isin=isin,
                asset_type=asset_type,
                country=country,
                currency=currency,
                shares=shares,
                value=value,
                weight_pct=weight_pct,
            )
        )

    for snap in subfunds.values():
        vals = [p.value for p in snap.positions if p.value is not None]
        if vals:
            snap.total_value = sum(vals)  # type: ignore[misc]

    return list(subfunds.values())
