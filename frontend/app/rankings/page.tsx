"use client";

import useSWR from "swr";
import Link from "next/link";
import { useState } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import {
  rankingsApi,
  type FundActivityRank,
  type FundCorrelation,
  type CommonHolder,
} from "@/lib/api";
import { positionsApi, type TopAsset } from "@/lib/api";
import { moversApi, type TopMover } from "@/lib/api";
import {
  TrendingUp,
  TrendingDown,
  BarChart2,
  Share2,
  Building2,
  Loader2,
  ArrowUpDown,
  GitMerge,
  Trophy,
  Search,
  Flame,
  CalendarDays,
} from "lucide-react";
import { cn } from "@/lib/utils";

// ─── Types ────────────────────────────────────────────────────────────────────

type OuterTab = "rankings" | "top" | "movers";
type RankingTab = "activity" | "correlations" | "common";

// ─── Shared helpers ───────────────────────────────────────────────────────────

function pct(n: number) {
  return `${(n * 100).toFixed(1)}%`;
}

function bar(value: number, max: number, colorCls: string) {
  const w = max > 0 ? Math.round((value / max) * 100) : 0;
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-1.5 bg-muted rounded-full overflow-hidden">
        <div className={cn("h-full rounded-full", colorCls)} style={{ width: `${w}%` }} />
      </div>
      <span className="text-xs tabular-nums w-8 text-right">{value}</span>
    </div>
  );
}

function LoadingSpinner() {
  return (
    <div className="flex items-center justify-center py-16">
      <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
    </div>
  );
}

function StatBadge({ icon, label, value }: { icon: React.ReactNode; label: string; value: number }) {
  return (
    <div className="flex items-center gap-3 p-3 rounded-lg border bg-card">
      <div className="text-muted-foreground">{icon}</div>
      <div>
        <div className="text-xl font-bold leading-none">{value}</div>
        <div className="text-xs text-muted-foreground mt-0.5">{label}</div>
      </div>
    </div>
  );
}

// ─── Rankings: Activity ───────────────────────────────────────────────────────

type ActivitySort = "total" | "buys" | "sells" | "snapshots";

