"""
API dla modułu Dane:

  POST   /api/v1/dane/upload          Wgrywa plik do S3 PortfolioComposition/
  GET    /api/v1/dane/files           Lista plików z S3 (bez _parsed)
  POST   /api/v1/dane/process         Parsuje plik, zapisuje _parsed do S3, zwraca podgląd
  POST   /api/v1/dane/save            Zapisuje sparsowane dane do DB i przenosi pliki do Loaded
"""

from __future__ import annotations

import mimetypes
from datetime import date
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db
from app.dependencies import get_current_user_id
from app.models import Subfund, Fund, PortfolioComposition, TFI
from app.services import s3_service
from app.services.dane_service import (
    parse_file_to_dane_rows,
    rows_to_xlsx,
    parsed_filename,
    DaneRow,
)

router = APIRouter(prefix="/api/v1/dane", tags=["dane"])


# ---------------------------------------------------------------------------
# Schematy odpowiedzi
# ---------------------------------------------------------------------------

class S3FileInfo(BaseModel):
    key: str
    filename: str
    size: int
    last_modified: str


class ProcessResult(BaseModel):
    parsed_filename: str
    total_rows: int
    flagged_rows: int   # wiersze z currency_fund != PLN
    rows: list[dict[str, Any]]


class SaveResult(BaseModel):
    saved_count: int
    source_filename: str
    parsed_filename: str
    created_tfi: bool = False
    created_fundusze: int = 0
    created_funds: int = 0


class LoadedFileInfo(BaseModel):
    source_filename: str
    record_count: int
    loaded_at: str   # ISO 8601


class DetectResult(BaseModel):
    parser_id: str | None
    tfi_name: str | None


# ---------------------------------------------------------------------------
# Helpers: get-or-create hierarchy
# ---------------------------------------------------------------------------

async def _get_or_create_tfi(
    db: AsyncSession, user_id: str, name: str
) -> tuple[TFI, bool]:
    result = await db.execute(
        select(TFI).where(TFI.user_id == user_id, func.lower(TFI.name) == name.lower())
    )
    obj = result.scalar_one_or_none()
    if obj:
        return obj, False
    obj = TFI(user_id=user_id, name=name)
    db.add(obj)
    await db.flush()
    return obj, True


async def _get_or_create_fund(
    db: AsyncSession, user_id: str, name: str, tfi_id
) -> tuple[Fund, bool]:
    result = await db.execute(
        select(Fund).where(Fund.user_id == user_id, func.lower(Fund.name) == name.lower())
    )
    obj = result.scalar_one_or_none()
    if obj:
        return obj, False
    obj = Fund(user_id=user_id, name=name, tfi_id=tfi_id)
    db.add(obj)
    await db.flush()
    return obj, True


async def _get_or_create_subfund(
    db: AsyncSession, user_id: str, name: str, tfi_id, fund_id
) -> tuple[Subfund, bool]:
    result = await db.execute(
        select(Subfund).where(Subfund.user_id == user_id, func.lower(Subfund.name) == name.lower())
    )
    obj = result.scalar_one_or_none()
    if obj:
        return obj, False
    obj = Subfund(user_id=user_id, name=name, tfi_id=tfi_id, fund_id=fund_id)
    db.add(obj)
    await db.flush()
    return obj, True


