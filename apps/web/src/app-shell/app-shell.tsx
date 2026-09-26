import { useCallback, useEffect, useMemo, useState } from "react";
import { Button, StatusBadge } from "../design-system/components";
import type { OperationalState } from "../design-system/contracts";
import {
  logoutCurrentSession,
  providerLoginPath,
  readHealth,
  readPreviewMode,
  readProviders,
  readSession,
} from "./api";
import {
  appRoutes,
  isKnownRoute,
  isPublicRoute,
  type AppRoutePath,
  type HealthView,
  type PreviewModeView,
  type ProviderView,
  type ShellRoutePath,
  type WebSessionView,
} from "./contracts";
import { DecisionPlanPage } from "./decision-plan";
import { RoutePage } from "./pages";
import { PortfolioDashboardPage } from "./portfolio-dashboard";
import { ResearchDossiersPage } from "./research-dossiers";
import { SystemAdminPage } from "./system-admin";
import { WatchtowerIncidentsPage } from "./watchtower-incidents";

function currentPath(): ShellRoutePath {
  const path = window.location.pathname;
  if (isPublicRoute(path)) return path;
  return isKnownRoute(path) ? path : "/";
}

function healthToOperational(value: HealthView["state"]): OperationalState {
  if (value === "READY" || value === "PARTIAL" || value === "STALE" || value === "DEGRADED" || value === "OFFLINE") return value;
  return "DEGRADED";
}

type LoginScreenProps = Readonly<{
  providers: ProviderView[];
  apiUnavailable: boolean;
}>;

function providerStatusCaption(provider: ProviderView | undefined): string {
  if (provider?.reason === "PUBLIC_MULTI_USER_DISABLED") {
    return "Telegram настроен, но публичная регистрация ещё не активирована.";
  }
  if (provider?.reason === "PROVIDER_ACTIVATION_DISABLED") {
    return "Telegram Login настроен, но активация входа ещё не разрешена.";
  }
  if (provider?.enabled) {
    return "Telegram Login доступен.";
  }
  return "Telegram Login остаётся fail-closed до reviewed provider configuration.";
}

function PrivacyPolicyPage() {
  return (
    <main className="login-shell" role="main">
      <section className="login-card" aria-labelledby="privacy-title">
        <p className="shell-eyebrow">OMNI-CIO V10</p>
        <h1 id="privacy-title">Политика обработки персональных данных</h1>
        <p className="shell-muted">Публичная регистрация остаётся отключённой до завершения отдельного legal/privacy gate.</p>
        <h2>Данные для входа</h2>
        <p>Telegram Login запрашивает только scope openid: идентификатор пользователя у провайдера и технические данные аутентификации из подписанного ID token. Профиль, телефон и telegram:bot_access не запрашиваются.</p>
        <h2>Использование внутри Omni-CIO</h2>
        <p>После успешной проверки Telegram identity сервер связывает её с внутренним аккаунтом, изолированным Tenant и server-side Session. Tenant не выбирается браузером.</p>
        <h2>До публичной активации</h2>
        <p>До включения регистрации должны быть утверждены и опубликованы сведения об операторе, правовых основаниях и целях обработки, сроках хранения, трансграничной обработке и канале обращений субъектов персональных данных. До этого момента Telegram Login остаётся fail-closed.</p>
        <p className="shell-caption"><a href="/">Вернуться к входу</a></p>
      </section>
    </main>
  );
}

function LoginScreen({ providers, apiUnavailable }: LoginScreenProps) {
  const telegram = providers.find((item) => item.provider === "telegram");
  return (
    <main className="login-shell" role="main">
      <section className="login-card" aria-labelledby="login-title">
        <p className="shell-eyebrow">OMNI-CIO V10</p>
        <h1 id="login-title">Вход в личный аккаунт</h1>
        <p className="shell-muted">Обычный вход — только через Telegram. Локального пароля Omni-CIO нет.</p>
        {apiUnavailable ? <div className="login-warning" role="alert">Authentication API недоступен. Доступ к приватным разделам закрыт.</div> : null}
        <div className="login-actions">
          <form method="post" action={providerLoginPath()}>
            <button className="ds-button ds-button--primary" disabled={!telegram?.enabled} type="submit">Продолжить через Telegram</button>
          </form>
        </div>
        <p className="shell-caption">{providerStatusCaption(telegram)}</p>
        <p className="shell-caption"><a href="/privacy">Политика обработки персональных данных</a></p>
      </section>
    </main>
  );
}

export function ApplicationShell() {
  const [session, setSession] = useState<WebSessionView | null>(null);
  const [providers, setProviders] = useState<ProviderView[]>([]);
  const [previewMode, setPreviewMode] = useState<PreviewModeView | null>(null);
  const [sessionUnavailable, setSessionUnavailable] = useState(false);
  const [path, setPath] = useState<ShellRoutePath>(currentPath);
  const isPublicPrivacy = path === "/privacy";
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
    if (isPublicPrivacy) return;
    void refreshSession();
    void readProviders().then(setProviders).catch(() => setProviders([]));
    void readPreviewMode().then(setPreviewMode).catch(() => setPreviewMode(null));
  }, [isPublicPrivacy, refreshSession]);

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

  if (isPublicPrivacy) {
    return <PrivacyPolicyPage />;
  }
  if (session === null) {
    return <main className="shell-loading" role="main"><span role="status">Проверка server-side session…</span></main>;
  }
  if (!session.authenticated) {
    return <LoginScreen providers={providers} apiUnavailable={sessionUnavailable} />;
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
          <span>USER</span>
          <Button
            variant="secondary"
            onClick={() => {
              void logoutCurrentSession()
                .then(() => {
                  setSession({ authenticated: false });
                  setSessionUnavailable(false);
                })
                .catch(() => setSessionUnavailable(true));
            }}
          >
            Выйти
          </Button>
        </div>
      </aside>
      <main className="shell-content" id="main-content">
        {sessionUnavailable ? <div className="shell-degraded" role="alert">Выход не подтверждён сервером. Текущая сессия остаётся активной.</div> : null}
        {previewMode?.synthetic ? (
          <div className="shell-degraded" role="status">
            SYNTHETIC PREVIEW · real registration, broker credentials and private portfolio data are disabled. Не вводи реальные токены на этом стенде.
          </div>
        ) : null}
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
