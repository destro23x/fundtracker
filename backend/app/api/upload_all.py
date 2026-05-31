"""
Endpoint POST /api/v1/snapshots/upload-all

Wgrywa plik Excel zawierający wiele subfunduszy i zapisuje wszystkie
pozycje do portfolio_composition.
"""

from __future__ import annotations

import uuid
from datetime import date

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete

from app.database import get_db
from app.models import Subfund, TFI, Fund, PortfolioComposition
from app.schemas import UploadAllResult, UploadedSubfund, SkippedSubfund
from app.dependencies import get_current_user_id
from app.services.parsers import (
    detect_parser,
    is_multi_fund,
    list_subfunds_from_file,
    parse_with_parser,
)

router = APIRouter(prefix="/api/v1", tags=["upload-all"])


@router.post("/snapshots/upload-all", response_model=UploadAllResult)
async def upload_all_subfunds(
    file: UploadFile = File(...),
    snapshot_date: date | None = Form(None),
    force: bool = Form(False),
    tfi_id: str | None = Form(None),
    fund_id: str | None = Form(None),
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """
    Wgrywa plik multi-funduszowy i zapisuje WSZYSTKIE subfundusze
    jako osobne fundusze + snapshoty. Fundusze są auto-tworzone jeśli
    nie istnieją (dopasowanie po nazwie).

    Parametr force=true: usuwa istniejący snapshot dla danej daty i wgrywa ponownie.
    """
    contents = await file.read()
    if len(contents) > 20 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="File too large (max 20 MB)")

    filename = file.filename or ""
    parser_id = detect_parser(filename, contents)

    if not parser_id or not is_multi_fund(parser_id):
        raise HTTPException(
            status_code=422,
            detail="Plik nie jest rozpoznawalnym formatem multi-funduszowym. "
                   "Użyj standardowego uploadu dla pliku z jednym funduszem.",
        )

    subfund_names = list_subfunds_from_file(parser_id, contents)
    if not subfund_names:
        raise HTTPException(status_code=422, detail="Nie wykryto żadnych subfunduszy w pliku.")

    # Zweryfikuj TFI jeśli podane
    tfi_uuid = None
    if tfi_id:
        import uuid as _uuid
        try:
            tfi_uuid = _uuid.UUID(tfi_id)
        except ValueError:
            raise HTTPException(status_code=422, detail="Nieprawidłowy format tfi_id")
        tfi_check = await db.execute(
            select(TFI).where(TFI.id == tfi_uuid, TFI.user_id == user_id)
        )
        if not tfi_check.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="TFI nie znalezione")

    # Zweryfikuj Fundusz jeśli podany
    fund_uuid = None
    if fund_id:
        import uuid as _uuid2
        try:
            fund_uuid = _uuid2.UUID(fund_id)
        except ValueError:
            raise HTTPException(status_code=422, detail="Nieprawidłowy format fund_id")
        fnd_check = await db.execute(
            select(Fund).where(Fund.id == fund_uuid, Fund.user_id == user_id)
        )
        if not fnd_check.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="Fundusz nie znaleziony")

    # Parsuj wszystkie subfundusze naraz
    all_portfolios = parse_with_parser(parser_id, contents, filename=filename, subfund_filter=None)
    portfolio_by_name = {p.subfund_name: p for p in all_portfolios if p.subfund_name}

    # Cache funduszy (parasoli) tworzonych w tej sesji — klucz: nazwa parasola
    umbrella_cache: dict[str, object] = {}

    created: list[UploadedSubfund] = []
    skipped: list[SkippedSubfund] = []

    for subfund_name in subfund_names:
        parsed = portfolio_by_name.get(subfund_name)
        if not parsed:
            skipped.append(SkippedSubfund(fund_name=subfund_name, reason="Brak danych po parsowaniu"))
            continue

        effective_date = snapshot_date or parsed.snapshot_date
        if not effective_date:
            skipped.append(SkippedSubfund(
                fund_name=subfund_name,
                reason="Nie można ustalić daty snapshotów. Podaj snapshot_date.",
            ))
            continue

        # Ustal fund_uuid: jawnie podany lub z Nazwy Parasola z pliku
        effective_fund_uuid = fund_uuid
        if effective_fund_uuid is None and parsed.umbrella_name:
            umbrella_key = parsed.umbrella_name.strip()
            if umbrella_key in umbrella_cache:
                effective_fund_uuid = umbrella_cache[umbrella_key].id  # type: ignore[attr-defined]
            else:
                existing_umbrella = await db.execute(
                    select(Fund).where(
                        Fund.user_id == user_id,
                        Fund.name == umbrella_key,
                    )
                )
                umbrella_obj = existing_umbrella.scalar_one_or_none()
                if not umbrella_obj:
                    umbrella_obj = Fund(
                        user_id=user_id,
                        name=umbrella_key,
                        tfi_id=tfi_uuid,
                    )
                    db.add(umbrella_obj)
                    await db.flush()
                elif tfi_uuid and umbrella_obj.tfi_id is None:
                    umbrella_obj.tfi_id = tfi_uuid
                umbrella_cache[umbrella_key] = umbrella_obj
                effective_fund_uuid = umbrella_obj.id

        # Znajdź lub utwórz subfundusz dla tego subfunduszu
        existing_fund_result = await db.execute(
            select(Subfund).where(Subfund.user_id == user_id, Subfund.name == subfund_name)
        )
        fund = existing_fund_result.scalar_one_or_none()
        fund_created = False
        if not fund:
            fund = Subfund(user_id=user_id, name=subfund_name, tfi_id=tfi_uuid, fund_id=effective_fund_uuid)
            db.add(fund)
            await db.flush()  # żeby uzyskać fund.id
            fund_created = True
        else:
            if tfi_uuid and fund.tfi_id is None:
                fund.tfi_id = tfi_uuid
            if effective_fund_uuid and fund.fund_id is None:
                fund.fund_id = effective_fund_uuid

        # Sprawdź duplikat: ta sama data + plik + subfundusz już w portfolio_composition
        dup_result = await db.execute(
            select(PortfolioComposition.id).where(
                PortfolioComposition.user_id == user_id,
                PortfolioComposition.subfund_name == subfund_name,
                PortfolioComposition.snapshot_date == effective_date,
            ).limit(1)
        )
        already_exists = dup_result.scalar_one_or_none() is not None
        if already_exists:
            if not force:
                skipped.append(SkippedSubfund(
                    fund_name=subfund_name,
                    reason=f"Snapshot na {effective_date} już istnieje",
                ))
                continue
            # force=True: usuń stare wiersze dla tej daty i subfunduszu
            await db.execute(
                delete(PortfolioComposition).where(
                    PortfolioComposition.user_id == user_id,
                    PortfolioComposition.subfund_name == subfund_name,
                    PortfolioComposition.snapshot_date == effective_date,
                )
            )
            await db.flush()

        # Zapisz pozycje do portfolio_composition
        first_id = uuid.uuid4()
        for i, p in enumerate(parsed.positions):
            db.add(PortfolioComposition(
                id=first_id if i == 0 else uuid.uuid4(),
                user_id=user_id,
                source_filename=filename,
                parsed_filename=filename,
                snapshot_date=effective_date,
                umbrella_name=parsed.umbrella_name,
                subfund_name=subfund_name,
                fund_type=None,
                company_name=p.company_name,
                isin=p.isin,
                asset_type=p.asset_type,
                shares=p.shares,
                value=p.value,
                weight_pct=p.weight_pct,
                currency_fund=parsed.currency or "PLN",
                currency_instrument=p.currency or "PLN",
            ))

        created.append(UploadedSubfund(
            fund_id=fund.id,
            fund_name=subfund_name,
            snapshot_id=first_id,
            snapshot_date=effective_date,
            position_count=len(parsed.positions),
            fund_created=fund_created,
        ))

    await db.commit()

    return UploadAllResult(
        parser_detected=parser_id,
        total_subfunds=len(subfund_names),
        created=created,
        skipped=skipped,
    )
