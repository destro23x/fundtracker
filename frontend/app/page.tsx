"use client";

import useSWR from "swr";
import { statsApi, fundsApi, articlesApi, type TopChange } from "@/lib/api";
import { cn } from "@/lib/utils";
import {
  TrendingUp,
  TrendingDown,
  Bell,
  Building2,
  DatabaseZap,
  Plus,
  X,
  Calendar,
  Upload,
  ArrowRight,
  Newspaper,
} from "lucide-react";
import Link from "next/link";
import { useAuth } from "@/contexts/AuthContext";

export default function DashboardPage() {
  const { user } = useAuth();
  const { data: stats, isLoading } = useSWR("stats", statsApi.get);
  const { data: funds } = useSWR("funds", () => fundsApi.list());
  const { data: articles } = useSWR("articles", () => articlesApi.list(10));

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold">Dashboard</h1>
        <p className="text-muted-foreground text-sm mt-1">
          Przegląd portfeli funduszy inwestycyjnych
        </p>
      </div>

      {/* ── Stat cards ───────────────────────────────────────────── */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <StatCard
          title="Obserwowane fundusze"
          value={isLoading ? "…" : String(stats?.fund_count ?? 0)}
          icon={<Building2 className="h-5 w-5 text-primary" />}
          href="/funds"
        />
        <StatCard
          title="Łączne snapshoty"
          value={isLoading ? "…" : String(stats?.snapshot_count ?? 0)}
          icon={<DatabaseZap className="h-5 w-5 text-green-500" />}
        />
        <StatCard
          title="Nieprzeczytane alerty"
          value={isLoading ? "…" : String(stats?.unread_alert_count ?? 0)}
          icon={<Bell className="h-5 w-5 text-orange-500" />}
          highlight={(stats?.unread_alert_count ?? 0) > 0}
          href="/alerts"
        />
      </div>

      {/* ── Latest snapshot banner ───────────────────────────────── */}
      {stats?.latest_snapshot && (
        <div className="flex items-center gap-4 p-4 border rounded-lg bg-card">
          <div className="p-2 bg-muted rounded-md shrink-0">
            <Calendar className="h-5 w-5 text-primary" />
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-xs text-muted-foreground">Ostatni snapshot</p>
            <p className="font-semibold truncate">{stats.latest_snapshot.fund_name}</p>
            <p className="text-sm text-muted-foreground">
              {new Date(stats.latest_snapshot.snapshot_date).toLocaleDateString("pl-PL", {
                year: "numeric",
                month: "long",
                day: "numeric",
              })}{" "}
              · {stats.latest_snapshot.position_count} pozycji
            </p>
          </div>
          {user && (
            <Link
              href="/upload"
              className="flex items-center gap-1.5 text-xs text-primary hover:underline shrink-0"
            >
              <Upload className="h-3.5 w-3.5" />
              Załaduj nowy
            </Link>
          )}
        </div>
      )}

      {!isLoading && !stats?.latest_snapshot && user && (
        <div className="flex flex-col items-center justify-center p-10 border-2 border-dashed rounded-lg text-center gap-3">
          <Upload className="h-8 w-8 text-muted-foreground" />
          <p className="font-medium">Brak danych</p>
          <p className="text-sm text-muted-foreground">
            Załaduj pierwszy plik Excel lub PDF, żeby rozpocząć śledzenie portfeli.
          </p>
          <Link
            href="/upload"
            className="mt-1 px-4 py-2 text-sm bg-primary text-primary-foreground rounded-md hover:opacity-90"
          >
            Załaduj plik
          </Link>
        </div>
      )}

      {/* ── Aktualności ──────────────────────────────────────────── */}
      <section>
        <div className="flex items-center justify-between mb-3">
          <h2 className="font-semibold">Aktualności</h2>
        </div>
        {articles && articles.length > 0 ? (
          <div className="space-y-3">
            {articles.map((a) => (
              <Link
                key={a.id}
                href={`/aktualnosci/${a.id}`}
                className="flex items-start gap-3 p-3 border rounded-lg hover:border-primary transition-colors bg-card group"
              >
                <div className="p-1.5 bg-muted rounded shrink-0 mt-0.5">
                  <Newspaper className="h-4 w-4 text-muted-foreground" />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="font-medium text-sm truncate group-hover:text-primary transition-colors">
                    {a.title}
                  </div>
                  <div className="text-xs text-muted-foreground mt-0.5">
                    {new Date(a.published_at).toLocaleDateString("pl-PL", {
                      day: "numeric",
                      month: "long",
                      year: "numeric",
                    })}
                    {a.author && ` · ${a.author}`}
                  </div>
                  <div className="text-xs text-muted-foreground mt-1 line-clamp-2">
                    {a.content}
                  </div>
                </div>
                <ArrowRight className="h-4 w-4 text-muted-foreground shrink-0 mt-0.5" />
              </Link>
            ))}
          </div>
        ) : (
          <div className="text-muted-foreground text-sm bg-muted/40 rounded-lg p-6 text-center">
            Brak aktualności.{" "}
            <Link href="/aktualnosci" className="text-primary hover:underline">
              Przejdź do sekcji →
            </Link>
          </div>
        )}
      </section>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* ── Top changes ─────────────────────────────────────────── */}
        {(stats?.top_changes?.length ?? 0) > 0 && (
          <section>
            <div className="flex items-center justify-between mb-3">
              <h2 className="font-semibold">Ostatnie zmiany</h2>
              <Link href="/alerts" className="text-sm text-primary hover:underline flex items-center gap-1">
                Wszystkie <ArrowRight className="h-3.5 w-3.5" />
              </Link>
            </div>
            <div className="space-y-2">
              {stats!.top_changes.slice(0, 7).map((c, i) => (
                <ChangeRow key={i} change={c} />
              ))}
            </div>
          </section>
        )}

        {/* ── Funds list ───────────────────────────────────────────── */}
        <section>
          <div className="flex items-center justify-between mb-3">
            <h2 className="font-semibold">Fundusze</h2>
          </div>

          {funds && funds.length > 0 ? (
            <div className="space-y-2">
              {funds.map((f) => (
                <Link
                  key={f.id}
                  href={`/subfunds?fund=${f.id}`}
                  className="flex items-center gap-3 p-3 border rounded-lg hover:border-primary transition-colors bg-card"
                >
                  <div className="p-1.5 bg-muted rounded">
                    <Building2 className="h-4 w-4 text-muted-foreground" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="font-medium text-sm truncate">{f.name}</div>
                    <div className="text-xs text-muted-foreground">
                      {f.subfund_count} {f.subfund_count === 1 ? "subfundusz" : f.subfund_count < 5 ? "subfundusze" : "subfunduszy"}
                    </div>
                  </div>
                  <ArrowRight className="h-4 w-4 text-muted-foreground shrink-0" />
                </Link>
              ))}
            </div>
          ) : (
            <div className="text-muted-foreground text-sm bg-muted/40 rounded-lg p-6 text-center">
              Brak funduszy w bazie.{" "}
              {user && (
                <Link href="/funds" className="text-primary hover:underline">
                  Dodaj pierwszy →
                </Link>
              )}
            </div>
          )}
        </section>
      </div>

      {/* ── Recent snapshots ────────────────────────────────────── */}
      {(stats?.recent_snapshots?.length ?? 0) > 0 && (
        <section>
          <h2 className="font-semibold mb-3">Ostatnie uploady</h2>
          <div className="space-y-1.5">
            {stats!.recent_snapshots.map((s) => (
              <div
                key={s.snapshot_id}
                className="flex items-center gap-3 px-4 py-2.5 border rounded-lg bg-card text-sm"
              >
                <Calendar className="h-4 w-4 text-muted-foreground shrink-0" />
                <span className="text-muted-foreground shrink-0">
                  {new Date(s.snapshot_date).toLocaleDateString("pl-PL", {
                    day: "2-digit",
                    month: "2-digit",
                    year: "numeric",
                  })}
                </span>
                <span className="truncate flex-1 text-sm">{s.upload_filename ?? "—"}</span>
              </div>
            ))}
          </div>
        </section>
      )}

    </div>
  );
}

