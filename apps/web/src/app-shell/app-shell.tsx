import { useCallback, useEffect, useMemo, useState } from "react";
import { Button, StatusBadge } from "../design-system/components";
import type { OperationalState } from "../design-system/contracts";
import {
  logoutCurrentSession,
  privateRemoteLogin,
  privateTestLogin,
  providerLoginUrl,
  readHealth,
  readPrivateAcceptanceStatus,
  readPrivateRemoteAcceptanceStatus,
  readProviders,
  readSession,
} from "./api";
import { appRoutes, isKnownRoute, type AppRoutePath, type HealthView, type ProviderView, type WebSessionView } from "./contracts";
import { DecisionPlanPage } from "./decision-plan";
import { RoutePage } from "./pages";
import { PortfolioDashboardPage } from "./portfolio-dashboard";
import { ResearchDossiersPage } from "./research-dossiers";
import { SystemAdminPage } from "./system-admin";
import { WatchtowerIncidentsPage } from "./watchtower-incidents";

function currentPath(): AppRoutePath {
  const path = window.location.pathname;
  return isKnownRoute(path) ? path : "/";
}

function healthToOperational(value: HealthView["state"]): OperationalState {
  if (value === "READY" || value === "PARTIAL" || value === "STALE" || value === "DEGRADED" || value === "OFFLINE") return value;
  return "DEGRADED";
}

function LoginScreen({
  providers,
  apiUnavailable,
  privateAcceptanceEnabled,
  privateRemoteAcceptanceEnabled,
  onPrivateAcceptance,
  onPrivateRemoteAcceptance,
}: {
  providers: ProviderView[];
  apiUnavailable: boolean;
  privateAcceptanceEnabled: boolean;
  privateRemoteAcceptanceEnabled: boolean;
  onPrivateAcceptance: () => void;
  onPrivateRemoteAcceptance: () => void;
}) {
  const provider = (name: "telegram" | "vk_id") => providers.find((item) => item.provider === name);
  const telegram = provider("telegram");
  const vk = provider("vk_id");
  return (
    <main className="login-shell" role="main">
      <section className="login-card" aria-labelledby="login-title">
        <p className="shell-eyebrow">OMNI-CIO V10</p>
        <h1 id="login-title">Вход в личный аккаунт</h1>
        <p className="shell-muted">Обычный вход — только через Telegram или VK ID. Локального пароля Omni-CIO нет.</p>
        {apiUnavailable ? <div className="login-warning" role="alert">Authentication API недоступен. Доступ к приватным разделам закрыт.</div> : null}
        <div className="login-actions">
          <a className="ds-button ds-button--primary" aria-disabled={!telegram?.enabled} href={telegram?.enabled ? providerLoginUrl("telegram") : undefined}>Продолжить через Telegram</a>
          <a className="ds-button ds-button--secondary" aria-disabled={!vk?.enabled} href={vk?.enabled ? providerLoginUrl("vk_id") : undefined}>Продолжить через VK ID</a>
          {privateAcceptanceEnabled ? (
            <Button variant="secondary" onClick={onPrivateAcceptance}>Локальный OWNER acceptance</Button>
          ) : null}
          {privateRemoteAcceptanceEnabled ? (
            <Button variant="secondary" onClick={onPrivateRemoteAcceptance}>Приватный OWNER доступ</Button>
          ) : null}
        </div>
        <p className="shell-caption">Provider buttons остаются fail-closed до reviewed local/private provider configuration.</p>
        {privateAcceptanceEnabled ? <p className="shell-caption">Локальный OWNER acceptance виден только на loopback и не является третьим login provider.</p> : null}
        {privateRemoteAcceptanceEnabled ? <p className="shell-caption">Приватный OWNER доступ разрешён только через reviewed tailnet transport и также не является третьим product login provider.</p> : null}
      </section>
    </main>
  );
}

