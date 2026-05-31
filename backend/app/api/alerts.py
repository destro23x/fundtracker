import uuid
from datetime import datetime, timezone
from decimal import Decimal
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models import Subfund, PortfolioComposition
from app.schemas import AlertOut, AlertMarkRead
from app.dependencies import get_current_user_id, get_optional_user_id

router = APIRouter(prefix="/alerts", tags=["alerts"])

_THRESHOLD = Decimal("0.005")


def _make_alert_id(subfund_name: str, company: str, alert_type: str) -> uuid.UUID:
    return uuid.uuid5(uuid.NAMESPACE_OID, f"{subfund_name}|{company}|{alert_type}")


def _generate_alerts(rows, uuid_map: dict, limit: int) -> list[AlertOut]:
    # Group: subfund_name -> date -> {pos_key: row}
    grouped: dict[str, dict] = {}
    for row in rows:
        name = row.subfund_name or row.umbrella_name or "unknown"
        if row.snapshot_date is None:
            continue
        key = row.isin.upper() if row.isin else (row.company_name or "").lower()
        grouped.setdefault(name, {}).setdefault(row.snapshot_date, {})[key] = row

    alerts: list[AlertOut] = []
    for subfund_name, by_date in grouped.items():
        sorted_dates = sorted(by_date.keys(), reverse=True)
        if len(sorted_dates) < 2:
            continue
        curr_pos = by_date[sorted_dates[0]]
        prev_pos = by_date[sorted_dates[1]]
        curr_date = sorted_dates[0]
        fund_id = uuid_map.get(subfund_name)
        if not fund_id:
            continue
        created_at = datetime(curr_date.year, curr_date.month, curr_date.day, tzinfo=timezone.utc)

        for key in set(curr_pos) | set(prev_pos):
            old_row = prev_pos.get(key)
            new_row = curr_pos.get(key)
            ref = new_row or old_row
            company = ref.company_name
            isin = ref.isin
            old_w = Decimal(str(old_row.weight_pct)) if old_row and old_row.weight_pct is not None else Decimal("0")
            new_w = Decimal(str(new_row.weight_pct)) if new_row and new_row.weight_pct is not None else Decimal("0")
            change = new_w - old_w

            if old_row is None:
                alert_type = "new_position"
                msg = f"Nowa pozycja: {company} ({new_w:.2f}%)"
            elif new_row is None:
                alert_type = "closed_position"
                msg = f"Zamknięto pozycję: {company} (było {old_w:.2f}%)"
            elif change >= _THRESHOLD:
                alert_type = "position_increase"
                msg = f"{company}: wzrost o {change:.2f}pp ({old_w:.2f}% → {new_w:.2f}%)"
            elif change <= -_THRESHOLD:
                alert_type = "position_decrease"
                msg = f"{company}: spadek o {abs(change):.2f}pp ({old_w:.2f}% → {new_w:.2f}%)"
            else:
                continue

            change_pct = (change / old_w * 100) if old_w != 0 else None
            alerts.append(AlertOut(
                id=_make_alert_id(subfund_name, company or key, alert_type),
                fund_id=fund_id,
                alert_type=alert_type,
                company_name=company,
                ticker=isin,
                change_pct=round(change_pct, 2) if change_pct is not None else None,
                old_weight=round(old_w, 4),
                new_weight=round(new_w, 4),
                message=msg,
                is_read=False,
                created_at=created_at,
            ))

    alerts.sort(
        key=lambda a: (a.created_at, abs(float((a.new_weight or 0) - (a.old_weight or 0)))),
        reverse=True,
    )
    return alerts[:limit]


@router.get("/", response_model=list[AlertOut])
async def list_alerts(
    unread_only: bool = False,
    limit: int = 200,
    db: AsyncSession = Depends(get_db),
    user_id: str | None = Depends(get_optional_user_id),
):
    rows = (await db.execute(
        select(PortfolioComposition)
    )).scalars().all()

    subfunds = (await db.execute(
        select(Subfund)
    )).scalars().all()
    uuid_map = {f.name: f.id for f in subfunds}

    return _generate_alerts(rows, uuid_map, limit=limit)


@router.post("/mark-read", response_model=dict)
async def mark_alerts_read(
    body: AlertMarkRead,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    # Alerts are generated on-the-fly; no persistent table to update
    return {"marked": len(body.ids)}


@router.post("/mark-all-read", response_model=dict)
async def mark_all_read(
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    # Alerts are generated on-the-fly; no persistent table to update
    return {"marked": 0}
