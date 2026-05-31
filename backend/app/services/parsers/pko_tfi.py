"""
Parser plików XLSX PKO TFI (PKO Towarzystwo Funduszy Inwestycyjnych S.A.).

Format: jeden arkusz, wiersze danych od row 1 (row 0 = nagłówki).
Kolumny (0-indexed):
  0  A: Identyfikator funduszu lub subfunduszu (izfia_code, np. "PKO064")
  1  B: Nazwa subfunduszu
  2  C: Typ funduszu (SFIO / FIO)
  3  D: Standardowy identyfikator subfunduszu (często "N/D")
  4  E: Waluta wyceny funduszu
  5  F: Nazwa emitenta
  6  G: Identyfikator instrumentu (ISIN)
  7  H: Alternatywny identyfikator instrumentu
  8  I: Typ instrumentu (asset_type)
  9  J: Kategoria instrumentu
 10  K: Kraj emitenta (kod 2-literowy, np. "PL")
 11  L: Kraj ryzyka
 12  M: Waluta instrumentu
 13  N: Ilość instrumentów w portfelu
 14  O: Wartość instrumentu w walucie wyceny funduszu
 15  P: Procentowy udział w wartości aktywów ogółem (ułamek → ×100 = %)
 16  Q: Procentowy udział w NAV
 17  R: Informacje uzupełniające

Detektory:
  - Wiersz nagłówkowy col 0 == "Identyfikator funduszu lub subfunduszu"

Data wyceny: brak w danych → wyciągana z metadanych pliku (docProps/core.xml,
  pole dcterms:created), zaokrąglana do końca poprzedniego kwartału.

Umbrella name: nazwa arkusza, z poprawioną wielkością liter
  (np. "PKO PARASOL FIO" → "PKO Parasol FIO").
"""

from __future__ import annotations

import io
import zipfile
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import date, timedelta, datetime
from decimal import Decimal
from typing import Optional

# ---------------------------------------------------------------------------
# Stałe
# ---------------------------------------------------------------------------

HEADER_COL0 = "Identyfikator funduszu lub subfunduszu"

NS_SS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
NS_DCTERMS = "http://purl.org/dc/terms/"

# Słowa, które zawsze zapisujemy wielkimi literami
_UPPER_WORDS = {"PKO", "FIO", "SFIO", "PPK", "ZE"}


# ---------------------------------------------------------------------------
# Modele danych
# ---------------------------------------------------------------------------

@dataclass
class PkoPosition:
    company_name: Optional[str]
    isin: Optional[str]
    asset_type: Optional[str]
    country: Optional[str]
    currency: Optional[str]
    shares: Optional[Decimal]
    value: Optional[Decimal]
    weight_pct: Optional[Decimal]  # w procentach (0.56, nie 0.0056)


@dataclass
class PkoSubfundSnapshot:
    umbrella_name: str
    subfund_name: str
    fund_id: Optional[str]         # zawsze None — PKO używa izfia_code
    izfia_code: Optional[str]      # col 0: np. "PKO064" (identyfikator IZFiA)
    fund_type: Optional[str]       # "SFIO", "FIO", "PPK" itp.
    currency_fund: Optional[str]
    snapshot_date: date
    positions: list[PkoPosition] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Pomocnicze
# ---------------------------------------------------------------------------

