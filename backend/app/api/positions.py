"""
Endpoint GET /api/v1/positions/search?q=Lubawa

Wyszukuje pozycje po nazwie spółki, tickerze lub ISIN we wszystkich funduszach
użytkownika (najnowszy snapshot każdego funduszu). Zwraca zagregowane wyniki.
"""

from __future__ import annotations

from decimal import Decimal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_

import uuid

from app.database import get_db
from app.models import Subfund, PortfolioComposition
from app.schemas import CompanyHoldings, HoldingPerFund, TopAsset
from app.dependencies import get_optional_user_id

router = APIRouter(prefix="/api/v1/positions", tags=["positions"])


@router.get("/search", response_model=list[CompanyHoldings])
async def search_positions(
    q: str = Query(..., min_length=2, description="Nazwa spółki, ticker lub ISIN"),
    db: AsyncSession = Depends(get_db),
    user_id: str | None = Depends(get_optional_user_id),
):
    """
    Szuka spółki po nazwie lub ISIN w portfolio_composition (najnowszy snapshot
    każdego subfunduszu). Grupuje wyniki po (isin lub company_name).
    """
    like_pattern = f"%{q.lower()}%"

    # 1. Wszystkie pasujące wiersze z portfolio_composition
    rows = (await db.execute(
        select(PortfolioComposition)
        .where(
            (
                func.lower(PortfolioComposition.company_name).like(like_pattern)
                | (func.upper(PortfolioComposition.isin) == q.upper())
            ),
        )
        .order_by(PortfolioComposition.subfund_name, PortfolioComposition.snapshot_date.desc())
    )).scalars().all()

    if not rows:
        return []

    # 2. Mapa subfund_name → Subfund.id (UUID) dla linków do szczegółów
    subfund_rows = (await db.execute(
        select(Subfund.id, Subfund.name)
    )).all()
    subfund_id_map: dict[str, uuid.UUID] = {r.name: r.id for r in subfund_rows}

    # 3. Per subfund zachowaj tylko najnowszy snapshot (po subfund_name + pos_key)
    latest: dict[tuple, PortfolioComposition] = {}
    for row in rows:
        subfund = row.subfund_name or row.umbrella_name or "unknown"
        pos_key = row.isin.upper() if row.isin else (row.company_name or "").lower()
        map_key = (subfund, pos_key)
        existing = latest.get(map_key)
        if existing is None or (row.snapshot_date and existing.snapshot_date and row.snapshot_date > existing.snapshot_date):
            latest[map_key] = row

    # 4. Grupuj po (isin lub company_name)
    groups: dict[str, dict] = {}
    for row in latest.values():
        subfund = row.subfund_name or row.umbrella_name or "unknown"
        pos_key = row.isin.upper() if row.isin else (row.company_name or "").lower()
        if pos_key not in groups:
            groups[pos_key] = {
                "company_name": row.company_name or "",
                "isin": row.isin,
                "ticker": None,
                "funds": [],
                "currencies": set(),
            }
        g = groups[pos_key]
        if row.company_name and len(row.company_name) > len(g["company_name"]):
            g["company_name"] = row.company_name
        currency = row.currency_fund or "PLN"
        g["currencies"].add(currency)
        subfund_uuid = subfund_id_map.get(subfund)
        g["funds"].append(
            HoldingPerFund(
                fund_id=subfund_uuid or uuid.uuid4(),
                fund_name=subfund,
                snapshot_id=row.id,
                snapshot_date=row.snapshot_date,
                shares=row.shares,
                value=row.value,
                weight_pct=row.weight_pct,
                currency=currency,
            )
        )

    # 5. Agreguj sumy
    results: list[CompanyHoldings] = []
    for g in groups.values():
        funds_list: list[HoldingPerFund] = sorted(
            g["funds"], key=lambda x: x.value or Decimal(0), reverse=True
        )
        total_shares = sum((f.shares for f in funds_list if f.shares), Decimal(0)) or None
        total_value = sum((f.value for f in funds_list if f.value), Decimal(0)) or None
        currencies: set[str] = g["currencies"]
        currency = next(iter(currencies)) if len(currencies) == 1 else "PLN"

        results.append(
            CompanyHoldings(
                company_name=g["company_name"],
                isin=g["isin"],
                ticker=g["ticker"],
                total_shares=total_shares,
                total_value=total_value,
                currency=currency,
                fund_count=len(funds_list),
                funds=funds_list,
            )
        )

    # Sortuj po total_value malejąco
    results.sort(key=lambda x: x.total_value or Decimal(0), reverse=True)
    return results


