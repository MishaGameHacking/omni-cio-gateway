export const appRoutes = [
  { path: "/", label: "Обзор" },
  { path: "/portfolio", label: "Портфель" },
  { path: "/assets", label: "Активы" },
  { path: "/watchtower", label: "Watchtower" },
  { path: "/research", label: "Research" },
  { path: "/risks", label: "Риски" },
  { path: "/decisions", label: "Решения" },
  { path: "/plans", label: "Планы" },
  { path: "/execution", label: "Исполнение" },
  { path: "/journal", label: "Журнал" },
  { path: "/system", label: "Система" },
  { path: "/settings", label: "Настройки" },
] as const;

export const publicRoutes = [
  { path: "/privacy", label: "Политика обработки персональных данных" },
] as const;

export type AppRoutePath = (typeof appRoutes)[number]["path"];
export type PublicRoutePath = (typeof publicRoutes)[number]["path"];
export type ShellRoutePath = AppRoutePath | PublicRoutePath;
export type IdentityProvider = "telegram";

export interface WebSessionView {
  authenticated: boolean;
  user_label?: string;
  tenant_label?: string;
  expires_at?: string;
}

export interface ProviderView {
  provider: IdentityProvider;
  enabled: boolean;
  reason?:
    | "NOT_CONFIGURED"
    | "PRIVATE_ACCEPTANCE_ONLY"
    | "PUBLIC_MULTI_USER_DISABLED"
    | "PROVIDER_ACTIVATION_DISABLED";
}

export interface PrivateAcceptanceStatusView {
  enabled: boolean;
}

export interface PreviewModeView {
  enabled: boolean;
  synthetic: boolean;
  broker_credentials_enabled: boolean;
  registration_enabled: boolean;
  label: string;
}

export interface HealthView {
  state: "READY" | "PARTIAL" | "STALE" | "DEGRADED" | "OFFLINE";
  freshness: "FRESH" | "STALE" | "UNKNOWN";
  checked_at: string;
}

export interface BrokerAccountBindingView {
  masked_label: string;
  access_level: "READ_ONLY";
}

export interface BrokerConnectionView {
  connection_id: string;
  provider: "t_invest";
  role: "read";
  state: "ACTIVE" | "REVOKED" | "ERROR";
  accounts: BrokerAccountBindingView[];
  last_verified_at?: string;
}

export interface BrokerProvisioningAccountView {
  selection_id: string;
  masked_label: string;
  access_level: "READ_ONLY";
}

export interface BrokerProvisioningPreviewView {
  challenge_id: string;
  expires_at: string;
  accounts: BrokerProvisioningAccountView[];
}

export interface Wp15LiveAcceptanceStatusView {
  enabled: boolean;
}

export interface Wp15LiveSampleView {
  label: string;
  quantity: string;
  unit_price: string;
  market_value: string;
  currency: string;
}

export interface Wp15LiveAcceptanceView {
  challenge_id: string;
  expires_at: string;
  masked_account: string;
  access_level: "READ_ONLY";
  portfolio_total: string;
  portfolio_currency: string;
  sample: Wp15LiveSampleView;
  freshness_state: "FRESH";
  retrieved_at: string;
  evaluated_at: string;
  age_seconds: string;
  normalized_position_count: number;
}

export interface Wp15LiveConfirmation {
  intended_account_confirmed: boolean;
  portfolio_summary_parity: boolean;
  sample_position_quantity_value_parity: boolean;
  freshness_confirmed: boolean;
}

export interface PortfolioMoneyView {
  amount: string;
  currency: string;
  source: string;
  as_of: string;
}

export interface PortfolioMarketQuoteView {
  amount: string;
  quotation_unit: string;
  quotation_semantics: string;
  source: string;
  as_of: string;
  freshness: "fresh" | "stale";
  age_seconds: string;
}

export interface PortfolioPositionView {
  instrument: {
    name: string;
    ticker: string | null;
    type: string;
    currency: string;
    class_code: string | null;
    isin: string | null;
    figi: string | null;
    uid: string | null;
    position_uid: string | null;
    issuer: string | null;
    sector: string | null;
    classification_state: string;
    classification_source: string;
    classification_as_of: string;
  };
  quantity_units: string;
  blocked_units: string;
  broker_unit_price: PortfolioMoneyView | null;
  broker_value: PortfolioMoneyView | null;
  current_market_last_price: PortfolioMarketQuoteView | null;
  current_market_value: PortfolioMoneyView | null;
  market_conversion_state: string;
  weight_within_position_currency_pct: string | null;
}

export interface PortfolioAccountView {
  masked_account: string;
  access: "READ_ONLY";
  connection_state: string;
  retrieved_at: string;
  freshness: { state: "fresh" | "stale"; age_seconds: string; evaluated_at: string };
  completeness: "complete" | "partial" | "unknown";
  broker_position_count: number;
  normalized_position_count: number;
  unresolved_position_count: number;
  portfolio_total: PortfolioMoneyView | null;
  cash: Array<{ currency: string; reported: string; available: string | null; blocked: string | null; source: string; as_of: string }>;
  positions: PortfolioPositionView[];
  concentration: Array<{ currency: string; normalized_position_value: string; top_1_weight_pct: string; top_5_weight_pct: string; basis: string }>;
  warnings: Array<{ code: string; severity: string; message: string }>;
  current_market: { state: string; retrieved_at: string | null; missing_instrument_count: number; stale_instrument_count: number };
}

export interface PortfolioDashboardView {
  schema_version: "1.0.0";
  generated_at: string;
  state: "EMPTY" | "UNAVAILABLE" | "PARTIAL" | "READY";
  connections: Array<{ connection_id: string; provider: string; role: string; state: string; last_verified_at: string | null; account_count: number }>;
  accounts: PortfolioAccountView[];
  warnings: Array<{ code: string; severity: string; message: string }>;
  calculation_policy: {
    decimal_transport: string;
    cross_currency_aggregation: string;
    broker_position_value: string;
    current_market_value: string;
    weights: string;
  };
}

export function isKnownRoute(pathname: string): pathname is AppRoutePath {
  return appRoutes.some((route) => route.path === pathname);
}

export function isPublicRoute(pathname: string): pathname is PublicRoutePath {
  return publicRoutes.some((route) => route.path === pathname);
}