def _quarter_end(dt: datetime) -> date:
    """Zwraca ostatni dzień poprzedniego kwartału względem dt."""
    q_start_month = ((dt.month - 1) // 3) * 3 + 1
    return date(dt.year, q_start_month, 1) - timedelta(days=1)


def _title_ws(name: str) -> str:
    """Zamienia nazwę arkusza CAPS na czytelny tytuł, zachowując skróty."""
    prefix = "" if name.startswith("PKO") else "PKO "
    full = prefix + name
    return " ".join(w if w in _UPPER_WORDS else w.capitalize() for w in full.split())


def _nd(val) -> Optional[str]:
    """Zwraca None gdy wartość to 'N/D' lub pusta."""
    if val is None:
        return None
    s = str(val).strip()
    return None if s in ("N/D", "", "N/A", "-") else s


# ---------------------------------------------------------------------------
# Niskopoziomowy odczyt XLSX przez raw XML (openpyxl nie radzi sobie z tym
# formatem — dimension ref="A1" blokuje iterator wierszy)
# ---------------------------------------------------------------------------

def _load_xlsx(file_bytes: bytes):
    """
    Zwraca (sheet_name, date_created, list_of_rows).

    Każdy wiersz to lista wartości (str/float/None) w kolejności kolumn A–R.
    """
    with zipfile.ZipFile(io.BytesIO(file_bytes)) as zf:
        # 1. Nazwa arkusza
        wb_root = ET.fromstring(zf.read("xl/workbook.xml"))
        sheets_el = wb_root.find(f"{{{NS_SS}}}sheets")
        sheet_name = (
            list(sheets_el)[0].get("name", "")
            if sheets_el is not None and len(list(sheets_el)) > 0
            else ""
        )

        # 2. Data z metadanych
        core_root = ET.fromstring(zf.read("docProps/core.xml"))
        created_el = core_root.find(f"{{{NS_DCTERMS}}}created")
        date_created: Optional[date] = None
        if created_el is not None and created_el.text:
            try:
                dt = datetime.fromisoformat(created_el.text.replace("Z", "+00:00"))
                date_created = _quarter_end(dt)
            except ValueError:
                pass

        # 3. Shared strings
        shared: list[str] = []
        if "xl/sharedStrings.xml" in zf.namelist():
            ss_root = ET.fromstring(zf.read("xl/sharedStrings.xml"))
            for si in ss_root.findall(f"{{{NS_SS}}}si"):
                parts = si.findall(f".//{{{NS_SS}}}t")
                shared.append("".join(p.text or "" for p in parts))

        # 4. Wiersze arkusza (sheet1.xml)
        sheet_files = sorted(
            n for n in zf.namelist()
            if n.startswith("xl/worksheets/sheet") and n.endswith(".xml")
        )
        if not sheet_files:
            return sheet_name, date_created, []

        ws_root = ET.fromstring(zf.read(sheet_files[0]))
        rows: list[list] = []
        for row_el in ws_root.findall(f".//{{{NS_SS}}}row"):
            # Ustal maksymalny indeks kolumny w tym wierszu
            cells: dict[int, object] = {}
            for cell_el in row_el.findall(f"{{{NS_SS}}}c"):
                ref = cell_el.get("r", "")
                col_letters = "".join(c for c in ref if c.isalpha())
                # Konwersja liter kolumny na 0-based index
                col_idx = 0
                for ch in col_letters:
                    col_idx = col_idx * 26 + (ord(ch.upper()) - ord("A") + 1)
                col_idx -= 1  # 0-based

                cell_type = cell_el.get("t", "n")
                v_el = cell_el.find(f"{{{NS_SS}}}v")
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
                row_list = [cells.get(i) for i in range(max_col + 1)]
                rows.append(row_list)

    return sheet_name, date_created, rows


# ---------------------------------------------------------------------------
# Publiczne API
# ---------------------------------------------------------------------------

def list_subfunds(file_bytes: bytes) -> list[str]:
    """Zwraca unikalne nazwy subfunduszy w pliku."""
    _, _, rows = _load_xlsx(file_bytes)
    seen: list[str] = []
    for row in rows[1:]:  # row 0 = nagłówki
        name = row[1] if len(row) > 1 else None
        s = _nd(name)
        if s and s not in seen:
            seen.append(s)
    return seen


def parse_pko_tfi(
    file_bytes: bytes,
    subfund_filter: Optional[str] = None,
) -> list[PkoSubfundSnapshot]:
    """
    Parsuje plik PKO TFI.

    Zwraca listę PkoSubfundSnapshot — jeden na każdy subfundusz
    (lub tylko jeden jeśli subfund_filter jest podany).
    """
    sheet_name, snapshot_date, rows = _load_xlsx(file_bytes)

    if not rows:
        raise ValueError("Plik nie zawiera danych.")

    # Weryfikacja nagłówka
    header_col0 = _nd(rows[0][0]) if rows[0] else ""
    if header_col0 != HEADER_COL0:
        raise ValueError(f"Nieoczekiwany nagłówek: {header_col0!r}")

    if snapshot_date is None:
        # Fallback: dziś
        snapshot_date = date.today()

    umbrella_name = _title_ws(sheet_name)

    # Grupowanie wierszy danych wg subfunduszu
    snapshots: dict[str, PkoSubfundSnapshot] = {}

    for row in rows[1:]:
        if not any(row):
            continue

        def _get(idx: int):
            return row[idx] if len(row) > idx else None

        subfund_name = _nd(_get(1))
        if not subfund_name:
            continue
        if subfund_filter and subfund_name != subfund_filter:
            continue

        izfia_code    = _nd(_get(0))  # col 0: "PKO064" = kod IZFiA
        fund_type = _nd(_get(2))
        currency_fund = _nd(_get(4))

        if subfund_name not in snapshots:
            snapshots[subfund_name] = PkoSubfundSnapshot(
                umbrella_name=umbrella_name,
                subfund_name=subfund_name,
                fund_id=None,
                izfia_code=izfia_code,
                fund_type=fund_type,
                currency_fund=currency_fund,
                snapshot_date=snapshot_date,
            )

        company_name  = _nd(_get(5))
        isin_raw      = _nd(_get(6))
        asset_type    = _nd(_get(8))
        country_raw   = _nd(_get(10))
        currency_inst = _nd(_get(12))

        shares_raw = _get(13)
        value_raw  = _get(14)
        weight_raw = _get(15)

        try:
            shares = Decimal(str(shares_raw)) if shares_raw is not None else None
        except Exception:
            shares = None

        try:
            value = Decimal(str(value_raw)) if value_raw is not None else None
        except Exception:
            value = None

        try:
            weight_pct = Decimal(str(weight_raw)) * 100 if weight_raw is not None else None
        except Exception:
            weight_pct = None

        snapshots[subfund_name].positions.append(
            PkoPosition(
                company_name=company_name,
                isin=isin_raw,
                asset_type=asset_type,
                country=country_raw,
                currency=currency_inst,
                shares=shares,
                value=value,
                weight_pct=weight_pct,
            )
        )

    return list(snapshots.values())
