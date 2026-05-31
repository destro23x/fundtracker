"""
Upload history endpoint — all snapshots grouped by TFI → Fund, from portfolio_composition.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.database import get_db
from app.dependencies import get_current_user_id
from app.models import Subfund, TFI, Fund, PortfolioComposition

router = APIRouter(prefix="/api/v1/upload-history", tags=["upload-history"])


# ─── Response schemas ─────────────────────────────────────────────────────────

class SnapshotEntry(BaseModel):
    snapshot_id: uuid.UUID
    snapshot_date: date
    position_count: int
    total_value: Decimal | None
    currency: str
    upload_filename: str | None
    uploaded_at: datetime


class FundEntry(BaseModel):
    subfund_id: uuid.UUID
    subfund_name: str
    fund_id: uuid.UUID | None
    fund_name: str | None
    snapshot_count: int
    latest_date: date | None
    snapshots: list[SnapshotEntry]


class TFIHistoryEntry(BaseModel):
    tfi_id: uuid.UUID | None
    tfi_name: str | None
    fund_count: int
    upload_count: int
    funds: list[FundEntry]


# ─── Endpoint ─────────────────────────────────────────────────────────────────

@router.get("/", response_model=list[TFIHistoryEntry])
async def get_upload_history(
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """
    Returns upload history grouped by TFI → Fund (subfundusz), derived from
    portfolio_composition.
    """
    # 1. All subfunds for this user with TFI/Fund metadata
    funds_rows = (await db.execute(
        select(
            Subfund.id,
            Subfund.name,
            Subfund.tfi_id,
            Subfund.fund_id,
            TFI.name.label("tfi_name"),
            Fund.name.label("fund_name"),
        )
        .outerjoin(TFI, Subfund.tfi_id == TFI.id)
        .outerjoin(Fund, Subfund.fund_id == Fund.id)
        .where(Subfund.user_id == user_id)
        .order_by(TFI.name.nullslast(), Subfund.name)
    )).all()

    if not funds_rows:
        return []

    subfund_names = [r.name for r in funds_rows]

    # 2. Aggregated snapshot info from portfolio_composition per (subfund_name, snapshot_date)
    agg_rows = (await db.execute(
        select(
            PortfolioComposition.subfund_name,
            PortfolioComposition.snapshot_date,
            PortfolioComposition.source_filename,
            PortfolioComposition.currency_fund,
            func.count(PortfolioComposition.id).label("position_count"),
            func.sum(PortfolioComposition.value).label("total_value"),
            func.min(PortfolioComposition.created_at).label("uploaded_at"),
        )
        .where(
            PortfolioComposition.user_id == user_id,
            PortfolioComposition.subfund_name.in_(subfund_names),
        )
        .group_by(
            PortfolioComposition.subfund_name,
            PortfolioComposition.snapshot_date,
            PortfolioComposition.source_filename,
            PortfolioComposition.currency_fund,
        )
        .order_by(PortfolioComposition.subfund_name, PortfolioComposition.snapshot_date.desc())
    )).all()

    # 3. Group agg rows by subfund_name
    snaps_by_name: dict[str, list] = {}
    for row in agg_rows:
        snaps_by_name.setdefault(row.subfund_name, []).append(row)

    # 4. Group subfunds by tfi_id
    tfi_groups: dict = {}
    for r in funds_rows:
        key = r.tfi_id
        if key not in tfi_groups:
            tfi_groups[key] = {
                "tfi_id": r.tfi_id,
                "tfi_name": r.tfi_name,
                "funds": [],
                "upload_keys": set(),
            }
        fund_snaps = snaps_by_name.get(r.name, [])
        for s in fund_snaps:
            tfi_groups[key]["upload_keys"].add((s.snapshot_date, s.source_filename))
        snap_id = uuid.uuid5(
            uuid.NAMESPACE_URL,
            f"{r.name}:{s.snapshot_date}:{s.source_filename or ''}",
        )
        tfi_groups[key]["funds"].append(FundEntry(
            subfund_id=r.id,
            subfund_name=r.name,
            fund_id=r.fund_id,
            fund_name=r.fund_name,
            snapshot_count=len(fund_snaps),
            latest_date=fund_snaps[0].snapshot_date if fund_snaps else None,
            snapshots=[
                SnapshotEntry(
                    snapshot_id=uuid.uuid5(
                        uuid.NAMESPACE_URL,
                        f"{r.name}:{s.snapshot_date}:{s.source_filename or ''}",
                    ),
                    snapshot_date=s.snapshot_date,
                    position_count=s.position_count,
                    total_value=s.total_value,
                    currency=s.currency_fund or "PLN",
                    upload_filename=s.source_filename,
                    uploaded_at=s.uploaded_at,
                )
                for s in fund_snaps
            ],
        ))

    # 5. Build result
    result = []
    for _, g in sorted(
        tfi_groups.items(),
        key=lambda kv: (kv[1]["tfi_name"] is None, kv[1]["tfi_name"] or ""),
    ):
        result.append(TFIHistoryEntry(
            tfi_id=g["tfi_id"],
            tfi_name=g["tfi_name"],
            fund_count=len(g["funds"]),
            upload_count=len(g["upload_keys"]),
            funds=g["funds"],
        ))

    return result



# ─── Response schemas ─────────────────────────────────────────────────────────

class SnapshotEntry(BaseModel):
    snapshot_id: uuid.UUID
    snapshot_date: date
    position_count: int
    total_value: Decimal | None
    currency: str
    upload_filename: str | None
    uploaded_at: datetime


class FundEntry(BaseModel):
    subfund_id: uuid.UUID
    subfund_name: str
    fund_id: uuid.UUID | None
    fund_name: str | None
    snapshot_count: int
    latest_date: date | None
    snapshots: list[SnapshotEntry]


class TFIHistoryEntry(BaseModel):
    tfi_id: uuid.UUID | None
    tfi_name: str | None
    fund_count: int
    upload_count: int          # distinct uploaded files (1 file = 1 upload, even if it has many subfunds)
    funds: list[FundEntry]


# ─── Endpoint ─────────────────────────────────────────────────────────────────

@router.get("/", response_model=list[TFIHistoryEntry])
async def get_upload_history(
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """
    Returns all uploaded snapshots grouped by TFI → Fund (subfundusz).
    Sorted by TFI name, then fund name, then snapshot date desc.
    """
    # 1. All funds for this user (with TFI and Fundusz names via join)
    funds_rows = (await db.execute(
        select(
            Subfund.id,
            Subfund.name,
            Subfund.tfi_id,
            Subfund.fund_id,
            TFI.name.label("tfi_name"),
            Fund.name.label("fund_name"),
        )
        .outerjoin(TFI, Subfund.tfi_id == TFI.id)
        .outerjoin(Fund, Subfund.fund_id == Fund.id)
        .where(Subfund.user_id == user_id)
        .order_by(TFI.name.nullslast(), Subfund.name)
    )).all()

    if not funds_rows:
        return []

    fund_ids = [r.id for r in funds_rows]

    # 2. Position counts per snapshot (subquery)
    pos_count_sq = (
        select(
            PortfolioPosition.snapshot_id,
            func.count(PortfolioPosition.id).label("cnt"),
        )
        .group_by(PortfolioPosition.snapshot_id)
        .subquery()
    )

    # 3. All snapshots for these funds
    snap_rows = (await db.execute(
        select(
            PortfolioSnapshot.id,
            PortfolioSnapshot.fund_id,
            PortfolioSnapshot.snapshot_date,
            PortfolioSnapshot.total_value,
            PortfolioSnapshot.currency,
            PortfolioSnapshot.upload_filename,
            PortfolioSnapshot.created_at,
            func.coalesce(pos_count_sq.c.cnt, 0).label("position_count"),
        )
        .outerjoin(pos_count_sq, PortfolioSnapshot.id == pos_count_sq.c.snapshot_id)
        .where(PortfolioSnapshot.fund_id.in_(fund_ids))
        .order_by(PortfolioSnapshot.fund_id, PortfolioSnapshot.snapshot_date.desc())
    )).all()

    # 4. Group snapshots by fund_id
    snaps_by_fund: dict = {}
    for s in snap_rows:
        snaps_by_fund.setdefault(s.fund_id, []).append(s)

    # 5. Group funds by tfi_id (None → "Bez TFI")
    tfi_groups: dict = {}  # tfi_id (or None) → {"tfi_name", "funds": [], "upload_keys": set}
    for r in funds_rows:
        key = r.tfi_id
        if key not in tfi_groups:
            tfi_groups[key] = {
                "tfi_id": r.tfi_id,
                "tfi_name": r.tfi_name,
                "funds": [],
                "upload_keys": set(),
            }
        fund_snaps = snaps_by_fund.get(r.id, [])
        for s in fund_snaps:
            # unique upload = (date, filename) — one Excel file lands on one date
            tfi_groups[key]["upload_keys"].add((s.snapshot_date, s.upload_filename))
        tfi_groups[key]["funds"].append(FundEntry(
            subfund_id=r.id,
            subfund_name=r.name,
            fund_id=r.fund_id,
            fund_name=r.fund_name,
            snapshot_count=len(fund_snaps),
            latest_date=fund_snaps[0].snapshot_date if fund_snaps else None,
            snapshots=[
                SnapshotEntry(
                    snapshot_id=s.id,
                    snapshot_date=s.snapshot_date,
                    position_count=s.position_count,
                    total_value=s.total_value,
                    currency=s.currency,
                    upload_filename=s.upload_filename,
                    uploaded_at=s.created_at,
                )
                for s in fund_snaps
            ],
        ))

    # 6. Build result sorted: TFIs with name first, then None last
    result = []
    for tfi_id, g in sorted(
        tfi_groups.items(),
        key=lambda kv: (kv[1]["tfi_name"] is None, kv[1]["tfi_name"] or ""),
    ):
        funds = g["funds"]
        result.append(TFIHistoryEntry(
            tfi_id=g["tfi_id"],
            tfi_name=g["tfi_name"],
            fund_count=len(funds),
            upload_count=len(g["upload_keys"]),
            funds=funds,
        ))

    return result
