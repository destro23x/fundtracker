"use client";

import { useState } from "react";
import useSWR from "swr";
import { subfundsApi, type PortfolioPosition, type TurnoverPeriodOut } from "@/lib/api";
import { formatCurrency } from "@/lib/utils";
import { Search, X, ArrowUpDown, Calendar } from "lucide-react";
import Link from "next/link";
import {
  BarChart,
  Bar,
  Cell,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
} from "recharts";

const BAR_COLORS = [
  "#3b82f6","#10b981","#f59e0b","#ef4444","#8b5cf6",
  "#06b6d4","#84cc16","#f97316","#ec4899","#14b8a6",
  "#6366f1","#eab308","#22c55e","#0ea5e9","#a855f7",
  "#fb923c","#34d399","#60a5fa","#f472b6","#4ade80",
];

// ─── Wskaźnik obrotu (PTR) ────────────────────────────────────────────────────

function formatAmount(v: number, currency: string): string {
  if (currency === "PLN") {
    if (v >= 1_000_000_000) return `${(v / 1_000_000_000).toFixed(2)} mld PLN`;
    if (v >= 1_000_000) return `${(v / 1_000_000).toFixed(1)} mln PLN`;
    if (v >= 1_000) return `${(v / 1_000).toFixed(0)} tys. PLN`;
    return `${v.toFixed(0)} PLN`;
  }
  return `${v.toFixed(1)}%`;
}

