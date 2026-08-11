import type {
  BrokerConnectionView,
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
