import { useCallback, useEffect, useState } from "react";
import { Button, Card, StatePanel, StatusBadge } from "../design-system/components";
import type { OperationalState } from "../design-system/contracts";
import {
  cancelWp15LiveAcceptance,
  commitBrokerReadConnection,
  confirmWp15LiveAcceptance,
  previewBrokerReadConnection,
  readBrokerConnections,
  readWp15LiveAcceptanceStatus,
  replaceBrokerReadCredential,
  revokeAllSessions,
  revokeBrokerReadConnection,
  startWp15LiveAcceptance,
} from "./api";
import type {
  AppRoutePath,
  BrokerConnectionView,
  BrokerProvisioningPreviewView,
  Wp15LiveAcceptanceView,
  Wp15LiveConfirmation,
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

const emptyLiveConfirmation: Wp15LiveConfirmation = {
  intended_account_confirmed: false,
  portfolio_summary_parity: false,
  sample_position_quantity_value_parity: false,
  freshness_confirmed: false,
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
  const [liveEnabled, setLiveEnabled] = useState(false);
  const [liveWorking, setLiveWorking] = useState(false);
  const [liveView, setLiveView] = useState<Wp15LiveAcceptanceView | null>(null);
  const [liveConfirmation, setLiveConfirmation] = useState<Wp15LiveConfirmation>(emptyLiveConfirmation);
  const [liveMessage, setLiveMessage] = useState<string | null>(null);

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
    void readWp15LiveAcceptanceStatus()
      .then((value) => setLiveEnabled(value.enabled))
      .catch(() => setLiveEnabled(false));
  }, [refresh]);

  const resetProvisioning = useCallback(() => {
    setToken("");
    setPreview(null);
    setSelected([]);
    setReplaceTarget(null);
  }, []);

  const resetLive = useCallback(() => {
    setLiveView(null);
    setLiveConfirmation(emptyLiveConfirmation);
  }, []);

  useEffect(() => {
    if (!liveView) return;
    const expiresAt = Date.parse(liveView.expires_at);
    const delay = Number.isFinite(expiresAt) ? Math.max(0, expiresAt - Date.now()) : 0;
    const timeoutId = window.setTimeout(() => {
      resetLive();
      setLiveMessage("Live challenge истёк. Приватные значения удалены из браузера.");
    }, delay);
    return () => window.clearTimeout(timeoutId);
  }, [liveView, resetLive]);

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

  const startLive = useCallback(async (connectionId: string, accountIndex: number) => {
    if (liveWorking) return;
    setLiveWorking(true);
    setLiveMessage("Получаем live READ snapshot из T-Invest. Для большого портфеля нормализация может занять несколько минут; страницу не закрывай.");
    resetLive();
    try {
      const value = await startWp15LiveAcceptance(connectionId, accountIndex);
      setLiveView(value);
      setLiveConfirmation(emptyLiveConfirmation);
      setLiveMessage("Live READ snapshot получен. Сверь значения с T-Invest и отметь только фактически проверенные пункты.");
    } catch {
      setLiveMessage("Live acceptance не прошёл: authority/account/freshness/completeness проверка закрылась fail-closed.");
    } finally {
      setLiveWorking(false);
    }
  }, [liveWorking, resetLive]);

  const confirmLive = useCallback(async () => {
    if (!liveView || liveWorking) return;
    const allConfirmed = Object.values(liveConfirmation).every(Boolean);
    if (!allConfirmed) return;
    setLiveWorking(true);
    setLiveMessage(null);
    try {
      await confirmWp15LiveAcceptance(liveView.challenge_id, liveConfirmation);
      resetLive();
      setLiveMessage("OWNER parity подтверждена. Создана только sanitized pending evidence; приватные суммы/позиции в неё не записаны.");
    } catch {
      setLiveMessage("Sanitized acceptance evidence не создана. Повтори live snapshot и сверку.");
    } finally {
      setLiveWorking(false);
    }
  }, [liveConfirmation, liveView, liveWorking, resetLive]);

  const cancelLive = useCallback(async () => {
    const challengeId = liveView?.challenge_id;
    resetLive();
    if (!challengeId) return;
    try {
      await cancelWp15LiveAcceptance(challengeId);
    } catch {
      setLiveMessage("Live challenge уже истёк или был удалён.");
    }
  }, [liveView?.challenge_id, resetLive]);

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
                {connection.accounts.map((account, accountIndex) => (
                  <li key={`${account.masked_label}-${accountIndex}`}>
                    <span>{account.masked_label}</span>
                    {liveEnabled && connection.state === "ACTIVE" ? (
                      <Button variant="secondary" disabled={liveWorking || liveView !== null} onClick={() => void startLive(connection.connection_id, accountIndex)}>
                        {liveWorking ? "Получаем snapshot…" : "Live READ acceptance"}
                      </Button>
                    ) : null}
                  </li>
                ))}
              </ul>
              <div className="shell-connection__actions">
                <Button variant="secondary" disabled={working || liveWorking || liveView !== null} onClick={() => { resetProvisioning(); setReplaceTarget(connection.connection_id); setMessage("Введи новый READ-token для тех же брокерских счетов."); }}>Заменить token</Button>
                <Button variant="danger" disabled={working || liveWorking || liveView !== null || connection.state !== "ACTIVE"} onClick={() => { setWorking(true); void revokeBrokerReadConnection(connection.connection_id).then(refresh).then(() => setMessage("Подключение отозвано.")).catch(() => setMessage("Не удалось отозвать подключение.")).finally(() => setWorking(false)); }}>Отключить</Button>
              </div>
            </article>
          ))}
        </div>
      )}

      {liveEnabled ? (
        <div className="shell-provisioning" aria-label="WP15 live READ acceptance" aria-busy={liveWorking}>
          <strong>WP15 deferred live acceptance</strong>
          <p className="shell-caption">Acceptance-only loopback surface. Это не Portfolio Dashboard: приватные значения живут только в текущем browser challenge и не попадают в durable evidence.</p>
          {liveView ? (
            <div className="shell-account-selection">
              <dl className="shell-definition-list">
                <div><dt>Счёт</dt><dd>{liveView.masked_account} · {liveView.access_level}</dd></div>
                <div><dt>Portfolio total</dt><dd>{liveView.portfolio_total} {liveView.portfolio_currency}</dd></div>
                <div><dt>Sample</dt><dd>{liveView.sample.label}</dd></div>
                <div><dt>Quantity</dt><dd>{liveView.sample.quantity}</dd></div>
                <div><dt>Unit price</dt><dd>{liveView.sample.unit_price} {liveView.sample.currency}</dd></div>
                <div><dt>Sample value</dt><dd>{liveView.sample.market_value} {liveView.sample.currency}</dd></div>
                <div><dt>Freshness</dt><dd>{liveView.freshness_state} · age {liveView.age_seconds}s · {liveView.retrieved_at}</dd></div>
              </dl>
              <label className="shell-checkbox"><input type="checkbox" checked={liveConfirmation.intended_account_confirmed} onChange={(event) => setLiveConfirmation((value) => ({ ...value, intended_account_confirmed: event.target.checked }))} /><span>Masked account — именно тот счёт, который я выбрал в T-Invest.</span></label>
              <label className="shell-checkbox"><input type="checkbox" checked={liveConfirmation.portfolio_summary_parity} onChange={(event) => setLiveConfirmation((value) => ({ ...value, portfolio_summary_parity: event.target.checked }))} /><span>Portfolio total/currency совпадает с T-Invest.</span></label>
              <label className="shell-checkbox"><input type="checkbox" checked={liveConfirmation.sample_position_quantity_value_parity} onChange={(event) => setLiveConfirmation((value) => ({ ...value, sample_position_quantity_value_parity: event.target.checked }))} /><span>Sample position quantity/value совпадает с T-Invest.</span></label>
              <label className="shell-checkbox"><input type="checkbox" checked={liveConfirmation.freshness_confirmed} onChange={(event) => setLiveConfirmation((value) => ({ ...value, freshness_confirmed: event.target.checked }))} /><span>Snapshot свежий на момент сравнения.</span></label>
              <div className="shell-stack">
                <Button disabled={liveWorking || !Object.values(liveConfirmation).every(Boolean)} onClick={() => void confirmLive()}>Подтвердить live acceptance</Button>
                <Button variant="secondary" disabled={liveWorking} onClick={() => void cancelLive()}>Отмена</Button>
              </div>
            </div>
          ) : null}
          {liveMessage ? <p role="status">{liveMessage}</p> : null}
        </div>
      ) : null}

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
            disabled={working || preview !== null || liveWorking || liveView !== null}
          />
        </label>
        {!preview ? (
          <Button variant="secondary" disabled={working || liveWorking || liveView !== null || token.trim().length === 0} onClick={() => void validateToken()}>
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
        <p className="shell-caption">Token не сохраняется в browser storage и после проверки очищается из формы. TRADE credential не принимается.</p>
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