// ── Sub-components ─────────────────────────────────────────────────────────

function StatCard({
  title,
  value,
  icon,
  highlight,
  href,
}: {
  title: string;
  value: string;
  icon: React.ReactNode;
  highlight?: boolean;
  href?: string;
}) {
  const inner = (
    <div
      className={cn(
        "p-4 border rounded-lg bg-card flex items-center gap-4",
        highlight && "border-orange-300 bg-orange-50/30 dark:bg-orange-950/10"
      )}
    >
      <div className="p-2 bg-muted rounded-md shrink-0">{icon}</div>
      <div>
        <div className="text-xs text-muted-foreground">{title}</div>
        <div className="text-2xl font-bold">{value}</div>
      </div>
    </div>
  );

  if (href) return <Link href={href} className="block hover:opacity-90 transition-opacity">{inner}</Link>;
  return inner;
}

const CHANGE_CFG: Record<string, { label: string; color: string; Icon: React.ElementType }> = {
  position_increase: { label: "+", color: "text-green-600", Icon: TrendingUp },
  position_decrease: { label: "−", color: "text-red-500", Icon: TrendingDown },
  new_position: { label: "Nowa", color: "text-blue-600", Icon: Plus },
  closed_position: { label: "Zamknięta", color: "text-gray-400", Icon: X },
};

function ChangeRow({ change }: { change: TopChange }) {
  const cfg = CHANGE_CFG[change.alert_type] ?? {
    label: change.alert_type,
    color: "text-muted-foreground",
    Icon: TrendingUp,
  };
  const { Icon } = cfg;

  return (
    <div className="flex items-start gap-3 px-3 py-2.5 border rounded-lg bg-card text-sm">
      <Icon className={cn("h-4 w-4 mt-0.5 shrink-0", cfg.color)} />
      <div className="flex-1 min-w-0">
        <p className="font-medium truncate">{change.company_name ?? "—"}</p>
        <p className="text-xs text-muted-foreground truncate">{change.fund_name}</p>
      </div>
      {change.new_weight !== null && (
        <div className="text-right shrink-0">
          <p className={cn("text-xs font-medium", cfg.color)}>
            {change.new_weight.toFixed(2)}%
          </p>
          {change.old_weight !== null && (
            <p className="text-xs text-muted-foreground">
              z {change.old_weight.toFixed(2)}%
            </p>
          )}
        </div>
      )}
    </div>
  );
}
