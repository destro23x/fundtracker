"""
Endpoints dla Funduszy (poziom pomiedzy TFI a Subfunduszami).

GET    /api/v1/funds/        - lista funduszy uzytkownika (ze zliczeniem subfunduszy)
POST   /api/v1/funds/        - utworz fundusz
DELETE /api/v1/funds/{id}    - usun fundusz (subfundusze dostaja fund_id=NULL)
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.database import get_db
from app.models import Fund, Subfund, TFI, PortfolioComposition
from app.schemas import FundCreate, FundOut
from app.dependencies import get_current_user_id, get_optional_user_id


class AssetBreakdownItem(BaseModel):
    asset_type: str
    weight_pct: float


class SubfundDistributionItem(BaseModel):
    asset_type: str
    subfund_count: int
    total_subfunds: int


router = APIRouter(prefix="/api/v1/funds", tags=["funds"])


@router.get("/", response_model=list[FundOut])
async def list_funds(
    tfi_id: uuid.UUID | None = Query(None),
    db: AsyncSession = Depends(get_db),
    user_id: str | None = Depends(get_optional_user_id),
):
    stmt = select(Fund).order_by(Fund.name)
    if tfi_id is not None:
        stmt = stmt.where(Fund.tfi_id == tfi_id)
    result = await db.execute(stmt)
    funds = result.scalars().all()

    counts_result = await db.execute(
        select(Subfund.fund_id, func.count(Subfund.id))
        .where(Subfund.fund_id.isnot(None))
        .group_by(Subfund.fund_id)
    )
    counts = {fid: cnt for fid, cnt in counts_result.all()}

    return [
        FundOut(
            id=f.id,
            name=f.name,
            tfi_id=f.tfi_id,
            created_at=f.created_at,
            subfund_count=counts.get(f.id, 0),
        )
        for f in funds
    ]


@router.post("/", response_model=FundOut, status_code=201)
async def create_fund(
    data: FundCreate,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    if data.tfi_id is not None:
        tfi_check = await db.execute(
            select(TFI).where(TFI.id == data.tfi_id, TFI.user_id == user_id)
        )
        if not tfi_check.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="TFI nie znalezione")

    fund = Fund(user_id=user_id, name=data.name.strip(), tfi_id=data.tfi_id)
    db.add(fund)
    await db.commit()
    await db.refresh(fund)
    return FundOut(id=fund.id, name=fund.name, tfi_id=fund.tfi_id, created_at=fund.created_at, subfund_count=0)


@router.delete("/{fund_id}", status_code=204)
async def delete_fund(
    fund_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    result = await db.execute(
        select(Fund).where(Fund.id == fund_id, Fund.user_id == user_id)
    )
    fund = result.scalar_one_or_none()
    if not fund:
        raise HTTPException(status_code=404, detail="Fundusz nie znaleziony")
    await db.delete(fund)
    await db.commit()


@router.get("/{fund_id}", response_model=FundOut)
async def get_fund(
    fund_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    fund = (await db.execute(
        select(Fund).where(Fund.id == fund_id)
    )).scalar_one_or_none()
    if not fund:
        raise HTTPException(status_code=404, detail="Fundusz nie znaleziony")

    count = (await db.execute(
        select(func.count(Subfund.id))
        .where(Subfund.fund_id == fund_id)
    )).scalar() or 0

    return FundOut(id=fund.id, name=fund.name, tfi_id=fund.tfi_id, created_at=fund.created_at, subfund_count=count)


@router.get("/{fund_id}/asset-breakdown", response_model=list[AssetBreakdownItem])
async def get_fund_asset_breakdown(
    fund_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user_id: str | None = Depends(get_optional_user_id),
):
    """Agreguje portfolio wg klasy aktywów dla wszystkich subfunduszy funduszu.
    Dla każdego subfunduszu bierze ostatni dostępny snapshot, sumuje wagi per asset_type,
    a następnie uśrednia przez liczbę subfunduszy.
    """
    fund = (await db.execute(
        select(Fund).where(Fund.id == fund_id)
    )).scalar_one_or_none()
    if not fund:
        raise HTTPException(status_code=404, detail="Fundusz nie znaleziony")

    subfund_names: list[str] = list(
        (await db.execute(
            select(Subfund.name).where(Subfund.fund_id == fund_id)
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
            PortfolioComposition.subfund_name.in_(subfund_names),
        )
        .group_by(PortfolioComposition.subfund_name)
        .subquery("latest_dates")
    )

    # Suma wag per (subfundusz, asset_type) w ostatnim snapshocie
    # Grupujemy po rzeczywistej kolumnie (nullable) — coalesce tylko w Pythonie
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


@router.get("/{fund_id}/subfund-distribution", response_model=list[SubfundDistributionItem])
async def get_fund_subfund_distribution(
    fund_id: uuid.UUID,
    threshold: float = Query(10.0, ge=0.0, le=100.0),
    db: AsyncSession = Depends(get_db),
):
    """Ile subfunduszy funduszu ma >= threshold% w danej klasie aktywów."""
    fund = (await db.execute(
        select(Fund).where(Fund.id == fund_id)
    )).scalar_one_or_none()
    if not fund:
        raise HTTPException(status_code=404, detail="Fundusz nie znaleziony")

    subfund_names: list[str] = list(
        (await db.execute(
            select(Subfund.name).where(Subfund.fund_id == fund_id)
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
