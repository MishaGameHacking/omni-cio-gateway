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

export function isKnownRoute(pathname: string): pathname is AppRoutePath {
  return appRoutes.some((route) => route.path === pathname);
}
