"use client";

import { useState, Suspense } from "react";
import { useSearchParams } from "next/navigation";
import useSWR, { mutate } from "swr";
import { subfundsApi, fundsApi, type Subfund } from "@/lib/api";
import { useAuth } from "@/contexts/AuthContext";
import { Plus, Trash2, ChevronRight, Search, X } from "lucide-react";
import Link from "next/link";
import { toast } from "sonner";

function SubfundsPageInner() {
  const { user } = useAuth();
  const searchParams = useSearchParams();
  const fundId = searchParams.get("fund") ?? undefined;

  const { data: funds, isLoading } = useSWR(
    ["subfunds", fundId],
    () => subfundsApi.list(fundId)
  );
  const { data: fundsList } = useSWR(fundId ? "funds-for-name" : null, () => fundsApi.list());
  const fundName = fundId ? fundsList?.find((f) => f.id === fundId)?.name : undefined;

  const [showForm, setShowForm] = useState(false);
  const [name, setName] = useState("");
  const [ticker, setTicker] = useState("");
  const [query, setQuery] = useState("");

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    if (!name.trim()) return;
    try {
      await subfundsApi.create({ name: name.trim(), ticker: ticker.trim() || undefined });
      mutate(["subfunds", fundId]);
      setName("");
      setTicker("");
      setShowForm(false);
      toast.success("Subfundusz dodany");
    } catch {
      toast.error("Błąd podczas tworzenia subfunduszu");
    }
  }

  async function handleDelete(id: string, fundName: string) {
    if (!confirm(`Usunąć subfundusz "${fundName}"? Zostaną usunięte wszystkie snapshoty i alerty.`))
      return;
    try {
      await subfundsApi.delete(id);
      mutate(["subfunds", fundId]);
      toast.success("Subfundusz usunięty");
    } catch {
      toast.error("Błąd podczas usuwania subfunduszu");
    }
  }

  return (
    <div className="space-y-6 max-w-3xl">
      <div className="flex items-center justify-between">
        <div>
          {fundId && (
            <Link href="/funds" className="text-xs text-muted-foreground hover:text-foreground mb-1 inline-block">
              ← Fundusze
            </Link>
          )}
          <h1 className="text-2xl font-bold">
            {fundName ? `Subfundusze: ${fundName}` : "Subfundusze"}
          </h1>
          <p className="text-muted-foreground text-sm mt-1">
            {fundId
              ? "Subfundusze należące do tego funduszu"
              : "Lista subfunduszy tworzonych automatycznie podczas parsowania plików TFI"}
          </p>
        </div>
        {user && (
        <button
          onClick={() => setShowForm((v) => !v)}
          className="flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-md text-sm font-medium hover:opacity-90"
        >
          <Plus className="h-4 w-4" />
          Nowy subfundusz
        </button>
        )}
      </div>

      {showForm && (
        <form
          onSubmit={handleCreate}
          className="p-4 border rounded-lg bg-card space-y-3"
        >
          <h3 className="font-medium">Dodaj subfundusz</h3>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-xs text-muted-foreground">Nazwa *</label>
              <input
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="np. PKO Akcji Plus"
                required
                className="mt-1 w-full border rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
              />
            </div>
            <div>
              <label className="text-xs text-muted-foreground">Ticker / symbol</label>
              <input
                value={ticker}
                onChange={(e) => setTicker(e.target.value)}
                placeholder="np. PKO-AP"
                className="mt-1 w-full border rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
              />
            </div>
          </div>
          <div className="flex gap-2">
            <button
              type="submit"
              className="px-4 py-2 bg-primary text-primary-foreground rounded-md text-sm font-medium"
            >
              Zapisz
            </button>
            <button
              type="button"
              onClick={() => setShowForm(false)}
              className="px-4 py-2 border rounded-md text-sm"
            >
              Anuluj
            </button>
          </div>
        </form>
      )}

      {isLoading && (
        <div className="text-muted-foreground text-sm">Ładowanie...</div>
      )}

      {funds && funds.length > 0 && (
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground pointer-events-none" />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Szukaj po nazwie lub tickerze…"
            className="w-full border rounded-md pl-9 pr-8 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary bg-background"
          />
          {query && (
            <button
              onClick={() => setQuery("")}
              className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
            >
              <X className="h-4 w-4" />
            </button>
          )}
        </div>
      )}

      {funds && funds.length === 0 && !isLoading && (
        <div className="text-muted-foreground text-sm bg-muted/40 rounded-lg p-8 text-center">
          {user
            ? 'Brak subfunduszy. Wgraj plik TFI przez „Upload” lub kliknij „Nowy subfundusz”.'
            : 'Brak subfunduszy.'}
        </div>
      )}

      {(() => {
        const filtered = (funds ?? []).filter((f) => {
          const q = query.toLowerCase();
          return (
            f.name.toLowerCase().includes(q) ||
            (f.ticker ?? "").toLowerCase().includes(q)
          );
        });
        return (
          <>
            <div className="space-y-2">
              {filtered.map((fund) => (
                <FundRow key={fund.id} fund={fund} onDelete={handleDelete} canDelete={!!user} />
              ))}
            </div>
            {query && filtered.length === 0 && (
              <div className="text-muted-foreground text-sm bg-muted/40 rounded-lg p-6 text-center">
                Brak subfunduszy pasujących do „{query}”.
              </div>
            )}
            {funds && funds.length > 0 && (
              <div className="text-xs text-muted-foreground">
                {query ? `${filtered.length} z ${funds.length}` : funds.length}{" "}
                {funds.length === 1 ? "subfundusz" : funds.length < 5 ? "subfundusze" : "subfunduszy"}
              </div>
            )}
          </>
        );
      })()}
    </div>
  );
}

export default function SubfundsPage() {
  return (
    <Suspense>
      <SubfundsPageInner />
    </Suspense>
  );
}

function FundRow({
  fund,
  onDelete,
  canDelete,
}: {
  fund: Subfund;
  onDelete: (id: string, name: string) => void;
  canDelete: boolean;
}) {
  return (
    <div className="flex items-center justify-between p-4 border rounded-lg bg-card hover:border-primary/50 transition-colors">
      <Link href={`/subfunds/${fund.id}`} className="flex-1 min-w-0">
        <div className="font-medium">{fund.name}</div>
        <div className="text-xs text-muted-foreground mt-0.5">
          {fund.ticker ?? "bez tickera"} · dodany{" "}
          {new Date(fund.created_at).toLocaleDateString("pl-PL")}
        </div>
      </Link>
      <div className="flex items-center gap-2 shrink-0 ml-4">
        <Link
          href={`/subfunds/${fund.id}`}
          className="p-2 hover:bg-muted rounded-md text-muted-foreground"
        >
          <ChevronRight className="h-4 w-4" />
        </Link>
        {canDelete && (
        <button
          onClick={() => onDelete(fund.id, fund.name)}
          className="p-2 hover:bg-destructive/10 hover:text-destructive rounded-md text-muted-foreground"
        >
          <Trash2 className="h-4 w-4" />
        </button>
        )}
      </div>
    </div>
  );
}
