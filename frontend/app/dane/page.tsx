"use client";

import { useState, useCallback, useRef } from "react";
import useSWR from "swr";
import { useDropzone } from "react-dropzone";
import { api, tfiApi } from "@/lib/api";
import { toast } from "sonner";
import { cn } from "@/lib/utils";
import {
  Upload,
  FileSpreadsheet,
  RefreshCw,
  CheckCircle2,
  AlertCircle,
  Loader2,
  ChevronDown,
  Save,
  X,
  Database,
} from "lucide-react";

// ---------------------------------------------------------------------------
// Typy
// ---------------------------------------------------------------------------

interface S3FileInfo {
  key: string;
  filename: string;
  size: number;
  last_modified: string;
}

interface LoadedFileInfo {
  source_filename: string;
  record_count: number;
  loaded_at: string;
}

interface DaneRow {
  umbrella_name: string | null;
  subfund_name: string | null;
  fund_id: string | null;
  izfia_id: string | null;
  fund_type: string | null;
  company_name: string;
  country: string | null;
  isin: string | null;
  asset_type: string | null;
  shares: number | null;
  currency_fund: string;
  currency_instrument: string;
  value: number | null;
  weight_pct: number | null;
  snapshot_date: string | null;
  currency_flag: boolean;
}

interface ProcessResult {
  parsed_filename: string;
  total_rows: number;
  flagged_rows: number;
  rows: DaneRow[];
}