PARSER_TFI: dict[str, str] = {
    "uniqa_fio":          "UNIQA TFI S.A.",
    "uniqa_tfi_xlsx":     "UNIQA TFI S.A.",
    "goldman_sachs_tfi":  "Goldman Sachs TFI S.A.",
    "alfa_sfio":          "Alfa TFI S.A.",
    "alior_sfio":         "Alior TFI S.A.",
    "noble_nfo":          "Noble Funds TFI S.A.",
    "pzu_tfi":            "PZU TFI S.A.",
    "superfund_tfi":      "Superfund TFI S.A.",
    "erste_tfi":          "Erste Asset Management GmbH",
    "bnp_paribas_tfi":    "BNP Paribas TFI S.A.",
    "generali_tfi":       "Generali Investments TFI S.A.",
    "pko_tfi":            "PKO Towarzystwo Funduszy Inwestycyjnych S.A.",
    "superfund_xlsx":     "Superfund TFI S.A.",
    "pekao_tfi":          "Pekao TFI S.A.",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _portfolio_prefix() -> str:
    cfg = get_settings()
    return cfg.s3_portfolio_prefix.rstrip("/") + "/"


def _portfolio_loaded_prefix() -> str:
    cfg = get_settings()
    return cfg.s3_portfolio_loaded_prefix.rstrip("/") + "/"


def _portfolio_key(filename: str) -> str:
    return _portfolio_prefix() + filename


def _portfolio_loaded_key(filename: str) -> str:
    return _portfolio_loaded_prefix() + filename


def _is_parsed(filename: str) -> bool:
    """Zwraca True jeśli plik ma _parsed w nazwie (przed rozszerzeniem)."""
    import os
    root, _ = os.path.splitext(filename)
    return root.endswith("_parsed")


# ---------------------------------------------------------------------------
# Endpointy
# ---------------------------------------------------------------------------

@router.post("/upload", response_model=S3FileInfo)
async def upload_portfolio_file(
    file: UploadFile = File(...),
    user_id: str = Depends(get_current_user_id),
):
    """Zapisuje przesłany plik do S3 pod kluczem PortfolioComposition/{filename}."""
    contents = await file.read()
    if len(contents) > 30 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Plik zbyt duży (max 30 MB)")

    filename = file.filename or "upload.xlsx"
    if _is_parsed(filename):
        raise HTTPException(
            status_code=400,
            detail="Nie można wgrać pliku z appendiksem _parsed — jest to plik wynikowy.",
        )

    key = _portfolio_key(filename)
    content_type = file.content_type or mimetypes.guess_type(filename)[0] or "application/octet-stream"

    try:
        s3_service.upload_file(key, contents, content_type)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Błąd S3: {exc}") from exc

    return S3FileInfo(
        key=key,
        filename=filename,
        size=len(contents),
        last_modified="",
    )


@router.get("/files", response_model=list[S3FileInfo])
async def list_portfolio_files(
    user_id: str = Depends(get_current_user_id),
):
    """Zwraca listę plików z S3 PortfolioComposition/ (bez plików _parsed)."""
    try:
        files = s3_service.list_files(_portfolio_prefix())
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Błąd S3: {exc}") from exc

    return [
        S3FileInfo(**f)
        for f in files
        if f["filename"] and not _is_parsed(f["filename"])
    ]


@router.get("/detect", response_model=DetectResult)
async def detect_file_tfi(
    filename: str,
    user_id: str = Depends(get_current_user_id),
):
    """Wykrywa TFI (parser) dla pliku z S3 bez jego przetwarzania."""
    key = _portfolio_key(filename)
    try:
        file_bytes = s3_service.download_file(key)
    except Exception as exc:
        raise HTTPException(status_code=404, detail=f"Plik nie znaleziony: {exc}") from exc

    from app.services.parsers import detect_parser
    parser_id = detect_parser(filename, file_bytes)
    return DetectResult(
        parser_id=parser_id,
        tfi_name=PARSER_TFI.get(parser_id or "", None),
    )


@router.post("/process", response_model=ProcessResult)
async def process_portfolio_file(
    filename: str = Form(...),
    user_id: str = Depends(get_current_user_id),
):
    """
    Pobiera plik z S3, parsuje go, zapisuje sparsowany xlsx pod {name}_parsed.xlsx
    i zwraca dane podglądu.
    """
    key = _portfolio_key(filename)

    # Pobierz z S3
    try:
        file_bytes = s3_service.download_file(key)
    except Exception as exc:
        raise HTTPException(status_code=404, detail=f"Plik nie znaleziony w S3: {exc}") from exc

    # Parsuj
    try:
        rows = parse_file_to_dane_rows(file_bytes, filename)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    if not rows:
        raise HTTPException(status_code=422, detail="Parser nie zwrócił żadnych wierszy.")

    # Generuj xlsx
    xlsx_bytes = rows_to_xlsx(rows)
    pf = parsed_filename(filename)
    parsed_key = _portfolio_key(pf)

    try:
        s3_service.upload_file(parsed_key, xlsx_bytes,
                               "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Błąd zapisu parsed do S3: {exc}") from exc

    flagged = sum(1 for r in rows if r.currency_flag)
    return ProcessResult(
        parsed_filename=pf,
        total_rows=len(rows),
        flagged_rows=flagged,
        rows=[r.to_dict() for r in rows],
    )


@router.post("/save", response_model=SaveResult)
async def save_portfolio_to_db(
    filename: str = Form(...),
    tfi_name: str | None = Form(None),
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """
    Pobiera sparsowany plik z S3, zapisuje rekordy do tabeli portfolio_composition,
    automatycznie tworzy hierarchię TFI → Fund → Subfund
    i przenosi oba pliki do PortfolioCompositionLoaded/.
    """
    pf = parsed_filename(filename)
    parsed_key = _portfolio_key(pf)

    # Pobierz sparsowany plik z S3 i sparsuj ponownie (źródło prawdy)
    try:
        parsed_bytes = s3_service.download_file(parsed_key)
    except Exception as exc:
        raise HTTPException(
            status_code=404,
            detail=f"Sparsowany plik '{pf}' nie znaleziony w S3. Najpierw wywołaj /process.",
        ) from exc

    # Odczytaj sparsowany xlsx (standardowy format DaneRow)
    import openpyxl
    import io as _io
    wb = openpyxl.load_workbook(_io.BytesIO(parsed_bytes), data_only=True)
    ws = wb.active
    rows_iter = ws.iter_rows(values_only=True)
    header = next(rows_iter, None)  # pierwsza linia to nagłówki

    records: list[PortfolioComposition] = []
    for row in rows_iter:
        if not row or not any(row):
            continue

        def _str(v) -> str | None:
            return str(v).strip() if v is not None else None

        def _dec(v) -> Decimal | None:
            if v is None:
                return None
            try:
                return Decimal(str(v))
            except Exception:
                return None

        def _date(v) -> date | None:
            if v is None:
                return None
            if isinstance(v, date):
                return v
            try:
                from datetime import datetime as _dt
                return _dt.fromisoformat(str(v)).date()
            except Exception:
                return None

        records.append(PortfolioComposition(
            user_id=user_id,
            source_filename=filename,
            parsed_filename=pf,
            snapshot_date=_date(row[14]) if len(row) > 14 else None,
            umbrella_name=_str(row[0]),
            subfund_name=_str(row[1]),
            fund_type=_str(row[2]),
            fund_id=_str(row[3]),
            izfia_id=_str(row[4]),
            company_name=_str(row[5]) or "",
            country=_str(row[6]),
            isin=_str(row[7]),
            asset_type=_str(row[8]),
            shares=_dec(row[9]),
            currency_fund=_str(row[10]) or "PLN",
            currency_instrument=_str(row[11]) or "PLN",
            value=_dec(row[12]),
            weight_pct=_dec(row[13]),
        ))

    if not records:
        raise HTTPException(status_code=422, detail="Sparsowany plik nie zawiera danych.")

    for rec in records:
        db.add(rec)

    # --- Automatyczne tworzenie hierarchii TFI / Fundusz / Subfundusz ---
    created_tfi = False
    created_fundusze = 0
    created_funds = 0

    effective_tfi_name = (tfi_name or "").strip() or None
    if not effective_tfi_name:
        # Spróbuj wykryć TFI z nazwy pliku przez detect_parser
        from app.services.parsers import detect_parser
        try:
            src_bytes = s3_service.download_file(_portfolio_key(filename))
            parser_id = detect_parser(filename, src_bytes)
            effective_tfi_name = PARSER_TFI.get(parser_id or "") or None
        except Exception:
            pass

    if effective_tfi_name:
        tfi_obj, created_tfi = await _get_or_create_tfi(db, user_id, effective_tfi_name)
        tfi_uuid = tfi_obj.id

        from collections import defaultdict
        umbrella_map: dict[str | None, set[str | None]] = defaultdict(set)
        for rec in records:
            umbrella_map[rec.umbrella_name or None].add(rec.subfund_name or None)

        for umbrella_name, subfund_names in umbrella_map.items():
            fundusz_obj = None
            if umbrella_name:
                fundusz_obj, f_created = await _get_or_create_fund(
                    db, user_id, umbrella_name, tfi_uuid
                )
                if f_created:
                    created_fundusze += 1
            for subfund_name in subfund_names:
                if subfund_name:
                    _, s_created = await _get_or_create_subfund(
                        db, user_id, subfund_name, tfi_uuid,
                        fundusz_obj.id if fundusz_obj else None,
                    )
                    if s_created:
                        created_funds += 1

    await db.commit()

    # Przenieś oba pliki do PortfolioCompositionLoaded/
    src_key = _portfolio_key(filename)
    try:
        s3_service.move_file(src_key, _portfolio_loaded_key(filename))
        s3_service.move_file(parsed_key, _portfolio_loaded_key(pf))
    except Exception as exc:
        # Przeniesienie do Loaded to operacja pomocnicza — nie rollbackuj DB
        # Logujemy, ale nie rzucamy błędu
        import logging
        logging.getLogger(__name__).warning("Błąd przenoszenia do Loaded: %s", exc)

    return SaveResult(
        saved_count=len(records),
        source_filename=filename,
        parsed_filename=pf,
        created_tfi=created_tfi,
        created_fundusze=created_fundusze,
        created_funds=created_funds,
    )


@router.get("/loaded", response_model=list[LoadedFileInfo])
async def list_loaded_files(
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """Zwraca listę plików załadowanych do bazy (distinct source_filename)."""
    stmt = (
        select(
            PortfolioComposition.source_filename,
            func.count().label("record_count"),
            func.min(PortfolioComposition.created_at).label("loaded_at"),
        )
        .where(PortfolioComposition.user_id == user_id)
        .group_by(PortfolioComposition.source_filename)
        .order_by(func.min(PortfolioComposition.created_at).desc())
    )
    result = await db.execute(stmt)
    rows = result.all()
    return [
        LoadedFileInfo(
            source_filename=r.source_filename,
            record_count=r.record_count,
            loaded_at=r.loaded_at.isoformat() if r.loaded_at else "",
        )
        for r in rows
    ]
