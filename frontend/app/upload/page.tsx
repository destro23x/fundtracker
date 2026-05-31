"use client";

import { useState, useCallback, Suspense } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import Link from "next/link";
import useSWR from "swr";
import { useDropzone } from "react-dropzone";
import { subfundsApi, snapshotsApi, tfiApi, fundsApi, type UploadAllResult, type TFI, type Fund } from "@/lib/api";
import { Upload, FileSpreadsheet, X, CheckCircle2, AlertCircle, Layers, ArrowRight } from "lucide-react";
import { toast } from "sonner";
import { cn } from "@/lib/utils";

interface PreviewResult {
  parser_detected: string | null;
  is_multi_fund: boolean;
  subfunds: string[];
  filename: string;
}

// Wydzielony komponent który używa useSearchParams — musi być w Suspense
function UploadForm() {
  const params = useSearchParams();
  const router = useRouter();
  const preselectedFundId = params.get("fund") ?? "";

  const { data: funds } = useSWR("subfunds", subfundsApi.list);
  const { data: tfiList } = useSWR("tfi", tfiApi.list);

  const [tfiId, setTfiId] = useState("");
  const [fundId, setFundId] = useState("");
  const [subfundId, setSubfundId] = useState(preselectedFundId);
  const [files, setFiles] = useState<File[]>([]);
  const [snapshotDate, setSnapshotDate] = useState("");
  const [useAI, setUseAI] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [previewing, setPreviewing] = useState(false);
  const [preview, setPreview] = useState<PreviewResult | null>(null);
  const [subfundName, setSubfundName] = useState("");
  const [uploadAllMode, setUploadAllMode] = useState(true);
  const [uploadAllResult, setUploadAllResult] = useState<UploadAllResult | null>(null);
  const [forceUpload, setForceUpload] = useState(false);
  const [result, setResult] = useState<{ success: boolean; message: string } | null>(null);

  // Fundusze filtrowane po wybranym TFI
  const { data: fundsDataList } = useSWR(
    tfiId ? ["funds", tfiId] : "funds",
    () => fundsApi.list(tfiId || undefined)
  );

  const onDrop = useCallback((accepted: File[]) => {
    if (accepted.length > 0) {
      setFiles((prev) => {
        const existing = new Set(prev.map((f) => f.name + f.size));
        const newFiles = accepted.filter((f) => !existing.has(f.name + f.size));
        return [...prev, ...newFiles];
      });
      setResult(null);
      setUploadAllResult(null);
      setPreview(null);
      setSubfundName("");
      // Podgląd subfunduszy tylko dla pojedynczego pliku
      if (accepted.length === 1 && subfundId) handlePreview(accepted[0], subfundId);
    }
  }, [subfundId]); // eslint-disable-line react-hooks/exhaustive-deps

  function removeFile(index: number) {
    setFiles((prev) => prev.filter((_, i) => i !== index));
    setPreview(null);
    setSubfundName("");
  }

  // Po wybraniu pliku i funduszu → automatyczny podgląd subfunduszy
  async function handlePreview(selectedFile: File, selectedFundId: string) {
    if (!selectedFile || !selectedFundId) return;
    const formData = new FormData();
    formData.append("file", selectedFile);
    setPreviewing(true);
    try {
      const { api } = await import("@/lib/api");
      const res = await api.post<PreviewResult>(
        `/api/v1/funds/${selectedFundId}/snapshots/preview-subfunds`,
        formData
      );
      setPreview(res.data);
      if (res.data.is_multi_fund) {
        setUploadAllMode(true); // domyślnie "wszystkie" dla pliku multi-fund
        setSubfundName(res.data.subfunds[0] ?? "");
      }
    } catch {
      // Nie blokujemy — podgląd jest opcjonalny
    } finally {
      setPreviewing(false);
    }
  }

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": [".xlsx"],
      "application/vnd.ms-excel": [".xls"],
      "application/pdf": [".pdf"],
    },
    multiple: true,
  });

  async function handleUploadAll() {
    if (files.length === 0) { toast.error("Wybierz pliki"); return; }
    if (!tfiId) { toast.error("Wybierz TFI"); return; }
    setUploading(true);
    setResult(null);
    setUploadAllResult(null);

    const allCreated: UploadAllResult["created"] = [];
    const allSkipped: UploadAllResult["skipped"] = [];
    let totalSubfunds = 0;
    const errors: string[] = [];

    for (const file of files) {
      const formData = new FormData();
      formData.append("file", file);
      formData.append("tfi_id", tfiId);
      if (fundId) formData.append("fund_id", fundId);
      if (snapshotDate) formData.append("snapshot_date", snapshotDate);
      if (forceUpload) formData.append("force", "true");
      try {
        const res = await snapshotsApi.uploadAll(formData);
        allCreated.push(...res.created);
        allSkipped.push(...res.skipped);
        totalSubfunds += res.total_subfunds;
      } catch (err: unknown) {
        const detail = (err as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail;
        const msg = typeof detail === "string" ? detail : "Nieznany błąd";
        errors.push(`${file.name}: ${msg}`);
      }
    }

    setUploading(false);

    if (allCreated.length > 0 || allSkipped.length > 0) {
      setUploadAllResult({ created: allCreated, skipped: allSkipped, total_subfunds: totalSubfunds, parser_detected: "" });
      toast.success(
        `Załadowano ${allCreated.length} subfunduszy${allSkipped.length > 0 ? `, pominięto ${allSkipped.length}` : ""}`
      );
    }
    if (errors.length > 0) {
      const msg = errors.join("; ");
      setResult({ success: false, message: msg });
      toast.error("Błędy: " + errors[0] + (errors.length > 1 ? ` (+${errors.length - 1})` : ""));
    }
  }

  async function handleUpload(e: React.FormEvent) {
    e.preventDefault();
    if (!subfundId) {
      toast.error("Wybierz subfundusz");
      return;
    }
    if (files.length === 0) {
      toast.error("Wybierz plik");
      return;
    }
    const file = files[0];

    const formData = new FormData();
    formData.append("file", file);
    if (snapshotDate) formData.append("snapshot_date", snapshotDate);
    if (subfundName) formData.append("subfund_name", subfundName);
    formData.append("use_ai", String(useAI));

    setUploading(true);
    setResult(null);
    try {
      const snapshot = await snapshotsApi.upload(subfundId, formData);
      setResult({
        success: true,
        message: `Zapisano ${snapshot.positions.length} pozycji na dzień ${snapshot.snapshot_date}`,
      });
      toast.success("Plik przetworzony pomyślnie");
      setTimeout(() => router.push(`/subfunds/${subfundId}`), 1500);
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail;
      if (
        detail &&
        typeof detail === "object" &&
        "subfunds" in detail &&
        Array.isArray((detail as { subfunds: string[] }).subfunds)
      ) {
        const d = detail as { message: string; subfunds: string[] };
        setPreview({ parser_detected: null, is_multi_fund: true, subfunds: d.subfunds, filename: file.name });
        setSubfundName(d.subfunds[0] ?? "");
        setUploadAllMode(true);
        setResult({ success: false, message: "Wykryto plik multi-funduszowy. Wybierz tryb uploadu." });
        toast.error("Wykryto plik multi-funduszowy");
      } else {
        const msg = typeof detail === "string" ? detail : "Nieznany błąd";
        setResult({ success: false, message: msg });
        toast.error("Błąd: " + msg);
      }
    } finally {
      setUploading(false);
    }
  }

  const isMultiFund = files.length === 1 && preview?.is_multi_fund && (preview.subfunds.length ?? 0) > 0;

  return (
    <div className="max-w-2xl space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Załaduj plik</h1>
        <p className="text-muted-foreground text-sm mt-1">
          Załaduj miesięczny raport portfela funduszu w formacie .xlsx, .xls lub .pdf
        </p>
      </div>

      <form
        onSubmit={uploadAllMode ? (e) => { e.preventDefault(); handleUploadAll(); } : handleUpload}
        className="space-y-5"
      >
        {/* TFI select — zawsze widoczny, wymagany */}
        <div>
          <label className="block text-sm font-medium mb-1">TFI *</label>
          <select
            value={tfiId}
            onChange={(e) => {
              setTfiId(e.target.value);
              // Wybranie TFI = tryb upload-all (o ile nie jest wybrany konkretny subfundusz)
              if (e.target.value && !fundId) setUploadAllMode(true);
            }}
            required
            className="w-full border rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary bg-background"
          >
            <option value="">-- wybierz TFI --</option>
            {(tfiList ?? []).map((t: TFI) => (
              <option key={t.id} value={t.id}>
                {t.name}
              </option>
            ))}
          </select>
          {tfiList && tfiList.length === 0 && (
            <p className="mt-1 text-xs text-muted-foreground">
              Brak TFI — <a href="/tfi" className="underline">dodaj najpierw TFI</a>
            </p>
          )}
        </div>

        {/* Fundusz — opcjonalny, filtrowany po TFI */}
        <div>
          <label className="block text-sm font-medium mb-1">
            Fundusz
            <span className="text-muted-foreground font-normal ml-1">(opcjonalnie)</span>
          </label>
          <select
            value={fundId}
            onChange={(e) => {
              const selectedId = e.target.value;
              setFundId(selectedId);
              // Auto-uzupełnij TFI na podstawie wybranego funduszu
              if (selectedId) {
                const f = (fundsDataList ?? []).find((f: Fund) => f.id === selectedId);
                if (f?.tfi_id) setTfiId(f.tfi_id);
              }
            }}
            className="w-full border rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary bg-background"
          >
            <option value="">-- wybierz fundusz --</option>
            {(fundsDataList ?? []).map((f: Fund) => (
              <option key={f.id} value={f.id}>
                {f.name}
              </option>
            ))}
          </select>
          {tfiId && fundsDataList && fundsDataList.length === 0 && (
            <p className="mt-1 text-xs text-muted-foreground">
              Brak funduszy dla tego TFI — <a href="/funds" className="underline">dodaj fundusz</a>
            </p>
          )}
        </div>

        {/* Subfundusz — opcjonalny; gdy wybrany → tryb single-fund */}
        <div>
          <label className="block text-sm font-medium mb-1">
            Subfundusz
            <span className="text-muted-foreground font-normal ml-1">(opcjonalnie — domyślnie załaduje wszystkie)</span>
          </label>
          <select
            value={subfundId}
            onChange={(e) => {
              const selectedId = e.target.value;
              setSubfundId(selectedId);
              setPreview(null);
              setSubfundName("");
              setUploadAllMode(!selectedId);
              // Auto-uzupełnij Fundusz i TFI na podstawie wybranego subfunduszu
              if (selectedId) {
                const sf = (funds ?? []).find((f) => f.id === selectedId);
                if (sf?.fund_id) setFundId(sf.fund_id);
                if (sf?.tfi_id) setTfiId(sf.tfi_id);
              }
              if (files.length === 1 && selectedId) handlePreview(files[0], selectedId);
            }}
            className="w-full border rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary bg-background"
          >
            <option value="">-- załaduj wszystkie subfundusze --</option>
            {funds?.map((f) => (
              <option key={f.id} value={f.id}>
                {f.name}
              </option>
            ))}
          </select>
        </div>

        {/* Dropzone */}
        <div>
          <label className="block text-sm font-medium mb-1">Plik Excel / PDF *</label>
          <div
            {...getRootProps()}
            className={cn(
              "border-2 border-dashed rounded-lg p-4 text-center cursor-pointer transition-colors",
              isDragActive
                ? "border-primary bg-primary/5"
                : "border-muted-foreground/30 hover:border-primary/50"
            )}
          >
            <input {...getInputProps()} />
            {files.length > 0 ? (
              <div className="space-y-2" onClick={(e) => e.stopPropagation()}>
                {files.map((f, i) => (
                  <div key={i} className="flex items-center gap-3 rounded-md bg-muted/50 px-3 py-2 text-left">
                    {f.name.endsWith(".pdf") ? (
                      <Upload className="h-5 w-5 shrink-0 text-orange-500" />
                    ) : (
                      <FileSpreadsheet className="h-5 w-5 shrink-0 text-green-500" />
                    )}
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium truncate">{f.name}</p>
                      <p className="text-xs text-muted-foreground">
                        {(f.size / 1024).toFixed(1)} KB
                        {i === 0 && preview?.parser_detected && (
                          <span className="ml-2 text-primary">
                            · parser: {preview.parser_detected.replace(/_/g, " ")}
                          </span>
                        )}
                      </p>
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
                  Upuść kolejne pliki lub <span className="text-primary">kliknij</span>, aby dodać więcej
                </p>
              </div>
            ) : (
              <div className="py-4">
                <Upload className="h-10 w-10 text-muted-foreground mx-auto mb-2" />
                <p className="text-sm text-muted-foreground">
                  Przeciągnij pliki lub <span className="text-primary">kliknij</span>
                </p>
                <p className="text-xs text-muted-foreground mt-1">.xlsx, .xls, .pdf — max 20 MB · możesz wybrać wiele plików</p>
              </div>
            )}
          </div>

          {previewing && (
            <p className="mt-2 text-xs text-muted-foreground">Wykrywam format pliku...</p>
          )}
        </div>

        {/* Tryb uploadu: jeden lub wszystkie subfundusze */}
        {isMultiFund && (
          <div className="rounded-lg border bg-muted/30 p-4 space-y-3">
            <p className="text-sm font-medium flex items-center gap-2">
              <Layers className="h-4 w-4 text-primary" />
              Plik zawiera{" "}
              <span className="text-primary font-bold">{preview.subfunds.length}</span>{" "}
              subfunduszy — wybierz tryb uploadu
            </p>
            <div className="grid grid-cols-2 gap-3">
              <button
                type="button"
                onClick={() => setUploadAllMode(true)}
                className={cn(
                  "rounded-md border p-3 text-left text-sm transition-colors",
                  uploadAllMode
                    ? "border-primary bg-primary/5 text-primary"
                    : "border-muted-foreground/30 hover:border-primary/50"
                )}
              >
                <p className="font-medium">Wszystkie subfundusze</p>
                <p className="text-xs text-muted-foreground mt-0.5">
                  Załaduj wszystkie {preview.subfunds.length} naraz — każdy jako osobny fundusz
                </p>
              </button>
              <button
                type="button"
                onClick={() => setUploadAllMode(false)}
                className={cn(
                  "rounded-md border p-3 text-left text-sm transition-colors",
                  !uploadAllMode
                    ? "border-primary bg-primary/5 text-primary"
                    : "border-muted-foreground/30 hover:border-primary/50"
                )}
              >
                <p className="font-medium">Jeden subfundusz</p>
                <p className="text-xs text-muted-foreground mt-0.5">
                  Wybierz konkretny subfundusz i fundusz docelowy
                </p>
              </button>
            </div>
          </div>
        )}

        {/* Wybór subfunduszu — tylko tryb "jeden" */}
        {isMultiFund && !uploadAllMode && (
          <div>
            <label className="block text-sm font-medium mb-1">Subfundusz *</label>
            <select
              value={subfundName}
              onChange={(e) => setSubfundName(e.target.value)}
              required
              className="w-full border rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary bg-background"
            >
              {preview.subfunds.map((name) => (
                <option key={name} value={name}>
                  {name}
                </option>
              ))}
            </select>
          </div>
        )}

        {/* Optional date */}
        <div>
          <label className="block text-sm font-medium mb-1">
            Data snapshotu{" "}
            <span className="text-muted-foreground font-normal">(opcjonalne — wykryjemy z nazwy pliku)</span>
          </label>
          <input
            type="date"
            value={snapshotDate}
            onChange={(e) => setSnapshotDate(e.target.value)}
            className="w-full border rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary bg-background"
          />
        </div>

        {/* AI toggle — tylko tryb jeden */}
        {!uploadAllMode && (
          <div className="flex items-center gap-3">
            <input
              type="checkbox"
              id="use-ai"
              checked={useAI}
              onChange={(e) => setUseAI(e.target.checked)}
              className="accent-primary"
            />
            <label htmlFor="use-ai" className="text-sm">
              Użyj AI parsera (GPT-4o mini) — dla niestandardowych formatów
            </label>
          </div>
        )}

        {/* Force override — tylko tryb upload-all */}
        {uploadAllMode && (
          <div className="flex items-center gap-3">
            <input
              type="checkbox"
              id="force-upload"
              checked={forceUpload}
              onChange={(e) => setForceUpload(e.target.checked)}
              className="accent-primary"
            />
            <label htmlFor="force-upload" className="text-sm">
              Nadpisz istniejące snapshoty (usuń stare dane i zaimportuj ponownie)
            </label>
          </div>
        )}

        {/* Result */}
        {result && (
          <div
            className={cn(
              "flex items-start gap-3 p-4 rounded-lg text-sm",
              result.success ? "bg-green-50 text-green-700" : "bg-red-50 text-red-700"
            )}
          >
            {result.success ? (
              <CheckCircle2 className="h-4 w-4 mt-0.5 shrink-0" />
            ) : (
              <AlertCircle className="h-4 w-4 mt-0.5 shrink-0" />
            )}
            {result.message}
          </div>
        )}

        <button
          type="submit"
          disabled={uploading}
          className="w-full flex items-center justify-center gap-2 px-4 py-3 bg-primary text-primary-foreground rounded-md font-medium hover:opacity-90 disabled:opacity-50"
        >
          {uploading ? (
            <>
              <span className="animate-spin h-4 w-4 border-2 border-white border-t-transparent rounded-full" />
              Przetwarzanie...
            </>
          ) : uploadAllMode ? (
            <>
              <Layers className="h-4 w-4" />
              Załaduj {files.length > 1 ? `${files.length} pliki / wszystkie subfundusze` : "wszystkie subfundusze"}
            </>
          ) : (
            <>
              <Upload className="h-4 w-4" />
              Załaduj i przetwórz
            </>
          )}
        </button>
      </form>

      {/* Wyniki bulk uploadu */}
      {uploadAllResult && (
        <div className="space-y-4">
          <div className="rounded-lg border bg-green-50 p-4">
            <p className="font-semibold text-green-800 flex items-center gap-2">
              <CheckCircle2 className="h-5 w-5" />
              Załadowano {uploadAllResult.created.length} z {uploadAllResult.total_subfunds} subfunduszy
              {uploadAllResult.skipped.length > 0 && ` · pominięto ${uploadAllResult.skipped.length}`}
            </p>
          </div>

          {uploadAllResult.created.length > 0 && (
            <div className="rounded-lg border divide-y">
              {uploadAllResult.created.map((s) => (
                <div key={s.snapshot_id} className="flex items-center justify-between px-4 py-3">
                  <div>
                    <p className="text-sm font-medium">{s.fund_name}</p>
                    <p className="text-xs text-muted-foreground">
                      {s.snapshot_date} · {s.position_count} pozycji
                      {s.fund_created && <span className="ml-2 text-primary">· nowy fundusz</span>}
                    </p>
                  </div>
                  <Link
                    href={`/funds/${s.fund_id}`}
                    className="flex items-center gap-1 text-xs text-primary hover:underline"
                  >
                    Otwórz <ArrowRight className="h-3 w-3" />
                  </Link>
                </div>
              ))}
            </div>
          )}

          {uploadAllResult.skipped.length > 0 && (
            <details className="rounded-lg border">
              <summary className="px-4 py-3 text-sm text-muted-foreground cursor-pointer">
                Pominięte subfundusze ({uploadAllResult.skipped.length})
              </summary>
              <div className="divide-y">
                {uploadAllResult.skipped.map((s, i) => (
                  <div key={i} className="px-4 py-2 text-sm">
                    <span className="font-medium">{s.fund_name}</span>
                    <span className="text-muted-foreground ml-2">— {s.reason}</span>
                  </div>
                ))}
              </div>
            </details>
          )}
        </div>
      )}
    </div>
  );
}

export default function UploadPage() {
  return (
    <Suspense fallback={<div className="p-6 text-muted-foreground text-sm">Ładowanie...</div>}>
      <UploadForm />
    </Suspense>
  );
}
