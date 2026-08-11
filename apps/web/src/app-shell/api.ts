import type {
  BrokerConnectionView,
  BrokerProvisioningPreviewView,
  HealthView,
  ProviderView,
  WebSessionView,
} from "./contracts";

const JSON_HEADERS = { "Content-Type": "application/json" } as const;

async function requestJson<T>(input: string, init?: RequestInit): Promise<T> {
  const response = await fetch(input, {
    credentials: "same-origin",
    cache: "no-store",
    ...init,
  });
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

export function readHealth(): Promise<HealthView> {
  return requestJson<HealthView>("/api/v10/web/health");
}

export function readBrokerConnections(): Promise<BrokerConnectionView[]> {
  return requestJson<BrokerConnectionView[]>("/api/v10/web/broker-connections");
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

export async function logoutCurrentSession(): Promise<void> {
  await requestJson<{ ok: true }>("/api/v10/web/session/logout", {
    method: "POST",
    headers: JSON_HEADERS,
    body: "{}",
  });
}

export async function revokeAllSessions(): Promise<void> {
  await requestJson<{ ok: true }>("/api/v10/web/session/revoke-all", {
    method: "POST",
    headers: JSON_HEADERS,
    body: "{}",
  });
}

export function providerLoginUrl(provider: "telegram" | "vk_id"): string {
  return `/api/v10/web/auth/${provider}/start`;
}
