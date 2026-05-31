"use client";

import useSWR from "swr";
import { useState } from "react";
import { uploadHistoryApi, type TFIHistoryEntry, type SnapshotEntry } from "@/lib/api";
import { Loader2, History, Building2, ChevronDown, ChevronRight, FileSpreadsheet, CalendarDays } from "lucide-react";

// ─── Helpers ──────────────────────────────────────────────────────────────────

function fmtDate(iso: string) {
  return new Date(iso).toLocaleDateString("pl-PL", {
    day: "2-digit", month: "2-digit", year: "numeric",
  });
}

function fmtDateTime(iso: string) {
  return new Date(iso).toLocaleString("pl-PL", {
    day: "2-digit", month: "2-digit", year: "numeric",
    hour: "2-digit", minute: "2-digit",
  });
}

interface UniqueUpload {
  key: string;
  snapshot_date: string;
  upload_filename: string | null;
  uploaded_at: string;
  subfund_count: number;
  total_positions: number;
}

function getUniqueUploads(entry: TFIHistoryEntry): UniqueUpload[] {
  const map = new Map<string, UniqueUpload>();
  for (const fund of entry.funds) {
    for (const snap of fund.snapshots) {
      const key = `${snap.snapshot_date}||${snap.upload_filename ?? ""}`;
      const existing = map.get(key);
      if (existing) {
        existing.subfund_count += 1;
        existing.total_positions += snap.position_count;
      } else {
        map.set(key, {
          key,
          snapshot_date: snap.snapshot_date,
          upload_filename: snap.upload_filename,
          uploaded_at: snap.uploaded_at,
          subfund_count: 1,
          total_positions: snap.position_count,
        });
      }
    }
  }
  return Array.from(map.values()).sort((a, b) =>
    b.snapshot_date.localeCompare(a.snapshot_date)
  );
}

// ─── TFI row (expandable) ─────────────────────────────────────────────────────

function TFIRow({ entry }: { entry: TFIHistoryEntry }) {
  const [open, setOpen] = useState(false);
  const uploads = open ? getUniqueUploads(entry) : [];

  return (
    <>
      <tr
        className="hover:bg-muted/20 transition-colors cursor-pointer select-none"
        onClick={() => setOpen((v) => !v)}
      >
        <td className="px-4 py-2.5">
          <span className="flex items-center gap-2">
            {open
              ? <ChevronDown className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
              : <ChevronRight className="h-3.5 w-3.5 text-muted-foreground shrink-0" />}
            <Building2 className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
            <span className="font-medium">
              {entry.tfi_name ?? <span className="text-muted-foreground italic">Bez TFI</span>}
            </span>
          </span>
        </td>
        <td className="px-4 py-2.5 text-right tabular-nums text-muted-foreground">
          {entry.fund_count}
        </td>
        <td className="px-4 py-2.5 text-right tabular-nums font-medium">
          {entry.upload_count}
        </td>
      </tr>

      {open && uploads.map((u) => (
        <tr key={u.key} className="bg-muted/10 border-t border-dashed">
          <td className="pl-12 pr-4 py-2" colSpan={3}>
            <div className="flex flex-wrap items-center gap-x-6 gap-y-1 text-sm">
              <span className="flex items-center gap-1.5 font-mono text-xs font-semibold">
                <CalendarDays className="h-3.5 w-3.5 text-muted-foreground" />
                {u.snapshot_date}
              </span>
              {u.upload_filename && (
                <span className="flex items-center gap-1.5 text-muted-foreground text-xs truncate max-w-[300px]">
                  <FileSpreadsheet className="h-3.5 w-3.5 shrink-0" />
                  {u.upload_filename}
                </span>
              )}
              <span className="text-xs text-muted-foreground">
                {u.subfund_count} subfund. · {u.total_positions} pozycji
              </span>
              <span className="text-xs text-muted-foreground ml-auto">
                wgrano {fmtDateTime(u.uploaded_at)}
              </span>
            </div>
          </td>
        </tr>
      ))}
    </>
  );
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export default function HistoriaPage() {
  const { data, isLoading, error } = useSWR("upload-history", uploadHistoryApi.get, {
    revalidateOnFocus: false,
  });

  const totalUploads = data?.reduce((s, t) => s + t.upload_count, 0) ?? 0;

  return (
    <div className="max-w-3xl mx-auto space-y-5">
      <div>
        <h1 className="text-xl font-bold flex items-center gap-2">
          <History className="h-5 w-5" />
          Historia uploadów
        </h1>
        {data && (
          <p className="text-sm text-muted-foreground mt-0.5">
            {data.length} TFI · {totalUploads} wgranych {totalUploads === 1 ? "raport" : totalUploads < 5 ? "raporty" : "raportów"} łącznie
          </p>
        )}
      </div>

      {isLoading && (
        <div className="flex items-center justify-center py-16 text-muted-foreground gap-2">
          <Loader2 className="h-5 w-5 animate-spin" />
          <span className="text-sm">Ładowanie…</span>
        </div>
      )}

      {error && (
        <p className="text-sm text-destructive text-center py-10">
          Błąd ładowania danych.
        </p>
      )}

      {data?.length === 0 && (
        <p className="text-sm text-muted-foreground text-center py-10">
          Brak danych — najpierw wgraj raporty.
        </p>
      )}

      {data && data.length > 0 && (
        <div className="rounded-lg border bg-card overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b bg-muted/30 text-muted-foreground text-xs uppercase tracking-wide">
                <th className="text-left px-4 py-2 font-medium">TFI</th>
                <th className="text-right px-4 py-2 font-medium">Subfundusze</th>
                <th className="text-right px-4 py-2 font-medium">Raporty</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {data.map((entry: TFIHistoryEntry) => (
                <TFIRow key={entry.tfi_id ?? "__none__"} entry={entry} />
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

