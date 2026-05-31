"use client";

import { useState, useRef, useEffect } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import { positionsApi, type CompanyHoldings, type HoldingPerFund } from "@/lib/api";
import { Search, Building2, ChevronDown, ChevronUp, ExternalLink, BarChart2, Table, Filter, TrendingUp, Pencil, Check } from "lucide-react";
import { TradingViewMiniChart } from "@/components/TradingViewMiniChart";
import { cn } from "@/lib/utils";
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
} from "recharts";

function fmt(n: number | null, decimals = 2) {
  if (n == null) return "—";
  return new Intl.NumberFormat("pl-PL", {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  }).format(n);
}

function fmtShares(n: number | null) {
  if (n == null) return "—";
  return new Intl.NumberFormat("pl-PL", { maximumFractionDigits: 0 }).format(n);
}

/** Resolve TradingView symbol from ticker + ISIN */
function resolveSymbol(ticker: string, isin: string | null): string {
  if (isin?.startsWith("PL")) return `GPW:${ticker}`;
  if (isin?.startsWith("US")) return ticker; // US stocks usually auto-resolve
  if (isin?.startsWith("DE")) return `XETRA:${ticker}`;
  return ticker; // best-effort for others
}

const CHART_COLORS = [
  "#3b82f6", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6",
  "#06b6d4", "#ec4899", "#84cc16", "#f97316", "#64748b",
];

function shortFundName(name: string): string {
  return name
    .replace(/^ALIOR\s+/i, "")
    .replace(/^Goldman Sachs\s+/i, "GS ")
    .replace(/^VeloFund\s+/i, "")
    .replace(/^Noble Funds\s+/i, "")
    .replace(/^PKO\s+/i, "PKO ");
}

