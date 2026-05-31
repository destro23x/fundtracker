"""
Top movers endpoint — top companies where funds collectively bought/sold most.
Derived directly from snapshot comparisons (latest vs previous snapshot per fund).
"""
from __future__ import annotations

import re
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from pydantic import BaseModel
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models import PortfolioComposition
from app.dependencies import get_optional_user_id

router = APIRouter(prefix="/movers", tags=["movers"])

# ─── Asset type inference ─────────────────────────────────────────────────────

_RE_CURRENCY      = re.compile(r'^[A-Z]{3}$')
_RE_BOND_TICKER   = re.compile(r'^(DS|WZ|OK|PS|IZ|DZ|EDO|COI|ROS|SP)\d{4}$', re.I)
_RE_FUTURE        = re.compile(r'^.{1,8}[HMUZ]\d{2}$')
_RE_OTC_DERIV     = re.compile(r'^\d[A-Z]{2}')
_RE_EQUITY_ISIN   = re.compile(r'^[A-Z]{2}[A-Z0-9]{10}$')
_RE_FIO           = re.compile(r'\b(FIO|SFIO|FIZ|ETF|UCITS)\b', re.I)


def _infer_asset_type(company_name: str | None, ticker: str | None, isin: str | None) -> str:
    cn  = (company_name or "").strip()
    tk  = (ticker or "").strip()
    isn = (isin or "").upper().strip()

    # Currency: exactly 3 uppercase letters as name or ticker
    if _RE_CURRENCY.match(cn) or _RE_CURRENCY.match(tk):
        return "waluta"

    # Fund units: ISIN starts with PLFIO or name contains FIO/SFIO/FIZ/ETF/UCITS
    if isn.startswith("PLFIO") or _RE_FIO.search(cn):
        return "fundusz"

    # OTC derivatives: ticker starts with digit + 2-letter country (e.g. 1US..., 2PL...)
    if _RE_OTC_DERIV.match(tk):
        return "instrument pochodny"

    # Exchange-traded futures/options: ticker like FGBMH26, FVH26
    if _RE_FUTURE.match(tk) and not _RE_BOND_TICKER.match(tk):
        return "instrument pochodny"

    # Polish government bonds: PL0000... ISIN or DS/WZ/OK/etc. ticker
    if isn.startswith("PL0000") or _RE_BOND_TICKER.match(tk):
        return "obligacje skarbowe"

    # Equity ISIN
    if _RE_EQUITY_ISIN.match(isn):
        return "akcje"

    return "inne"

# ─── Response models ─────────────────────────────────────────────────────────

class TopMover(BaseModel):
    company_name: str
    ticker: str | None
    asset_type: str          # waluta / akcje / obligacje skarbowe / fundusz / instrument pochodny / inne
    fund_count: int
    alert_count: int           # number of fund-level position events
    total_weight_pp: float | None  # sum of |weight_change| in pp
    total_shares: float | None     # sum of |shares_change|
    funds: list[str]
    latest_date: str | None


class TopMoversResult(BaseModel):
    buys: list[TopMover]
    sells: list[TopMover]
    days: int | None


def _pos_key(p) -> str:
    return p.isin.upper() if p.isin else p.company_name.lower()


_ASSET_TYPE_MAP = {
    "stock":                    "akcje",
    "bond_government":          "obligacje skarbowe",
    "bond_corporate":           "obligacje korporacyjne",
    "bond_municipal":           "obligacje municypalne",
    "covered_bond":             "list zastawny",
    "cash":                     "waluta",
    "fund":                     "fundusz",
    "etf_foreign":              "fundusz",
    "derivative_fx":            "instrument pochodny",
    "derivative_swap":          "instrument pochodny",
    "derivative_futures_index": "instrument pochodny",
    "derivative_futures_bond":  "instrument pochodny",
    "derivative_futures_equity":"instrument pochodny",
    "repo":                     "repo",
    "other":                    "inne",
}


def _normalize_asset_type(raw: str | None) -> str:
    if not raw:
        return "inne"
    return _ASSET_TYPE_MAP.get(raw.lower(), raw)


def _to_movers(group: dict, limit: int) -> list[TopMover]:
    items = sorted(
        group.values(),
        key=lambda g: (len(g["fund_ids"]), g["total_weight_pp"]),
        reverse=True,
    )[:limit]
    return [
        TopMover(
            company_name=g["company_name"],
            ticker=g["ticker"],
            asset_type=g["asset_type"],
            fund_count=len(g["fund_ids"]),
            alert_count=g["event_count"],
            total_weight_pp=float(g["total_weight_pp"]),
            total_shares=float(g["total_shares"]) if g["total_shares"] else None,
            funds=sorted(g["fund_names"]),
            latest_date=(
                g["latest_date"].strftime("%Y-%m-%d")
                if hasattr(g["latest_date"], "strftime")
                else str(g["latest_date"])
            ),
        )
        for g in items
    ]