interface SaveResult {
  saved_count: number;
  source_filename: string;
  parsed_filename: string;
  created_tfi: boolean;
  created_fundusze: number;
  created_funds: number;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const apiBase = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

const filesFetcher = () =>
  api.get<S3FileInfo[]>("/api/v1/dane/files").then((r) => r.data);

const loadedFetcher = () =>
  api.get<LoadedFileInfo[]>("/api/v1/dane/loaded").then((r) => r.data);

function fmtSize(bytes: number) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

function fmtNum(v: number | null) {
  if (v == null) return "—";
  return v.toLocaleString("pl-PL", { maximumFractionDigits: 4 });
}

const COLS = [
  { label: "Fundusz",         init: 140 },
  { label: "Subfundusz",      init: 140 },
  { label: "Typ funduszu",    init:  90 },
  { label: "ISIN funduszu",    init: 120 },
  { label: "Kod IZFiA",        init:  80 },
  { label: "Emitent",         init: 160 },
  { label: "Kraj",            init:  60 },
  { label: "ISIN",            init: 110 },
  { label: "Typ instrumentu", init: 160 },
  { label: "Ilość",           init: 100 },
  { label: "Waluta fund.",    init:  90 },
  { label: "Waluta instr.",   init:  90 },
  { label: "Wartość",         init: 110 },
  { label: "Udział %",        init:  80 },
  { label: "Data",            init:  90 },
];

const ASSET_TYPE_PL: Record<string, string> = {
  stock: "Akcje",
  bond_government: "Obligacje skarbowe",
  bond_corporate: "Obligacje korporacyjne",
  bond_municipal: "Obligacje samorządowe",
  covered_bond: "Listy zastawne",
  etf_foreign: "Tytuły uczestnictwa",
  fund: "Fundusze inwestycyjne",
  cash: "Waluta",
  repo: "Buy-sell-back",
  derivative_fx: "Instr. pochodne – FX Forward",
  derivative_swap: "Instr. pochodne – Swap",
  derivative_futures_index: "Instr. pochodne – Futures (indeksy)",
  derivative_futures_bond: "Instr. pochodne – Futures (obligacje)",
  derivative_futures_equity: "Instr. pochodne – Futures (akcje)",
  other: "Inne",
};

function fmtAssetType(v: string | null) {
  if (!v) return "—";
  return ASSET_TYPE_PL[v] ?? v;
}

// ---------------------------------------------------------------------------
// Sekcja 1: Załaduj skład portfela
// ---------------------------------------------------------------------------

function UploadSection({ onUploaded }: { onUploaded: () => void }) {
  const [files, setFiles] = useState<File[]>([]);
  const [uploading, setUploading] = useState(false);

  const onDrop = useCallback((accepted: File[]) => {
    if (accepted.length > 0) {
      setFiles((prev) => {
        const existing = new Set(prev.map((f) => f.name + f.size));
        const newFiles = accepted.filter((f) => !existing.has(f.name + f.size));
        return [...prev, ...newFiles];
      });
    }
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    multiple: true,
    accept: {
      "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": [".xlsx"],
      "application/vnd.ms-excel": [".xls"],
      "application/pdf": [".pdf"],
    },
  });

  function removeFile(index: number) {
    setFiles((prev) => prev.filter((_, i) => i !== index));
  }

  const handleUpload = async () => {
    if (files.length === 0) return;
    setUploading(true);
    const errors: string[] = [];
    for (const file of files) {
      try {
        const form = new FormData();
        form.append("file", file);
        await api.post("/api/v1/dane/upload", form);
        toast.success(`Plik „${file.name}" zapisany w S3`);
      } catch (err: any) {
        const msg = err?.response?.data?.detail ?? "Błąd uploadu";
        errors.push(`${file.name}: ${msg}`);
      }
    }
    setUploading(false);
    if (errors.length === 0) {
      setFiles([]);
      onUploaded();
    } else {
      errors.forEach((e) => toast.error(e));
      // usuń poprawnie przesłane pliki (zakładamy błąd = te same pliki)
      onUploaded();
    }
  };

  return (
    <div className="rounded-lg border bg-card p-6 space-y-4">
      <h2 className="text-lg font-semibold">Załaduj skład portfela</h2>
      <p className="text-sm text-muted-foreground">
        Pliki zostaną zapisane w S3 w folderze <code>PortfolioComposition/</code>.
      </p>

      <div
        {...getRootProps()}
        className={cn(
          "border-2 border-dashed rounded-lg p-6 text-center cursor-pointer transition-colors",
          isDragActive
            ? "border-primary bg-primary/5"
            : "border-muted-foreground/25 hover:border-primary/50"
        )}
      >
        <input {...getInputProps()} />
        {files.length > 0 ? (
          <div className="space-y-2" onClick={(e) => e.stopPropagation()}>
            {files.map((f, i) => (
              <div key={i} className="flex items-center gap-3 rounded-md bg-muted/50 px-3 py-2 text-left">
                <FileSpreadsheet className="h-5 w-5 shrink-0 text-primary" />
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium truncate">{f.name}</p>
                  <p className="text-xs text-muted-foreground">{fmtSize(f.size)}</p>
                </div>
                <button
                  type="button"
                  onClick={() => removeFile(i)}
                  className="shrink-0 text-muted-foreground hover:text-destructive"
                >
                  <X className="h-4 w-4" />
                </button>
              </div>
            ))}
            <p className="text-xs text-muted-foreground pt-1">
              Upuść kolejne pliki lub <span className="text-primary underline">kliknij</span>, aby dodać więcej
            </p>
          </div>
        ) : isDragActive ? (
          <p className="text-sm text-primary">Upuść pliki tutaj…</p>
        ) : (
          <div>
            <FileSpreadsheet className="mx-auto h-10 w-10 text-muted-foreground mb-3" />
            <p className="text-sm text-muted-foreground">
              Przeciągnij pliki xlsx/xls/pdf lub{" "}
              <span className="text-primary underline">kliknij aby wybrać</span>
            </p>
            <p className="text-xs text-muted-foreground mt-1">Możesz wybrać wiele plików naraz</p>
          </div>
        )}
      </div>

      <button
        disabled={files.length === 0 || uploading}
        onClick={handleUpload}
        className={cn(
          "flex items-center gap-2 px-4 py-2 rounded-md text-sm font-medium transition-colors",
          files.length > 0 && !uploading
            ? "bg-primary text-primary-foreground hover:bg-primary/90"
            : "bg-muted text-muted-foreground cursor-not-allowed"
        )}
      >
        {uploading ? (
          <Loader2 className="h-4 w-4 animate-spin" />
        ) : (
          <Upload className="h-4 w-4" />
        )}
        {uploading
          ? "Ładowanie…"
          : files.length > 1
          ? `Załaduj ${files.length} pliki do S3`
          : "Załaduj do S3"}
      </button>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Sekcja 2: Przetwórz
// ---------------------------------------------------------------------------

function ProcessSection({ files, onSaved }: { files: S3FileInfo[]; onSaved: () => void }) {
  const [selectedFile, setSelectedFile] = useState("");
  const [processing, setProcessing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [result, setResult] = useState<ProcessResult | null>(null);
  const [saved, setSaved] = useState<SaveResult | null>(null);
  const [colWidths, setColWidths] = useState<number[]>(COLS.map((c) => c.init));
  const [detectedTfi, setDetectedTfi] = useState<string | null>(null);
  const [detecting, setDetecting] = useState(false);
  const resizingRef = useRef<{ colIndex: number; startX: number; startW: number } | null>(null);

  const onResizerMouseDown = (colIndex: number, e: React.MouseEvent) => {
    e.preventDefault();
    resizingRef.current = { colIndex, startX: e.clientX, startW: colWidths[colIndex] };
    const onMouseMove = (ev: MouseEvent) => {
      if (!resizingRef.current) return;
      const { colIndex: ci, startX, startW } = resizingRef.current;
      const newW = Math.max(40, startW + (ev.clientX - startX));
      setColWidths((prev) => prev.map((w, i) => (i === ci ? newW : w)));
    };
    const onMouseUp = () => {
      resizingRef.current = null;
      window.removeEventListener("mousemove", onMouseMove);
      window.removeEventListener("mouseup", onMouseUp);
    };
    window.addEventListener("mousemove", onMouseMove);
    window.addEventListener("mouseup", onMouseUp);
  };

  const handleFileSelect = async (filename: string) => {
    setSelectedFile(filename);
    setResult(null);
    setSaved(null);
    setDetectedTfi(null);
    if (!filename) return;
    setDetecting(true);
    try {
      const resp = await api.get<{ parser_id: string | null; tfi_name: string | null }>(
        `/api/v1/dane/detect?filename=${encodeURIComponent(filename)}`
      );
      setDetectedTfi(resp.data.tfi_name ?? "Nierozpoznany");
    } catch {
      setDetectedTfi("Nierozpoznany");
    } finally {
      setDetecting(false);
    }
  };

  const handleProcess = async () => {
    if (!selectedFile) return;
    setProcessing(true);
    setResult(null);
    setSaved(null);
    try {
      const form = new FormData();
      form.append("filename", selectedFile);
      const resp = await api.post<ProcessResult>("/api/v1/dane/process", form);
      setResult(resp.data);
      if (resp.data.flagged_rows > 0) {
        toast.warning(
          `${resp.data.flagged_rows} rekordów ma walutę wyceny funduszu różną od PLN (zaznaczone czerwono)`
        );
      } else {
        toast.success(`Sparsowano ${resp.data.total_rows} wierszy`);
      }
    } catch (err: any) {
      toast.error(err?.response?.data?.detail ?? "Błąd parsowania");
    } finally {
      setProcessing(false);
    }
  };

  const handleSave = async () => {
    if (!selectedFile) return;
    setSaving(true);
    try {
      const form = new FormData();
      form.append("filename", selectedFile);
      if (detectedTfi && detectedTfi !== "Nierozpoznany") {
        form.append("tfi_name", detectedTfi);
      }
      const resp = await api.post<SaveResult>("/api/v1/dane/save", form);
      setSaved(resp.data);

      const parts: string[] = [`Zapisano ${resp.data.saved_count} rekordów`];
      if (resp.data.created_tfi) parts.push(`nowe TFI: ${detectedTfi}`);
      if (resp.data.created_fundusze > 0) parts.push(`${resp.data.created_fundusze} nowych funduszy`);
      if (resp.data.created_funds > 0) parts.push(`${resp.data.created_funds} nowych subfunduszy`);
      toast.success(parts.join(" · "));

      setResult(null);
      setSelectedFile("");
      setDetectedTfi(null);
      onSaved();
    } catch (err: any) {
      toast.error(err?.response?.data?.detail ?? "Błąd zapisu do bazy");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="rounded-lg border bg-card p-6 space-y-4">
      <h2 className="text-lg font-semibold">Przetwórz</h2>
      <p className="text-sm text-muted-foreground">
        Wybierz plik z folderu <code>PortfolioComposition/</code>, aby go sparsować
        i zapisać w znormalizowanym formacie.
      </p>

      {/* Wybór pliku */}
      <div className="space-y-3">
        <div className="flex items-center gap-3">
          <div className="relative flex-1">
            <select
              value={selectedFile}
              onChange={(e) => handleFileSelect(e.target.value)}
              className="w-full appearance-none rounded-md border bg-background px-3 py-2 pr-8 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
            >
              <option value="">— wybierz plik —</option>
              {files.map((f) => (
                <option key={f.key} value={f.filename}>
                  {f.filename} ({fmtSize(f.size)})
                </option>
              ))}
            </select>
            <ChevronDown className="pointer-events-none absolute right-2 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          </div>

          <button
            disabled={!selectedFile || processing}
            onClick={handleProcess}
            className={cn(
              "flex items-center gap-2 px-4 py-2 rounded-md text-sm font-medium whitespace-nowrap transition-colors",
              selectedFile && !processing
                ? "bg-primary text-primary-foreground hover:bg-primary/90"
                : "bg-muted text-muted-foreground cursor-not-allowed"
            )}
          >
            {processing ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <RefreshCw className="h-4 w-4" />
            )}
            {processing ? "Przetwarzanie…" : "Przetwórz"}
          </button>
        </div>

        {/* Wykryte TFI */}
        {selectedFile && (
          <div className="flex items-center gap-2">
            <span className="text-xs text-muted-foreground whitespace-nowrap">TFI:</span>
            {detecting ? (
              <span className="flex items-center gap-1.5 text-xs text-muted-foreground">
                <Loader2 className="h-3 w-3 animate-spin" /> Wykrywanie…
              </span>
            ) : (
              <span className={cn(
                "inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium border",
                detectedTfi && detectedTfi !== "Nierozpoznany"
                  ? "bg-green-50 text-green-800 border-green-200"
                  : "bg-yellow-50 text-yellow-800 border-yellow-200"
              )}>
                {detectedTfi ?? "—"}
              </span>
            )}
          </div>
        )}
      </div>

      {/* Podgląd wyników */}
      {result && (
        <div className="space-y-3">
          <div className="flex items-center justify-between text-sm">
            <span className="text-muted-foreground">
              Wiersze: <strong>{result.total_rows}</strong>
              {result.flagged_rows > 0 && (
                <span className="ml-2 text-red-600">
                  ({result.flagged_rows} z walutą funduszu ≠ PLN)
                </span>
              )}
            </span>
            <button
              disabled={saving}
              onClick={handleSave}
              className={cn(
                "flex items-center gap-2 px-4 py-2 rounded-md text-sm font-medium transition-colors",
                !saving
                  ? "bg-green-600 text-white hover:bg-green-700"
                  : "bg-muted text-muted-foreground cursor-not-allowed"
              )}
            >
              {saving ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Save className="h-4 w-4" />
              )}
              {saving ? "Zapisywanie…" : "Zapisz do bazy"}
            </button>
          </div>

          {/* Tabela podglądu */}
          <div className="overflow-auto max-h-[60vh] rounded-md border text-xs select-none">
            <table
              className="border-collapse table-fixed"
              style={{ width: colWidths.reduce((a, b) => a + b, 0) + "px" }}
            >
              <colgroup>
                {colWidths.map((w, i) => (
                  <col key={i} style={{ width: w + "px" }} />
                ))}
              </colgroup>
              <thead className="sticky top-0 bg-muted z-10">
                <tr>
                  {COLS.map((col, i) => (
                    <th
                      key={col.label}
                      className="px-2 py-2 text-left font-semibold border-b overflow-hidden"
                      style={{ position: "relative", width: colWidths[i] + "px" }}
                    >
                      <span className="block truncate pr-2">{col.label}</span>
                      <div
                        onMouseDown={(e) => onResizerMouseDown(i, e)}
                        className="absolute right-0 top-0 bottom-0 w-1 cursor-col-resize hover:bg-primary/50 active:bg-primary"
                        style={{ userSelect: "none" }}
                      />
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {result.rows.map((row, i) => (
                  <tr
                    key={i}
                    className={cn(
                      "border-b last:border-0",
                      row.currency_flag
                        ? "bg-red-50 text-red-800"
                        : i % 2 === 0
                        ? "bg-background"
                        : "bg-muted/20"
                    )}
                  >
                    <td className="px-2 py-1.5 overflow-hidden" title={row.umbrella_name ?? ""}>
                      <span className="block truncate">{row.umbrella_name ?? "—"}</span>
                    </td>
                    <td className="px-2 py-1.5 overflow-hidden" title={row.subfund_name ?? ""}>
                      <span className="block truncate">{row.subfund_name ?? "—"}</span>
                    </td>
                    <td className="px-2 py-1.5 overflow-hidden" title={row.fund_type ?? ""}>
                      <span className="block truncate">{row.fund_type ?? "—"}</span>
                    </td>
                    <td className="px-2 py-1.5 font-mono overflow-hidden" title={row.fund_id ?? ""}>
                      <span className="block truncate">{row.fund_id ?? "—"}</span>
                    </td>
                    <td className="px-2 py-1.5 font-mono overflow-hidden" title={row.izfia_id ?? ""}>
                      <span className="block truncate">{row.izfia_id ?? "—"}</span>
                    </td>
                    <td className="px-2 py-1.5 overflow-hidden" title={row.company_name}>
                      <span className="block truncate">{row.company_name}</span>
                    </td>
                    <td className="px-2 py-1.5 overflow-hidden">
                      <span className="block truncate">{row.country ?? "—"}</span>
                    </td>
                    <td className="px-2 py-1.5 font-mono overflow-hidden">
                      <span className="block truncate">{row.isin ?? "—"}</span>
                    </td>
                    <td className="px-2 py-1.5 overflow-hidden" title={fmtAssetType(row.asset_type)}>
                      <span className="block truncate">{fmtAssetType(row.asset_type)}</span>
                    </td>
                    <td className="px-2 py-1.5 text-right overflow-hidden">
                      <span className="block truncate">{fmtNum(row.shares)}</span>
                    </td>
                    <td className={cn("px-2 py-1.5 font-medium overflow-hidden", row.currency_flag && "text-red-700")}>
                      <span className="block truncate">{row.currency_fund}</span>
                    </td>
                    <td className="px-2 py-1.5 overflow-hidden">
                      <span className="block truncate">{row.currency_instrument}</span>
                    </td>
                    <td className="px-2 py-1.5 text-right overflow-hidden">
                      <span className="block truncate">{fmtNum(row.value)}</span>
                    </td>
                    <td className="px-2 py-1.5 text-right overflow-hidden">
                      <span className="block truncate">
                        {row.weight_pct != null ? `${row.weight_pct.toFixed(2)}%` : "—"}
                      </span>
                    </td>
                    <td className="px-2 py-1.5 overflow-hidden">
                      <span className="block truncate">{row.snapshot_date ?? "—"}</span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Potwierdzenie zapisu */}
      {saved && (
        <div className="flex items-center gap-2 rounded-md border border-green-200 bg-green-50 px-4 py-3 text-sm text-green-800">
          <CheckCircle2 className="h-4 w-4 flex-shrink-0" />
          <span>
            Zapisano <strong>{saved.saved_count}</strong> rekordów. Pliki przeniesione do{" "}
            <code>PortfolioCompositionLoaded/</code>.
          </span>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Sekcja 3: Załadowane pliki
// ---------------------------------------------------------------------------

function LoadedFilesSection({
  loaded,
  isLoading,
  onRefresh,
}: {
  loaded: LoadedFileInfo[] | undefined;
  isLoading: boolean;
  onRefresh: () => void;
}) {

  function fmtDate(iso: string) {
    if (!iso) return "—";
    return new Date(iso).toLocaleString("pl-PL", {
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
    });
  }

  return (
    <div className="rounded-xl border bg-card p-5 space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Database className="h-5 w-5 text-primary" />
          <h2 className="text-base font-semibold">Załadowane pliki</h2>
        </div>
        <button
          onClick={() => onRefresh()}
          className="flex items-center gap-1.5 rounded-md border px-3 py-1.5 text-xs hover:bg-muted transition-colors"
        >
          <RefreshCw className="h-3.5 w-3.5" />
          Odśwież
        </button>
      </div>

      {isLoading ? (
        <div className="flex items-center gap-2 text-sm text-muted-foreground py-4">
          <Loader2 className="h-4 w-4 animate-spin" />
          Ładowanie...
        </div>
      ) : !loaded || loaded.length === 0 ? (
        <p className="text-sm text-muted-foreground py-4">Brak załadowanych plików.</p>
      ) : (
        <div className="overflow-x-auto rounded-md border">
          <table className="w-full text-sm">
            <thead className="bg-muted/50">
              <tr>
                <th className="px-3 py-2 text-left font-medium">Plik źródłowy</th>
                <th className="px-3 py-2 text-right font-medium">Rekordów</th>
                <th className="px-3 py-2 text-right font-medium">Data załadowania</th>
              </tr>
            </thead>
            <tbody>
              {loaded.map((f, i) => (
                <tr
                  key={f.source_filename}
                  className={cn(
                    "border-t",
                    i % 2 === 0 ? "bg-background" : "bg-muted/20"
                  )}
                >
                  <td className="px-3 py-2 font-mono text-xs">{f.source_filename}</td>
                  <td className="px-3 py-2 text-right tabular-nums">{f.record_count.toLocaleString("pl-PL")}</td>
                  <td className="px-3 py-2 text-right text-muted-foreground">{fmtDate(f.loaded_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Strona główna
// ---------------------------------------------------------------------------

export default function DanePage() {
  const { data: files = [], mutate: mutateFiles } = useSWR<S3FileInfo[]>("dane-files", filesFetcher, {
    revalidateOnFocus: false,
  });
  const { data: loaded, isLoading: loadedLoading, mutate: mutateLoaded } = useSWR<LoadedFileInfo[]>(
    "dane-loaded",
    loadedFetcher,
    { revalidateOnFocus: false }
  );

  const handleSaved = () => {
    mutateFiles();
    mutateLoaded();
  };

  return (
    <div className="max-w-7xl mx-auto space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Dane</h1>
        <p className="text-sm text-muted-foreground mt-1">
          Zarządzanie składami portfeli: upload, parsowanie i zapis do bazy danych.
        </p>
      </div>

      <UploadSection onUploaded={() => mutateFiles()} />
      <ProcessSection files={files} onSaved={handleSaved} />
      <LoadedFilesSection loaded={loaded} isLoading={loadedLoading} onRefresh={() => mutateLoaded()} />
    </div>
  );
}
