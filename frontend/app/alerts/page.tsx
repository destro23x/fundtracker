"use client";

import { useState } from "react";
import useSWR, { mutate } from "swr";
import { alertsApi, alertRulesApi, fundsApi, type Alert, type AlertRule, type AlertRuleCreate, type Fund } from "@/lib/api";
import { TrendingUp, TrendingDown, Plus, X, Bell, CheckCheck, Settings2, Pencil, Trash2, ToggleLeft, ToggleRight, Download } from "lucide-react";
import { toast } from "sonner";
import { cn } from "@/lib/utils";
import { useAuth } from "@/contexts/AuthContext";

const TYPE_CONFIG: Record<string, { label: string; color: string; Icon: typeof Bell }> = {
  position_increase: { label: "Zwiększenie", color: "text-green-600", Icon: TrendingUp },
  position_decrease: { label: "Zmniejszenie", color: "text-red-500", Icon: TrendingDown },
  new_position: { label: "Nowa pozycja", color: "text-blue-600", Icon: Plus },
  closed_position: { label: "Zamknięcie", color: "text-gray-400", Icon: X },
};

// ─── Formularz reguły ───────────────────────────────────────────────────────

const EMPTY_FORM: AlertRuleCreate = {
  name: "",
  is_active: true,
  track_new: true,
  track_closed: true,
  track_increases: true,
  track_decreases: true,
  min_weight_pp: 2,
  min_rel_pct: 20,
  fund_id: null,
};