# ─── Endpoint ─────────────────────────────────────────────────────────────────

@router.get("/top", response_model=TopMoversResult)
async def get_top_movers(
    days: int | None = Query(default=None, ge=1, le=3650),
    limit: int = Query(default=15, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
    user_id: str | None = Depends(get_optional_user_id),
) -> TopMoversResult:
    """
    Top companies where funds collectively bought (buys) or sold (sells) most,
    ranked by number of distinct subfunds, then total weight change.
    Computed from portfolio_composition by comparing the two most recent
    snapshot dates per subfund.
    """
    since_date: date | None = (
        (datetime.now(tz=timezone.utc) - timedelta(days=days)).date()
        if days is not None
        else None
    )

    # 1. Load all portfolio_composition rows
    rows = (await db.execute(
        select(PortfolioComposition)
    )).scalars().all()

    if not rows:
        return TopMoversResult(buys=[], sells=[], days=days)

    # 2. Group: subfund_name → snapshot_date → {key → row}
    subfund_data: dict[str, dict[date, dict[str, PortfolioComposition]]] = {}
    for row in rows:
        name = row.subfund_name or row.umbrella_name or "unknown"
        dt = row.snapshot_date
        if dt is None:
            continue
        pos_key = row.isin.upper() if row.isin else (row.company_name or "").lower()
        subfund_data.setdefault(name, {}).setdefault(dt, {})[pos_key] = row

    # 3. For each subfund pick the two latest snapshot dates
    pairs: list[tuple[str, date, date]] = []
    for name, by_date in subfund_data.items():
        sorted_dates = sorted(by_date.keys(), reverse=True)
        if len(sorted_dates) < 2:
            continue
        curr_date, prev_date = sorted_dates[0], sorted_dates[1]
        if since_date and curr_date < since_date:
            continue
        pairs.append((name, curr_date, prev_date))

    if not pairs:
        return TopMoversResult(buys=[], sells=[], days=days)

    # 4. Aggregate diffs across all subfund pairs
    buy_groups: dict[str, dict] = {}
    sell_groups: dict[str, dict] = {}
    UNCHANGED_THRESHOLD = Decimal("0.005")  # ignore < 0.005 pp change

    for subfund_name, curr_date, prev_date in pairs:
        curr_pos = subfund_data[subfund_name].get(curr_date, {})
        prev_pos = subfund_data[subfund_name].get(prev_date, {})
        all_keys = set(curr_pos) | set(prev_pos)

        for key in all_keys:
            old = prev_pos.get(key)
            new = curr_pos.get(key)

            row = new or old
            company_name = row.company_name
            isin = row.isin
            asset_type = _normalize_asset_type(
                row.asset_type or _infer_asset_type(company_name, None, isin)
            )

            old_weight = Decimal(str(old.weight_pct)) if old and old.weight_pct is not None else Decimal("0")
            new_weight = Decimal(str(new.weight_pct)) if new and new.weight_pct is not None else Decimal("0")
            old_shares = Decimal(str(old.shares)) if old and old.shares is not None else Decimal("0")
            new_shares = Decimal(str(new.shares)) if new and new.shares is not None else Decimal("0")

            weight_change = new_weight - old_weight

            if old is None:
                group = buy_groups   # new position
            elif new is None:
                group = sell_groups  # closed position
            elif weight_change >= UNCHANGED_THRESHOLD:
                group = buy_groups   # position increased
            elif weight_change <= -UNCHANGED_THRESHOLD:
                group = sell_groups  # position decreased
            else:
                continue  # unchanged — skip

            if key not in group:
                group[key] = {
                    "company_name": company_name,
                    "ticker": None,
                    "isin": isin,
                    "asset_type": asset_type,
                    "fund_ids": set(),
                    "fund_names": set(),
                    "event_count": 0,
                    "total_weight_pp": Decimal("0"),
                    "total_shares": Decimal("0"),
                    "latest_date": curr_date,
                }
            g = group[key]
            g["fund_ids"].add(subfund_name)
            g["fund_names"].add(subfund_name)
            g["event_count"] += 1
            g["total_weight_pp"] += abs(weight_change)
            g["total_shares"] += abs(new_shares - old_shares)
            if curr_date > g["latest_date"]:
                g["latest_date"] = curr_date
            if isin and not g["isin"]:
                g["isin"] = isin

    return TopMoversResult(
        buys=_to_movers(buy_groups, limit),
        sells=_to_movers(sell_groups, limit),
        days=days,
    )
