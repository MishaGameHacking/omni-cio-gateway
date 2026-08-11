import { useEffect, useState } from "react";
import { Button, Card, StatePanel, StatusBadge } from "../design-system/components";
import type { OperationalState } from "../design-system/contracts";
import { readBrokerConnections, revokeAllSessions } from "./api";
import type { AppRoutePath, BrokerConnectionView } from "./contracts";

const routeTitles: Record<AppRoutePath, string> = {
  "/": "Обзор",
  "/portfolio": "Портфель",
  "/assets": "Активы",
  "/watchtower": "Watchtower",
  "/research": "Research",
  "/risks": "Риски",
  "/decisions": "Решения",
  "/plans": "Планы",
  "/execution": "Исполнение",
  "/journal": "Журнал",
  "/system": "Система",
  "/settings": "Настройки",
};

function PlaceholderPage({ path }: { path: AppRoutePath }) {
  return (
    <section className="shell-page" aria-labelledby="page-title">
      <div className="shell-page__heading">
        <p className="shell-eyebrow">OMNI-CIO V10</p>
        <h1 id="page-title">{routeTitles[path]}</h1>
      </div>
      <StatePanel kind="empty" title="Раздел готов к следующему work package">
        WP17 создаёт стабильный shell без ранней финансовой бизнес-логики.
      </StatePanel>
    </section>
  );
}

export function SystemPage({ healthState, freshness }: { healthState: OperationalState; freshness: string }) {
  const gitSha = __OMNI_WEB_BUILD_SHA__;
  const version = __OMNI_WEB_VERSION__;
  return (
    <section className="shell-page" aria-labelledby="page-title">
      <div className="shell-page__heading">
        <p className="shell-eyebrow">SYSTEM</p>
        <h1 id="page-title">Система</h1>
      </div>
      <div className="shell-grid shell-grid--two">
        <Card title="Web build">
          <dl className="shell-definition-list">
            <div><dt>Version</dt><dd>{version}</dd></div>
            <div><dt>Git SHA</dt><dd><code>{gitSha}</code></dd></div>
          </dl>
        </Card>
        <Card title="Runtime state">
          <div className="shell-stack">
            <StatusBadge state={healthState} />
            <span className="shell-muted">Freshness: {freshness}</span>
          </div>
        </Card>
      </div>
    </section>
  );
}

export function SettingsPage() {
  const [connections, setConnections] = useState<BrokerConnectionView[] | null>(null);
  const [connectionError, setConnectionError] = useState(false);
  const [revoked, setRevoked] = useState(false);

  useEffect(() => {
    let active = true;
    readBrokerConnections()
      .then((value) => {
        if (active) setConnections(value);
      })
      .catch(() => {
        if (active) setConnectionError(true);
      });
    return () => {
      active = false;
    };
  }, []);

  return (
    <section className="shell-page" aria-labelledby="page-title">
      <div className="shell-page__heading">
        <p className="shell-eyebrow">ACCOUNT</p>
        <h1 id="page-title">Настройки</h1>
      </div>
      <div className="shell-grid shell-grid--two">
        <Card title="Broker Connections">
          {connectionError ? (
            <StatePanel kind="warning" title="Подключения временно недоступны">
              Shell остаётся доступным; broker credentials не запрашиваются повторно автоматически.
            </StatePanel>
          ) : connections === null ? (
            <p className="shell-muted" role="status">Загрузка подключений…</p>
          ) : connections.length === 0 ? (
            <StatePanel kind="empty" title="T-Invest ещё не подключён">
              READ-token будет вводиться только в authenticated Web flow и не возвращается в браузер после сохранения.
            </StatePanel>
          ) : (
            <div className="shell-connection-list">
              {connections.map((connection) => (
                <article key={connection.connection_id} className="shell-connection">
                  <div><strong>T-Invest</strong><span>READ ONLY</span></div>
                  <StatusBadge state={connection.state === "ACTIVE" ? "READY" : "DEGRADED"} />
                  <ul>
                    {connection.accounts.map((account) => (
                      <li key={account.account_fingerprint_sha256}>{account.masked_label}</li>
                    ))}
                  </ul>
                </article>
              ))}
            </div>
          )}
          <Button variant="secondary" disabled>Добавить T-Invest READ connection</Button>
          <p className="shell-caption">Provisioning action включится только вместе с reviewed WP17 backend contract.</p>
        </Card>
        <Card title="Сессии">
          <p className="shell-muted">Можно отозвать все server-side sessions этого аккаунта.</p>
          <Button
            variant="secondary"
            onClick={() => {
              void revokeAllSessions().then(() => setRevoked(true));
            }}
          >
            Выйти на всех устройствах
          </Button>
          {revoked ? <p role="status">Все сессии отозваны.</p> : null}
        </Card>
      </div>
    </section>
  );
}

export function RoutePage({ path, healthState, freshness }: { path: AppRoutePath; healthState: OperationalState; freshness: string }) {
  if (path === "/system") return <SystemPage healthState={healthState} freshness={freshness} />;
  if (path === "/settings") return <SettingsPage />;
  return <PlaceholderPage path={path} />;
}