@router.get("/company-history", response_model=list[HoldingPerFund])
async def get_company_history(
    isin: str | None = Query(None, description="ISIN spółki"),
    q: str | None = Query(None, min_length=2, description="Nazwa spółki lub ticker"),
    db: AsyncSession = Depends(get_db),
    user_id: str | None = Depends(get_optional_user_id),
):
    """
    Zwraca wszystkie historyczne snapshoty dla danej spółki we wszystkich subfunduszach
    (źródło: portfolio_composition). Wymaga isin lub q.
    """
    if not isin and not q:
        return []

    if isin:
        filter_clause = func.upper(PortfolioComposition.isin) == isin.upper()
    else:
        like_pattern = f"%{q.lower()}%"
        filter_clause = (
            func.lower(PortfolioComposition.company_name).like(like_pattern)
            | (func.upper(PortfolioComposition.isin) == q.upper())
        )

    rows = (await db.execute(
        select(PortfolioComposition)
        .where(filter_clause)
        .order_by(PortfolioComposition.snapshot_date, PortfolioComposition.subfund_name)
    )).scalars().all()

    if not rows:
        return []

    subfund_rows = (await db.execute(
        select(Subfund.id, Subfund.name)
    )).all()
    subfund_id_map: dict[str, uuid.UUID] = {r.name: r.id for r in subfund_rows}

    result: list[HoldingPerFund] = []
    for row in rows:
        subfund = row.subfund_name or row.umbrella_name or "unknown"
        subfund_uuid = subfund_id_map.get(subfund)
        result.append(
            HoldingPerFund(
                fund_id=subfund_uuid or uuid.uuid4(),
                fund_name=subfund,
                snapshot_id=row.id,
                snapshot_date=row.snapshot_date,
                shares=row.shares,
                value=row.value,
                weight_pct=row.weight_pct,
                currency=row.currency_fund or "PLN",
            )
        )

    return result


@router.get("/top", response_model=list[TopAsset])
async def get_top_assets(
    limit: int = Query(50, ge=1, le=200, description="Liczba zwracanych pozycji"),
    db: AsyncSession = Depends(get_db),
    user_id: str | None = Depends(get_optional_user_id),
):
    """
    Zwraca top N aktywów (domyślnie 50) z największą łączną wartością
    z najnowszego snapshotu każdego subfunduszu (źródło: portfolio_composition).
    Cała agregacja odbywa się w SQL — wydajne nawet dla dużych zbiorów danych.
    """
    # CTE: najnowsza data snapshotu per subfund_name
    latest_cte = (
        select(
            PortfolioComposition.subfund_name,
            func.max(PortfolioComposition.snapshot_date).label("latest_date"),
        )
        .where(
            PortfolioComposition.subfund_name.isnot(None),
            PortfolioComposition.snapshot_date.isnot(None),
        )
        .group_by(PortfolioComposition.subfund_name)
        .cte("latest_per_subfund")
    )

    # Klucz agregacji: ISIN (uppercase) gdy dostępny, inaczej company_name (lowercase)
    key_expr = func.coalesce(
        func.upper(PortfolioComposition.isin),
        func.lower(PortfolioComposition.company_name),
    )

    rows = (await db.execute(
        select(
            func.min(PortfolioComposition.company_name).label("company_name"),
            func.min(PortfolioComposition.isin).label("isin"),
            func.sum(PortfolioComposition.value).label("total_value"),
            func.sum(PortfolioComposition.shares).label("total_shares"),
            func.count(func.distinct(PortfolioComposition.subfund_name)).label("fund_count"),
            func.max(PortfolioComposition.currency_fund).label("currency"),
        )
        .select_from(PortfolioComposition)
        .join(
            latest_cte,
            and_(
                PortfolioComposition.subfund_name == latest_cte.c.subfund_name,
                PortfolioComposition.snapshot_date == latest_cte.c.latest_date,
            ),
        )
        .where(
            PortfolioComposition.value.isnot(None),
        )
        .group_by(key_expr)
        .order_by(func.sum(PortfolioComposition.value).desc())
        .limit(limit)
    )).all()

    if not rows:
        return []

    return [
        TopAsset(
            rank=i + 1,
            company_name=r.company_name,
            isin=r.isin,
            ticker=None,
            total_value=r.total_value,
            total_shares=r.total_shares if r.total_shares else None,
            fund_count=r.fund_count,
            currency=r.currency or "PLN",
        )
        for i, r in enumerate(rows)
    ]
