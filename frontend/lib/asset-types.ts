/**
 * Tłumaczenia technicznych/angielskich nazw klas aktywów na polskie.
 * Nazwy, które już są po polsku, pozostają niezmienione (brak wpisu = passthrough).
 */
const ASSET_TYPE_LABELS: Record<string, string> = {
  // ── Goldman Sachs / angielskie kody techniczne ─────────────────────────────
  stock:                       "Akcje",
  fund:                        "Fundusze inwestycyjne",
  etf_foreign:                 "ETF zagraniczne",
  bond_government:             "Obligacje skarbowe",
  bond_corporate:              "Obligacje korporacyjne",
  bond_municipal:              "Obligacje komunalne",
  covered_bond:                "Listy zastawne",
  cash:                        "Środki pieniężne",
  repo:                        "Transakcje repo",
  derivative_futures_index:    "Kontrakty futures na indeksy",
  derivative_futures_equity:   "Kontrakty futures na akcje",
  derivative_futures_bond:     "Kontrakty futures na obligacje",
  derivative_fx:               "Instrumenty walutowe (FX)",
  derivative_swap:             "Swapy",
  futures:                     "Kontrakty futures",
  other:                       "Inne",

  // ── Krótkie kody (różni dostawcy) ─────────────────────────────────────────
  JU:         "Jednostki uczestnictwa",
  TYTUCZ:     "Tytuły uczestnictwa",
  OBLIGKORPO: "Obligacje korporacyjne",
  OBLIGSKARB: "Obligacje skarbowe",
  CERTFINWE:  "Certyfikaty finansowe",
  FUTTOWAR:   "Kontrakty futures na towary",
  BSB:        "Transakcje buy-sell-back",
  SBB:        "Transakcje sell-buy-back",
  ETF:        "ETF",
  FX:         "Instrumenty walutowe (FX)",
  IRS:        "Swapy procentowe (IRS)",
  CDS:        "CDS",
  REIT:       "REIT",

  // ── Polskie nazwy pisane małą literą (normalizacja wielkości) ──────────────
  "akcje zwykłe":         "Akcje zwykłe",
  "akcje uprzywilejowane": "Akcje uprzywilejowane",
  "bony skarbowe":        "Bony skarbowe",
  "kwity depozytowe":     "Kwity depozytowe",
  "listy zastawne":       "Listy zastawne",
  "obligacje gwarantowane": "Obligacje gwarantowane",
  "obligacje korporacyjne": "Obligacje korporacyjne",
  "obligacje samorządowe":  "Obligacje samorządowe",
  "obligacje skarbowe":   "Obligacje skarbowe",
  "tytuły uczestnictwa":  "Tytuły uczestnictwa",
};

/** Zwraca polską nazwę klasy aktywów lub oryginalną wartość, jeśli brak tłumaczenia. */
export function translateAssetType(raw: string): string {
  return ASSET_TYPE_LABELS[raw] ?? raw;
}
