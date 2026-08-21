import { useEffect, useState } from "react";
import { Button, StatePanel, StatusBadge } from "../design-system/components";
import type { OperationalState } from "../design-system/contracts";
import {
  logoutCurrentSession,
  previewLogin,
  privateTestLogin,
  providerLoginUrl,
  readHealth,
  readPreviewMode,
  readPrivateAcceptanceStatus,
  readProviders,
  readSession,
} from "./api";
import type {
  AppRoutePath,
  PreviewModeView,
  ProviderView,
  WebSessionView,
} from "./contracts";
import { appRoutes, isKnownRoute } from "./contracts";
import { RoutePage } from "./pages";

function navigate(path: AppRoutePath) {
  if (window.location.pathname !== path) window.history.pushState({}, "", path);
  window.dispatchEvent(new PopStateEvent("popstate"));
}

function useRoute(): AppRoutePath {
  const initial = isKnownRoute(window.location.pathname) ? window.location.pathname : "/";
  const [route, setRoute] = useState<AppRoutePath>(initial);
  useEffect(() => {
    const onPopState = () => setRoute(isKnownRoute(window.location.pathname) ? window.location.pathname : "/");
    window.addEventListener("popstate", onPopState);
    return () => window.removeEventListener("popstate", onPopState);
  }, []);
  return route;
}

function ProviderButton({ provider }: { provider: ProviderView }) {
  const label = provider.provider === "telegram" ? "Продолжить через Telegram" : "Продолжить через VK ID";
  if (!provider.enabled) {
    return (
      <Button variant="secondary" disabled aria-describedby={`${provider.provider}-reason`}>
        {label}
        <span id={`${provider.provider}-reason`} className="sr-only">
          {provider.reason ?? "Provider not configured"}
        </span>
      </Button>
    );
  }
  return <a className="ds-button" href={providerLoginUrl(provider.provider)}>{label}</a>;
}

function LoginScreen({
  providers,
  previewMode,
  privateAcceptanceEnabled,
  onPreviewLogin,
  onPrivateLogin,
  busy,
}: {
  providers: ProviderView[];
  previewMode: PreviewModeView | null;
  privateAcceptanceEnabled: boolean;
  onPreviewLogin: () => void;
  onPrivateLogin: () => void;
  busy: boolean;
}) {
  return (
    <main className="login-layout">
      <section className="login-panel" aria-labelledby="login-title">
        <p className="shell-eyebrow">OMNI-CIO V10</p>
        <h1 id="login-title">Инвестиционные решения с проверяемой логикой</h1>
        <p>
          Серверная сессия, tenant isolation и READ-only broker boundary. Пароли и токены не сохраняются в браузере.
        </p>
        {previewMode?.enabled ? (
          <div className="shell-stack">
            <Button disabled={busy} onClick={onPreviewLogin}>
              {busy ? "Открываем…" : previewMode.label}
            </Button>
            <p className="shell-caption">
              Синтетический публичный preview: реальные пользователи, broker-токены и приватные портфели отключены.
            </p>
          </div>
        ) : null}
        <div className="login-actions">
          {providers.map((provider) => <ProviderButton provider={provider} key={provider.provider} />)}
          {privateAcceptanceEnabled ? (
            <Button disabled={busy} onClick={onPrivateLogin}>
              {busy ? "Вход…" : "Локальный OWNER acceptance"}
            </Button>
          ) : null}
        </div>
        <p className="shell-caption">
          Локальный OWNER acceptance виден только на loopback и не является третьим login provider.
        </p>
        {!previewMode?.enabled && providers.every((provider) => !provider.enabled) ? (
          <StatePanel kind="warning" title="Вход пока не настроен">
            Telegram Login и VK ID остаются fail-closed до появления проверенных credentials.
          </StatePanel>
        ) : null}
      </section>
    </main>
  );
}

