"use client";

import { useState } from "react";
import useSWR from "swr";
import {
  fundsApi,
  subfundsApi,
  tfiApi,
  type SubfundDistributionItem,
} from "@/lib/api";
import { translateAssetType } from "@/lib/asset-types";
import Link from "next/link";

const FALLBACK_COLORS = [
  "#3b82f6", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6",
  "#06b6d4", "#84cc16", "#f97316", "#ec4899", "#14b8a6",
  "#6366f1", "#eab308", "#22c55e", "#0ea5e9", "#a855f7",
];

const ASSET_COLORS: Record<string, string> = {
  "Akcje": "#3b82f6",
  "Obligacje skarbowe": "#10b981",
  "Obligacje korporacyjne": "#06b6d4",
  "Obligacje": "#10b981",
  "Instrumenty rynku pieniężnego": "#f59e0b",
  "Środki pieniężne": "#84cc16",
  "Fundusze inwestycyjne": "#8b5cf6",
  "ETF zagraniczne": "#f97316",
  "Instrumenty pochodne": "#ef4444",
};

function colorFor(name: string, idx: number): string {
  return ASSET_COLORS[name] ?? FALLBACK_COLORS[idx % FALLBACK_COLORS.length];
}

const THRESHOLDS = [5, 10, 25, 50] as const;

// ─── Wykres rozkładu subfunduszy ─────────────────────────────────────────────

function SubfundDistributionChart({
  items,
  threshold,
  onThresholdChange,
}: {
  items: SubfundDistributionItem[];
  threshold: number;
  onThresholdChange: (t: number) => void;
}) {
  const total = items[0]?.total_subfunds ?? 0;

  return (
    <div className="space-y-5">
      {/* Selektor progu */}
      <div className="flex items-center gap-2 flex-wrap">
        <span className="text-xs text-muted-foreground">Próg:</span>
        {THRESHOLDS.map((t) => (
          <button
            key={t}
            onClick={() => onThresholdChange(t)}
            className={`px-2.5 py-0.5 rounded-full text-xs border transition-colors ${
              t === threshold
                ? "bg-primary text-primary-foreground border-primary"
                : "border-border hover:border-primary/60 text-muted-foreground"
            }`}
          >
            {t}%
          </button>
        ))}
        <span className="text-xs text-muted-foreground">
          — subfundusze z &gt;{threshold}% w klasie aktywów
        </span>
      </div>

      {items.length === 0 ? (
        <p className="text-sm text-muted-foreground py-2 text-center">
          Żaden subfundusz nie ma więcej niż {threshold}% w żadnej klasie aktywów.
        </p>
      ) : (
        <div className="space-y-3">
          {items.map((item, idx) => {
            const label = translateAssetType(item.asset_type);
            const pct = total > 0 ? (item.subfund_count / total) * 100 : 0;
            const color = colorFor(label, idx);
            return (
              <div key={idx} className="space-y-1">
                <div className="flex items-center justify-between gap-4">
                  <span className="text-sm min-w-0 truncate">{label}</span>
                  <span className="text-xs tabular-nums shrink-0 text-muted-foreground">
                    <strong className="text-foreground">{item.subfund_count}</strong>
                    {" "}/ {total} subfunduszy
                  </span>
                </div>
                <div className="h-2.5 bg-muted rounded-full overflow-hidden">
                  <div
                    className="h-full rounded-full transition-all duration-300"
                    style={{ width: `${pct}%`, backgroundColor: color }}
                  />
                </div>
              </div>
            );
          })}
        </div>
      )}

      <p className="text-xs text-muted-foreground">
        Łącznie {total} subfunduszy z danymi portfelowymi (ostatni dostępny snapshot każdego)
      </p>
    </div>
  );
}

// ─── Strona funduszu ─────────────────────────────────────────────────────────

export default function FundDetailPage({ params }: { params: { id: string } }) {
  const fundId = params.id;
  const [threshold, setThreshold] = useState<number>(10);

  const { data: fund } = useSWR(`fund-${fundId}`, () => fundsApi.get(fundId));
  const { data: distribution, isLoading } = useSWR(
    `fund-distribution-${fundId}-${threshold}`,
    () => fundsApi.subfundDistribution(fundId, threshold)
  );
  const { data: subfunds } = useSWR(`subfunds-fund-${fundId}`, () =>
    subfundsApi.list(fundId)
  );
  const { data: tfiList } = useSWR("tfi", () => tfiApi.list());

  const tfiName = tfiList?.find((t) => t.id === fund?.tfi_id)?.name;

  return (
    <div className="space-y-6 max-w-4xl">
      {/* Nawigacja wstecz */}
      <div>
        <Link href="/funds" className="text-xs text-muted-foreground hover:underline">
          ← Fundusze
        </Link>
        <h1 className="text-2xl font-bold mt-1">{fund?.name ?? "…"}</h1>
        {tfiName && <p className="text-sm text-muted-foreground mt-0.5">{tfiName}</p>}
      </div>

      {/* Rozkład klas aktywów */}
      <div className="rounded-lg border bg-card p-5 space-y-4">
        <h2 className="font-semibold">Skład portfela wg klasy aktywów</h2>

        {isLoading && (
          <div className="text-sm text-muted-foreground py-4">Ładowanie danych…</div>
        )}

        {!isLoading && distribution !== undefined && (
          <SubfundDistributionChart
            items={distribution}
            threshold={threshold}
            onThresholdChange={setThreshold}
          />
        )}

        {!isLoading && distribution === undefined && (
          <div className="text-sm text-muted-foreground py-6 text-center bg-muted/30 rounded-lg">
            Brak danych portfelowych. Załaduj pliki Excel na stronie{" "}
            <Link href="/upload" className="underline hover:text-foreground">Dane</Link>.
          </div>
        )}
      </div>

      {/* Lista subfunduszy */}
      {subfunds && subfunds.length > 0 && (
        <div className="rounded-lg border bg-card p-5 space-y-3">
          <h2 className="font-semibold">
            Subfundusze{" "}
            <span className="text-muted-foreground font-normal text-sm">({subfunds.length})</span>
          </h2>
          <div className="divide-y">
            {subfunds.map((s) => (
              <Link
                key={s.id}
                href={`/subfunds/${s.id}`}
                className="flex items-center justify-between py-2.5 hover:text-primary text-sm transition-colors"
              >
                <span>{s.name}</span>
                <span className="text-xs text-muted-foreground">szczegóły →</span>
              </Link>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

