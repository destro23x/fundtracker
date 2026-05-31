"use client";

import { useState, useCallback, useRef } from "react";
import useSWR, { mutate } from "swr";
import { useDropzone } from "react-dropzone";
import { tfiApi, snapshotsApi, type TFI, type UploadAllResult } from "@/lib/api";
import { useAuth } from "@/contexts/AuthContext";
import { Plus, Trash2, Upload, ChevronRight, Loader2, CheckCircle2, AlertCircle, X } from "lucide-react";
import { toast } from "sonner";
import Link from "next/link";
import { cn } from "@/lib/utils";

// ─── TFI upload card ─────────────────────────────────────────────────────────

function TFICard({ tfi, onDelete, canDelete }: { tfi: TFI; onDelete: (id: string) => void; canDelete: boolean }) {
  const [uploading, setUploading] = useState(false);
  const [result, setResult] = useState<UploadAllResult | null>(null);
  const [snapshotDate, setSnapshotDate] = useState("");
  const [forceUpload, setForceUpload] = useState(false);
  const [expanded, setExpanded] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const onDrop = useCallback(
    async (accepted: File[]) => {
      const file = accepted[0];
      if (!file) return;
      await doUpload(file);
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [tfi.id, snapshotDate, forceUpload]
  );

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": [".xlsx"],
      "application/vnd.ms-excel": [".xls"],
      "application/pdf": [".pdf"],
    },
    maxFiles: 1,
    noClick: true,
  });

  async function doUpload(file: File) {
    setUploading(true);
    setResult(null);
    const formData = new FormData();
    formData.append("file", file);
    formData.append("tfi_id", tfi.id);
    if (snapshotDate) formData.append("snapshot_date", snapshotDate);
    if (forceUpload) formData.append("force", "true");
    try {
      const res = await snapshotsApi.uploadAll(formData);
      setResult(res);
      mutate("tfi");
      mutate("funds");
      toast.success(
        `${tfi.name}: załadowano ${res.created.length} subfunduszy` +
          (res.skipped.length > 0 ? `, pominięto ${res.skipped.length}` : "")
      );
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: unknown } } })?.response?.data
        ?.detail;
      const msg = typeof detail === "string" ? detail : "Nieznany błąd uploadu";
      toast.error(msg);
    } finally {
      setUploading(false);
    }
  }

  return (
    <div className="rounded-lg border bg-card overflow-hidden">
      {/* Header */}
      <div className="flex items-center gap-3 px-4 py-3">
        {canDelete && (
        <button
          onClick={() => setExpanded((v) => !v)}
          className="p-0.5 shrink-0"
          title="Rozwiń / zwiń"
        >
          <ChevronRight
            className={cn("h-4 w-4 text-muted-foreground transition-transform", expanded && "rotate-90")}
          />
        </button>
        )}

        <Link
          href={`/tfi/${tfi.id}`}
          className="flex-1 flex items-center gap-2 min-w-0 hover:text-primary"
        >
          <span className="font-medium truncate">{tfi.name}</span>
          <span className="text-xs text-muted-foreground shrink-0">
            {tfi.subfund_count} subfund{tfi.subfund_count === 1 ? "" : tfi.subfund_count < 5 ? "usze" : "uszy"}
          </span>
        </Link>

        {tfi.subfund_count > 0 && (
          <Link
            href={`/funds?tfi=${tfi.id}`}
            className="text-xs text-muted-foreground hover:text-foreground shrink-0"
          >
            pokaż subfundusze →
          </Link>
        )}

        {canDelete && (
        <button
          onClick={() => onDelete(tfi.id)}
          className="p-1.5 hover:bg-destructive/10 hover:text-destructive rounded text-muted-foreground shrink-0"
          title="Usuń TFI"
        >
          <Trash2 className="h-4 w-4" />
        </button>
        )}
      </div>

      {/* Upload area — collapsed by default, expand on click */}
      {canDelete && expanded && (
        <div className="border-t px-4 py-4 space-y-3 bg-muted/10">
          {/* Options row */}
          <div className="flex flex-wrap items-center gap-3 text-sm">
            <div className="flex items-center gap-1.5">
              <label className="text-xs text-muted-foreground">Data snapshotu:</label>
              <input
                type="date"
                value={snapshotDate}
                onChange={(e) => setSnapshotDate(e.target.value)}
                className="border rounded px-2 py-0.5 text-xs focus:outline-none focus:ring-1 focus:ring-primary bg-background"
              />
              <span className="text-xs text-muted-foreground">(opcjonalnie)</span>
            </div>
            <label className="flex items-center gap-1.5 text-xs text-muted-foreground cursor-pointer">
              <input
                type="checkbox"
                checked={forceUpload}
                onChange={(e) => setForceUpload(e.target.checked)}
                className="rounded"
              />
              Nadpisz istniejące snapshoty
            </label>
          </div>

          {/* Drop zone */}
          <div
            {...getRootProps()}
            className={cn(
              "border-2 border-dashed rounded-lg p-6 text-center cursor-pointer transition-colors",
              isDragActive ? "border-primary bg-primary/5" : "border-muted hover:border-primary/50"
            )}
            onClick={() => inputRef.current?.click()}
          >
            <input {...getInputProps()} ref={inputRef} />
            {uploading ? (
              <div className="flex items-center justify-center gap-2 text-muted-foreground">
                <Loader2 className="h-5 w-5 animate-spin" />
                <span className="text-sm">Przetwarzanie…</span>
              </div>
            ) : (
              <>
                <Upload className="h-7 w-7 mx-auto mb-2 text-muted-foreground" />
                <p className="text-sm font-medium">
                  {isDragActive ? "Upuść plik tutaj" : "Kliknij lub przeciągnij plik TFI"}
                </p>
                <p className="text-xs text-muted-foreground mt-0.5">.xlsx, .xls lub .pdf</p>
              </>
            )}
          </div>

          {/* Result */}
          {result && (
            <div className="space-y-1.5 text-sm">
              {result.created.map((s) => (
                <div key={s.snapshot_id} className="flex items-center gap-2 text-green-700 dark:text-green-400">
                  <CheckCircle2 className="h-3.5 w-3.5 shrink-0" />
                  <span>
                    {s.fund_name} — {s.position_count} poz. ({s.snapshot_date})
                    {s.fund_created && (
                      <span className="ml-1 text-xs bg-green-100 dark:bg-green-900/30 px-1 rounded">nowy</span>
                    )}
                  </span>
                </div>
              ))}
              {result.skipped.map((s, i) => (
                <div key={i} className="flex items-center gap-2 text-amber-600 dark:text-amber-400">
                  <AlertCircle className="h-3.5 w-3.5 shrink-0" />
                  <span>{s.fund_name}: {s.reason}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export default function TFIPage() {
  const { user } = useAuth();
  const { data: tfiList, isLoading } = useSWR("tfi", tfiApi.list);
  const [showForm, setShowForm] = useState(false);
  const [name, setName] = useState("");
  const [saving, setSaving] = useState(false);

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    if (!name.trim()) return;
    setSaving(true);
    try {
      await tfiApi.create(name.trim());
      mutate("tfi");
      setName("");
      setShowForm(false);
      toast.success("TFI dodane");
    } catch {
      toast.error("Błąd podczas tworzenia TFI");
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete(id: string) {
    const item = tfiList?.find((t) => t.id === id);
    if (!confirm(`Usunąć TFI „${item?.name}"? Subfundusze zostaną odłączone (nie usunięte).`)) return;
    try {
      await tfiApi.delete(id);
      mutate("tfi");
      toast.success("TFI usunięte");
    } catch {
      toast.error("Błąd podczas usuwania TFI");
    }
  }

  return (
    <div className="max-w-2xl space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">TFI</h1>
          <p className="text-muted-foreground text-sm mt-1">
            Towarzystwa Funduszy Inwestycyjnych — dodaj TFI, a subfundusze powstaną automatycznie
            po wgraniu pliku Excel / PDF
          </p>
        </div>
        {user && (
        <button
          onClick={() => setShowForm((v) => !v)}
          className="flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-md text-sm font-medium hover:opacity-90"
        >
          <Plus className="h-4 w-4" />
          Nowe TFI
        </button>
        )}
      </div>

      {showForm && (
        <form onSubmit={handleCreate} className="p-4 border rounded-lg bg-card flex items-end gap-3">
          <div className="flex-1">
            <label className="text-xs text-muted-foreground">Nazwa TFI *</label>
            <input
              autoFocus
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="np. Goldman Sachs TFI, PKO TFI"
              required
              className="mt-1 w-full border rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
            />
          </div>
          <button
            type="submit"
            disabled={saving}
            className="px-4 py-2 bg-primary text-primary-foreground rounded-md text-sm font-medium disabled:opacity-60"
          >
            {saving ? "Zapisywanie…" : "Zapisz"}
          </button>
          <button
            type="button"
            onClick={() => setShowForm(false)}
            className="p-2 text-muted-foreground hover:text-foreground"
          >
            <X className="h-4 w-4" />
          </button>
        </form>
      )}

      {isLoading && (
        <div className="flex items-center gap-2 text-muted-foreground text-sm">
          <Loader2 className="h-4 w-4 animate-spin" />
          Ładowanie…
        </div>
      )}

      {tfiList && tfiList.length === 0 && !isLoading && (
        <div className="text-center py-12 text-muted-foreground text-sm bg-muted/30 rounded-lg">
          Brak TFI. Kliknij „Nowe TFI" żeby zacząć.
        </div>
      )}

      <div className="space-y-3">
        {tfiList?.map((t) => (
          <TFICard key={t.id} tfi={t} onDelete={handleDelete} canDelete={!!user} />
        ))}
      </div>
    </div>
  );
}
