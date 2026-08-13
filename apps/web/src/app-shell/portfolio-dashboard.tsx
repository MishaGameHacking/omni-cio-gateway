import { useCallback, useEffect, useMemo, useState } from "react";
import { Button, Card, Skeleton, StatePanel, StatusBadge } from "../design-system/components";
import { readPortfolioDashboard } from "./api";
import type { PortfolioAccountView, PortfolioDashboardView, PortfolioPositionView } from "./contracts";
import { formatDecimal } from "./decimal-format";

function money(value: { amount: string; currency: string } | null): string {
  return value ? `${formatDecimal(value.amount)} ${value.currency}` : "—";
}

function warningState(account: PortfolioAccountView): "READY" | "PARTIAL" | "STALE" | "DEGRADED" {
  if (account.freshness.state === "stale") return "STALE";
  if (account.unresolved_position_count > 0 || account.completeness !== "complete") return "PARTIAL";
  if (account.current_market.state === "UNAVAILABLE") return "DEGRADED";
  return "READY";
}

function IdentityValue({ value }: { value: string | null }) {
  return value ? <code>{value}</code> : <span>unavailable</span>;
}

function PositionTable({ positions, assetsMode, snapshotAsOf }: { positions: PortfolioPositionView[]; assetsMode: boolean; snapshotAsOf: string }) {
  if (positions.length === 0) {
    return <StatePanel kind="empty" title="Нормализованных позиций нет">Если broker snapshot частичный, причина остаётся видимой в предупреждениях ниже.</StatePanel>;
  }
  return (
    <div className="wp18-table-wrap">
      <table className="wp18-table">
        <thead>
          <tr>
            <th>Инструмент</th>
            <th>Issuer / sector / class</th>
            <th>Количество</th>
            <th>Broker value</th>
            <th>Вес*</th>
            <th>{assetsMode ? "Market quote" : "Current market"}</th>
            <th>As-of / источник</th>
          </tr>
        </thead>
        <tbody>
          {positions.map((position, index) => (
            <tr key={`${position.instrument.uid ?? position.instrument.ticker ?? position.instrument.name}-${index}`}>
              <td>
                <strong>{position.instrument.ticker ?? position.instrument.name}</strong>
                <span className="wp18-subline">{position.instrument.name}</span>
                <details className="wp18-position-detail">
                  <summary>Position detail</summary>
                  <dl className="shell-definition-list">
                    <div><dt>Type</dt><dd>{position.instrument.type}</dd></div>
                    <div><dt>Currency</dt><dd>{position.instrument.currency}</dd></div>
                    <div><dt>Class</dt><dd>{position.instrument.class_code ?? "unavailable"}</dd></div>
                    <div><dt>UID</dt><dd><IdentityValue value={position.instrument.uid} /></dd></div>
                    <div><dt>Position UID</dt><dd><IdentityValue value={position.instrument.position_uid} /></dd></div>
                    <div><dt>FIGI</dt><dd><IdentityValue value={position.instrument.figi} /></dd></div>
                    <div><dt>ISIN</dt><dd><IdentityValue value={position.instrument.isin} /></dd></div>
                    <div><dt>Research</dt><dd>link unavailable — no deterministic current-state WP18 binding</dd></div>
                    <div><dt>Incidents</dt><dd>link unavailable — no accepted instrument incident index in WP18</dd></div>
                  </dl>
                </details>
              </td>
              <td>
                <strong>{position.instrument.issuer ?? "issuer unavailable"}</strong>
                <span className="wp18-subline">{position.instrument.sector ?? "sector unavailable"} · {position.instrument.class_code ?? "class unavailable"}</span>
                <span className="wp18-subline">{position.instrument.classification_state}</span>
                <span className="wp18-subline">{position.instrument.classification_source} · {position.instrument.classification_as_of}</span>
              </td>
              <td>
                {formatDecimal(position.quantity_units, 8)}
                {position.blocked_units !== "0" ? <span className="wp18-subline">blocked {formatDecimal(position.blocked_units, 8)}</span> : null}
                <span className="wp18-subline">T-Invest GetPortfolio · {snapshotAsOf}</span>
              </td>
              <td>
                {money(position.broker_value)}
                <span className="wp18-subline">{position.broker_value ? `${position.broker_value.source} · ${position.broker_value.as_of}` : `unavailable · ${snapshotAsOf}`}</span>
              </td>
              <td>
                {position.weight_within_position_currency_pct ? `${formatDecimal(position.weight_within_position_currency_pct)}%` : "—"}
                <span className="wp18-subline">derived same-currency broker values · {snapshotAsOf}</span>
              </td>
              <td>
                {position.current_market_value ? money(position.current_market_value) : position.current_market_last_price ? `${formatDecimal(position.current_market_last_price.amount)} ${position.current_market_last_price.currency}` : "—"}
                <span className="wp18-subline">{position.market_conversion_state}</span>
                <span className="wp18-subline">{position.current_market_last_price ? `${position.current_market_last_price.source} · ${position.current_market_last_price.as_of}` : `quote unavailable · snapshot ${snapshotAsOf}`}</span>
              </td>
              <td>
                {position.broker_unit_price?.as_of ?? snapshotAsOf}
                <span className="wp18-subline">{position.broker_unit_price?.source ?? "T-Invest GetPortfolio"}</span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="shell-caption">* Вес считается только внутри нормализованных позиций одной валюты. Cross-currency aggregation без явного FX conversion запрещён.</p>
    </div>
  );
}

function AccountPanel({ account, assetsMode }: { account: PortfolioAccountView; assetsMode: boolean }) {
  const marketAsOf = account.current_market.retrieved_at ?? account.retrieved_at;
  return (
    <section className="wp18-account" aria-label={`Broker account ${account.masked_account}`}>
      <div className="wp18-account__heading">
        <div>
          <p className="shell-eyebrow">T-INVEST · READ ONLY</p>
          <h2>{account.masked_account}</h2>
          <p className="shell-caption">Connection state: <strong>{account.connection_state}</strong> · WP17 BrokerConnection</p>
          <p className="shell-caption">Broker snapshot: T-Invest GetPortfolio/GetPositions · {account.retrieved_at}</p>
        </div>
        <StatusBadge state={warningState(account)} />
      </div>
      <div className="wp18-kpis">
        <Card title="Broker portfolio total">
          <strong className="wp18-kpi">{money(account.portfolio_total)}</strong>
          <span className="wp18-subline">{account.portfolio_total ? `${account.portfolio_total.source} · ${account.portfolio_total.as_of}` : `unavailable · snapshot ${account.retrieved_at}`}</span>
        </Card>
        <Card title="Freshness">
          <strong className="wp18-kpi">{account.freshness.state.toUpperCase()}</strong>
          <span className="wp18-subline">age {formatDecimal(account.freshness.age_seconds)}s · evaluated {account.freshness.evaluated_at}</span>
          <span className="wp18-subline">source snapshot · {account.retrieved_at}</span>
        </Card>
        <Card title="Completeness">
          <strong className="wp18-kpi">{account.normalized_position_count}/{account.broker_position_count}</strong>
          <span className="wp18-subline">unresolved {account.unresolved_position_count}</span>
          <span className="wp18-subline">T-Invest GetPortfolio normalization · {account.retrieved_at}</span>
        </Card>
        <Card title="Current market">
          <strong className="wp18-kpi">{account.current_market.state}</strong>
          <span className="wp18-subline">missing {account.current_market.missing_instrument_count} · stale {account.current_market.stale_instrument_count}</span>
          <span className="wp18-subline">T-Invest GetLastPrices · {marketAsOf}</span>
        </Card>
      </div>

      {account.cash.length > 0 ? (
        <Card title="Cash">
          <div className="wp18-cash">
            {account.cash.map((row) => (
              <div key={row.currency}>
                <strong>{row.currency}</strong>
                <span>reported {formatDecimal(row.reported)}</span>
                <span>available {formatDecimal(row.available)}</span>
                <span>blocked {formatDecimal(row.blocked)}</span>
                <small>{row.source} · {row.as_of}</small>
              </div>
            ))}
          </div>
        </Card>
      ) : null}

      <Card title={assetsMode ? "Assets · sorted by broker value" : "Positions · top by broker value"}>
        <PositionTable positions={account.positions} assetsMode={assetsMode} snapshotAsOf={account.retrieved_at} />
      </Card>

      {account.concentration.length > 0 ? (
        <Card title="Concentration">
          <div className="wp18-concentration">
            {account.concentration.map((row) => (
              <div key={row.currency}>
                <strong>{row.currency}</strong>
                <span>Top 1: {formatDecimal(row.top_1_weight_pct)}%</span>
                <span>Top 5: {formatDecimal(row.top_5_weight_pct)}%</span>
                <small>{row.basis} · {account.retrieved_at}</small>
              </div>
            ))}
          </div>
        </Card>
      ) : null}

      {account.warnings.length > 0 ? (
        <div className="wp18-warning-list" role="status">
          {account.warnings.map((warning, index) => (
            <StatePanel key={`${warning.code}-${index}`} kind="warning" title={warning.code}>{warning.message}</StatePanel>
          ))}
        </div>
      ) : null}
    </section>
  );
}

export function PortfolioDashboardPage({ assetsMode = false }: { assetsMode?: boolean }) {
  const [dashboard, setDashboard] = useState<PortfolioDashboardView | null>(null);
  const [loading, setLoading] = useState(true);
  const [failed, setFailed] = useState(false);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const value = await readPortfolioDashboard();
      setDashboard(value);
      setFailed(false);
    } catch {
      setDashboard(null);
      setFailed(true);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void refresh(); }, [refresh]);

  const globalState = useMemo(() => {
    if (!dashboard) return "RECOVERING" as const;
    if (dashboard.state === "READY") return "READY" as const;
    if (dashboard.state === "PARTIAL") return "PARTIAL" as const;
    if (dashboard.state === "UNAVAILABLE") return "DEGRADED" as const;
    return "RECOVERING" as const;
  }, [dashboard]);

  return (
    <section className="shell-page wp18-dashboard" aria-labelledby="page-title">
      <div className="shell-page__heading wp18-page-heading">
        <div>
          <p className="shell-eyebrow">WP18 · PORTFOLIO DATA</p>
          <h1 id="page-title">{assetsMode ? "Активы" : "Портфель"}</h1>
          <p className="shell-muted">Current-on-demand READ snapshot. Страница читает данные при открытии и по явному Refresh; silent polling отсутствует. Partial/stale данные не скрываются.</p>
        </div>
        <div className="wp18-page-actions">
          <StatusBadge state={globalState} />
          <Button variant="secondary" disabled={loading} onClick={() => void refresh()}>{loading ? "Обновление…" : "Обновить"}</Button>
        </div>
      </div>

      {failed ? <StatePanel kind="error" title="Portfolio API недоступен">Нулевые значения не подставлены. Проверь broker connection/runtime state и повтори чтение.</StatePanel> : null}
      {!failed && loading && dashboard === null ? (
        <Card title="Читаем broker snapshot">
          <Skeleton label="Читаем broker snapshot" />
          <p className="shell-caption">READ-only запрос может включать instrument enrichment и current-market quotes.</p>
        </Card>
      ) : null}
      {dashboard?.state === "EMPTY" ? <StatePanel kind="empty" title="Broker connection не подключён">Добавь T-Invest READ connection в Настройки → Broker Connections.</StatePanel> : null}
      {dashboard?.warnings.map((warning, index) => <StatePanel key={`${warning.code}-${index}`} kind="warning" title={warning.code}>{warning.message}</StatePanel>)}
      {dashboard?.accounts.map((account) => <AccountPanel key={account.masked_account} account={account} assetsMode={assetsMode} />)}

      {dashboard ? (
        <Card title="Calculation policy">
          <dl className="shell-definition-list">
            <div><dt>Decimals</dt><dd>{dashboard.calculation_policy.decimal_transport}</dd></div>
            <div><dt>Cross-currency</dt><dd>{dashboard.calculation_policy.cross_currency_aggregation}</dd></div>
            <div><dt>Broker position value</dt><dd>{dashboard.calculation_policy.broker_position_value}</dd></div>
            <div><dt>Current market</dt><dd>{dashboard.calculation_policy.current_market_value}</dd></div>
            <div><dt>Generated</dt><dd>{dashboard.generated_at}</dd></div>
            <div><dt>Refresh</dt><dd>manual pull-to-refresh; no silent polling</dd></div>
          </dl>
        </Card>
      ) : null}
    </section>
  );
}