function HoldingsCard({ h }: { h: CompanyHoldings }) {
  const [open, setOpen] = useState(false);
  const [view, setView] = useState<"table" | "chart" | "notowania">("table");
  const [tvSymbol, setTvSymbol] = useState<string>(
    h.ticker ? resolveSymbol(h.ticker, h.isin) : ""
  );
  const [editingSymbol, setEditingSymbol] = useState(false);
  const [symbolDraft, setSymbolDraft] = useState("");
  const [chartMode, setChartMode] = useState<"current" | "history">("current");
  const [logScale, setLogScale] = useState(false);
  const [historyData, setHistoryData] = useState<HoldingPerFund[] | null>(null);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [selectedFunds, setSelectedFunds] = useState<Set<string>>(new Set());
  const [fundFilter, setFundFilter] = useState("");

  async function loadHistory() {
    if (historyData) {
      setChartMode("history");
      return;
    }
    setHistoryLoading(true);
    try {
      const data = await positionsApi.companyHistory(
        h.isin ? { isin: h.isin } : { q: h.company_name }
      );
      const allFundNames = Array.from(new Set(data.map((p) => p.fund_name)));
      setHistoryData(data);
      setSelectedFunds(new Set(allFundNames));
      setFundFilter("");
      setChartMode("history");
    } catch {
      // silently fail, stay in current mode
    } finally {
      setHistoryLoading(false);
    }
  }

  function toggleFund(name: string) {
    setSelectedFunds((prev) => {
      const next = new Set(prev);
      if (next.has(name)) {
        // nie pozwól odznaczył ostatniego
        if (next.size <= 1) return prev;
        next.delete(name);
      } else {
        next.add(name);
      }
      return next;
    });
  }

  // Bar chart: latest snapshot per fund.
  // When history is loaded use it (covers funds that no longer hold the stock).
  // Falls back to h.funds before history is fetched.
  const barData = (() => {
    const source: HoldingPerFund[] = historyData && historyData.length > 0
      ? (() => {
          const latestPerFund = new Map<string, HoldingPerFund>();
          for (const p of historyData) {
            const existing = latestPerFund.get(p.fund_id);
            if (!existing || p.snapshot_date > existing.snapshot_date) {
              latestPerFund.set(p.fund_id, p);
            }
          }
          return Array.from(latestPerFund.values()).sort(
            (a, b) => (b.shares ?? 0) - (a.shares ?? 0)
          );
        })()
      : h.funds;

    return source.map((f) => ({
      name: shortFundName(f.fund_name),
      fullName: f.fund_name,
      shares: f.shares ?? 0,
      value: f.value ?? 0,
      currency: f.currency,
      date: f.snapshot_date,
    }));
  })();

  // Y-axis domain computed from data so Recharts never has to guess
  const maxShares = barData.length ? Math.max(...barData.map((d) => d.shares)) : 1;
  const yDomain: [number, number] = logScale
    ? [1, Math.max(1, maxShares)]
    : [0, Math.ceil(maxShares * 1.05)];

  // Line chart: pivot history by date → { date, FundA, FundB }[]
  const fundNames = Array.from(new Set((historyData ?? []).map((p) => p.fund_name)));
  const visibleFundNames = fundNames.filter((n) => selectedFunds.has(n));
  const lineData: Record<string, string | number>[] = [];
  if (historyData) {
    const dateMap = new Map<string, Record<string, string | number>>();
    for (const point of historyData) {
      if (!dateMap.has(point.snapshot_date)) {
        dateMap.set(point.snapshot_date, { date: point.snapshot_date });
      }
      dateMap.get(point.snapshot_date)![point.fund_name] = point.shares ?? 0;
    }
    lineData.push(
      ...Array.from(dateMap.values()).sort((a, b) =>
        String(a.date).localeCompare(String(b.date))
      )
    );
  }
  const hasMultipleDates = lineData.length > 1;

  // Zmiany procentowe vs poprzedni snapshot: date → fundName → pctChange
  const lineChanges = new Map<string, Map<string, number | null>>();
  for (let i = 1; i < lineData.length; i++) {
    const curr = lineData[i];
    const prev = lineData[i - 1];
    const changes = new Map<string, number | null>();
    for (const name of fundNames) {
      const currVal = curr[name] as number | undefined;
      const prevVal = prev[name] as number | undefined;
      if (currVal != null && prevVal != null && prevVal !== 0) {
        changes.set(name, ((currVal - prevVal) / prevVal) * 100);
      } else {
        changes.set(name, null);
      }
    }
    lineChanges.set(String(curr.date), changes);
  }

  return (
    <div className="rounded-lg border bg-card shadow-sm overflow-hidden">
      {/* Nagłówek — sumaryczne dane */}
      <div
        className="flex items-center gap-4 px-5 py-4 cursor-pointer hover:bg-muted/30 transition-colors"
        onClick={() => setOpen((v) => !v)}
      >
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <Building2 className="h-4 w-4 text-muted-foreground shrink-0" />
            <span className="font-semibold truncate">{h.company_name}</span>
            {h.isin && (
              <span className="text-xs text-muted-foreground font-mono shrink-0">{h.isin}</span>
            )}
            {h.ticker && (
              <span className="text-xs bg-primary/10 text-primary px-1.5 py-0.5 rounded shrink-0">
                {h.ticker}
              </span>
            )}
          </div>
          <p className="text-xs text-muted-foreground mt-0.5">
            {h.fund_count} {h.fund_count === 1 ? "subfundusz" : "subfunduszy"}
          </p>
        </div>

        {/* Sumy */}
        <div className="text-right shrink-0 hidden sm:block">
          <p className="font-mono font-medium text-sm">
            {fmt(h.total_value)} {h.currency}
          </p>
          <p className="text-xs text-muted-foreground">{fmtShares(h.total_shares)} szt.</p>
        </div>

        <button className="text-muted-foreground shrink-0">
          {open ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
        </button>
      </div>

      {/* Rozwinięta sekcja */}
      {open && (
        <div className="border-t">
          {/* Przełącznik Tabela / Wykres */}
          <div className="flex items-center gap-1.5 px-5 py-2.5 border-b bg-muted/10">
            <button
              onClick={() => setView("table")}
              className={cn(
                "flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-md font-medium transition-colors",
                view === "table"
                  ? "bg-primary text-primary-foreground"
                  : "text-muted-foreground hover:bg-muted/50"
              )}
            >
              <Table className="h-3 w-3" />
              Tabela
            </button>
            <button
              onClick={() => setView("chart")}
              className={cn(
                "flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-md font-medium transition-colors",
                view === "chart"
                  ? "bg-primary text-primary-foreground"
                  : "text-muted-foreground hover:bg-muted/50"
              )}
            >
              <BarChart2 className="h-3 w-3" />
              Wykres
            </button>
            {h.ticker && (
              <button
                onClick={() => {
                  setTvSymbol(resolveSymbol(h.ticker!, h.isin));
                  setView("notowania");
                }}
                className={cn(
                  "flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-md font-medium transition-colors",
                  view === "notowania"
                    ? "bg-primary text-primary-foreground"
                    : "text-muted-foreground hover:bg-muted/50"
                )}
              >
                <TrendingUp className="h-3 w-3" />
                Notowania TV
              </button>
            )}
          </div>

          {/* --- Widok: Tabela --- */}
          {view === "table" && (
            <div className="divide-y">
              <div className="grid grid-cols-5 gap-2 px-5 py-2 text-xs font-medium text-muted-foreground bg-muted/20">
                <span className="col-span-2">Subfundusz</span>
                <span className="text-right">Ilość (szt.)</span>
                <span className="text-right">Wartość</span>
                <span className="text-right">Udział %</span>
              </div>
              {h.funds.map((f) => (
                <div
                  key={f.snapshot_id}
                  className="grid grid-cols-5 gap-2 px-5 py-3 items-center text-sm hover:bg-muted/20"
                >
                  <div className="col-span-2 min-w-0">
                    <Link
                      href={`/subfunds/${f.fund_id}`}
                      className="text-primary hover:underline flex items-center gap-1 truncate"
                    >
                      {f.fund_name}
                      <ExternalLink className="h-3 w-3 shrink-0" />
                    </Link>
                    <p className="text-xs text-muted-foreground">{f.snapshot_date}</p>
                  </div>
                  <span className="text-right font-mono text-sm">{fmtShares(f.shares)}</span>
                  <span className="text-right font-mono text-sm">
                    {fmt(f.value)} {f.currency}
                  </span>
                  <span className="text-right font-mono text-sm">
                    {f.weight_pct != null ? `${fmt(f.weight_pct, 4)}%` : "—"}
                  </span>
                </div>
              ))}

              {/* Suma */}
              <div className="grid grid-cols-5 gap-2 px-5 py-3 items-center text-sm bg-muted/30 font-semibold">
                <span className="col-span-2 text-muted-foreground">Razem</span>
                <span className="text-right font-mono">{fmtShares(h.total_shares)}</span>
                <span className="text-right font-mono">
                  {fmt(h.total_value)} {h.currency}
                </span>
                <span />
              </div>
            </div>
          )}

          {/* --- Widok: Wykres --- */}
          {view === "chart" && (
            <div className="p-5 space-y-4">
              {/* Sub-przełącznik: Aktualne / Historia */}
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-1.5">
                  <button
                    onClick={() => setChartMode("current")}
                    className={cn(
                      "text-xs px-2.5 py-1 rounded font-medium transition-colors",
                      chartMode === "current"
                        ? "bg-secondary text-secondary-foreground"
                        : "text-muted-foreground hover:bg-muted/50"
                    )}
                  >
                    Aktualne
                  </button>
                  <button
                    onClick={loadHistory}
                    disabled={historyLoading}
                    className={cn(
                      "text-xs px-2.5 py-1 rounded font-medium transition-colors disabled:opacity-60",
                      chartMode === "history"
                        ? "bg-secondary text-secondary-foreground"
                        : "text-muted-foreground hover:bg-muted/50"
                    )}
                  >
                    {historyLoading ? "Ładowanie…" : "Historia"}
                  </button>
                </div>
                {chartMode === "current" && (
                  <button
                    onClick={() => setLogScale((v) => !v)}
                    className={cn(
                      "text-xs px-2.5 py-1 rounded font-medium transition-colors",
                      logScale
                        ? "bg-secondary text-secondary-foreground"
                        : "text-muted-foreground hover:bg-muted/50"
                    )}
                  >
                    log
                  </button>
                )}
              </div>

              {/* Bar chart — aktualne zaangażowanie per fundusz
                   Renderowany też w trybie Historia gdy jest tylko jeden snapshot,
                   wtedy barData pochodzi z historyData (łącznie z nieaktywnymi subfunduszami). */}
              {(chartMode === "current" || (chartMode === "history" && historyData != null && !hasMultipleDates)) && (
                <div>
                  <p className="text-xs text-muted-foreground mb-3">
                    {chartMode === "history"
                      ? "Zaangażowanie wg subfunduszu — ostatni snapshot (łącznie z nieaktywnymi)"
                      : historyData
                      ? "Liczba akcji wg subfunduszu (ostatni snapshot na fundusz)"
                      : "Liczba akcji wg subfunduszu (najnowszy snapshot)"}
                  </p>
                  <ResponsiveContainer width="100%" height={280}>
                    <BarChart
                      data={barData}
                      margin={{ top: 5, right: 10, left: 0, bottom: 60 }}
                    >
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis
                        dataKey="name"
                        tick={{ fontSize: 11 }}
                        angle={-35}
                        textAnchor="end"
                        interval={0}
                      />
                      <YAxis
                        {...(logScale ? { scale: "log" as const, allowDataOverflow: true } : {})}
                        domain={yDomain}
                        tick={{ fontSize: 11 }}
                        tickFormatter={(v: number) =>
                          new Intl.NumberFormat("pl-PL", {
                            notation: "compact",
                            maximumFractionDigits: 1,
                          }).format(v)
                        }
                      />
                      <Tooltip
                        content={({ active, payload }) => {
                          if (!active || !payload?.length) return null;
                          const d = payload[0].payload as typeof barData[0];
                          return (
                            <div className="bg-background border rounded shadow-lg px-3 py-2 text-sm">
                              <p className="font-medium text-xs text-muted-foreground mb-1">
                                {d.fullName}
                              </p>
                              <p className="font-mono font-semibold">
                                {new Intl.NumberFormat("pl-PL", {
                                  maximumFractionDigits: 0,
                                }).format(d.shares)}{" "}
                                szt.
                              </p>
                              {d.value > 0 && (
                                <p className="font-mono text-xs text-muted-foreground mt-0.5">
                                  ≈{" "}
                                  {new Intl.NumberFormat("pl-PL", {
                                    maximumFractionDigits: 0,
                                  }).format(d.value)}{" "}
                                  {d.currency}
                                </p>
                              )}
                              {"date" in d && d.date && (
                                <p className="text-xs text-muted-foreground mt-1 border-t pt-1">
                                  snapshot: {d.date}
                                </p>
                              )}
                            </div>
                          );
                        }}
                      />
                      <Bar
                        dataKey="shares"
                        name="Liczba akcji"
                        fill="#3b82f6"
                        radius={[3, 3, 0, 0]}
                      />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              )}

              {/* Line chart — historia w czasie */}
              {chartMode === "history" && historyData && (
                <div>
                  {hasMultipleDates && (
                    <>
                      <p className="text-xs text-muted-foreground mb-3">
                        Liczba akcji w czasie (wg subfunduszu)
                      </p>

                      {/* Filtry funduszy */}
                      {(() => {
                        const q = fundFilter.trim().toLowerCase();
                        const visibleNames = q
                          ? fundNames.filter((n) => n.toLowerCase().includes(q))
                          : fundNames;
                        const allVisibleChecked = visibleNames.every((n) => selectedFunds.has(n));
                        return (
                          <div className="p-3 bg-muted/20 rounded-md mb-3 space-y-2">
                            {/* Pasek wyszukiwania + przyciski */}
                            <div className="flex items-center gap-2">
                              <div className="relative flex-1">
                                <Filter className="absolute left-2 top-1/2 -translate-y-1/2 h-3 w-3 text-muted-foreground" />
                                <input
                                  type="text"
                                  value={fundFilter}
                                  onChange={(e) => setFundFilter(e.target.value)}
                                  placeholder="Filtruj fundusze…"
                                  className="w-full pl-6 pr-3 py-1 text-xs border rounded bg-background focus:outline-none focus:ring-1 focus:ring-primary"
                                />
                                {fundFilter && (
                                  <button
                                    onClick={() => setFundFilter("")}
                                    className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                                  >
                                    ×
                                  </button>
                                )}
                              </div>
                              <div className="flex gap-2 shrink-0">
                                {!allVisibleChecked && visibleNames.length > 0 && (
                                  <button
                                    onClick={() =>
                                      setSelectedFunds((prev) => {
                                        const next = new Set(prev);
                                        visibleNames.forEach((n) => next.add(n));
                                        return next;
                                      })
                                    }
                                    className="text-xs text-primary hover:underline whitespace-nowrap"
                                  >
                                    Zaznacz {q ? "widoczne" : "wszystkie"}
                                  </button>
                                )}
                                {allVisibleChecked && visibleNames.length > 0 && (
                                  <button
                                    onClick={() =>
                                      setSelectedFunds((prev) => {
                                        const next = new Set(prev);
                                        visibleNames.forEach((n) => next.delete(n));
                                        // zostaw co najmniej jeden fundusz zaznaczony
                                        if (next.size === 0 && visibleNames.length > 0) {
                                          next.add(visibleNames[0]);
                                        }
                                        return next;
                                      })
                                    }
                                    className="text-xs text-muted-foreground hover:underline whitespace-nowrap"
                                  >
                                    Odznacz {q ? "widoczne" : "wszystkie"}
                                  </button>
                                )}
                              </div>
                            </div>
                            {/* Checkboxy */}
                            <div className="flex flex-wrap gap-x-3 gap-y-1.5">
                              {visibleNames.length === 0 && (
                                <p className="text-xs text-muted-foreground italic">Brak wyników dla &ldquo;{fundFilter}&rdquo;</p>
                              )}
                              {visibleNames.map((name) => {
                                const i = fundNames.indexOf(name);
                                const color = CHART_COLORS[i % CHART_COLORS.length];
                                const checked = selectedFunds.has(name);
                                return (
                                  <label
                                    key={name}
                                    className="flex items-center gap-1.5 text-xs cursor-pointer select-none"
                                  >
                                    <input
                                      type="checkbox"
                                      checked={checked}
                                      onChange={() => toggleFund(name)}
                                      style={{ accentColor: color }}
                                      className="w-3 h-3 cursor-pointer"
                                    />
                                    <span
                                      style={checked ? { color } : undefined}
                                      className={cn("font-medium", !checked && "text-muted-foreground line-through")}
                                    >
                                      {shortFundName(name)}
                                    </span>
                                  </label>
                                );
                              })}
                            </div>
                            {q && (
                              <p className="text-xs text-muted-foreground">
                                {visibleNames.length} z {fundNames.length} funduszy
                              </p>
                            )}
                          </div>
                        );
                      })()}
                      <ResponsiveContainer width="100%" height={300}>
                        <LineChart
                          data={lineData}
                          margin={{ top: 5, right: 110, left: 0, bottom: 5 }}
                        >
                          <CartesianGrid strokeDasharray="3 3" />
                          <XAxis dataKey="date" tick={{ fontSize: 11 }} />
                          <YAxis
                            tick={{ fontSize: 11 }}
                            tickFormatter={(v: number) =>
                              new Intl.NumberFormat("pl-PL", {
                                notation: "compact",
                                maximumFractionDigits: 0,
                              }).format(v)
                            }
                          />
                          <Tooltip
                            wrapperStyle={{ pointerEvents: "all" }}
                            content={({ active, payload, label }) => {
                              if (!active || !payload?.length) return null;
                              const changes = lineChanges.get(label as string);
                              return (
                                <div className="bg-background border rounded shadow-lg text-sm min-w-[200px] max-h-[320px] flex flex-col">
                                  <p className="font-medium text-xs text-muted-foreground border-b px-3 py-2 pb-1.5 shrink-0">
                                    {label}
                                  </p>
                                  <div className="overflow-y-scroll px-3 py-1.5 space-y-1.5">
                                  {payload.map((entry) => {
                                    const fundKey = entry.dataKey as string;
                                    const change = changes?.get(fundKey);
                                    const isPos = change != null && change > 0;
                                    const isNeg = change != null && change < 0;
                                    return (
                                      <div key={fundKey} className="flex items-start justify-between gap-3">
                                        <div className="flex items-center gap-1.5 min-w-0">
                                          <div
                                            className="w-2 h-2 rounded-full shrink-0 mt-0.5"
                                            style={{ background: entry.color }}
                                          />
                                          <span className="text-xs text-muted-foreground truncate">
                                            {shortFundName(fundKey)}
                                          </span>
                                        </div>
                                        <div className="text-right shrink-0">
                                          <span className="font-mono font-semibold text-xs">
                                            {new Intl.NumberFormat("pl-PL", {
                                              maximumFractionDigits: 0,
                                            }).format(entry.value as number)}{" "}
                                            szt.
                                          </span>
                                          {change != null && (
                                            <span
                                              className={cn(
                                                "block text-xs font-mono",
                                                isPos
                                                  ? "text-green-600 dark:text-green-400"
                                                  : isNeg
                                                  ? "text-red-500"
                                                  : "text-muted-foreground"
                                              )}
                                            >
                                              {isPos ? "▲ +" : isNeg ? "▼ " : ""}
                                              {change.toFixed(2)}%
                                            </span>
                                          )}
                                          {change == null && (
                                            <span className="block text-xs text-muted-foreground">
                                              brak poprzedniego
                                            </span>
                                          )}
                                        </div>
                                      </div>
                                    );
                                  })}
                                  </div>
                                </div>
                              );
                            }}
                          />
                          {fundNames.map((name, i) =>
                            visibleFundNames.includes(name) ? (
                              <Line
                                key={name}
                                type="monotone"
                                dataKey={name}
                                name={shortFundName(name)}
                                stroke={CHART_COLORS[i % CHART_COLORS.length]}
                                dot={lineData.length <= 12}
                                strokeWidth={2}
                                connectNulls
                                label={(props: { x: number; y: number; index: number; value: number | null }) => {
                                  if (props.index !== lineData.length - 1 || props.value == null) return null as unknown as React.ReactElement;
                                  return (
                                    <text
                                      key={`lbl-${name}`}
                                      x={props.x + 6}
                                      y={props.y}
                                      fill={CHART_COLORS[i % CHART_COLORS.length]}
                                      fontSize={10}
                                      dominantBaseline="middle"
                                    >
                                      {shortFundName(name)}
                                    </text>
                                  );
                                }}
                              />
                            ) : null
                          )}
                        </LineChart>
                      </ResponsiveContainer>
                    </>
                  )}
                </div>
              )}
            </div>
          )}
          {/* --- Widok: Notowania TradingView --- */}
          {view === "notowania" && h.ticker && (
            <div className="p-5 space-y-3">
              {/* Symbol edytowalny */}
              <div className="flex items-center gap-2">
                <span className="text-xs text-muted-foreground">Symbol TradingView:</span>
                {editingSymbol ? (
                  <form
                    className="flex items-center gap-1.5"
                    onSubmit={(e) => {
                      e.preventDefault();
                      if (symbolDraft.trim()) setTvSymbol(symbolDraft.trim().toUpperCase());
                      setEditingSymbol(false);
                    }}
                  >
                    <input
                      autoFocus
                      value={symbolDraft}
                      onChange={(e) => setSymbolDraft(e.target.value)}
                      className="px-2 py-0.5 text-xs border rounded font-mono bg-background focus:outline-none focus:ring-1 focus:ring-primary w-32"
                      placeholder="np. WSE:PKN"
                    />
                    <button
                      type="submit"
                      className="text-green-600 hover:text-green-700"
                      title="Zatwierdź"
                    >
                      <Check className="h-3.5 w-3.5" />
                    </button>
                  </form>
                ) : (
                  <button
                    onClick={() => {
                      setSymbolDraft(tvSymbol);
                      setEditingSymbol(true);
                    }}
                    className="flex items-center gap-1 text-xs font-mono font-semibold text-primary hover:underline"
                  >
                    {tvSymbol}
                    <Pencil className="h-3 w-3" />
                  </button>
                )}
                <a
                  href={`https://www.tradingview.com/chart/?symbol=${encodeURIComponent(tvSymbol)}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-xs text-muted-foreground hover:text-foreground flex items-center gap-0.5"
                >
                  <ExternalLink className="h-3 w-3" />
                  pełny wykres
                </a>
              </div>
              <p className="text-xs text-muted-foreground">
                Jeśli wykres nie wyświetla się poprawnie, edytuj symbol — np.{" "}
                <code className="font-mono bg-muted px-1 rounded">GPW:LBW</code> lub{" "}
                <code className="font-mono bg-muted px-1 rounded">NASDAQ:NVDA</code>.
                {" "}Możesz też{" "}
                <a
                  href={`https://www.tradingview.com/search/?text=${encodeURIComponent(h.company_name)}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="underline hover:text-foreground"
                >
                  wyszukać spółkę na TradingView
                </a>{" "}
                i skopiować symbol.
              </p>
              <TradingViewMiniChart symbol={tvSymbol} />
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default function SearchPage() {
  const searchParams = useSearchParams();
  const [query, setQuery] = useState(searchParams.get("q") ?? "");
  const [results, setResults] = useState<CompanyHoldings[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // Auto-search when ?q= is present in URL
  useEffect(() => {
    const q = searchParams.get("q")?.trim();
    if (q && q.length >= 2) {
      setLoading(true);
      setError(null);
      setResults(null);
      positionsApi.search(q)
        .then(setResults)
        .catch(() => setError("Błąd podczas wyszukiwania. Spróbuj ponownie."))
        .finally(() => setLoading(false));
    }
  }, []);

  async function handleSearch(e: React.FormEvent) {
    e.preventDefault();
    const q = query.trim();
    if (q.length < 2) return;
    setLoading(true);
    setError(null);
    setResults(null);
    try {
      const data = await positionsApi.search(q);
      setResults(data);
    } catch {
      setError("Błąd podczas wyszukiwania. Spróbuj ponownie.");
    } finally {
      setLoading(false);
    }
  }

  const totalValue =
    results?.reduce((s, h) => s + (h.total_value ?? 0), 0) ?? 0;

  return (
    <div className="max-w-3xl space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Szukaj aktywa</h1>
        <p className="text-muted-foreground text-sm mt-1">
          Sprawdź łączne zaangażowanie we wszystkich subfunduszach dla wybranej spółki.
        </p>
      </div>

      {/* Wyszukiwarka */}
      <form onSubmit={handleSearch} className="flex gap-2">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <input
            ref={inputRef}
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="np. Lubawa, PKN, PL0000503639…"
            className="w-full pl-9 pr-4 py-2.5 border rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-primary bg-background"
          />
        </div>
        <button
          type="submit"
          disabled={loading || query.trim().length < 2}
          className="px-5 py-2.5 bg-primary text-primary-foreground rounded-md text-sm font-medium hover:opacity-90 disabled:opacity-50 flex items-center gap-2"
        >
          {loading ? (
            <span className="animate-spin h-4 w-4 border-2 border-white border-t-transparent rounded-full" />
          ) : (
            <Search className="h-4 w-4" />
          )}
          Szukaj
        </button>
      </form>

      {/* Błąd */}
      {error && (
        <p className="text-sm text-destructive bg-destructive/10 px-4 py-3 rounded-lg">{error}</p>
      )}

      {/* Wyniki */}
      {results !== null && (
        <>
          {results.length === 0 ? (
            <div className="text-center py-12 text-muted-foreground">
              <Search className="h-10 w-10 mx-auto mb-3 opacity-30" />
              <p>Nie znaleziono spółki <strong>&ldquo;{query}&rdquo;</strong> w żadnym subfunduszu.</p>
              <p className="text-xs mt-1">Spróbuj wpisać fragment nazwy lub ISIN.</p>
            </div>
          ) : (
            <>
              <div className="flex items-center justify-between text-sm">
                <p className="text-muted-foreground">
                  Znaleziono{" "}
                  <span className="font-semibold text-foreground">{results.length}</span>{" "}
                  {results.length === 1 ? "spółkę" : "spółki"}
                </p>
                {totalValue > 0 && (
                  <p className="text-muted-foreground">
                    Łączna wartość:{" "}
                    <span className="font-semibold text-foreground font-mono">
                      {new Intl.NumberFormat("pl-PL", { maximumFractionDigits: 0 }).format(
                        totalValue
                      )}{" "}
                      PLN
                    </span>
                  </p>
                )}
              </div>

              <div className="space-y-3">
                {results.map((h) => (
                  <HoldingsCard key={h.isin ?? h.company_name} h={h} />
                ))}
              </div>
            </>
          )}
        </>
      )}
    </div>
  );
}
