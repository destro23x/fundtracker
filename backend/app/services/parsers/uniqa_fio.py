"""
Parser dla PDF UNIQA FIO — „Publikacja_portfela_FIO_YYYYMMDD.pdf".

Format linii danych (po ekstrakcji tekstu przez pdfplumber):
  CODE UNIQA_FUND_FULL_NAME SUBFUND_NAME N/D FUND_CCY COMPANY_NAME ISIN N/D ASSET_TYPE N/D COUNTRY CURRENCY SHARES VALUE WEIGHT%

Przykład:
  AXA002 UNIQA Fundusz Inwestycyjny Otwarty UNIQA Akcji FIO N/D PLN ORLEN S.A. PLPKN0000018 N/D Akcje N/D PL PLN 137923 18528575,82 8,38%
"""

from __future__ import annotations

import io
import re
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Optional

# Stała część nazwy funduszu nadrzędnego
FUND_FULL_NAME = "UNIQA Fundusz Inwestycyjny Otwarty"

# Pierwsza linia pierwszej strony zaczyna się od tego tekstu
DETECTION_TEXT = "Skład portfela dla funduszu UNIQA FIO"

# Wyciągnij datę z nagłówka strony: „na dzień 31.03.2026r."
_DATE_RE = re.compile(r"na dzień\s+(\d{1,2})\.(\d{1,2})\.(\d{4})")

# ISIN: 2 litery + 10 liter/cyfr
_ISIN_RE = re.compile(r"\b([A-Z]{2}[A-Z0-9]{10})\b")

# W fragmencie PRZED ISIN — ostatnie wystąpienie "N/D [A-Z]{3} " oddziela
# informacje o subfunduszu od nazwy spółki.
_BEFORE_COMPANY_RE = re.compile(r"N/D ([A-Z]{3}) (.+)$")

# Fragment PO ISIN: N/D ASSET_TYPE N/D COUNTRY CURRENCY SHARES VALUE WEIGHT
# (wartości mogą być ujemne, waluta może być złożona np. EUR)
_AFTER_ISIN_RE = re.compile(
    r"^N/D (.+?) N/D ([A-Z]{2}) ([A-Z]{2,7}) ([-\d,]+) ([-\d,]+) ([-\d,]+)%"
)


# ---------------------------------------------------------------------------
# Typy danych
# ---------------------------------------------------------------------------

@dataclass
class UniqaPosition:
    company_name: str
    isin: Optional[str]
    asset_type: Optional[str]
    country: Optional[str]
    currency: str
    shares: Optional[Decimal]
    value: Optional[Decimal]
    weight_pct: Optional[Decimal]


@dataclass
class UniqaSubfundSnapshot:
    subfund_name: str
    snapshot_date: date
    positions: list[UniqaPosition] = field(default_factory=list)
    total_value: Optional[Decimal] = None
    fund_id: Optional[str] = None      # nieużywane (brak ISIN funduszu w PDF)
    izfia_code: Optional[str] = None   # kod IZFiA, np. AXA002


# ---------------------------------------------------------------------------
# Pomocnicze
# ---------------------------------------------------------------------------

def _to_decimal(s: str) -> Optional[Decimal]:
    if not s or s == "N/D":
        return None
    try:
        return Decimal(s.replace(",", ".").replace(" ", ""))
    except InvalidOperation:
        return None


# ---------------------------------------------------------------------------
# Główna funkcja parsowania
# ---------------------------------------------------------------------------

def parse_uniqa_fio(
    file_bytes: bytes,
    filename: str = "",
    subfund_filter: str | None = None,
) -> list[UniqaSubfundSnapshot]:
    import pdfplumber

    snapshot_date: Optional[date] = None
    subfunds: dict[str, UniqaSubfundSnapshot] = {}

    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            for line in text.split("\n"):
                line = line.strip()
                if not line:
                    continue

                # Próba wyciągnięcia daty z nagłówka strony
                if snapshot_date is None:
                    dm = _DATE_RE.search(line)
                    if dm:
                        snapshot_date = date(int(dm.group(3)), int(dm.group(2)), int(dm.group(1)))

                # Linia danych musi zawierać ISIN
                isin_m = _ISIN_RE.search(line)
                if not isin_m:
                    continue

                isin = isin_m.group(1)
                before_isin = line[: isin_m.start()].strip()
                after_isin = line[isin_m.end() :].strip()

                # --- Rozbiór fragmentu przed ISIN ---
                # "AXA002 UNIQA Fundusz Inwestycyjny Otwarty UNIQA Akcji FIO N/D PLN ORLEN S.A."
                bc_m = _BEFORE_COMPANY_RE.search(before_isin)
                if not bc_m:
                    continue

                company_name = bc_m.group(2).strip()
                if not company_name or company_name == "N/D":
                    continue

                subfund_info = before_isin[: bc_m.start()].strip()
                # subfund_info = "AXA002 UNIQA Fundusz Inwestycyjny Otwarty UNIQA Akcji FIO"
                parts = subfund_info.split(" ", 1)
                if len(parts) < 2:
                    continue
                fund_code = parts[0]  # np. "AXA002"
                rest = parts[1]  # "UNIQA Fundusz Inwestycyjny Otwarty UNIQA Akcji FIO"
                subfund_name = rest.replace(FUND_FULL_NAME, "").strip()
                # Usuń sufiks typu funduszu z nazwy subfunduszu
                subfund_name = re.sub(r"\s+(FIO|SFIO|NFO|FIZ|FIZAN|FIF)\s*$", "", subfund_name).strip()
                if not subfund_name:
                    continue

                if subfund_filter and subfund_name != subfund_filter:
                    continue

                # --- Rozbiór fragmentu po ISIN ---
                # "N/D Akcje N/D PL PLN 137923 18528575,82 8,38%"
                ai_m = _AFTER_ISIN_RE.match(after_isin)
                if not ai_m:
                    continue

                asset_type = ai_m.group(1).strip()
                country = ai_m.group(2)
                currency = ai_m.group(3)
                shares = _to_decimal(ai_m.group(4))
                value = _to_decimal(ai_m.group(5))
                weight_pct = _to_decimal(ai_m.group(6))

                if subfund_name not in subfunds:
                    subfunds[subfund_name] = UniqaSubfundSnapshot(
                        subfund_name=subfund_name,
                        snapshot_date=snapshot_date or date.today(),
                        izfia_code=fund_code,
                    )

                subfunds[subfund_name].positions.append(
                    UniqaPosition(
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

    # Uzupełnij datę w snapshotach (może być None jeśli nie znaleziono)
    if snapshot_date:
        for s in subfunds.values():
            s.snapshot_date = snapshot_date

    return list(subfunds.values())


def list_subfunds(file_bytes: bytes) -> list[str]:
    """Zwraca listę nazw subfunduszy w pliku (bez parsowania pozycji)."""
    snapshots = parse_uniqa_fio(file_bytes)
    return [s.subfund_name for s in snapshots]
