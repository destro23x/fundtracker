"""
Endpoints dla TFI (Towarzystwa Funduszy Inwestycyjnych).

GET    /api/v1/tfi/        – lista TFI użytkownika (ze zliczeniem subfunduszy)
POST   /api/v1/tfi/        – utwórz TFI
DELETE /api/v1/tfi/{id}    – usuń TFI (subfundusze dostają tfi_id=NULL)
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.database import get_db
from app.models import TFI, Subfund, PortfolioComposition
from app.schemas import TFICreate, TFIOut
from app.dependencies import get_current_user_id, get_optional_user_id


class AssetBreakdownItem(BaseModel):
    asset_type: str
    weight_pct: float


class SubfundDistributionItem(BaseModel):
    asset_type: str
    subfund_count: int
    total_subfunds: int


router = APIRouter(prefix="/api/v1/tfi", tags=["tfi"])


@router.get("/", response_model=list[TFIOut])
async def list_tfi(
    db: AsyncSession = Depends(get_db),
    user_id: str | None = Depends(get_optional_user_id),
):
    result = await db.execute(
        select(TFI).order_by(TFI.name)
    )
    tfi_list = result.scalars().all()

    # Pobierz liczby subfunduszy w jednym zapytaniu
    counts_result = await db.execute(
        select(Subfund.tfi_id, func.count(Subfund.id))
        .where(Subfund.tfi_id.isnot(None))
        .group_by(Subfund.tfi_id)
    )
    counts = {tfi_id: count for tfi_id, count in counts_result.all()}

    return [
        TFIOut(
            id=t.id,
            name=t.name,
            created_at=t.created_at,
            subfund_count=counts.get(t.id, 0),
        )
        for t in tfi_list
    ]


@router.post("/", response_model=TFIOut, status_code=201)
async def create_tfi(
    data: TFICreate,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    tfi = TFI(user_id=user_id, name=data.name.strip())
    db.add(tfi)
    await db.commit()
    await db.refresh(tfi)
    return TFIOut(id=tfi.id, name=tfi.name, created_at=tfi.created_at, subfund_count=0)


@router.delete("/{tfi_id}", status_code=204)
async def delete_tfi(
    tfi_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    result = await db.execute(
        select(TFI).where(TFI.id == tfi_id, TFI.user_id == user_id)
    )
    tfi = result.scalar_one_or_none()
    if not tfi:
        raise HTTPException(status_code=404, detail="TFI nie znalezione")
    await db.delete(tfi)
    await db.commit()


@router.get("/{tfi_id}", response_model=TFIOut)
async def get_tfi(
    tfi_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user_id: str | None = Depends(get_optional_user_id),
):
    tfi = (await db.execute(
        select(TFI).where(TFI.id == tfi_id)
    )).scalar_one_or_none()
    if not tfi:
        raise HTTPException(status_code=404, detail="TFI nie znalezione")

    count = (await db.execute(
        select(func.count(Subfund.id))
        .where(Subfund.tfi_id == tfi_id)
    )).scalar() or 0

    return TFIOut(id=tfi.id, name=tfi.name, created_at=tfi.created_at, subfund_count=count)


@router.get("/{tfi_id}/asset-breakdown", response_model=list[AssetBreakdownItem])
async def get_tfi_asset_breakdown(
    tfi_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """Agreguje portfolio wg klasy aktywów dla wszystkich subfunduszy TFI."""
    tfi = (await db.execute(
        select(TFI).where(TFI.id == tfi_id, TFI.user_id == user_id)
    )).scalar_one_or_none()
    if not tfi:
        raise HTTPException(status_code=404, detail="TFI nie znalezione")

    subfund_names: list[str] = list(
        (await db.execute(
            select(Subfund.name).where(Subfund.tfi_id == tfi_id, Subfund.user_id == user_id)
        )).scalars().all()
    )
    if not subfund_names:
        return []

    # Najnowsza data snapshotu per subfundusz
    latest_sq = (
        select(
            PortfolioComposition.subfund_name,
            func.max(PortfolioComposition.snapshot_date).label("max_date"),
        )
        .where(
            PortfolioComposition.user_id == user_id,
            PortfolioComposition.subfund_name.in_(subfund_names),
        )
        .group_by(PortfolioComposition.subfund_name)
        .subquery("latest_dates")
    )

    # Suma wag per (subfundusz, asset_type) w ostatnim snapshocie
    subfund_asset_sq = (
        select(
            PortfolioComposition.subfund_name,
            PortfolioComposition.asset_type,
            func.sum(PortfolioComposition.weight_pct).label("subfund_weight"),
        )
        .join(
            latest_sq,
            (PortfolioComposition.subfund_name == latest_sq.c.subfund_name)
            & (PortfolioComposition.snapshot_date == latest_sq.c.max_date),
        )
        .where(PortfolioComposition.user_id == user_id)
        .group_by(
            PortfolioComposition.subfund_name,
            PortfolioComposition.asset_type,
        )
        .subquery("subfund_asset_weights")
    )

    # Średnia waga per asset_type po wszystkich subfunduszach
    rows = (await db.execute(
        select(
            subfund_asset_sq.c.asset_type,
            func.avg(subfund_asset_sq.c.subfund_weight).label("avg_weight"),
        )
        .group_by(subfund_asset_sq.c.asset_type)
        .order_by(func.avg(subfund_asset_sq.c.subfund_weight).desc())
    )).all()

    return [
        AssetBreakdownItem(asset_type=row.asset_type or "Nieznane", weight_pct=float(row.avg_weight or 0))
        for row in rows
    ]


@router.get("/{tfi_id}/subfund-distribution", response_model=list[SubfundDistributionItem])
async def get_tfi_subfund_distribution(
    tfi_id: uuid.UUID,
    threshold: float = Query(10.0, ge=0.0, le=100.0),
    db: AsyncSession = Depends(get_db),
    user_id: str | None = Depends(get_optional_user_id),
):
    """Ile subfunduszy TFI ma >= threshold% w danej klasie aktywów."""
    tfi = (await db.execute(
        select(TFI).where(TFI.id == tfi_id)
    )).scalar_one_or_none()
    if not tfi:
        raise HTTPException(status_code=404, detail="TFI nie znalezione")

    subfund_names: list[str] = list(
        (await db.execute(
            select(Subfund.name).where(Subfund.tfi_id == tfi_id)
        )).scalars().all()
    )
    if not subfund_names:
        return []

    latest_sq = (
        select(
            PortfolioComposition.subfund_name,
            func.max(PortfolioComposition.snapshot_date).label("max_date"),
        )
        .where(
            PortfolioComposition.subfund_name.in_(subfund_names),
        )
        .group_by(PortfolioComposition.subfund_name)
        .subquery("latest_dates")
    )

    subfund_asset_sq = (
        select(
            PortfolioComposition.subfund_name,
            PortfolioComposition.asset_type,
            func.sum(PortfolioComposition.weight_pct).label("subfund_weight"),
        )
        .join(
            latest_sq,
            (PortfolioComposition.subfund_name == latest_sq.c.subfund_name)
            & (PortfolioComposition.snapshot_date == latest_sq.c.max_date),
        )
        .group_by(
            PortfolioComposition.subfund_name,
            PortfolioComposition.asset_type,
        )
        .subquery("subfund_asset_weights")
    )

    total = (await db.execute(
        select(func.count(func.distinct(subfund_asset_sq.c.subfund_name)))
    )).scalar() or 0

    if total == 0:
        return []

    rows = (await db.execute(
        select(
            subfund_asset_sq.c.asset_type,
            func.count(subfund_asset_sq.c.subfund_name).label("subfund_count"),
        )
        .where(subfund_asset_sq.c.subfund_weight >= threshold)
        .group_by(subfund_asset_sq.c.asset_type)
        .order_by(func.count(subfund_asset_sq.c.subfund_name).desc())
    )).all()

    return [
        SubfundDistributionItem(
            asset_type=row.asset_type or "Nieznane",
            subfund_count=row.subfund_count,
            total_subfunds=total,
        )
        for row in rows
    ]
