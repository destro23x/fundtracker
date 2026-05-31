import uuid
from datetime import date
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from pydantic import BaseModel, ConfigDict

from app.database import get_db
from app.models import Subfund, PortfolioComposition
from app.schemas import SubfundCreate, SubfundUpdate, SubfundOut
from app.dependencies import get_current_user_id, get_optional_user_id


class TurnoverPeriodOut(BaseModel):
    date_from: str
    date_to: str
    bought: float
    sold: float
    average_assets: float
    ptr: float | None        # procent, None gdy brak danych
    currency: str            # "PLN" lub "%" (gdy brak wartości — proxy z weight_pct)


def _build_pos(rows) -> tuple[dict[str, float], str]:
    """Zwraca słownik {klucz_pozycji: wartość} oraz jednostkę (PLN lub %)."""
    vals: dict[str, float] = {}
    for r in rows:
        key = r.isin if r.isin else r.company_name
        if r.value is not None:
            vals[key] = vals.get(key, 0.0) + float(r.value)
    if vals:
        return vals, "PLN"
    pcts: dict[str, float] = {}
    for r in rows:
        key = r.isin if r.isin else r.company_name
        if r.weight_pct is not None:
            pcts[key] = pcts.get(key, 0.0) + float(r.weight_pct)
    return pcts, "%"


class PortfolioPositionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    company_name: str
    isin: str | None
    asset_type: str | None
    weight_pct: float | None
    value: float | None
    shares: float | None
    currency_fund: str
    snapshot_date: str | None

    @classmethod
    def from_row(cls, row: PortfolioComposition) -> "PortfolioPositionOut":
        return cls(
            id=str(row.id),
            company_name=row.company_name,
            isin=row.isin,
            asset_type=row.asset_type,
            weight_pct=float(row.weight_pct) if row.weight_pct is not None else None,
            value=float(row.value) if row.value is not None else None,
            shares=float(row.shares) if row.shares is not None else None,
            currency_fund=row.currency_fund or "PLN",
            snapshot_date=str(row.snapshot_date) if row.snapshot_date else None,
        )

router = APIRouter(prefix="/subfunds", tags=["subfunds"])


@router.get("/", response_model=list[SubfundOut])
async def list_subfunds(
    fund_id: Optional[uuid.UUID] = Query(None, description="Filtruj po funduszu"),
    db: AsyncSession = Depends(get_db),
    user_id: str | None = Depends(get_optional_user_id),
):
    q = select(Subfund)
    if fund_id is not None:
        q = q.where(Subfund.fund_id == fund_id)
    result = await db.execute(q.order_by(Subfund.created_at.desc()))
    return result.scalars().all()


