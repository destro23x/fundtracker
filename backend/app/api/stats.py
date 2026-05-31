from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.database import get_db
from app.models import Subfund, PortfolioComposition
from app.dependencies import get_optional_user_id
from app.api.alerts import _generate_alerts

router = APIRouter(prefix="/stats", tags=["stats"])


@router.get("/")
async def get_stats(
    db: AsyncSession = Depends(get_db),
    user_id: str | None = Depends(get_optional_user_id),
):
    # Fund count
    fund_count = (await db.execute(
        select(func.count()).select_from(Subfund)
    )).scalar() or 0

    # All portfolio_composition rows
    all_rows = (await db.execute(
        select(PortfolioComposition)
    )).scalars().all()

    # Snapshot count = distinct (subfund_name, snapshot_date) pairs
    snapshot_count = (await db.execute(
        select(func.count()).select_from(
            select(
                PortfolioComposition.subfund_name,
                PortfolioComposition.snapshot_date,
            )
            .distinct()
            .subquery()
        )
    )).scalar() or 0

    # Unread alert count = total generated alerts (all are "unread")
    subfunds = (await db.execute(
        select(Subfund)
    )).scalars().all()
    uuid_map = {f.name: f.id for f in subfunds}
    generated_alerts = _generate_alerts(all_rows, uuid_map, limit=1000)
    unread_count = len(generated_alerts)

    # Latest snapshot date across all subfunds
    latest_date_row = (await db.execute(
        select(func.max(PortfolioComposition.snapshot_date))
    )).scalar()

    latest_snapshot = None
    if latest_date_row:
        # Most-recently uploaded subfund on latest date
        latest_sub_row = (await db.execute(
            select(
                PortfolioComposition.subfund_name,
                PortfolioComposition.source_filename,
                func.count(PortfolioComposition.id).label("pos_count"),
            )
            .where(
                PortfolioComposition.snapshot_date == latest_date_row,
            )
            .group_by(
                PortfolioComposition.subfund_name,
                PortfolioComposition.source_filename,
            )
            .order_by(PortfolioComposition.subfund_name)
            .limit(1)
        )).first()
        if latest_sub_row:
            subfund_obj = uuid_map.get(latest_sub_row.subfund_name)
            latest_snapshot = {
                "fund_id": str(subfund_obj) if subfund_obj else latest_sub_row.subfund_name,
                "fund_name": latest_sub_row.subfund_name,
                "snapshot_id": str(subfund_obj) if subfund_obj else latest_sub_row.subfund_name,
                "snapshot_date": latest_date_row.isoformat(),
                "position_count": latest_sub_row.pos_count,
                "upload_filename": latest_sub_row.source_filename,
            }

    # Recent 20 uploaded files, newest snapshot_date first
    recent_rows = (await db.execute(
        select(
            PortfolioComposition.source_filename,
            func.max(PortfolioComposition.snapshot_date).label("snapshot_date"),
        )
        .group_by(PortfolioComposition.source_filename)
        .order_by(func.max(PortfolioComposition.snapshot_date).desc())
        .limit(20)
    )).all()

    recent_snapshots = [
        {
            "snapshot_id": f"{r.source_filename}_{r.snapshot_date.isoformat()}",
            "fund_name": r.source_filename or "",
            "snapshot_date": r.snapshot_date.isoformat(),
            "upload_filename": r.source_filename,
        }
        for r in recent_rows
    ]

    # Top 10 changes from generated alerts
    top_changes = [
        {
            "fund_name": next((f.name for f in subfunds if str(f.id) == str(a.fund_id)), str(a.fund_id)),
            "fund_id": str(a.fund_id),
            "company_name": a.company_name,
            "ticker": a.ticker,
            "alert_type": a.alert_type,
            "old_weight": float(a.old_weight) if a.old_weight is not None else None,
            "new_weight": float(a.new_weight) if a.new_weight is not None else None,
            "change_pct": float(a.change_pct) if a.change_pct is not None else None,
            "message": a.message,
            "created_at": a.created_at.isoformat(),
        }
        for a in generated_alerts[:10]
    ]

    return {
        "fund_count": fund_count,
        "snapshot_count": snapshot_count,
        "unread_alert_count": unread_count,
        "latest_snapshot": latest_snapshot,
        "recent_snapshots": recent_snapshots,
        "top_changes": top_changes,
    }

