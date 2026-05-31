import axios from "axios";

export const api = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000",
});

export function setAuthToken(token: string | null) {
  if (token) {
    api.defaults.headers.common["Authorization"] = `Bearer ${token}`;
  } else {
    delete api.defaults.headers.common["Authorization"];
  }
}

// Redirect to /login on 401 (only in browser, not on /login page itself)
api.interceptors.response.use(
  (res) => res,
  (error) => {
    if (
      error.response?.status === 401 &&
      typeof window !== "undefined" &&
      !window.location.pathname.startsWith("/login")
    ) {
      const authEnabled = process.env.NEXT_PUBLIC_AUTH_ENABLED === "true";
      if (authEnabled) {
        window.location.href = "/login";
      }
    }
    return Promise.reject(error);
  }
);

// --- Auth API ---

export const authApi = {
  login: (email: string, password: string) =>
    api.post<{ access_token: string }>("/api/v1/auth/login", { email, password }).then((r) => r.data),
  register: (email: string, password: string) =>
    api.post<{ access_token: string }>("/api/v1/auth/register", { email, password }).then((r) => r.data),
  me: () =>
    api.get<{ id: string; email: string }>("/api/v1/auth/me").then((r) => r.data),
};

// --- Types ---

export interface Subfund {
  id: string;
  name: string;
  ticker: string | null;
  description: string | null;
  tfi_id: string | null;
  fund_id: string | null;
  created_at: string;
}

export interface SnapshotSummary {
  id: string;
  fund_id: string;
  snapshot_date: string;
  total_value: number | null;
  currency: string;
  upload_filename: string | null;
  position_count: number;
}

export interface Position {
  id: string;
  company_name: string;
  ticker: string | null;
  isin: string | null;
  shares: number | null;
  value: number | null;
  weight_pct: number | null;
  currency: string;
  asset_type: string | null;
}

export interface Snapshot extends SnapshotSummary {
  positions: Position[];
}

export interface PositionChange {
  company_name: string;
  ticker: string | null;
  isin: string | null;
  change_type: "new" | "closed" | "increased" | "decreased" | "unchanged";
  old_weight_pct: number | null;
  new_weight_pct: number | null;
  weight_change_pct: number | null;
  old_value: number | null;
  new_value: number | null;
  old_shares: number | null;
  new_shares: number | null;
}

export interface PortfolioDiff {
  fund_id: string;
  from_date: string;
  to_date: string;
  from_snapshot_id: string;
  to_snapshot_id: string;
  changes: PositionChange[];
}

export interface PortfolioPosition {
  id: string;
  company_name: string;
  isin: string | null;
  asset_type: string | null;
  weight_pct: number | null;
  value: number | null;
  shares: number | null;
  currency_fund: string;
  snapshot_date: string | null;
}

export interface Alert {
  id: string;
  fund_id: string;
  alert_type: string;
  company_name: string | null;
  ticker: string | null;
  change_pct: number | null;
  old_weight: number | null;
  new_weight: number | null;
  message: string;
  is_read: boolean;
  created_at: string;
}

export interface UploadedSubfund {
  fund_id: string;
  fund_name: string;
  snapshot_id: string;
  snapshot_date: string;
  position_count: number;
  fund_created: boolean;
}

export interface SkippedSubfund {
  fund_name: string;
  reason: string;
}

export interface UploadAllResult {
  parser_detected: string;
  total_subfunds: number;
  created: UploadedSubfund[];
  skipped: SkippedSubfund[];
}

// --- API calls ---

export interface Fund {
  id: string;
  name: string;
  tfi_id: string | null;
  created_at: string;
  subfund_count: number;
}

export interface AssetBreakdownItem {
  asset_type: string;
  weight_pct: number;
}

export interface SubfundDistributionItem {
  asset_type: string;
  subfund_count: number;
  total_subfunds: number;
}

