import type {
  BrokerConnectionView,
  BrokerProvisioningPreviewView,
  HealthView,
  PortfolioDashboardView,
  PreviewModeView,
  ProviderView,
  WebSessionView,
  Wp15LiveAcceptanceStatusView,
  Wp15LiveAcceptanceView,
  Wp15LiveConfirmation,
} from "./contracts";

const JSON_HEADERS = { "Content-Type": "application/json" } as const;
const REMOTE_CSRF_COOKIE = "__Host-omni_v10_csrf";
const REMOTE_CSRF_HEADER = "X-Omni-CSRF";
const SAFE_METHODS = new Set(["GET", "HEAD", "OPTIONS"]);
let remoteCsrfToken: string | null = null;

function readCookie(name: string): string | null {
  const prefix = `${name}=`;
  for (const item of document.cookie.split(";")) {
    const candidate = item.trim();
    if (candidate.startsWith(prefix)) return candidate.slice(prefix.length);
  }
  return null;
}

function requestHeaders(init?: RequestInit): Headers {
  const headers = new Headers(init?.headers);
  const method = (init?.method ?? "GET").toUpperCase();
  if (!SAFE_METHODS.has(method)) {
    const csrf = remoteCsrfToken ?? readCookie(REMOTE_CSRF_COOKIE);
    if (csrf) headers.set(REMOTE_CSRF_HEADER, csrf);
  }
  return headers;
}

async function requestJson<T>(input: string, init?: RequestInit): Promise<T> {
  const response = await fetch(input, {
    credentials: "same-origin",
    cache: "no-store",
    ...init,
    headers: requestHeaders(init),
  });
  if (!response.ok) {
    throw new Error(`WEB_API_${response.status}`);
  }
  const csrf = response.headers.get(REMOTE_CSRF_HEADER);
  if (csrf) remoteCsrfToken = csrf;
  return (await response.json()) as T;
}

export async function readSession(): Promise<WebSessionView> {
  const session = await requestJson<WebSessionView>("/api/v10/web/session");
  if (!session.authenticated) remoteCsrfToken = null;
  return session;
}

export function readProviders(): Promise<ProviderView[]> {
  return requestJson<ProviderView[]>("/api/v10/web/auth/providers");
}

export function readPreviewMode(): Promise<PreviewModeView> {
  return requestJson<PreviewModeView>("/api/v10/web/preview-mode");
}

export function readHealth(): Promise<HealthView> {
  return requestJson<HealthView>("/api/v10/web/health");
}

export function readBrokerConnections(): Promise<BrokerConnectionView[]> {
  return requestJson<BrokerConnectionView[]>("/api/v10/web/broker-connections");
}

export function readPortfolioDashboard(): Promise<PortfolioDashboardView> {
  return requestJson<PortfolioDashboardView>("/api/v10/web/portfolio-dashboard");
}

export function previewBrokerReadConnection(token: string): Promise<BrokerProvisioningPreviewView> {
  return requestJson<BrokerProvisioningPreviewView>("/api/v10/web/broker-connections/preview", {
    method: "POST",
    headers: JSON_HEADERS,
    body: JSON.stringify({ token }),
  });
}

export function commitBrokerReadConnection(challengeId: string, selectedAccounts: string[]): Promise<BrokerConnectionView> {
  return requestJson<BrokerConnectionView>("/api/v10/web/broker-connections/commit", {
    method: "POST",
    headers: JSON_HEADERS,
    body: JSON.stringify({ challenge_id: challengeId, selected_accounts: selectedAccounts }),
  });
}

export async function replaceBrokerReadCredential(connectionId: string, challengeId: string, selectedAccounts: string[]): Promise<void> {
  await requestJson<{ ok: true }>(`/api/v10/web/broker-connections/${encodeURIComponent(connectionId)}/replace`, {
    method: "POST",
    headers: JSON_HEADERS,
    body: JSON.stringify({ challenge_id: challengeId, selected_accounts: selectedAccounts }),
  });
}

export async function revokeBrokerReadConnection(connectionId: string): Promise<void> {
  await requestJson<{ ok: true }>(`/api/v10/web/broker-connections/${encodeURIComponent(connectionId)}`, {
    method: "DELETE",
  });
}

export function readWp15LiveAcceptanceStatus(): Promise<Wp15LiveAcceptanceStatusView> {
  return requestJson<Wp15LiveAcceptanceStatusView>("/api/v10/web/wp15-live-acceptance/status");
}

export function startWp15LiveAcceptance(connectionId: string, accountIndex: number): Promise<Wp15LiveAcceptanceView> {
  return requestJson<Wp15LiveAcceptanceView>("/api/v10/web/wp15-live-acceptance/start", {
    method: "POST",
    headers: JSON_HEADERS,
    body: JSON.stringify({ connection_id: connectionId, account_index: accountIndex }),
  });
}

export async function confirmWp15LiveAcceptance(challengeId: string, confirmation: Wp15LiveConfirmation): Promise<void> {
  await requestJson<{ accepted: true; pending_owner_finalization: true }>("/api/v10/web/wp15-live-acceptance/confirm", {
    method: "POST",
    headers: JSON_HEADERS,
    body: JSON.stringify({ challenge_id: challengeId, ...confirmation }),
  });
}

export async function cancelWp15LiveAcceptance(challengeId: string): Promise<void> {
  await requestJson<{ cancelled: boolean }>("/api/v10/web/wp15-live-acceptance/cancel", {
    method: "POST",
    headers: JSON_HEADERS,
    body: JSON.stringify({ challenge_id: challengeId }),
  });
}

export async function logoutCurrentSession(): Promise<void> {
  await requestJson<{ ok: true }>("/api/v10/web/session/logout", {
    method: "POST",
    headers: JSON_HEADERS,
    body: "{}",
  });
  remoteCsrfToken = null;
}

export async function revokeAllSessions(): Promise<void> {
  await requestJson<{ ok: true }>("/api/v10/web/session/revoke-all", {
    method: "POST",
    headers: JSON_HEADERS,
    body: "{}",
  });
  remoteCsrfToken = null;
}

export function providerLoginPath(provider: "telegram" | "vk_id"): string {
  return `/api/v10/web/auth/${provider}/start`;
}