function TurnoverSection({ subfundId }: { subfundId: string }) {
  const { data: periods, isLoading } = useSWR(
    `subfund-turnover-${subfundId}`,
    () => subfundsApi.turnover(subfundId)
  );

  if (isLoading || !periods || periods.length === 0) return null;

  const latest = periods[0];

  return (
    <div className="rounded-lg border bg-card overflow-hidden">
      {/* Nagłówek z wyróżnionym ostatnim PTR */}
      <div className="p-4 border-b flex items-center justify-between gap-4">
        <div>
          <h2 className="font-semibold">Wskaźnik obrotu portfela (PTR)</h2>
          <p className="text-xs text-muted-foreground mt-0.5">
            min(kupno, sprzedaż) / średnie aktywa × 100%
            {latest.currency === "%" && (
              <span className="ml-1 text-yellow-500 dark:text-yellow-400">
                · szacunkowy (brak danych wartościowych, obliczony z wag)
              </span>
            )}
          </p>
        </div>
        {latest.ptr !== null && (
          <div className="text-right shrink-0">
            <div
              className={`text-2xl font-bold tabular-nums ${
                latest.ptr < 25
                  ? "text-green-500"
                  : latest.ptr < 75
                  ? "text-yellow-500"
                  : "text-red-500"
              }`}
            >
              {latest.ptr.toFixed(1)}%
            </div>
            <div className="text-xs text-muted-foreground">
              {latest.date_from.slice(0, 7)} → {latest.date_to.slice(0, 7)}
            </div>
          </div>
        )}
      </div>

      {/* Tabela wszystkich okresów */}
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-xs text-muted-foreground bg-muted/30">
              <th className="text-left px-4 py-2 font-medium">Okres</th>
              <th className="text-right px-4 py-2 font-medium">PTR</th>
              <th className="text-right px-4 py-2 font-medium">Kupno</th>
              <th className="text-right px-4 py-2 font-medium">Sprzedaż</th>
              <th className="text-right px-4 py-2 font-medium">Śred. aktywa</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border/40">
            {periods.map((p: TurnoverPeriodOut, i: number) => (
              <tr
                key={i}
                className={i === 0 ? "font-medium" : "text-muted-foreground text-xs"}
              >
                <td className="px-4 py-2.5 tabular-nums whitespace-nowrap">
                  {p.date_from} → {p.date_to}
                </td>
                <td className="px-4 py-2.5 text-right tabular-nums font-semibold">
                  {p.ptr !== null ? `${p.ptr.toFixed(1)}%` : "—"}
                </td>
                <td className="px-4 py-2.5 text-right tabular-nums text-emerald-600 dark:text-emerald-400">
                  +{formatAmount(p.bought, p.currency)}
                </td>
                <td className="px-4 py-2.5 text-right tabular-nums text-red-500">
                  −{formatAmount(p.sold, p.currency)}
                </td>
                <td className="px-4 py-2.5 text-right tabular-nums">
                  {formatAmount(p.average_assets, p.currency)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export default function SubfundDetailPage({ params }: { params: { id: string } }) {
  const subfundId = params.id;
  const { data: subfund } = useSWR(`subfund-${subfundId}`, () => subfundsApi.get(subfundId));
  const { data: dates } = useSWR(`subfund-dates-${subfundId}`, () => subfundsApi.portfolioDates(subfundId));

  const [selectedDate, setSelectedDate] = useState<string | undefined>(undefined);
  const activeDate = selectedDate ?? dates?.[0];

  const { data: positions, isLoading } = useSWR(
    activeDate ? `portfolio-${subfundId}-${activeDate}` : null,
    () => subfundsApi.portfolio(subfundId, activeDate)
  );

  return (
    <div className="space-y-6 max-w-5xl">
      {/* Header */}
      <div>
        <Link href="/subfunds" className="text-xs text-muted-foreground hover:underline">
          ← Subfundusze
        </Link>
        <h1 className="text-2xl font-bold mt-1">{subfund?.name ?? "…"}</h1>
        {subfund?.ticker && <p className="text-sm text-muted-foreground">{subfund.ticker}</p>}
      </div>

      {/* Wskaźnik obrotu */}
      <TurnoverSection subfundId={subfundId} />

      {/* Date selector */}
      {dates && dates.length > 1 && (
        <div className="flex items-center gap-2 flex-wrap">
          <Calendar className="h-4 w-4 text-muted-foreground shrink-0" />
          <span className="text-sm text-muted-foreground">Data:</span>
          {dates.map((d) => (
            <button
              key={d}
              onClick={() => setSelectedDate(d)}
              className={`px-3 py-1 rounded-full text-sm border transition-colors ${
                d === activeDate
                  ? "bg-primary text-primary-foreground border-primary"
                  : "hover:border-primary/50 text-muted-foreground"
              }`}
            >
              {d}
            </button>
          ))}
        </div>
      )}

      {/* No data */}
      {!isLoading && dates && dates.length === 0 && (
        <div className="text-muted-foreground text-sm bg-muted/40 rounded-lg p-8 text-center">
          Brak danych dla tego subfunduszu. Załaduj plik Excel na stronie{" "}
          <Link href="/upload" className="underline hover:text-foreground">Dane</Link>.
        </div>
      )}

      {/* Portfolio */}
      {(isLoading || (positions && positions.length > 0)) && (
        <PortfolioSection positions={positions ?? []} isLoading={isLoading} date={activeDate} />
      )}
    </div>
  );
}

// ─── Wykres słupkowy ─────────────────────────────────────────────────────────

function PortfolioBarChart({ positions }: { positions: PortfolioPosition[] }) {
  const withWeight = positions
    .filter((p) => p.weight_pct != null && p.weight_pct > 0)
    .sort((a, b) => (b.weight_pct ?? 0) - (a.weight_pct ?? 0));

  const totalExplicit = withWeight.reduce((s, p) => s + (p.weight_pct ?? 0), 0);
  const TOP = 20;
  const top = withWeight.slice(0, TOP);
  const rest = withWeight.slice(TOP);
  const restWeight = rest.reduce((s, p) => s + (p.weight_pct ?? 0), 0);
  const remaining = 100 - totalExplicit;

  const chartData: Array<{ name: string; weight: number; color: string }> = top.map((p, i) => ({
    name: p.company_name.length > 32 ? p.company_name.slice(0, 30) + "…" : p.company_name,
    weight: Math.round((p.weight_pct ?? 0) * 100) / 100,
    color: BAR_COLORS[i % BAR_COLORS.length],
  }));

  if (restWeight > 0.01) {
    chartData.push({
      name: `Pozostałe (${rest.length})`,
      weight: Math.round(restWeight * 100) / 100,
      color: "#94a3b8",
    });
  }
  if (remaining > 0.1) {
    chartData.push({ name: "Inne", weight: Math.round(remaining * 100) / 100, color: "#e2e8f0" });
  }

  const chartHeight = Math.max(220, chartData.length * 26 + 20);

  return (
    <div className="border-b p-4">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-medium text-muted-foreground">Skład portfela (%)</h3>
        <span className="text-xs text-muted-foreground">
          {totalExplicit < 99.5
            ? `wykazane: ${totalExplicit.toFixed(2)}%`
            : `łącznie: ${totalExplicit.toFixed(2)}%`}
        </span>
      </div>
      <ResponsiveContainer width="100%" height={chartHeight}>
        <BarChart layout="vertical" data={chartData} margin={{ left: 0, right: 48, top: 0, bottom: 0 }}>
          <XAxis
            type="number"
            domain={[0, Math.max(100, totalExplicit)]}
            unit="%"
            tick={{ fontSize: 10 }}
            tickCount={6}
          />
          <YAxis
            type="category"
            dataKey="name"
            width={180}
            tick={{ fontSize: 11 }}
            tickLine={false}
          />
          <Tooltip
            formatter={(v: number) => [`${v.toFixed(2)}%`, "Waga"]}
            cursor={{ fill: "rgba(0,0,0,0.04)" }}
          />
          <Bar
            dataKey="weight"
            radius={[0, 3, 3, 0]}
            label={{ position: "right", fontSize: 10, formatter: (v: number) => `${v}%` }}
          >
            {chartData.map((_, i) => (
              <Cell key={i} fill={chartData[i].color} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

// ─── Sekcja portfela ──────────────────────────────────────────────────────────

type SortCol = "name" | "weight" | "value";

function PortfolioSection({
  positions,
  isLoading,
  date,
}: {
  positions: PortfolioPosition[];
  isLoading: boolean | undefined;
  date: string | undefined;
}) {
  const [query, setQuery] = useState("");
  const [sortCol, setSortCol] = useState<SortCol>("weight");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("desc");

  const filtered = positions.filter((p) => {
    const q = query.toLowerCase();
    return (
      p.company_name.toLowerCase().includes(q) ||
      (p.isin ?? "").toLowerCase().includes(q) ||
      (p.asset_type ?? "").toLowerCase().includes(q)
    );
  });

  const sorted = [...filtered].sort((a, b) => {
    let cmp = 0;
    if (sortCol === "weight") cmp = (b.weight_pct ?? -Infinity) - (a.weight_pct ?? -Infinity);
    else if (sortCol === "name") cmp = a.company_name.localeCompare(b.company_name, "pl");
    else if (sortCol === "value") cmp = (b.value ?? -Infinity) - (a.value ?? -Infinity);
    return sortDir === "asc" ? -cmp : cmp;
  });

  function toggleSort(col: SortCol) {
    if (sortCol === col) setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    else { setSortCol(col); setSortDir(col === "name" ? "asc" : "desc"); }
  }

  function SortIcon({ col }: { col: SortCol }) {
    if (sortCol !== col)
      return <ArrowUpDown className="h-3 w-3 ml-1 text-muted-foreground/40 inline-block" />;
    return <span className="ml-1">{sortDir === "desc" ? "↓" : "↑"}</span>;
  }

  const totalWeight = positions.reduce((s, p) => s + (p.weight_pct ?? 0), 0);

  return (
    <div className="border rounded-lg bg-card overflow-hidden">
      {/* Header */}
      <div className="p-4 border-b flex items-center justify-between gap-4 flex-wrap">
        <div>
          <h2 className="font-semibold">Skład portfela</h2>
          {date && (
            <p className="text-xs text-muted-foreground mt-0.5">
              Na dzień <span className="font-medium text-foreground">{date}</span>
            </p>
          )}
        </div>
        <div className="relative">
          <Search className="h-3.5 w-3.5 absolute left-2.5 top-1/2 -translate-y-1/2 text-muted-foreground pointer-events-none" />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Szukaj pozycji…"
            className="pl-8 pr-7 py-1.5 text-xs border rounded-md bg-background focus:outline-none focus:ring-1 focus:ring-primary w-48"
          />
          {query && (
            <button
              onClick={() => setQuery("")}
              className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
            >
              <X className="h-3 w-3" />
            </button>
          )}
        </div>
      </div>

      {/* Bar chart */}
      {!isLoading && positions.length > 0 && <PortfolioBarChart positions={positions} />}

      {/* Table */}
      {isLoading ? (
        <div className="p-8 text-center text-muted-foreground text-sm animate-pulse">
          Ładowanie pozycji…
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-muted/30 select-none">
              <tr>
                <th className="text-right px-3 py-2 w-8 text-xs text-muted-foreground font-medium">#</th>
                <th
                  className="text-left px-3 py-2 font-medium cursor-pointer hover:text-foreground"
                  onClick={() => toggleSort("name")}
                >
                  Aktywo <SortIcon col="name" />
                </th>
                <th className="text-left px-3 py-2 font-medium hidden md:table-cell text-xs">ISIN</th>
                <th className="text-left px-3 py-2 font-medium hidden lg:table-cell text-xs">Typ</th>
                <th
                  className="text-right px-3 py-2 font-medium cursor-pointer hover:text-foreground"
                  onClick={() => toggleSort("weight")}
                >
                  Waga % <SortIcon col="weight" />
                </th>
                <th
                  className="text-right px-3 py-2 font-medium cursor-pointer hover:text-foreground hidden lg:table-cell"
                  onClick={() => toggleSort("value")}
                >
                  Wartość <SortIcon col="value" />
                </th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {sorted.map((p, i) => (
                <tr key={p.id} className="hover:bg-muted/20">
                  <td className="px-3 py-2 text-right text-xs text-muted-foreground tabular-nums">{i + 1}</td>
                  <td className="px-3 py-2">
                    <span className="font-medium">{p.company_name}</span>
                  </td>
                  <td className="px-3 py-2 font-mono text-xs text-muted-foreground hidden md:table-cell">
                    {p.isin ?? "—"}
                  </td>
                  <td className="px-3 py-2 text-xs text-muted-foreground hidden lg:table-cell">
                    {p.asset_type ?? "—"}
                  </td>
                  <td className="px-3 py-2 text-right tabular-nums font-medium">
                    {p.weight_pct != null ? `${p.weight_pct.toFixed(2)}%` : "—"}
                  </td>
                  <td className="px-3 py-2 text-right tabular-nums text-muted-foreground text-xs hidden lg:table-cell">
                    {p.value != null ? formatCurrency(p.value) : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {query && sorted.length === 0 && (
            <div className="p-6 text-center text-muted-foreground text-sm">
              Brak pozycji pasujących do „{query}".
            </div>
          )}
        </div>
      )}

      {/* Footer */}
      {positions.length > 0 && (
        <div className="px-4 py-2 border-t bg-muted/10 text-xs text-muted-foreground flex justify-between">
          <span>
            {query ? `${sorted.length} z ${positions.length} pozycji` : `${positions.length} pozycji`}
          </span>
          <span>Łącznie: {totalWeight.toFixed(2)}%</span>
        </div>
      )}
    </div>
  );
}