function ActivityTable({ data }: { data: FundActivityRank[] }) {
  const [sort, setSort] = useState<ActivitySort>("total");

  const sorted = [...data].sort((a, b) => {
    if (sort === "buys") return b.buy_alerts - a.buy_alerts;
    if (sort === "sells") return b.sell_alerts - a.sell_alerts;
    if (sort === "snapshots") return b.snapshot_count - a.snapshot_count;
    return b.total_alerts - a.total_alerts;
  });

  const maxTotal = Math.max(...data.map((d) => d.total_alerts), 1);
  const maxBuys = Math.max(...data.map((d) => d.buy_alerts), 1);
  const maxSells = Math.max(...data.map((d) => d.sell_alerts), 1);

  const colBtn = (col: ActivitySort, label: string) => (
    <button
      onClick={() => setSort(col)}
      className={cn(
        "flex items-center gap-1 hover:text-foreground",
        sort === col ? "text-foreground font-semibold" : "text-muted-foreground"
      )}
    >
      {label}
      <ArrowUpDown className="h-3 w-3" />
    </button>
  );

  if (data.length === 0) {
    return (
      <div className="text-center text-muted-foreground text-sm py-12">
        Brak danych — załaduj snapshoty dla funduszy.
      </div>
    );
  }

  return (
    <div className="overflow-x-auto rounded-lg border">
      <table className="w-full text-sm">
        <thead className="bg-muted/30">
          <tr>
            <th className="text-left p-3 font-medium w-6">#</th>
            <th className="text-left p-3 font-medium">Fundusz</th>
            <th className="p-3 font-medium text-right">{colBtn("snapshots", "Snapshoty")}</th>
            <th className="p-3 font-medium">{colBtn("total", "Łączna aktywność")}</th>
            <th className="p-3 font-medium">{colBtn("buys", "Zakupy / nowe")}</th>
            <th className="p-3 font-medium">{colBtn("sells", "Sprzedaże / zamknięcia")}</th>
          </tr>
        </thead>
        <tbody className="divide-y">
          {sorted.map((f, i) => (
            <tr key={f.fund_id} className="hover:bg-muted/20">
              <td className="p-3 text-muted-foreground text-xs">{i + 1}</td>
              <td className="p-3">
                <Link href={`/subfunds/${f.fund_id}`} className="font-medium hover:underline">
                  {f.fund_name}
                </Link>
                {f.latest_snapshot_date && (
                  <div className="text-xs text-muted-foreground mt-0.5">
                    ostatni snapshot: {f.latest_snapshot_date}
                  </div>
                )}
              </td>
              <td className="p-3 text-right tabular-nums">{f.snapshot_count}</td>
              <td className="p-3 min-w-[140px]">{bar(f.total_alerts, maxTotal, "bg-primary")}</td>
              <td className="p-3 min-w-[120px]">{bar(f.buy_alerts, maxBuys, "bg-green-500")}</td>
              <td className="p-3 min-w-[120px]">{bar(f.sell_alerts, maxSells, "bg-red-400")}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ─── Rankings: Correlations ───────────────────────────────────────────────────

function CorrelationTable({ data }: { data: FundCorrelation[] }) {
  const [minShared, setMinShared] = useState(3);

  const { data: freshData, isLoading } = useSWR(
    `rankings-corr-${minShared}`,
    () => rankingsApi.correlations(minShared),
    { fallbackData: data }
  );

  const rows = freshData ?? data;

  function similarityColor(j: number): string {
    if (j >= 0.6) return "text-green-600 font-bold";
    if (j >= 0.35) return "text-yellow-600 font-semibold";
    return "text-muted-foreground";
  }

  if (rows.length === 0 && !isLoading) {
    return (
      <div className="text-center text-muted-foreground text-sm py-12">
        Brak par funduszy z co najmniej {minShared} wspólnymi pozycjami.
        <br />
        <button onClick={() => setMinShared(1)} className="mt-2 text-primary hover:underline text-xs">
          Pokaż wszystkie pary
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-3 text-sm">
        <span className="text-muted-foreground">Min. wspólnych pozycji:</span>
        {[1, 3, 5, 10, 20].map((v) => (
          <button
            key={v}
            onClick={() => setMinShared(v)}
            className={cn(
              "px-2.5 py-1 rounded-md text-xs font-medium",
              minShared === v ? "bg-primary text-primary-foreground" : "bg-muted text-muted-foreground hover:bg-accent"
            )}
          >
            {v}
          </button>
        ))}
        {isLoading && <Loader2 className="h-3 w-3 animate-spin text-muted-foreground" />}
      </div>
      <div className="overflow-x-auto rounded-lg border">
        <table className="w-full text-sm">
          <thead className="bg-muted/30">
            <tr>
              <th className="text-left p-3 font-medium">Fundusz A</th>
              <th className="text-left p-3 font-medium">Fundusz B</th>
              <th className="text-right p-3 font-medium">Wspólne pozycje</th>
              <th className="text-right p-3 font-medium">Pozycji A</th>
              <th className="text-right p-3 font-medium">Pozycji B</th>
              <th className="text-right p-3 font-medium">Podobieństwo (Jaccard)</th>
            </tr>
          </thead>
          <tbody className="divide-y">
            {rows.map((c, i) => (
              <tr key={i} className="hover:bg-muted/20">
                <td className="p-3">
                  <Link href={`/subfunds/${c.fund_a_id}`} className="hover:underline font-medium">
                    {c.fund_a_name}
                  </Link>
                </td>
                <td className="p-3">
                  <Link href={`/subfunds/${c.fund_b_id}`} className="hover:underline font-medium">
                    {c.fund_b_name}
                  </Link>
                </td>
                <td className="p-3 text-right tabular-nums">{c.shared_positions}</td>
                <td className="p-3 text-right tabular-nums text-muted-foreground">{c.total_positions_a}</td>
                <td className="p-3 text-right tabular-nums text-muted-foreground">{c.total_positions_b}</td>
                <td className={cn("p-3 text-right tabular-nums", similarityColor(c.jaccard_similarity))}>
                  {pct(c.jaccard_similarity)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="text-xs text-muted-foreground">
        Jaccard = wspólne / (A ∪ B). Im wyższy %, tym bardziej zbliżony skład portfeli.
      </p>
    </div>
  );
}

// ─── Rankings: Common Stocks ──────────────────────────────────────────────────

const COMMON_FUNDS_PREVIEW = 3;

function FundsCell({ funds }: { funds: string[] }) {
  const [expanded, setExpanded] = useState(false);
  const visible = expanded ? funds : funds.slice(0, COMMON_FUNDS_PREVIEW);
  const hidden = funds.length - COMMON_FUNDS_PREVIEW;
  return (
    <div className="flex flex-wrap gap-1 items-center">
      {visible.map((name) => (
        <span key={name} className="px-1.5 py-0.5 rounded bg-muted text-muted-foreground text-xs">
          {name}
        </span>
      ))}
      {!expanded && hidden > 0 && (
        <button
          onClick={() => setExpanded(true)}
          className="px-1.5 py-0.5 rounded bg-muted text-primary text-xs font-medium hover:bg-accent transition-colors"
        >
          +{hidden} więcej…
        </button>
      )}
      {expanded && hidden > 0 && (
        <button
          onClick={() => setExpanded(false)}
          className="px-1.5 py-0.5 rounded bg-muted text-muted-foreground text-xs hover:bg-accent transition-colors"
        >
          zwiń
        </button>
      )}
    </div>
  );
}

function CommonStocksTable({ data }: { data: CommonHolder[] }) {
  const [minFunds, setMinFunds] = useState(2);

  const { data: freshData, isLoading } = useSWR(
    `rankings-common-${minFunds}`,
    () => rankingsApi.commonStocks(minFunds),
    { fallbackData: data }
  );

  const rows = freshData ?? data;
  const maxCount = Math.max(...rows.map((r) => r.fund_count), 1);

  if (rows.length === 0 && !isLoading) {
    return (
      <div className="text-center text-muted-foreground text-sm py-12">
        Brak aktywów trzymanych przez co najmniej {minFunds} fundusze.
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-3 text-sm">
        <span className="text-muted-foreground">Min. funduszy trzyma aktywo:</span>
        {[2, 3, 5].map((v) => (
          <button
            key={v}
            onClick={() => setMinFunds(v)}
            className={cn(
              "px-2.5 py-1 rounded-md text-xs font-medium",
              minFunds === v ? "bg-primary text-primary-foreground" : "bg-muted text-muted-foreground hover:bg-accent"
            )}
          >
            {v}+
          </button>
        ))}
        {isLoading && <Loader2 className="h-3 w-3 animate-spin text-muted-foreground" />}
      </div>
      <div className="overflow-x-auto rounded-lg border">
        <table className="w-full text-sm">
          <thead className="bg-muted/30">
            <tr>
              <th className="text-left p-3 font-medium w-6">#</th>
              <th className="text-left p-3 font-medium">Aktywo</th>
              <th className="text-left p-3 font-medium">ISIN</th>
              <th className="p-3 font-medium">Liczba funduszy</th>
              <th className="text-left p-3 font-medium">Fundusze</th>
            </tr>
          </thead>
          <tbody className="divide-y">
            {rows.map((r, i) => (
              <tr key={i} className="hover:bg-muted/20">
                <td className="p-3 text-muted-foreground text-xs">{i + 1}</td>
                <td className="p-3 font-medium">
                  <Link
                    href={`/search?q=${encodeURIComponent(r.isin ?? r.company_name)}`}
                    className="hover:underline hover:text-primary transition-colors"
                  >
                    {r.company_name}
                  </Link>
                </td>
                <td className="p-3 font-mono text-xs text-muted-foreground">{r.isin ?? "—"}</td>
                <td className="p-3 min-w-[140px]">{bar(r.fund_count, maxCount, "bg-primary")}</td>
                <td className="p-3"><FundsCell funds={r.funds} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ─── Rankings tab (inner sub-tabs) ───────────────────────────────────────────

function RankingsTab() {
  const [tab, setTab] = useState<RankingTab>("activity");

  const { data: activity, isLoading: loadingActivity } = useSWR("rankings-activity", rankingsApi.activity);
  const { data: correlations, isLoading: loadingCorr } = useSWR("rankings-corr-3", () => rankingsApi.correlations(3));
  const { data: common, isLoading: loadingCommon } = useSWR("rankings-common-2", () => rankingsApi.commonStocks(2));

  const innerTabs: { id: RankingTab; label: string; icon: React.ReactNode }[] = [
    { id: "activity",     label: "Aktywność funduszy", icon: <BarChart2 className="h-4 w-4" /> },
    { id: "correlations", label: "Korelacje portfeli",  icon: <GitMerge className="h-4 w-4" /> },
    { id: "common",       label: "Popularne aktywa",    icon: <Building2 className="h-4 w-4" /> },
  ];

  return (
    <div className="space-y-4">
      <div className="flex gap-1 border-b">
        {innerTabs.map(({ id, label, icon }) => (
          <button
            key={id}
            onClick={() => setTab(id)}
            className={cn(
              "flex items-center gap-1.5 px-4 py-2.5 text-sm font-medium border-b-2 transition-colors",
              tab === id
                ? "border-primary text-primary"
                : "border-transparent text-muted-foreground hover:text-foreground hover:border-muted-foreground"
            )}
          >
            {icon}
            {label}
          </button>
        ))}
      </div>
      {tab === "activity" && (
        loadingActivity ? <LoadingSpinner /> : (
          <>
            {activity && activity.length > 0 && (
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 mb-4">
                <StatBadge icon={<BarChart2 className="h-4 w-4" />} label="Funduszy" value={activity.length} />
                <StatBadge icon={<TrendingUp className="h-4 w-4" />} label="Łącznych alertów" value={activity.reduce((s, f) => s + f.total_alerts, 0)} />
                <StatBadge icon={<TrendingDown className="h-4 w-4" />} label="Łącznie sprzedaży" value={activity.reduce((s, f) => s + f.sell_alerts, 0)} />
              </div>
            )}
            <ActivityTable data={activity ?? []} />
          </>
        )
      )}
      {tab === "correlations" && (loadingCorr ? <LoadingSpinner /> : <CorrelationTable data={correlations ?? []} />)}
      {tab === "common"       && (loadingCommon ? <LoadingSpinner /> : <CommonStocksTable data={common ?? []} />)}
    </div>
  );
}

// ─── Top wartościami tab ──────────────────────────────────────────────────────

function fmtValue(v: number, currency: string) {
  if (v >= 1_000_000_000) return `${(v / 1_000_000_000).toFixed(2)} mld ${currency}`;
  if (v >= 1_000_000)     return `${(v / 1_000_000).toFixed(2)} mln ${currency}`;
  if (v >= 1_000)         return `${(v / 1_000).toFixed(1)} tys. ${currency}`;
  return `${v.toFixed(0)} ${currency}`;
}

function fmtSharesTop(v: number | null) {
  if (!v) return "—";
  if (v >= 1_000_000) return `${(v / 1_000_000).toFixed(2)} M`;
  if (v >= 1_000)     return `${(v / 1_000).toFixed(1)} tys.`;
  return new Intl.NumberFormat("pl-PL").format(Math.round(v));
}

const LIMIT_OPTIONS = [25, 50, 100];

function AssetRow({ item, maxValue }: { item: TopAsset; maxValue: number }) {
  const p = maxValue > 0 ? (item.total_value / maxValue) * 100 : 0;
  return (
    <div className="flex items-center gap-3 px-4 py-3 border-b last:border-0 hover:bg-muted/20 transition-colors group">
      <span className="w-8 text-right text-sm font-mono text-muted-foreground shrink-0">{item.rank}</span>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <Link
            href={`/search?q=${encodeURIComponent(item.isin ?? item.company_name)}`}
            className="font-medium text-sm truncate hover:underline hover:text-primary"
            title={item.company_name}
          >
            {item.company_name}
          </Link>
          {item.ticker && <span className="text-xs text-muted-foreground font-mono shrink-0">{item.ticker}</span>}
          {item.isin && <span className="text-xs text-muted-foreground/60 font-mono hidden md:inline shrink-0">{item.isin}</span>}
        </div>
        <div className="mt-1 h-1.5 w-full bg-muted rounded-full overflow-hidden">
          <div className="h-full bg-primary/70 rounded-full transition-all" style={{ width: `${p}%` }} />
        </div>
      </div>
      <span className="w-36 text-right text-sm font-mono font-semibold shrink-0">
        {fmtValue(item.total_value, item.currency)}
      </span>
      <span className="w-24 text-right text-xs font-mono text-muted-foreground shrink-0 hidden sm:block">
        {fmtSharesTop(item.total_shares)}
      </span>
      <span className="w-16 text-right text-xs text-muted-foreground shrink-0">{item.fund_count} fund.</span>
      <Link
        href={`/search?q=${encodeURIComponent(item.isin ?? item.company_name)}`}
        className="opacity-0 group-hover:opacity-100 transition-opacity text-muted-foreground hover:text-primary shrink-0"
        title="Szczegóły"
      >
        <Search className="h-3.5 w-3.5" />
      </Link>
    </div>
  );
}

function TopTab() {
  const [limit, setLimit] = useState(50);
  const { data, error, isLoading } = useSWR(
    ["positions/top", limit],
    () => positionsApi.top(limit),
    { revalidateOnFocus: false }
  );
  const maxValue = data?.[0]?.total_value ?? 1;

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between gap-4">
        <p className="text-sm text-muted-foreground">
          Aktywa
          
           z największym łącznym kapitałem we wszystkich funduszach (najnowszy snapshot każdego funduszu)
        </p>
        <div className="flex items-center gap-1 shrink-0">
          {LIMIT_OPTIONS.map((l) => (
            <button
              key={l}
              onClick={() => setLimit(l)}
              className={`text-xs px-2.5 py-1 rounded font-medium transition-colors ${
                limit === l ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:bg-muted/50"
              }`}
            >
              Top {l}
            </button>
          ))}
        </div>
      </div>
      <div className="rounded-lg border bg-card overflow-hidden">
        <div className="flex items-center gap-3 px-4 py-2 bg-muted/40 border-b text-xs text-muted-foreground font-medium">
          <span className="w-8 text-right shrink-0">#</span>
          <span className="flex-1">Aktywo</span>
          <span className="w-36 text-right shrink-0">Wartość łączna</span>
          <span className="w-24 text-right shrink-0 hidden sm:block">Ilość</span>
          <span className="w-16 text-right shrink-0">Fundusze</span>
          <span className="w-3.5 shrink-0" />
        </div>
        {isLoading && (
          <div className="flex items-center justify-center gap-2 py-16 text-muted-foreground">
            <Loader2 className="h-5 w-5 animate-spin" />
            <span className="text-sm">Ładowanie…</span>
          </div>
        )}
        {error && <p className="text-sm text-destructive text-center py-10">Błąd ładowania danych.</p>}
        {data && data.length === 0 && <p className="text-sm text-muted-foreground text-center py-10">Brak danych — najpierw wgraj snapshoty.</p>}
        {data?.map((item) => <AssetRow key={item.isin ?? item.company_name} item={item} maxValue={maxValue} />)}
      </div>
      {data && (
        <p className="text-xs text-muted-foreground text-right">
          {data.length} pozycji · wartości w walucie pozycji (PLN, EUR, …)
        </p>
      )}
    </div>
  );
}

// ─── Top aktywa tab (movers) ──────────────────────────────────────────────────

const ASSET_TYPE_STYLES: Record<string, { label: string; className: string }> = {
  "akcje":                      { label: "Akcje",               className: "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400" },
  "obligacje skarbowe":         { label: "Obligacje skarbowe",  className: "bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400" },
  "waluta":                     { label: "Waluta",              className: "bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400" },
  "fundusz":                    { label: "Fundusz",             className: "bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-400" },
  "instrument pochodny":        { label: "Instrument pochodny", className: "bg-orange-100 text-orange-700 dark:bg-orange-900/30 dark:text-orange-400" },
  "stock":                      { label: "Akcje",               className: "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400" },
  "bond_government":            { label: "Obl. skarbowe",       className: "bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400" },
  "bond_corporate":             { label: "Obl. korporacyjne",   className: "bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400" },
  "bond_municipal":             { label: "Obl. municypalne",    className: "bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400" },
  "covered_bond":               { label: "List zastawny",       className: "bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400" },
  "cash":                       { label: "Gotówka/Waluta",      className: "bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400" },
  "fund":                       { label: "Fundusz",             className: "bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-400" },
  "etf_foreign":                { label: "ETF",                 className: "bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-400" },
  "derivative_fx":              { label: "Derywat FX",          className: "bg-orange-100 text-orange-700 dark:bg-orange-900/30 dark:text-orange-400" },
  "derivative_swap":            { label: "Swap",                className: "bg-orange-100 text-orange-700 dark:bg-orange-900/30 dark:text-orange-400" },
  "derivative_futures_index":   { label: "Futures",             className: "bg-orange-100 text-orange-700 dark:bg-orange-900/30 dark:text-orange-400" },
  "derivative_futures_bond":    { label: "Futures",             className: "bg-orange-100 text-orange-700 dark:bg-orange-900/30 dark:text-orange-400" },
  "derivative_futures_equity":  { label: "Futures",             className: "bg-orange-100 text-orange-700 dark:bg-orange-900/30 dark:text-orange-400" },
  "repo":                       { label: "Repo",                className: "bg-slate-100 text-slate-700 dark:bg-slate-900/30 dark:text-slate-400" },
  "other":                      { label: "Inne",                className: "bg-muted text-muted-foreground" },
  "inne":                       { label: "Inne",                className: "bg-muted text-muted-foreground" },
};

function AssetTypeBadge({ type }: { type: string }) {
  const cfg = ASSET_TYPE_STYLES[type] ?? ASSET_TYPE_STYLES["inne"];
  return (
    <span className={cn("text-xs px-1.5 py-0.5 rounded font-medium shrink-0", cfg.className)}>
      {cfg.label}
    </span>
  );
}

function fmtNum(n: number | null | undefined, decimals = 2) {
  if (n == null) return "—";
  return n.toFixed(decimals);
}

function fmtSharesMover(n: number | null | undefined) {
  if (n == null || n === 0) return null;
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(2)} M`;
  if (n >= 1_000)     return `${(n / 1_000).toFixed(1)} tys.`;
  return n.toFixed(0);
}

const DAY_OPTIONS: { label: string; value: number | null }[] = [
  { label: "30 dni",      value: 30 },
  { label: "90 dni",      value: 90 },
  { label: "180 dni",     value: 180 },
  { label: "365 dni",     value: 365 },
  { label: "Wszystkie",   value: null },
];

function MoverRow({ item, rank, color }: { item: TopMover; rank: number; color: "green" | "red" }) {
  const [expanded, setExpanded] = useState(false);
  const searchQ = encodeURIComponent(item.company_name);
  return (
    <div
      className={cn(
        "rounded-lg border bg-card px-4 py-3 space-y-1.5",
        expanded && "bg-muted/10"
      )}
    >
      <div className="flex items-center gap-3">
        <span className="text-xs text-muted-foreground w-5 shrink-0 font-mono">{rank}</span>
        <Link href={`/search?q=${searchQ}`} className="flex-1 min-w-0 hover:text-primary transition-colors">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="font-semibold text-sm truncate">{item.company_name}</span>
            {item.ticker && item.ticker !== item.company_name && (
              <span className="text-xs font-mono bg-primary/10 text-primary px-1.5 py-0.5 rounded shrink-0">
                {item.ticker}
              </span>
            )}
            <AssetTypeBadge type={item.asset_type} />
          </div>
          {item.latest_date && (
            <div className="flex items-center gap-1 text-xs text-muted-foreground mt-0.5">
              <CalendarDays className="h-3 w-3" />
              ostatnia zmiana: {item.latest_date}
            </div>
          )}
        </Link>
        <div className="flex items-center gap-2 shrink-0">
          <button
            onClick={() => setExpanded((v) => !v)}
            className={cn(
              "text-xs font-bold px-2 py-0.5 rounded-full cursor-pointer select-none hover:opacity-80 transition-opacity",
              color === "green"
                ? "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400"
                : "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400"
            )}
          >
            {item.fund_count} {item.fund_count === 1 ? "fundusz" : item.fund_count < 5 ? "fundusze" : "funduszy"}
          </button>
          {item.total_weight_pp != null && (
            <span className="text-xs font-mono text-muted-foreground hidden sm:inline">
              {color === "green" ? "+" : "−"}{fmtNum(item.total_weight_pp)} pp
            </span>
          )}
          {fmtSharesMover(item.total_shares) && (
            <span className={cn(
              "text-xs font-mono hidden md:inline px-2 py-0.5 rounded",
              color === "green"
                ? "bg-green-50 text-green-600 dark:bg-green-900/20 dark:text-green-400"
                : "bg-red-50 text-red-600 dark:bg-red-900/20 dark:text-red-400"
            )}>
              {color === "green" ? "+" : "−"}{fmtSharesMover(item.total_shares)} szt.
            </span>
          )}
        </div>
      </div>
      {expanded && item.funds.length > 0 && (
        <div className="flex flex-wrap gap-1.5 pt-1 pl-8">
          {item.funds.map((name) => (
            <span key={name} className="text-xs bg-muted text-muted-foreground px-2 py-0.5 rounded">
              {name}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

function MoverColumn({ title, subtitle, items, color, icon }: {
  title: string; subtitle: string; items: TopMover[]; color: "green" | "red"; icon: React.ReactNode;
}) {
  const headerColor = color === "green"
    ? "border-green-200 bg-green-50 dark:border-green-900 dark:bg-green-950/30"
    : "border-red-200 bg-red-50 dark:border-red-900 dark:bg-red-950/30";
  return (
    <div className="flex-1 min-w-0 space-y-2">
      <div className={cn("rounded-lg border px-4 py-3", headerColor)}>
        <div className="flex items-center gap-2">
          <div className={color === "green" ? "text-green-600 dark:text-green-400" : "text-red-600 dark:text-red-400"}>{icon}</div>
          <div>
            <div className="font-semibold text-sm">{title}</div>
            <div className="text-xs text-muted-foreground">{subtitle}</div>
          </div>
          <span className="ml-auto text-lg font-bold">{items.length}</span>
        </div>
      </div>
      {items.length === 0 ? (
        <div className="text-center text-muted-foreground text-sm py-8 border rounded-lg">
          <Building2 className="h-8 w-8 mx-auto mb-2 opacity-20" />
          Brak danych dla wybranego okresu.
        </div>
      ) : (
        <div className="space-y-1.5">
          {items.map((item, i) => <MoverRow key={item.company_name} item={item} rank={i + 1} color={color} />)}
        </div>
      )}
    </div>
  );
}

function MoversTab() {
  const [days, setDays] = useState<number | null>(null);
  const { data, isLoading } = useSWR(`movers-${days}`, () => moversApi.top(days));

  return (
    <div className="space-y-5">
      <div className="flex items-center gap-2 flex-wrap">
        <span className="text-sm text-muted-foreground">Okres:</span>
        {DAY_OPTIONS.map(({ label, value }) => (
          <button
            key={label}
            onClick={() => setDays(value)}
            className={cn(
              "px-3 py-1.5 rounded-md text-xs font-medium transition-colors",
              days === value ? "bg-primary text-primary-foreground" : "bg-muted text-muted-foreground hover:bg-accent"
            )}
          >
            {label}
          </button>
        ))}
        {isLoading && <Loader2 className="h-4 w-4 animate-spin text-muted-foreground ml-1" />}
      </div>
      {isLoading && !data ? (
        <div className="flex items-center justify-center py-20">
          <Loader2 className="h-7 w-7 animate-spin text-muted-foreground" />
        </div>
      ) : (
        <div className="flex flex-col lg:flex-row gap-4">
          <MoverColumn title="Dokupowały" subtitle="nowe i zwiększone pozycje" items={data?.buys ?? []} color="green" icon={<TrendingUp className="h-5 w-5" />} />
          <MoverColumn title="Sprzedawały" subtitle="zamknięte i zmniejszone pozycje" items={data?.sells ?? []} color="red" icon={<TrendingDown className="h-5 w-5" />} />
        </div>
      )}
      {data && (
        <p className="text-xs text-muted-foreground text-center">
          Kliknij wiersz, aby zobaczyć listę funduszy. Kolumna &ldquo;pp&rdquo; to suma zmian udziałów w portfelu (w punktach procentowych).
        </p>
      )}
    </div>
  );
}

// ─── Page ─────────────────────────────────────────────────────────────────────

const OUTER_TABS: { id: OuterTab; label: string; icon: React.ReactNode }[] = [
  { id: "rankings", label: "Ranking funduszy", icon: <Share2 className="h-4 w-4" /> },
  { id: "top",      label: "Top wartościami",  icon: <Trophy className="h-4 w-4" /> },
  { id: "movers",   label: "Top aktywa",       icon: <Flame className="h-4 w-4" /> },
];

export default function RankingsPage() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const [tab, setTab] = useState<OuterTab>((searchParams.get("tab") as OuterTab | null) ?? "rankings");

  function switchTab(t: OuterTab) {
    setTab(t);
    router.replace(`/rankings?tab=${t}`, { scroll: false });
  }

  return (
    <div className="space-y-6 max-w-6xl">
      <div>
        <h1 className="text-2xl font-bold flex items-center gap-2">
          <BarChart2 className="h-6 w-6 text-primary" />
          Rankingi i analizy
        </h1>
        <p className="text-muted-foreground text-sm mt-1">
          Aktywność funduszy, top aktywa wartościami oraz zmiany zaangażowania.
        </p>
      </div>

      <div className="flex gap-1 border-b">
        {OUTER_TABS.map(({ id, label, icon }) => (
          <button
            key={id}
            onClick={() => switchTab(id)}
            className={cn(
              "flex items-center gap-1.5 px-5 py-3 text-sm font-medium border-b-2 transition-colors",
              tab === id
                ? "border-primary text-primary"
                : "border-transparent text-muted-foreground hover:text-foreground hover:border-muted-foreground"
            )}
          >
            {icon}
            {label}
          </button>
        ))}
      </div>

      {tab === "rankings" && <RankingsTab />}
      {tab === "top"      && <TopTab />}
      {tab === "movers"   && <MoversTab />}
    </div>
  );
}
