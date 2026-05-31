"""
Parser dla pliku XLSX SUPERFUND TFI — format „Zestawienie_Portfeli_SUPERFUND*.xlsx".

Plik jest eksportem XLS w „trybie zgodności" — zawiera zniekształcony tekst (OCR).

Struktura (arkusz „Table 1"):
  Wiersz 0:  nagłówki (col A pusta, B=NAZWA PEŁNA INSTRUMENTU, C=ISIN, ...)
  Wiersze 1+: dane — jeden wiersz = jedna pozycja

Kolumny (0-based, A–I):
  A (0)  Pełna nazwa subfunduszu       → subfund_name
  B (1)  Nazwa pełna instrumentu       → company_name
  C (2)  ISIN                          → isin
  D (3)  Emitent                       (pominięty)
  E (4)  Typ instrumentu               → asset_type
  F (5)  Waluta                        → currency
  G (6)  Ilość                         → shares  (mogą być OCR-spacje: "15    308 36")
  H (7)  Wartość całkowita             → value   (j.w.)
  I (8)  Udział w aktywach netto (%)   → weight_pct (już w %, np. 95.02)

Umbrella name: zawsze "SUPERFUND" (hardcode — dane w pliku są zbyt zniekształcone).
Snapshot date: wyciągana z nazwy pliku (YYYYMMDD_...).
"""

from __future__ import annotations

import io
import re
import zipfile
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Optional

# ---------------------------------------------------------------------------
# Stałe
# ---------------------------------------------------------------------------

UMBRELLA_NAME = "SUPERFUND"
DETECTION_HEADER_B = "NAZWA PEŁNA INSTRUMENTU"

_ISIN_RE = re.compile(r"^[A-Z]{2}[A-Z0-9]{10}$")
_DATE_IN_FILENAME_RE = re.compile(r"(\d{8})")
_NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"


# ---------------------------------------------------------------------------
# Modele
# ---------------------------------------------------------------------------

@dataclass
class SuperfundXlsxPosition:
    company_name: Optional[str]
    isin: Optional[str]
    asset_type: Optional[str]
    currency: str
    shares: Optional[Decimal]
    value: Optional[Decimal]
    weight_pct: Optional[Decimal]


@dataclass
class SuperfundXlsxSubfundSnapshot:
    subfund_name: str
    snapshot_date: date
    positions: list[SuperfundXlsxPosition] = field(default_factory=list)
    total_value: Optional[Decimal] = None


# ---------------------------------------------------------------------------
# Pomocnicze
# ---------------------------------------------------------------------------

def _date_from_filename(filename: str) -> Optional[date]:
    m = _DATE_IN_FILENAME_RE.search(filename)
    if m:
        try:
            return datetime.strptime(m.group(1), "%Y%m%d").date()
        except ValueError:
            pass
    return None


def _to_decimal(v) -> Optional[Decimal]:
    """Konwertuje wartość (może zawierać OCR-spacje) na Decimal."""
    if v is None:
        return None
    s = str(v).replace(" ", "").replace(",", ".").strip()
    if not s:
        return None
    try:
        return Decimal(s)
    except InvalidOperation:
        return None


def _load_xlsx_raw(file_bytes: bytes) -> list[list]:
    """
    Odczytuje wiersze przez surowy ZIP/XML (openpyxl nie radzi sobie z
    dimension ref='A1', który blokuje iterator wierszy w trybie read_only).
    """
    with zipfile.ZipFile(io.BytesIO(file_bytes)) as zf:
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
            return []

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
    return rows


# ---------------------------------------------------------------------------
# Publiczne API
# ---------------------------------------------------------------------------

def list_subfunds(file_bytes: bytes) -> list[str]:
    """Zwraca unikalne nazwy subfunduszy (col A, pomija wiersze prawne i gotówkę)."""
    rows = _load_xlsx_raw(file_bytes)
    seen: list[str] = []
    for row in rows[1:]:
        if not row or not row[0]:
            continue
        name = str(row[0]).strip()
        # Kolumna A zawiera też nagłówek prawny (>200 znaków) — pomijamy
        if name.startswith("SUPERFUND") and len(name) < 200 and name not in seen:
            seen.append(name)
    return seen


def parse_superfund_xlsx(
    file_bytes: bytes,
    filename: str = "",
    subfund_filter: Optional[str] = None,
) -> list[SuperfundXlsxSubfundSnapshot]:
    """Parsuje plik SUPERFUND XLSX i zwraca listę SuperfundXlsxSubfundSnapshot."""
    rows = _load_xlsx_raw(file_bytes)
    if not rows:
        raise ValueError("Plik SUPERFUND XLSX nie zawiera danych.")

    snapshot_date = _date_from_filename(filename) or date.today()
    subfunds: dict[str, SuperfundXlsxSubfundSnapshot] = {}

    for row in rows[1:]:
        def _get(idx: int):
            return row[idx] if len(row) > idx else None

        subfund_raw = str(_get(0)).strip() if _get(0) else None
        # Pomiń wiersze z nagłówkiem prawnym i wiersze bez nazwy subfunduszu
        if not subfund_raw or not subfund_raw.startswith("SUPERFUND") or len(subfund_raw) > 200:
            continue

        isin_raw = str(_get(2)).strip() if _get(2) else None
        if not isin_raw or not _ISIN_RE.match(isin_raw):
            continue  # pomiń gotówkę / waluty

        subfund_name = subfund_raw
        if subfund_filter and subfund_name != subfund_filter:
            continue

        if subfund_name not in subfunds:
            subfunds[subfund_name] = SuperfundXlsxSubfundSnapshot(
                subfund_name=subfund_name,
                snapshot_date=snapshot_date,
            )

        company_name = str(_get(1)).strip() if _get(1) else None
        asset_type = str(_get(4)).strip() if _get(4) else None
        currency = str(_get(5)).strip() if _get(5) else "PLN"
        shares = _to_decimal(_get(6))
        value = _to_decimal(_get(7))
        weight_pct = _to_decimal(_get(8))

        subfunds[subfund_name].positions.append(
            SuperfundXlsxPosition(
                company_name=company_name,
                isin=isin_raw,
                asset_type=asset_type,
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
