"""
Rankings endpoint — activity ranking and inter-fund correlations.
"""
from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from pydantic import BaseModel
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.database import get_db
from app.models import Subfund, PortfolioComposition
from app.dependencies import get_optional_user_id

router = APIRouter(prefix="/rankings", tags=["rankings"])


# ─── Response models ─────────────────────────────────────────────────────────

class FundActivityRank(BaseModel):
    fund_id: str
    fund_name: str
    snapshot_count: int
    latest_snapshot_date: str | None
    total_alerts: int
    buy_alerts: int    # new_position + position_increase
    sell_alerts: int   # closed_position + position_decrease


class FundCorrelation(BaseModel):
    fund_a_id: str
    fund_a_name: str
    fund_b_id: str
    fund_b_name: str
    shared_positions: int
    total_positions_a: int
    total_positions_b: int
    jaccard_similarity: float


class CommonHolder(BaseModel):
    """Funds that hold a given stock — for the 'hot stocks' section."""
    company_name: str
    isin: str | None
    fund_count: int
    funds: list[str]


# ─── Helpers ─────────────────────────────────────────────────────────────────

async def _subfund_uuid_map(db: AsyncSession) -> dict[str, str]:
    """Returns {subfund_name: str(uuid)} for all subfunds."""
    result = await db.execute(select(Subfund))
    return {f.name: str(f.id) for f in result.scalars().all()}


def _group_by_subfund_date(rows) -> dict[str, dict]:
    """Returns {subfund_name: {date: {pos_key: row}}}."""
    data: dict[str, dict] = {}
    for row in rows:
        name = row.subfund_name or row.umbrella_name or "unknown"
        dt = row.snapshot_date
        if dt is None:
            continue
        key = row.isin.upper() if row.isin else (row.company_name or "").lower()
        data.setdefault(name, {}).setdefault(dt, {})[key] = row
    return data


def _latest_pos(by_date: dict) -> dict:
    """Returns pos_key→row dict for the most recent snapshot date."""
    if not by_date:
        return {}
    return by_date[max(by_date.keys())]


def _compute_activity(by_date: dict) -> tuple[int, int]:
    """Returns (buys, sells) comparing the two latest snapshot dates."""
    sorted_dates = sorted(by_date.keys(), reverse=True)
    if len(sorted_dates) < 2:
        return (0, 0)
    curr_pos = by_date[sorted_dates[0]]
    prev_pos = by_date[sorted_dates[1]]
    THRESHOLD = Decimal("0.005")
    buys = sells = 0
    for key in set(curr_pos) | set(prev_pos):
        old = prev_pos.get(key)
        new = curr_pos.get(key)
        old_w = Decimal(str(old.weight_pct)) if old and old.weight_pct is not None else Decimal("0")
        new_w = Decimal(str(new.weight_pct)) if new and new.weight_pct is not None else Decimal("0")
        change = new_w - old_w
        if old is None:
            buys += 1
        elif new is None:
            sells += 1
        elif change >= THRESHOLD:
            buys += 1
        elif change <= -THRESHOLD:
            sells += 1
    return (buys, sells)


# ─── Endpoints ───────────────────────────────────────────────────────────────

@router.get("/activity", response_model=list[FundActivityRank])
async def get_activity_ranking(
    db: AsyncSession = Depends(get_db),
    user_id: str | None = Depends(get_optional_user_id),
) -> list[FundActivityRank]:
    """Rank funds by position-change activity derived from portfolio_composition."""
    uuid_map = await _subfund_uuid_map(db)

    all_rows = (await db.execute(
        select(PortfolioComposition)
    )).scalars().all()

    if not all_rows:
        return []

    grouped = _group_by_subfund_date(all_rows)

    result: list[FundActivityRank] = []
    for subfund_name, by_date in grouped.items():
        snap_count = len(by_date)
        latest_date = max(by_date.keys())
        buys, sells = _compute_activity(by_date)
        fund_id = uuid_map.get(subfund_name, subfund_name)
        result.append(
            FundActivityRank(
                fund_id=fund_id,
                fund_name=subfund_name,
                snapshot_count=snap_count,
                latest_snapshot_date=str(latest_date),
                total_alerts=buys + sells,
                buy_alerts=buys,
                sell_alerts=sells,
            )
        )

    result.sort(key=lambda x: x.total_alerts, reverse=True)
    return result


@router.get("/correlations", response_model=list[FundCorrelation])
async def get_correlations(
    min_shared: int = 3,
    db: AsyncSession = Depends(get_db),
    user_id: str | None = Depends(get_optional_user_id),
) -> list[FundCorrelation]:
    """Pairwise Jaccard similarity between funds based on latest snapshot positions."""
    uuid_map = await _subfund_uuid_map(db)

    all_rows = (await db.execute(
        select(PortfolioComposition)
    )).scalars().all()

    if not all_rows:
        return []

    grouped = _group_by_subfund_date(all_rows)

    # Build position key sets for the latest snapshot per subfund
    fund_pos_sets: dict[str, set[str]] = {
        name: set(_latest_pos(by_date).keys())
        for name, by_date in grouped.items()
    }

    names = list(fund_pos_sets.keys())
    correlations: list[FundCorrelation] = []

    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            a, b = names[i], names[j]
            a_pos, b_pos = fund_pos_sets[a], fund_pos_sets[b]
            shared = a_pos & b_pos
            if len(shared) < min_shared:
                continue
            union = a_pos | b_pos
            jaccard = len(shared) / len(union) if union else 0.0
            correlations.append(
                FundCorrelation(
                    fund_a_id=uuid_map.get(a, a),
                    fund_a_name=a,
                    fund_b_id=uuid_map.get(b, b),
                    fund_b_name=b,
                    shared_positions=len(shared),
                    total_positions_a=len(a_pos),
                    total_positions_b=len(b_pos),
                    jaccard_similarity=round(jaccard, 4),
                )
            )

    correlations.sort(key=lambda x: x.jaccard_similarity, reverse=True)
    return correlations[:100]


@router.get("/common-stocks", response_model=list[CommonHolder])
async def get_common_stocks(
    min_funds: int = 2,
    db: AsyncSession = Depends(get_db),
    user_id: str | None = Depends(get_optional_user_id),
) -> list[CommonHolder]:
    """Stocks held by multiple funds in their latest snapshots."""
    all_rows = (await db.execute(
        select(PortfolioComposition)
    )).scalars().all()

    if not all_rows:
        return []

    grouped = _group_by_subfund_date(all_rows)

    stock_map: dict[str, dict] = {}
    for subfund_name, by_date in grouped.items():
        for key, row in _latest_pos(by_date).items():
            if key not in stock_map:
                stock_map[key] = {
                    "company_name": row.company_name or "",
                    "isin": row.isin,
                    "funds": set(),
                }
            # prefer longer/more descriptive company_name
            if row.company_name and len(row.company_name) > len(stock_map[key]["company_name"]):
                stock_map[key]["company_name"] = row.company_name
            stock_map[key]["funds"].add(subfund_name)

    result: list[CommonHolder] = [
        CommonHolder(
            company_name=v["company_name"],
            isin=v["isin"],
            fund_count=len(v["funds"]),
            funds=sorted(v["funds"]),
        )
        for v in stock_map.values()
        if len(v["funds"]) >= min_funds
    ]
    result.sort(key=lambda x: x.fund_count, reverse=True)
    return result[:50]