@router.post("/", response_model=SubfundOut, status_code=status.HTTP_201_CREATED)
async def create_subfund(
    body: SubfundCreate,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    subfund = Subfund(user_id=user_id, **body.model_dump())
    db.add(subfund)
    await db.commit()
    await db.refresh(subfund)
    return subfund


@router.get("/{subfund_id}", response_model=SubfundOut)
async def get_subfund(
    subfund_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user_id: str | None = Depends(get_optional_user_id),
):
    result = await db.execute(select(Subfund).where(Subfund.id == subfund_id))
    subfund = result.scalar_one_or_none()
    if not subfund:
        raise HTTPException(status_code=404, detail="Subfund not found")
    return subfund


@router.patch("/{subfund_id}", response_model=SubfundOut)
async def update_subfund(
    subfund_id: uuid.UUID,
    body: SubfundUpdate,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    subfund = await _get_subfund_or_404(db, subfund_id, user_id)
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(subfund, field, value)
    await db.commit()
    await db.refresh(subfund)
    return subfund


@router.delete("/{subfund_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_subfund(
    subfund_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    subfund = await _get_subfund_or_404(db, subfund_id, user_id)
    await db.delete(subfund)
    await db.commit()


async def _get_subfund_or_404(db: AsyncSession, subfund_id: uuid.UUID, user_id: str) -> Subfund:
    result = await db.execute(
        select(Subfund).where(Subfund.id == subfund_id, Subfund.user_id == user_id)
    )
    subfund = result.scalar_one_or_none()
    if not subfund:
        raise HTTPException(status_code=404, detail="Subfund not found")
    return subfund


@router.get("/{subfund_id}/portfolio/dates", response_model=list[str])
async def list_portfolio_dates(
    subfund_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user_id: str | None = Depends(get_optional_user_id),
):
    result_sf = await db.execute(select(Subfund).where(Subfund.id == subfund_id))
    subfund = result_sf.scalar_one_or_none()
    if not subfund:
        raise HTTPException(status_code=404, detail="Subfund not found")
    result = await db.execute(
        select(PortfolioComposition.snapshot_date)
        .where(
            PortfolioComposition.subfund_name == subfund.name,
            PortfolioComposition.snapshot_date.isnot(None),
        )
        .distinct()
        .order_by(PortfolioComposition.snapshot_date.desc())
    )
    return [str(d) for d in result.scalars().all()]


@router.get("/{subfund_id}/portfolio", response_model=list[PortfolioPositionOut])
async def get_portfolio(
    subfund_id: uuid.UUID,
    snapshot_date: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    user_id: str | None = Depends(get_optional_user_id),
):
    result_sf = await db.execute(select(Subfund).where(Subfund.id == subfund_id))
    subfund = result_sf.scalar_one_or_none()
    if not subfund:
        raise HTTPException(status_code=404, detail="Subfund not found")

    if snapshot_date is None:
        latest = (await db.execute(
            select(func.max(PortfolioComposition.snapshot_date)).where(
                PortfolioComposition.subfund_name == subfund.name,
            )
        )).scalar()
        if not latest:
            return []
        snapshot_date = str(latest)

    rows = (await db.execute(
        select(PortfolioComposition)
        .where(
            PortfolioComposition.subfund_name == subfund.name,
            PortfolioComposition.snapshot_date == date.fromisoformat(snapshot_date),
        )
        .order_by(PortfolioComposition.weight_pct.desc().nullslast())
    )).scalars().all()

    return [PortfolioPositionOut.from_row(r) for r in rows]


@router.get("/{subfund_id}/turnover", response_model=list[TurnoverPeriodOut])
async def get_turnover(
    subfund_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user_id: str | None = Depends(get_optional_user_id),
):
    """
    Wskaźnik obrotu portfela (PTR) dla każdej pary kolejnych snapshots.
    PTR = min(kupno, sprzedaż) / średnie_aktywa × 100%
    """
    result = await db.execute(select(Subfund).where(Subfund.id == subfund_id))
    subfund = result.scalar_one_or_none()
    if not subfund:
        raise HTTPException(status_code=404, detail="Subfund not found")

    # Wszystkie daty rosnąco
    dates = list((await db.execute(
        select(PortfolioComposition.snapshot_date)
        .where(
            PortfolioComposition.subfund_name == subfund.name,
            PortfolioComposition.snapshot_date.isnot(None),
        )
        .distinct()
        .order_by(PortfolioComposition.snapshot_date.asc())
    )).scalars().all())

    if len(dates) < 2:
        return []

    # Pobieramy wszystkie pozycje jednym zapytaniem
    all_rows = (await db.execute(
        select(
            PortfolioComposition.snapshot_date,
            PortfolioComposition.isin,
            PortfolioComposition.company_name,
            PortfolioComposition.value,
            PortfolioComposition.weight_pct,
        )
        .where(
            PortfolioComposition.subfund_name == subfund.name,
            PortfolioComposition.snapshot_date.isnot(None),
        )
    )).all()

    by_date: dict = {}
    for row in all_rows:
        by_date.setdefault(row.snapshot_date, []).append(row)

    result = []
    for i in range(len(dates) - 1):
        d_from, d_to = dates[i], dates[i + 1]
        pos_from, cur_from = _build_pos(by_date.get(d_from, []))
        pos_to, cur_to = _build_pos(by_date.get(d_to, []))

        if not pos_from or not pos_to:
            continue

        currency = "PLN" if cur_from == "PLN" and cur_to == "PLN" else "%"

        total_from = sum(pos_from.values())
        total_to = sum(pos_to.values())
        if total_from == 0 or total_to == 0:
            continue

        avg_assets = (total_from + total_to) / 2.0
        bought = sold = 0.0
        for key in set(pos_from) | set(pos_to):
            diff = pos_to.get(key, 0.0) - pos_from.get(key, 0.0)
            if diff > 0:
                bought += diff
            else:
                sold += abs(diff)

        ptr = round(min(bought, sold) / avg_assets * 100, 2) if avg_assets > 0 else None

        result.append(TurnoverPeriodOut(
            date_from=str(d_from),
            date_to=str(d_to),
            bought=round(bought, 2),
            sold=round(sold, 2),
            average_assets=round(avg_assets, 2),
            ptr=ptr,
            currency=currency,
        ))

    result.reverse()  # Najnowszy okres na górze
    return result