export interface TurnoverPeriodOut {
  date_from: string;
  date_to: string;
  bought: number;
  sold: number;
  average_assets: number;
  ptr: number | null;
  currency: string; // "PLN" lub "%"
}

export const fundsApi = {
  list: (tfi_id?: string) =>
    api
      .get<Fund[]>("/api/v1/funds/", { params: tfi_id ? { tfi_id } : undefined })
      .then((r) => r.data),
  get: (id: string) => api.get<Fund>(`/api/v1/funds/${id}`).then((r) => r.data),
  create: (name: string, tfi_id?: string) =>
    api.post<Fund>("/api/v1/funds/", { name, tfi_id: tfi_id ?? null }).then((r) => r.data),
  delete: (id: string) => api.delete(`/api/v1/funds/${id}`),
  assetBreakdown: (id: string) =>
    api.get<AssetBreakdownItem[]>(`/api/v1/funds/${id}/asset-breakdown`).then((r) => r.data),
  subfundDistribution: (id: string, threshold = 10) =>
    api.get<SubfundDistributionItem[]>(`/api/v1/funds/${id}/subfund-distribution`, { params: { threshold } }).then((r) => r.data),
};

export interface TFI {
  id: string;
  name: string;
  created_at: string;
  subfund_count: number;
}

export const tfiApi = {
  list: () => api.get<TFI[]>("/api/v1/tfi/").then((r) => r.data),
  get: (id: string) => api.get<TFI>(`/api/v1/tfi/${id}`).then((r) => r.data),
  create: (name: string) => api.post<TFI>("/api/v1/tfi/", { name }).then((r) => r.data),
  delete: (id: string) => api.delete(`/api/v1/tfi/${id}`),
  assetBreakdown: (id: string) =>
    api.get<AssetBreakdownItem[]>(`/api/v1/tfi/${id}/asset-breakdown`).then((r) => r.data),
  subfundDistribution: (id: string, threshold = 10) =>
    api.get<SubfundDistributionItem[]>(`/api/v1/tfi/${id}/subfund-distribution`, { params: { threshold } }).then((r) => r.data),
};

export const subfundsApi = {
  list: (fundId?: string) =>
    api.get<Subfund[]>("/api/v1/subfunds/", { params: fundId ? { fund_id: fundId } : {} }).then((r) => r.data),
  create: (data: { name: string; ticker?: string; description?: string }) =>
    api.post<Subfund>("/api/v1/subfunds/", data).then((r) => r.data),
  get: (id: string) => api.get<Subfund>(`/api/v1/subfunds/${id}`).then((r) => r.data),
  delete: (id: string) => api.delete(`/api/v1/subfunds/${id}`),
  portfolioDates: (id: string) =>
    api.get<string[]>(`/api/v1/subfunds/${id}/portfolio/dates`).then((r) => r.data),
  portfolio: (id: string, date?: string) =>
    api.get<PortfolioPosition[]>(`/api/v1/subfunds/${id}/portfolio`, { params: date ? { snapshot_date: date } : {} }).then((r) => r.data),
  turnover: (id: string) =>
    api.get<TurnoverPeriodOut[]>(`/api/v1/subfunds/${id}/turnover`).then((r) => r.data),
};

