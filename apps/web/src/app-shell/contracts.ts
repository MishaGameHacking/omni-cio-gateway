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

export type AppRoutePath = (typeof appRoutes)[number]["path"];
export type IdentityProvider = "telegram" | "vk_id";

export interface WebSessionView {
  authenticated: boolean;
  user_label?: string;
  tenant_label?: string;
  expires_at?: string;
}

export interface ProviderView {
  provider: IdentityProvider;
  enabled: boolean;
  reason?: "NOT_CONFIGURED" | "PRIVATE_ACCEPTANCE_ONLY";
}

export interface PrivateAcceptanceStatusView {
  enabled: boolean;
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

export function isKnownRoute(pathname: string): pathname is AppRoutePath {
  return appRoutes.some((route) => route.path === pathname);
}