export function ApplicationShell() {
  const [session, setSession] = useState<WebSessionView | null>(null);
  const [providers, setProviders] = useState<ProviderView[]>([]);
  const [privateAcceptanceEnabled, setPrivateAcceptanceEnabled] = useState(false);
  const [privateRemoteAcceptanceEnabled, setPrivateRemoteAcceptanceEnabled] = useState(false);
  const [sessionUnavailable, setSessionUnavailable] = useState(false);
  const [path, setPath] = useState<AppRoutePath>(currentPath);
  const [health, setHealth] = useState<HealthView | null>(null);
  const [healthUnavailable, setHealthUnavailable] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);

  const refreshSession = useCallback(async () => {
    try {
      const value = await readSession();
      setSession(value);
      setSessionUnavailable(false);
    } catch {
      setSession({ authenticated: false });
      setSessionUnavailable(true);
    }
  }, []);

  useEffect(() => {
    void refreshSession();
    void readProviders().then(setProviders).catch(() => setProviders([]));
    void readPrivateAcceptanceStatus()
      .then((value) => setPrivateAcceptanceEnabled(value.enabled))
      .catch(() => setPrivateAcceptanceEnabled(false));
    void readPrivateRemoteAcceptanceStatus()
      .then((value) => setPrivateRemoteAcceptanceEnabled(value.enabled))
      .catch(() => setPrivateRemoteAcceptanceEnabled(false));
  }, [refreshSession]);

  useEffect(() => {
    if (!session?.authenticated) return;
    void readHealth()
      .then((value) => {
        setHealth(value);
        setHealthUnavailable(false);
      })
      .catch(() => {
        setHealth(null);
        setHealthUnavailable(true);
      });
  }, [session?.authenticated]);

  useEffect(() => {
    const onPopState = () => setPath(currentPath());
    window.addEventListener("popstate", onPopState);
    return () => window.removeEventListener("popstate", onPopState);
  }, []);

  const navigate = useCallback((nextPath: AppRoutePath) => {
    if (nextPath !== window.location.pathname) window.history.pushState({}, "", nextPath);
    setPath(nextPath);
    setMenuOpen(false);
    window.scrollTo({ top: 0, behavior: "instant" });
  }, []);

  const healthState = useMemo<OperationalState>(() => {
    if (healthUnavailable) return "DEGRADED";
    return health ? healthToOperational(health.state) : "RECOVERING";
  }, [health, healthUnavailable]);

  if (session === null) {
    return <main className="shell-loading" role="main"><span role="status">Проверка server-side session…</span></main>;
  }
  if (!session.authenticated) {
    return (
      <LoginScreen
        providers={providers}
        apiUnavailable={sessionUnavailable}
        privateAcceptanceEnabled={privateAcceptanceEnabled}
        privateRemoteAcceptanceEnabled={privateRemoteAcceptanceEnabled}
        onPrivateAcceptance={() => {
          void privateTestLogin()
            .then(refreshSession)
            .catch(() => setSessionUnavailable(true));
        }}
        onPrivateRemoteAcceptance={() => {
          void privateRemoteLogin()
            .then(refreshSession)
            .catch(() => setSessionUnavailable(true));
        }}
      />
    );
  }

  return (
    <div className="app-shell">
      <header className="shell-topbar">
        <div className="shell-brand"><span className="shell-brand__mark" aria-hidden="true">O</span><span>OMNI-CIO</span></div>
        <div className="shell-topbar__status" aria-label="Глобальное состояние">
          <StatusBadge state={healthState} />
          <span className="shell-freshness">{health?.freshness ?? "UNKNOWN"}</span>
        </div>
        <button className="shell-menu-button" type="button" aria-expanded={menuOpen} aria-controls="primary-navigation" onClick={() => setMenuOpen((value) => !value)}>Меню</button>
      </header>
      <aside className={`shell-sidebar${menuOpen ? " shell-sidebar--open" : ""}`}>
        <nav id="primary-navigation" aria-label="Основная навигация">
          <ul className="shell-nav">
            {appRoutes.map((route) => (
              <li key={route.path}><button type="button" className="shell-nav__item" aria-current={path === route.path ? "page" : undefined} onClick={() => navigate(route.path)}>{route.label}</button></li>
            ))}
          </ul>
        </nav>
        <div className="shell-account">
          <span>{session.user_label ?? "OWNER"}</span>
          <Button variant="secondary" onClick={() => { void logoutCurrentSession().finally(() => setSession({ authenticated: false })); }}>Выйти</Button>
        </div>
      </aside>
      <main className="shell-content" id="main-content">
        {healthUnavailable ? <div className="shell-degraded" role="status">Downstream API недоступен — shell работает в DEGRADED режиме.</div> : null}
        {path === "/portfolio" || path === "/assets" ? (
          <PortfolioDashboardPage assetsMode={path === "/assets"} />
        ) : path === "/watchtower" ? (
          <WatchtowerIncidentsPage />
        ) : path === "/research" ? (
          <ResearchDossiersPage />
        ) : path === "/risks" || path === "/decisions" || path === "/plans" ? (
          <DecisionPlanPage focus={path === "/risks" ? "risks" : path === "/decisions" ? "decisions" : "plans"} />
        ) : path === "/system" ? (
          <SystemAdminPage healthState={healthState} freshness={health?.freshness ?? "UNKNOWN"} />
        ) : (
          <RoutePage
            path={path}
            healthState={healthState}
            freshness={health?.freshness ?? "UNKNOWN"}
            onSessionsRevoked={() => setSession({ authenticated: false })}
          />
        )}
      </main>
    </div>
  );
}
