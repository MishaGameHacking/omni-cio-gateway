import "./system-admin.css";
import { useEffect, useState } from "react";
import { Card, StatePanel, StatusBadge } from "../design-system/components";
import type { OperationalState } from "../design-system/contracts";
import { readSystemStatus } from "./system-api";
import type { SystemStatusView } from "./system-contracts";

function Value({ value }: { value: string | number | null | undefined }) {
  return <>{value === null || value === undefined || value === "" ? "UNAVAILABLE" : value}</>;
}

function BoolState({ value }: { value: boolean }) {
  return <strong>{value ? "ENABLED" : "DISABLED"}</strong>;
}

export function SystemAdminPage({
  healthState,
  freshness,
}: {
  healthState: OperationalState;
  freshness: string;
}) {
  const [status, setStatus] = useState<SystemStatusView | null>(null);
  const [unavailable, setUnavailable] = useState(false);

  useEffect(() => {
    let active = true;
    void readSystemStatus()
      .then((value) => {
        if (!active) return;
        setStatus(value);
        setUnavailable(false);
      })
      .catch(() => {
        if (!active) return;
        setStatus(null);
        setUnavailable(true);
      });
    return () => {
      active = false;
    };
  }, []);

  const version = __OMNI_WEB_VERSION__;

  return (
    <section className="shell-page system-admin" aria-labelledby="page-title">
      <div className="shell-page__heading">
        <p className="shell-eyebrow">SYSTEM / ADMIN</p>
        <h1 id="page-title">Система</h1>
        <p className="shell-muted">
          OWNER-only read-only diagnostics. Никакой broker-write или Real execution authority здесь нет.
        </p>
      </div>

      {unavailable ? (
        <StatePanel kind="warning" title="System diagnostics API недоступен">
          Shell остаётся доступным. Неизвестное состояние не преобразуется в READY.
        </StatePanel>
      ) : null}

      <div className="system-admin__summary">
        <Card title="Operational state">
          <div className="shell-stack">
            <StatusBadge state={status?.state ?? healthState} />
            <span className="shell-muted">
              Freshness: {freshness} · snapshot <Value value={status?.generated_at} />
            </span>
          </div>
        </Card>
        <Card title="Release / deploy">
          <dl className="shell-definition-list">
            <div>
              <dt>Web version</dt>
              <dd>{version}</dd>
            </div>
            <div>
              <dt>Runtime release</dt>
              <dd><Value value={status?.release.release} /></dd>
            </div>
            <div>
              <dt>Git SHA</dt>
              <dd><code><Value value={status?.release.git_sha} /></code></dd>
            </div>
            <div>
              <dt>Last deploy</dt>
              <dd><Value value={status?.release.last_deploy_at} /></dd>
            </div>
            <div>
              <dt>Web artifact mtime</dt>
              <dd><Value value={status?.release.web_artifact_at} /></dd>
            </div>
          </dl>
        </Card>
      </div>

      <Card title="Service health">
        {status ? (
          <div className="system-admin__services">
            {status.services.map((service) => (
              <article className="system-admin__service" key={service.id}>
                <div>
                  <strong>{service.label}</strong>
                  <span className="shell-caption">{service.availability}</span>
                </div>
                <StatusBadge state={service.state} />
                <p className="shell-muted">{service.detail}</p>
                {service.observed_at ? <time>{service.observed_at}</time> : null}
              </article>
            ))}
          </div>
        ) : (
          <p className="shell-muted">Service observations unavailable.</p>
        )}
      </Card>

      <div className="shell-grid shell-grid--two">
        <Card title="Database / migrations">
          <dl className="shell-definition-list">
            <div><dt>State</dt><dd><Value value={status?.database.state} /></dd></div>
            <div><dt>Current</dt><dd><Value value={status?.database.current_migration} /></dd></div>
            <div><dt>Expected</dt><dd><Value value={status?.database.expected_migration} /></dd></div>
            <div><dt>Exact series</dt><dd>{status ? String(status.database.exact_migration_state) : "UNAVAILABLE"}</dd></div>
          </dl>
        </Card>

        <Card title="Backup / recovery">
          <dl className="shell-definition-list">
            <div><dt>State</dt><dd><Value value={status?.backup.state} /></dd></div>
            <div><dt>Last success</dt><dd><Value value={status?.backup.last_success_at} /></dd></div>
            <div><dt>RPO</dt><dd>{status ? `${status.backup.rpo_minutes} min` : "UNAVAILABLE"}</dd></div>
            <div><dt>RTO</dt><dd>{status ? `${status.backup.rto_minutes} min` : "UNAVAILABLE"}</dd></div>
          </dl>
        </Card>

        <Card title="Resources">
          <dl className="shell-definition-list">
            <div><dt>Disk state</dt><dd><Value value={status?.resources.disk.state} /></dd></div>
            <div><dt>Disk free</dt><dd>{status?.resources.disk.free_gib === null || status?.resources.disk.free_gib === undefined ? "UNAVAILABLE" : `${status.resources.disk.free_gib} GiB`}</dd></div>
            <div><dt>Disk free %</dt><dd>{status?.resources.disk.free_percent === null || status?.resources.disk.free_percent === undefined ? "UNAVAILABLE" : `${status.resources.disk.free_percent}%`}</dd></div>
            <div><dt>GPU temperature</dt><dd>{status?.resources.temperature.gpu_c === null || status?.resources.temperature.gpu_c === undefined ? "UNAVAILABLE" : `${status.resources.temperature.gpu_c} °C`}</dd></div>
            <div><dt>Temperature state</dt><dd><Value value={status?.resources.temperature.state} /></dd></div>
          </dl>
        </Card>

        <Card title="Safety / kill switches">
          <dl className="shell-definition-list">
            <div><dt>Mode</dt><dd><Value value={status?.safety.mode} /></dd></div>
            <div><dt>Real trading</dt><dd>{status ? <BoolState value={status.safety.real_execution_enabled} /> : "UNAVAILABLE"}</dd></div>
            <div><dt>Trading methods</dt><dd>{status ? <BoolState value={status.safety.trading_methods} /> : "UNAVAILABLE"}</dd></div>
            <div><dt>Broker write authority</dt><dd>{status ? <BoolState value={status.safety.broker_write_authority} /> : "UNAVAILABLE"}</dd></div>
            <div><dt>Public ingress</dt><dd>{status ? <BoolState value={status.safety.public_ingress} /> : "UNAVAILABLE"}</dd></div>
            <div><dt>Watchtower switch</dt><dd>{status ? <BoolState value={status.safety.watchtower_enabled} /> : "UNAVAILABLE"}</dd></div>
          </dl>
          <p className="shell-caption">WP22 exposes switch state only. It does not add a mutation endpoint.</p>
        </Card>
      </div>

      <div className="shell-grid shell-grid--two">
        <Card title="Recent jobs">
          {status && status.recent_jobs.length ? (
            <div className="system-admin__activity">
              {status.recent_jobs.map((job, index) => (
                <article key={`${job.job_type}-${job.observed_at ?? "unknown"}-${index}`}>
                  <strong>{job.job_type}</strong>
                  <span>{job.state} · attempt {job.attempts}/{job.max_attempts}</span>
                  <time>{job.observed_at ?? "UNAVAILABLE"}</time>
                </article>
              ))}
            </div>
          ) : (
            <p className="shell-muted">No durable job observations available.</p>
          )}
        </Card>

        <Card title="Recent sanitized errors">
          {status && status.recent_errors.length ? (
            <div className="system-admin__activity">
              {status.recent_errors.map((error, index) => (
                <article key={`${error.job_type}-${error.observed_at ?? "unknown"}-${index}`}>
                  <strong>{error.job_type}</strong>
                  <span>{error.state} · {error.error_class}</span>
                  <time>{error.observed_at ?? "UNAVAILABLE"}</time>
                </article>
              ))}
            </div>
          ) : (
            <p className="shell-muted">No sanitized durable job errors.</p>
          )}
          <p className="shell-caption">Raw exception text, tokens, account identifiers and private payloads are never returned.</p>
        </Card>
      </div>
    </section>
  );
}