function RuleForm({
  initial,
  onSave,
  onCancel,
}: {
  initial: AlertRuleCreate;
  onSave: (data: AlertRuleCreate) => Promise<void>;
  onCancel: () => void;
}) {
  const [form, setForm] = useState<AlertRuleCreate>(initial);
  const [saving, setSaving] = useState(false);
  const { data: funds } = useSWR("funds", () => fundsApi.list());

  function set<K extends keyof AlertRuleCreate>(key: K, val: AlertRuleCreate[K]) {
    setForm((f) => ({ ...f, [key]: val }));
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!form.name.trim()) { toast.error("Podaj nazwę reguły"); return; }
    setSaving(true);
    try {
      await onSave(form);
    } finally {
      setSaving(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4 p-4 border rounded-lg bg-muted/20">
      {/* Nazwa */}
      <div>
        <label className="block text-xs font-medium mb-1">Nazwa reguły *</label>
        <input
          type="text"
          value={form.name}
          onChange={(e) => set("name", e.target.value)}
          placeholder="np. Duże zmiany PZU"
          className="w-full border rounded-md px-3 py-1.5 text-sm bg-background focus:outline-none focus:ring-2 focus:ring-primary"
        />
      </div>

      {/* Typy zdarzeń */}
      <div>
        <p className="text-xs font-medium mb-2">Śledź zdarzenia</p>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
          {(
            [
              { key: "track_new", label: "Nowe pozycje" },
              { key: "track_closed", label: "Zamknięcia" },
              { key: "track_increases", label: "Zwiększenia" },
              { key: "track_decreases", label: "Zmniejszenia" },
            ] as const
          ).map(({ key, label }) => (
            <label key={key} className="flex items-center gap-2 text-sm cursor-pointer select-none">
              <input
                type="checkbox"
                checked={!!form[key]}
                onChange={(e) => set(key, e.target.checked)}
                className="w-4 h-4 cursor-pointer"
              />
              {label}
            </label>
          ))}
        </div>
      </div>

      {/* Progi */}
      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="block text-xs font-medium mb-1">Min. zmiana wagi (pp)</label>
          <input
            type="number"
            min={0}
            step={0.1}
            value={form.min_weight_pp}
            onChange={(e) => set("min_weight_pp", parseFloat(e.target.value) || 0)}
            className="w-full border rounded-md px-3 py-1.5 text-sm bg-background focus:outline-none focus:ring-2 focus:ring-primary"
          />
          <p className="text-xs text-muted-foreground mt-0.5">punkty procentowe</p>
        </div>
        <div>
          <label className="block text-xs font-medium mb-1">Min. zmiana względna (%)</label>
          <input
            type="number"
            min={0}
            step={1}
            value={form.min_rel_pct}
            onChange={(e) => set("min_rel_pct", parseFloat(e.target.value) || 0)}
            className="w-full border rounded-md px-3 py-1.5 text-sm bg-background focus:outline-none focus:ring-2 focus:ring-primary"
          />
          <p className="text-xs text-muted-foreground mt-0.5">warunek alternatywny (LUB)</p>
        </div>
      </div>

      {/* Fundusz (opcjonalnie) */}
      <div>
        <label className="block text-xs font-medium mb-1">Ogranicz do funduszu (opcjonalnie)</label>
        <select
          value={form.fund_id ?? ""}
          onChange={(e) => set("fund_id", e.target.value || null)}
          className="w-full border rounded-md px-3 py-1.5 text-sm bg-background focus:outline-none focus:ring-2 focus:ring-primary"
        >
          <option value="">Wszystkie fundusze</option>
          {funds?.map((f) => (
            <option key={f.id} value={f.id}>
              {f.name}
            </option>
          ))}
        </select>
      </div>

      <div className="flex justify-end gap-2 pt-1">
        <button
          type="button"
          onClick={onCancel}
          className="px-4 py-1.5 text-sm border rounded-md text-muted-foreground hover:text-foreground"
        >
          Anuluj
        </button>
        <button
          type="submit"
          disabled={saving}
          className="px-4 py-1.5 text-sm bg-primary text-primary-foreground rounded-md hover:opacity-90 disabled:opacity-50"
        >
          {saving ? "Zapisuję…" : "Zapisz regułę"}
        </button>
      </div>
    </form>
  );
}

// ─── Karta reguły ──────────────────────────────────────────────────────────

function RuleCard({ rule, funds }: { rule: AlertRule; funds: { id: string; name: string }[] }) {
  const [editing, setEditing] = useState(false);

  const fundName = rule.fund_id
    ? (funds.find((f) => f.id === rule.fund_id)?.name ?? rule.fund_id)
    : null;

  async function toggleActive() {
    await alertRulesApi.update(rule.id, { is_active: !rule.is_active });
    mutate("alert-rules");
    toast.success(rule.is_active ? "Reguła wyłączona" : "Reguła włączona");
  }

  async function handleDelete() {
    await alertRulesApi.delete(rule.id);
    mutate("alert-rules");
    toast.success("Reguła usunięta");
  }

  async function handleSave(data: AlertRuleCreate) {
    await alertRulesApi.update(rule.id, data);
    mutate("alert-rules");
    toast.success("Reguła zaktualizowana");
    setEditing(false);
  }

  const trackedTypes = [
    rule.track_new && "nowe",
    rule.track_closed && "zamknięcia",
    rule.track_increases && "wzrosty",
    rule.track_decreases && "spadki",
  ]
    .filter(Boolean)
    .join(", ");

  if (editing) {
    return (
      <RuleForm
        initial={{
          name: rule.name,
          is_active: rule.is_active,
          track_new: rule.track_new,
          track_closed: rule.track_closed,
          track_increases: rule.track_increases,
          track_decreases: rule.track_decreases,
          min_weight_pp: Number(rule.min_weight_pp),
          min_rel_pct: Number(rule.min_rel_pct),
          fund_id: rule.fund_id,
        }}
        onSave={handleSave}
        onCancel={() => setEditing(false)}
      />
    );
  }

  return (
    <div
      className={cn(
        "flex items-start gap-3 p-4 border rounded-lg transition-all",
        !rule.is_active && "opacity-50"
      )}
    >
      <button
        onClick={toggleActive}
        className={cn("mt-0.5 shrink-0", rule.is_active ? "text-primary" : "text-muted-foreground")}
        title={rule.is_active ? "Wyłącz regułę" : "Włącz regułę"}
      >
        {rule.is_active ? <ToggleRight className="h-5 w-5" /> : <ToggleLeft className="h-5 w-5" />}
      </button>

      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className="font-medium text-sm">{rule.name}</span>
          {!rule.is_active && (
            <span className="text-xs text-muted-foreground bg-muted px-1.5 py-0.5 rounded">wyłączona</span>
          )}
        </div>
        <p className="text-xs text-muted-foreground mt-0.5">
          Śledzi: {trackedTypes || "—"} · min.{" "}
          <span className="font-medium text-foreground">{rule.min_weight_pp} pp</span> LUB{" "}
          <span className="font-medium text-foreground">{rule.min_rel_pct}%</span>
          {fundName && (
            <> · tylko <span className="font-medium text-foreground">{fundName}</span></>
          )}
        </p>
      </div>

      <div className="flex items-center gap-1 shrink-0">
        <button
          onClick={() => setEditing(true)}
          className="p-1.5 text-muted-foreground hover:text-foreground rounded"
          title="Edytuj"
        >
          <Pencil className="h-3.5 w-3.5" />
        </button>
        <button
          onClick={handleDelete}
          className="p-1.5 text-muted-foreground hover:text-destructive rounded"
          title="Usuń"
        >
          <Trash2 className="h-3.5 w-3.5" />
        </button>
      </div>
    </div>
  );
}

// ─── Sekcja reguł ──────────────────────────────────────────────────────────

function RulesSection() {
  const [showForm, setShowForm] = useState(false);
  const { data: rules, isLoading } = useSWR("alert-rules", alertRulesApi.list);
  const { data: funds } = useSWR("funds", () => fundsApi.list());

  async function handleCreate(data: AlertRuleCreate) {
    await alertRulesApi.create(data);
    mutate("alert-rules");
    toast.success("Reguła dodana");
    setShowForm(false);
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Settings2 className="h-4 w-4 text-muted-foreground" />
          <h2 className="font-semibold">Reguły alertów</h2>
          {rules && rules.length > 0 && (
            <span className="text-xs text-muted-foreground bg-muted px-1.5 py-0.5 rounded">
              {rules.length}
            </span>
          )}
        </div>
        {!showForm && (
          <button
            onClick={() => setShowForm(true)}
            className="flex items-center gap-1.5 text-xs text-primary hover:underline"
          >
            <Plus className="h-3.5 w-3.5" />
            Dodaj regułę
          </button>
        )}
      </div>

      {isLoading && <p className="text-xs text-muted-foreground">Ładowanie…</p>}

      {!isLoading && rules?.length === 0 && !showForm && (
        <div className="text-xs text-muted-foreground bg-muted/30 rounded-lg px-4 py-3 border border-dashed">
          Brak reguł — używane są wartości domyślne (≥ 2 pp lub ≥ 20% względnie).{" "}
          <button onClick={() => setShowForm(true)} className="text-primary hover:underline">
            Dodaj pierwszą regułę
          </button>
        </div>
      )}

      {showForm && (
        <RuleForm initial={EMPTY_FORM} onSave={handleCreate} onCancel={() => setShowForm(false)} />
      )}

      <div className="space-y-2">
        {rules?.map((rule) => (
          <RuleCard key={rule.id} rule={rule} funds={funds ?? []} />
        ))}
      </div>
    </div>
  );
}

// ─── Strona główna ─────────────────────────────────────────────────────────

function exportAlertsToCSV(alerts: Alert[], funds: Fund[]) {
  const fundMap = new Map(funds.map((f) => [f.id, f.name]));
  const typeLabel: Record<string, string> = {
    position_increase: "Zwiększenie",
    position_decrease: "Zmniejszenie",
    new_position: "Nowa pozycja",
    closed_position: "Zamknięcie pozycji",
  };

  const header = ["Data", "Typ", "Fundusz", "Spółka", "Ticker", "Waga przed (%)", "Waga po (%)", "Zmiana (%)", "Wiadomość", "Przeczytany"];
  const rows = alerts.map((a) => [
    new Date(a.created_at).toLocaleString("pl-PL"),
    typeLabel[a.alert_type] ?? a.alert_type,
    fundMap.get(a.fund_id) ?? a.fund_id,
    a.company_name ?? "",
    a.ticker ?? "",
    a.old_weight != null ? a.old_weight.toFixed(4) : "",
    a.new_weight != null ? a.new_weight.toFixed(4) : "",
    a.change_pct != null ? a.change_pct.toFixed(4) : "",
    `"${a.message.replace(/"/g, '""')}"`,
    a.is_read ? "tak" : "nie",
  ]);

  const csv = [header, ...rows].map((r) => r.join(";")).join("\n");
  const blob = new Blob(["\uFEFF" + csv], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `alerty_${new Date().toISOString().slice(0, 10)}.csv`;
  a.click();
  URL.revokeObjectURL(url);
}

export default function AlertsPage() {
  const { user } = useAuth();
  const { data: alerts, isLoading } = useSWR("alerts-all", () => alertsApi.list());
  const { data: funds } = useSWR("funds", () => fundsApi.list());

  const unread = alerts?.filter((a) => !a.is_read) ?? [];

  async function markAll() {
    await alertsApi.markAllRead();
    mutate("alerts-all");
    mutate("alerts-unread");
    toast.success("Wszystkie alerty oznaczone jako przeczytane");
  }

  async function markOne(id: string) {
    await alertsApi.markRead([id]);
    mutate("alerts-all");
    mutate("alerts-unread");
  }

  return (
    <div className="max-w-3xl space-y-8">
      {user && <RulesSection />}
      {user && <hr className="border-border" />}

      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold">Alerty</h1>
            <p className="text-muted-foreground text-sm mt-1">
              {unread.length > 0 ? `${unread.length} nieprzeczytanych` : "Wszystko przeczytane"}
            </p>
          </div>
          <div className="flex items-center gap-2">
            {(alerts?.length ?? 0) > 0 && (
              <button
                onClick={() => exportAlertsToCSV(alerts!, funds ?? [])}
                className="flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground px-3 py-1.5 border rounded-md"
                title="Pobierz CSV"
              >
                <Download className="h-4 w-4" />
                Eksport CSV
              </button>
            )}
            {unread.length > 0 && (
              <button
                onClick={markAll}
                className="flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground px-3 py-1.5 border rounded-md"
              >
                <CheckCheck className="h-4 w-4" />
                Oznacz wszystkie
              </button>
            )}
          </div>
        </div>

        {isLoading && <p className="text-muted-foreground text-sm">Ładowanie...</p>}

        {alerts?.length === 0 && !isLoading && (
          <div className="text-muted-foreground text-sm bg-muted/40 rounded-lg p-8 text-center">
            Brak alertów. Załaduj kolejny snapshot, żeby zobaczyć zmiany w portfelu.
          </div>
        )}

        <div className="space-y-2">
          {alerts?.map((alert) => (
            <AlertCard key={alert.id} alert={alert} onRead={markOne} />
          ))}
        </div>
      </div>
    </div>
  );
}

function AlertCard({ alert, onRead }: { alert: Alert; onRead: (id: string) => void }) {
  const cfg = TYPE_CONFIG[alert.alert_type] ?? {
    label: alert.alert_type,
    color: "text-muted-foreground",
    Icon: Bell,
  };
  const { Icon } = cfg;

  return (
    <div
      className={cn(
        "flex items-start gap-4 p-4 border rounded-lg transition-all",
        alert.is_read ? "bg-background opacity-60" : "bg-card border-primary/20 shadow-sm"
      )}
    >
      <div className={cn("mt-0.5 shrink-0", cfg.color)}>
        <Icon className="h-5 w-5" />
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-1">
          <span className={cn("text-xs font-medium", cfg.color)}>{cfg.label}</span>
          {!alert.is_read && (
            <span className="h-1.5 w-1.5 rounded-full bg-primary inline-block" />
          )}
        </div>
        <p className="text-sm">{alert.message}</p>
        <p className="text-xs text-muted-foreground mt-1">
          {new Date(alert.created_at).toLocaleString("pl-PL")}
        </p>
      </div>
      {!alert.is_read && (
        <button
          onClick={() => onRead(alert.id)}
          className="shrink-0 text-xs text-muted-foreground hover:text-foreground px-2 py-1 border rounded"
        >
          Przeczytane
        </button>
      )}
    </div>
  );
}
