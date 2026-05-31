import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatCurrency(value: number | null | undefined, currency = "PLN"): string {
  if (value == null) return "—";
  const formatted = new Intl.NumberFormat("pl-PL", {
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(value);
  // Use Intl currency formatting only for standard 3-letter ISO codes
  if (/^[A-Z]{3}$/.test(currency ?? "")) {
    try {
      return new Intl.NumberFormat("pl-PL", {
        style: "currency",
        currency,
        minimumFractionDigits: 0,
        maximumFractionDigits: 0,
      }).format(value);
    } catch {
      // fallthrough
    }
  }
  // Composite or non-standard currency (e.g. "SEK/PLN") — append as text
  return `${formatted} ${currency ?? ""}`.trim();
}

export function formatPct(value: number | null | undefined, decimals = 2): string {
  if (value == null) return "—";
  return `${value.toFixed(decimals)}%`;
}

export function formatChangeType(type: string): string {
  const map: Record<string, string> = {
    new: "Nowa",
    closed: "Zamknięta",
    increased: "Zwiększona",
    decreased: "Zmniejszona",
    unchanged: "Bez zmian",
  };
  return map[type] ?? type;
}
