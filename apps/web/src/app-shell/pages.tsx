import { useCallback, useEffect, useState } from "react";
import { Button, Card, StatePanel, StatusBadge } from "../design-system/components";
import type { OperationalState } from "../design-system/contracts";
import {
  commitBrokerReadConnection,
  previewBrokerReadConnection,
  readBrokerConnections,
  replaceBrokerReadCredential,
  revokeAllSessions,
  revokeBrokerReadConnection,
} from "./api";
import type {
  AppRoutePath,
  BrokerConnectionView,
  BrokerProvisioningPreviewView,
} from "./contracts";

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

function BrokerConnectionsCard() {
  const [connections, setConnections] = useState<BrokerConnectionView[] | null>(null);
  const [connectionError, setConnectionError] = useState(false);
  const [token, setToken] = useState("");
  const [preview, setPreview] = useState<BrokerProvisioningPreviewView | null>(null);
  const [selected, setSelected] = useState<string[]>([]);
  const [replaceTarget, setReplaceTarget] = useState<string | null>(null);
  const [working, setWorking] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const value = await readBrokerConnections();
      setConnections(value);
      setConnectionError(false);
    } catch {
      setConnectionError(true);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const resetProvisioning = useCallback(() => {
    setToken("");
    setPreview(null);
    setSelected([]);
    setReplaceTarget(null);
  }, []);

  const validateToken = useCallback(async () => {
    const candidate = token.trim();
    if (!candidate || working) return;
    setWorking(true);
    setMessage(null);
    try {
      const result = await previewBrokerReadConnection(candidate);
      setToken("");
      setPreview(result);
      setSelected(result.accounts.map((account) => account.selection_id));
      setMessage("READ-token проверен. Подтверди нужные брокерские счета.");
    } catch {
      setToken("");
      setPreview(null);
      setSelected([]);
      setMessage("Token отклонён или broker API недоступен. Секрет не сохранён.");
    } finally {
      setWorking(false);
    }
  }, [token, working]);

  const commit = useCallback(async () => {
    if (!preview || selected.length === 0 || working) return;
    setWorking(true);
    setMessage(null);
    try {
      if (replaceTarget) {
        await replaceBrokerReadCredential(replaceTarget, preview.challenge_id, selected);
        setMessage("READ credential заменён для того же verified account set.");
      } else {
        await commitBrokerReadConnection(preview.challenge_id, selected);
        setMessage("T-Invest READ connection сохранён.");
      }
      resetProvisioning();
      await refresh();
    } catch {
      setMessage("Подключение не сохранено: проверка scope/authority не прошла.");
    } finally {
      setWorking(false);
    }
  }, [preview, refresh, replaceTarget, resetProvisioning, selected, working]);

  return (
    <Card title="Broker Connections">
      {connectionError ? (
        <StatePanel kind="warning" title="Подключения временно недоступны">
          Shell остаётся доступным; broker credentials не запрашиваются повторно автоматически.
        </StatePanel>
      ) : connections === null ? (
        <p className="shell-muted" role="status">Загрузка подключений…</p>
      ) : connections.length === 0 ? (
        <StatePanel kind="empty" title="T-Invest ещё не подключён">
          Введи READ-token ниже. После проверки браузер больше не получает raw token обратно.
        </StatePanel>
      ) : (
        <div className="shell-connection-list">
          {connections.map((connection) => (
            <article key={connection.connection_id} className="shell-connection">
              <div><strong>T-Invest</strong><span>READ ONLY</span></div>
              <StatusBadge state={connection.state === "ACTIVE" ? "READY" : "DEGRADED"} />
              <ul>
                {connection.accounts.map((account) => (
                  <li key={account.masked_label}>{account.masked_label}</li>
                ))}
              </ul>
              <div className="shell-connection__actions">
                <Button variant="secondary" disabled={working} onClick={() => { resetProvisioning(); setReplaceTarget(connection.connection_id); setMessage("Введи новый READ-token для тех же брокерских счетов."); }}>Заменить token</Button>
                <Button variant="danger" disabled={working || connection.state !== "ACTIVE"} onClick={() => { setWorking(true); void revokeBrokerReadConnection(connection.connection_id).then(refresh).then(() => setMessage("Подключение отозвано.")).catch(() => setMessage("Не удалось отозвать подключение.")).finally(() => setWorking(false)); }}>Отключить</Button>
              </div>
            </article>
          ))}
        </div>
      )}

      <div className="shell-provisioning" aria-label="T-Invest READ provisioning">
        <label className="ds-field" htmlFor="tinvest-read-token">
          <span>{replaceTarget ? "Новый T-Invest READ-token" : "T-Invest READ-token"}</span>
          <input
            className="ds-input"
            id="tinvest-read-token"
            type="password"
            autoComplete="off"
            spellCheck={false}
            value={token}
            onChange={(event) => setToken(event.target.value)}
            disabled={working || preview !== null}
          />
        </label>
        {!preview ? (
          <Button variant="secondary" disabled={working || token.trim().length === 0} onClick={() => void validateToken()}>
            Проверить READ-token
          </Button>
        ) : (
          <div className="shell-account-selection">
            <strong>Доступные счета</strong>
            {preview.accounts.map((account) => (
              <label key={account.selection_id} className="shell-checkbox">
                <input
                  type="checkbox"
                  checked={selected.includes(account.selection_id)}
                  onChange={(event) => setSelected((items) => event.target.checked ? [...items, account.selection_id] : items.filter((item) => item !== account.selection_id))}
                />
                <span>{account.masked_label} · READ ONLY</span>
              </label>
            ))}
            <div className="shell-stack">
              <Button disabled={working || selected.length === 0} onClick={() => void commit()}>{replaceTarget ? "Заменить credential" : "Подключить выбранные счета"}</Button>
              <Button variant="secondary" disabled={working} onClick={resetProvisioning}>Отмена</Button>
            </div>
          </div>
        )}
        <p className="shell-caption">Token не сохраняется в browser storage и после проверки очищается из формы. TRADE credential в WP17 не принимается.</p>
        {message ? <p role="status">{message}</p> : null}
      </div>
    </Card>
  );
}

export function SettingsPage({ onSessionsRevoked }: { onSessionsRevoked: () => void }) {
  const [revokingSessions, setRevokingSessions] = useState(false);
  return (
    <section className="shell-page" aria-labelledby="page-title">
      <div className="shell-page__heading">
        <p className="shell-eyebrow">ACCOUNT</p>
        <h1 id="page-title">Настройки</h1>
      </div>
      <div className="shell-grid shell-grid--two">
        <BrokerConnectionsCard />
        <Card title="Сессии">
          <p className="shell-muted">Можно отозвать все server-side sessions этого аккаунта.</p>
          <Button
            variant="secondary"
            disabled={revokingSessions}
            onClick={() => {
              setRevokingSessions(true);
              void revokeAllSessions()
                .then(onSessionsRevoked)
                .catch(() => setRevokingSessions(false));
            }}
          >
            Выйти на всех устройствах
          </Button>
        </Card>
      </div>
    </section>
  );
}

export function RoutePage({ path, healthState, freshness, onSessionsRevoked }: { path: AppRoutePath; healthState: OperationalState; freshness: string; onSessionsRevoked: () => void }) {
  if (path === "/system") return <SystemPage healthState={healthState} freshness={freshness} />;
  if (path === "/settings") return <SettingsPage onSessionsRevoked={onSessionsRevoked} />;
  return <PlaceholderPage path={path} />;
}