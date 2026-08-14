import type {
  BrokerConnectionView,
  BrokerProvisioningPreviewView,
  HealthView,
  PortfolioDashboardView,
  PrivateAcceptanceStatusView,
  PrivateRemoteAcceptanceStatusView,
  ProviderView,
  WebSessionView,
  Wp15LiveAcceptanceStatusView,
  Wp15LiveAcceptanceView,
  Wp15LiveConfirmation,
} from "./contracts";

const JSON_HEADERS = { "Content-Type": "application/json" } as const;
const UNSAFE_METHODS = new Set(["POST", "PUT", "PATCH", "DELETE"]);
const CSRF_EXEMPT_PATHS = new Set([
  "/api/v10/web/private-test-login",
  "/api/v10/web/private-remote-login",
]);
let csrfToken: string | null = null;
let csrfEndpointUnavailable = false;

async function loadCsrfToken(): Promise<string | null> {
  if (csrfToken) return csrfToken;
  if (csrfEndpointUnavailable) return null;
  const response = await fetch("/api/v10/web/session/csrf", {
    credentials: "same-origin",
    cache: "no-store",
  });
  if (response.status === 404) {
    csrfEndpointUnavailable = true;
    return null;
  }
  if (!response.ok) throw new Error(`WEB_API_${response.status}`);
  const value = (await response.json()) as { csrf_token?: unknown };
  if (typeof value.csrf_token !== "string" || !/^[0-9a-f]{64}$/.test(value.csrf_token)) {
    throw new Error("WEB_API_CSRF_CONTRACT_INVALID");
  }
  csrfToken = value.csrf_token;
  return csrfToken;
}

function resetCsrfState(): void {
  csrfToken = null;
  csrfEndpointUnavailable = false;
}

async function requestJson<T>(input: string, init?: RequestInit): Promise<T> {
  const method = (init?.method ?? "GET").toUpperCase();
  const headers = new Headers(init?.headers);
  if (UNSAFE_METHODS.has(method) && !CSRF_EXEMPT_PATHS.has(input)) {
    const token = await loadCsrfToken();
    if (token) headers.set("X-Omni-CSRF", token);
  }
  const response = await fetch(input, {
    credentials: "same-origin",
    cache: "no-store",
    ...init,
    headers,
  });
  if (response.status === 401) csrfToken = null;
  if (!response.ok) {
    throw new Error(`WEB_API_${response.status}`);
  }
  return (await response.json()) as T;
}

export function readSession(): Promise<WebSessionView> {
  return requestJson<WebSessionView>("/api/v10/web/session");
}

export function readProviders(): Promise<ProviderView[]> {
  return requestJson<ProviderView[]>("/api/v10/web/auth/providers");
}

export function readPrivateAcceptanceStatus(): Promise<PrivateAcceptanceStatusView> {
  return requestJson<PrivateAcceptanceStatusView>("/api/v10/web/private-test-login/status");
}

export function readPrivateRemoteAcceptanceStatus(): Promise<PrivateRemoteAcceptanceStatusView> {
  return requestJson<PrivateRemoteAcceptanceStatusView>("/api/v10/web/private-remote-login/status");
}

export async function privateTestLogin(): Promise<void> {
  await requestJson<{ ok: true }>("/api/v10/web/private-test-login", {
    method: "POST",
    headers: JSON_HEADERS,
    body: "{}",
  });
  resetCsrfState();
}

export async function privateRemoteLogin(): Promise<void> {
  await requestJson<{ ok: true }>("/api/v10/web/private-remote-login", {
    method: "POST",
    headers: JSON_HEADERS,
    body: "{}",
  });
  resetCsrfState();
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
  try {
    await requestJson<{ ok: true }>("/api/v10/web/session/logout", {
      method: "POST",
      headers: JSON_HEADERS,
      body: "{}",
    });
  } finally {
    resetCsrfState();
  }
}

export async function revokeAllSessions(): Promise<void> {
  try {
    await requestJson<{ ok: true }>("/api/v10/web/session/revoke-all", {
      method: "POST",
      headers: JSON_HEADERS,
      body: "{}",
    });
  } finally {
    resetCsrfState();
  }
}

export function providerLoginUrl(provider: "telegram" | "vk_id"): string {
  return `/api/v10/web/auth/${provider}/start`;
}