export const snapshotsApi = {
  list: (fundId: string) =>
    api.get<SnapshotSummary[]>(`/api/v1/funds/${fundId}/snapshots/`).then((r) => r.data),
  get: (fundId: string, snapshotId: string) =>
    api.get<Snapshot>(`/api/v1/funds/${fundId}/snapshots/${snapshotId}`).then((r) => r.data),
  previewSubfunds: (fundId: string, file: File) => {
    const fd = new FormData();
    fd.append("file", file);
    return api
      .post<{ parser_detected: string | null; is_multi_fund: boolean; subfunds: string[]; filename: string }>(
        `/api/v1/funds/${fundId}/snapshots/preview-subfunds`,
        fd
      )
      .then((r) => r.data);
  },
  upload: (fundId: string, formData: FormData) =>
    api
      .post<Snapshot>(`/api/v1/funds/${fundId}/snapshots/upload`, formData)
      .then((r) => r.data),
  uploadAll: (formData: FormData) =>
    api
      .post<UploadAllResult>("/api/v1/snapshots/upload-all", formData)
      .then((r) => r.data),
  diff: (fundId: string, fromId: string, toId: string) =>
    api
      .get<PortfolioDiff>(`/api/v1/funds/${fundId}/snapshots/diff`, {
        params: { from_id: fromId, to_id: toId },
      })
      .then((r) => r.data),
  delete: (fundId: string, snapshotId: string) =>
    api.delete(`/api/v1/funds/${fundId}/snapshots/${snapshotId}`),
};

export const alertsApi = {
  list: (unreadOnly?: boolean) =>
    api
      .get<Alert[]>("/api/v1/alerts/", { params: { unread_only: unreadOnly } })
      .then((r) => r.data),
  markRead: (ids: string[]) =>
    api.post("/api/v1/alerts/mark-read", { ids }).then((r) => r.data),
  markAllRead: () => api.post("/api/v1/alerts/mark-all-read").then((r) => r.data),
};

// --- Alert Rules ---

export interface AlertRule {
  id: string;
  name: string;
  is_active: boolean;
  track_new: boolean;
  track_closed: boolean;
  track_increases: boolean;
  track_decreases: boolean;
  min_weight_pp: number;
  min_rel_pct: number;
  fund_id: string | null;
  created_at: string;
}

export interface AlertRuleCreate {
  name: string;
  is_active?: boolean;
  track_new?: boolean;
  track_closed?: boolean;
  track_increases?: boolean;
  track_decreases?: boolean;
  min_weight_pp?: number;
  min_rel_pct?: number;
  fund_id?: string | null;
}

export const alertRulesApi = {
  list: () => api.get<AlertRule[]>("/api/v1/alert-rules/").then((r) => r.data),
  create: (data: AlertRuleCreate) =>
    api.post<AlertRule>("/api/v1/alert-rules/", data).then((r) => r.data),
  update: (id: string, data: Partial<AlertRuleCreate>) =>
    api.patch<AlertRule>(`/api/v1/alert-rules/${id}`, data).then((r) => r.data),
  delete: (id: string) => api.delete(`/api/v1/alert-rules/${id}`),
};

// --- Typy: wyszukiwanie po spółce ---

export interface HoldingPerFund {
  fund_id: string;
  fund_name: string;
  snapshot_id: string;
  snapshot_date: string;
  shares: number | null;
  value: number | null;
  weight_pct: number | null;
  currency: string;
}

export interface CompanyHoldings {
  company_name: string;
  isin: string | null;
  ticker: string | null;
  total_shares: number | null;
  total_value: number | null;
  currency: string;
  fund_count: number;
  funds: HoldingPerFund[];
}

export const positionsApi = {
  search: (q: string) =>
    api.get<CompanyHoldings[]>("/api/v1/positions/search", { params: { q } }).then((r) => r.data),
  companyHistory: (params: { isin?: string; q?: string }) =>
    api
      .get<HoldingPerFund[]>("/api/v1/positions/company-history", { params })
      .then((r) => r.data),
  top: (limit = 50) =>
    api.get<TopAsset[]>("/api/v1/positions/top", { params: { limit } }).then((r) => r.data),
};

export interface TopAsset {
  rank: number;
  company_name: string;
  isin: string | null;
  ticker: string | null;
  total_value: number;
  total_shares: number | null;
  fund_count: number;
  currency: string;
}

// --- Stats ---

export interface SnapshotRef {
  fund_id: string;
  fund_name: string;
  snapshot_id: string;
  snapshot_date: string;
  upload_filename: string | null;
}