export function ApplicationShell() {
  const route = useRoute();
  const [session, setSession] = useState<WebSessionView | null>(null);
  const [providers, setProviders] = useState<ProviderView[]>([]);
  const [previewMode, setPreviewMode] = useState<PreviewModeView | null>(null);
  const [privateAcceptanceEnabled, setPrivateAcceptanceEnabled] = useState(false);
  const [healthState, setHealthState] = useState<OperationalState>("OFFLINE");
  const [freshness, setFreshness] = useState("UNKNOWN");
  const [loading, setLoading] = useState(true);
  const [unavailable, setUnavailable] = useState(false);
  const [authenticating, setAuthenticating] = useState(false);
  const [logoutError, setLogoutError] = useState<string | null>(null);

  async function initialize() {
    setLoading(true);
    const [sessionResult, providerResult, privateResult, previewResult] = await Promise.allSettled([
      readSession(),
      readProviders(),
      readPrivateAcceptanceStatus(),
      readPreviewMode(),
    ]);
    if (providerResult.status === "fulfilled") setProviders(providerResult.value);
    if (privateResult.status === "fulfilled") setPrivateAcceptanceEnabled(privateResult.value.enabled);
    if (previewResult.status === "fulfilled") setPreviewMode(previewResult.value);
    if (sessionResult.status === "rejected") {
      setUnavailable(true);
      setSession(null);
      setHealthState("OFFLINE");
      setFreshness("UNKNOWN");
      setLoading(false);
      return;
    }
    setUnavailable(false);
    setSession(sessionResult.value);
    if (sessionResult.value.authenticated) {
      try {
        const health = await readHealth();
        setHealthState(health.state);
        setFreshness(health.freshness);
      } catch {
        setHealthState("OFFLINE");
        setFreshness("UNKNOWN");
      }
    }
    setLoading(false);
  }

  useEffect(() => { void initialize(); }, []);

  async function authenticatePreview() {
    setAuthenticating(true);
    try {
      await previewLogin();
      await initialize();
    } catch {
      setUnavailable(true);
    } finally {
      setAuthenticating(false);
    }
  }

  async function authenticatePrivately() {
    setAuthenticating(true);
    try {
      await privateTestLogin();
      await initialize();
    } catch {
      setUnavailable(true);
    } finally {
      setAuthenticating(false);
    }
  }

  function logout() {
    setLogoutError(null);
    void logoutCurrentSession()
      .then(() => initialize())
      .catch(() => {
        setLogoutError("Выход не подтверждён сервером. Текущая сессия остаётся активной.");
      });
  }

  if (loading) return <main className="login-layout"><p role="status">Загрузка Omni-CIO…</p></main>;
  if (unavailable) {
    return (
      <main className="login-layout">
        <StatePanel kind="error" title="Web API недоступен">
          Fail-closed: интерфейс не показывает фиктивный успешный статус. Проверь локальный runtime и PostgreSQL.
        </StatePanel>
      </main>
    );
  }
  if (!session?.authenticated) {
    return (
      <LoginScreen
        providers={providers}
        previewMode={previewMode}
        privateAcceptanceEnabled={privateAcceptanceEnabled}
        onPreviewLogin={() => void authenticatePreview()}
        onPrivateLogin={() => void authenticatePrivately()}
        busy={authenticating}
      />
    );
  }

  return (
    <div className="app-shell">
      <aside className="app-sidebar" aria-label="Основная навигация">
        <div className="app-brand">
          <strong>OMNI-CIO</strong>
          <span>V10 · READ ONLY</span>
        </div>
        <nav>
          {appRoutes.map((item) => (
            <a
              aria-current={route === item.path ? "page" : undefined}
              href={item.path}
              key={item.path}
              onClick={(event) => { event.preventDefault(); navigate(item.path); }}
            >
              {item.label}
            </a>
          ))}
        </nav>
      </aside>
      <div className="app-workspace">
        <header className="app-topbar">
          <div>
            <span>USER</span>
            <strong>{session.user_label ?? "USER"}</strong>
            <span>{session.tenant_label ?? "TENANT"}</span>
          </div>
          <div className="app-topbar__state">
            <StatusBadge state={healthState} />
            <span>Freshness: {freshness}</span>
            <Button variant="secondary" onClick={logout}>Выйти</Button>
          </div>
        </header>
        {logoutError ? <div className="shell-degraded" role="alert">{logoutError}</div> : null}
        {previewMode?.synthetic ? (
          <div className="shell-degraded" role="status">
            SYNTHETIC PREVIEW · real registration, broker credentials and private portfolio data are disabled. Не вводи реальные токены на этом стенде.
          </div>
        ) : healthState !== "READY" ? (
          <div className="shell-degraded" role="status">
            Runtime state: {healthState}. Финансовые данные не маскируются под свежие.
          </div>
        ) : null}
        <RoutePage path={route} healthState={healthState} freshness={freshness} />
      </div>
    </div>
  );
}