export interface TopChange {
  fund_name: string;
  fund_id: string;
  company_name: string | null;
  ticker: string | null;
  alert_type: string;
  old_weight: number | null;
  new_weight: number | null;
  change_pct: number | null;
  message: string;
  created_at: string;
}

export interface DashboardStats {
  fund_count: number;
  snapshot_count: number;
  unread_alert_count: number;
  latest_snapshot: (SnapshotRef & { position_count: number }) | null;
  recent_snapshots: SnapshotRef[];
  top_changes: TopChange[];
}

export const statsApi = {
  get: () => api.get<DashboardStats>("/api/v1/stats/").then((r) => r.data),
};

// --- Rankings ---

export interface FundActivityRank {
  fund_id: string;
  fund_name: string;
  snapshot_count: number;
  latest_snapshot_date: string | null;
  total_alerts: number;
  buy_alerts: number;
  sell_alerts: number;
}

export interface FundCorrelation {
  fund_a_id: string;
  fund_a_name: string;
  fund_b_id: string;
  fund_b_name: string;
  shared_positions: number;
  total_positions_a: number;
  total_positions_b: number;
  jaccard_similarity: number;
}

export interface CommonHolder {
  company_name: string;
  isin: string | null;
  fund_count: number;
  funds: string[];
}

export const rankingsApi = {
  activity: () =>
    api.get<FundActivityRank[]>("/api/v1/rankings/activity").then((r) => r.data),
  correlations: (minShared = 3) =>
    api
      .get<FundCorrelation[]>("/api/v1/rankings/correlations", {
        params: { min_shared: minShared },
      })
      .then((r) => r.data),
  commonStocks: (minFunds = 2) =>
    api
      .get<CommonHolder[]>("/api/v1/rankings/common-stocks", {
        params: { min_funds: minFunds },
      })
      .then((r) => r.data),
};

// --- Movers ---

export interface TopMover {
  company_name: string;
  ticker: string | null;
  asset_type: string;
  fund_count: number;
  alert_count: number;
  total_weight_pp: number | null;
  total_shares: number | null;
  funds: string[];
  latest_date: string | null;
}

export interface TopMoversResult {
  buys: TopMover[];
  sells: TopMover[];
  days: number | null;
}

export const moversApi = {
  top: (days: number | null = 90, limit = 15) =>
    api
      .get<TopMoversResult>("/api/v1/movers/top", {
        params: { days: days ?? undefined, limit },
      })
      .then((r) => r.data),
};

// --- Upload history ---

export interface SnapshotEntry {
  snapshot_id: string;
  snapshot_date: string;
  position_count: number;
  total_value: number | null;
  currency: string;
  upload_filename: string | null;
  uploaded_at: string;
}

export interface FundHistoryEntry {
  subfund_id: string;
  subfund_name: string;
  fund_id: string | null;
  fund_name: string | null;
  snapshot_count: number;
  latest_date: string | null;
  snapshots: SnapshotEntry[];
}

export interface TFIHistoryEntry {
  tfi_id: string | null;
  tfi_name: string | null;
  fund_count: number;
  upload_count: number;  // liczba wgranych plików (migawek portfela)
  funds: FundHistoryEntry[];
}

export const uploadHistoryApi = {
  get: () =>
    api.get<TFIHistoryEntry[]>("/api/v1/upload-history/").then((r) => r.data),
};

// --- Articles (Aktualności) ---

export interface Article {
  id: string;
  title: string;
  content: string;
  author: string | null;
  published_at: string;
  created_at: string;
}

export const articlesApi = {
  list: (limit = 20) =>
    api.get<Article[]>("/api/v1/articles/", { params: { limit } }).then((r) => r.data),
  get: (id: string) =>
    api.get<Article>(`/api/v1/articles/${id}`).then((r) => r.data),
  create: (title: string, content: string) =>
    api.post<Article>("/api/v1/articles/", { title, content }).then((r) => r.data),
  delete: (id: string) =>
    api.delete(`/api/v1/articles/${id}`),
};
