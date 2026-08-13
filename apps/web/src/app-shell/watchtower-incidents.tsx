import { useEffect, useMemo, useState } from "react";
import { Button, Card, StatePanel } from "../design-system/components";

type IncidentFilter = "all" | "active" | "resolved" | "critical";
type IncidentSeverity = "info" | "warning" | "error" | "unknown";
type TimelineRow = { revision: number; state: "open" | "acknowledged" | "closed"; at: string; evidence_ids: string[] };
type EvidenceView = {
  evidence_id: string;
  source_kind: string;
  published_at: string | null;
  retrieved_at: string;
  local_received_at: string;
  payload_sha256: string;
  instrument: { ticker: string | null; name: string | null } | null;
  content_available: boolean;
  watchtower_alert_verified: boolean;
};
type WatchtowerIncidentView = {
  incident_id: string;
  opened_at: string;
  current_state: "open" | "acknowledged" | "closed";
  lifecycle_state: "ACTIVE" | "RESOLVED";
  severity: IncidentSeverity;
  critical: boolean;
  risk_impact: "OWNER_ATTENTION_REQUIRED" | "INFORMATIONAL" | "UNKNOWN";
  subject: string | null;
  message_code: string | null;
  requested_action: string | null;
  alert_effective_at: string | null;
  alert_metadata_state: "VERIFIED" | "MISSING" | "CONFLICT";
  dedup: { state: "VERIFIED" | "MISSING" | "CONFLICT"; fingerprint_sha256: string | null; reopened: boolean };
  timeline: TimelineRow[];
  evidence: EvidenceView[];
  links: { decisions: string[]; plans: string[] };
};
type WatchtowerIncidentPayload = {
  schema_version: "1.0.0";
  generated_at: string;
  state: "EMPTY" | "PARTIAL" | "READY";
  truncated: boolean;
  counts: { total: number; active: number; resolved: number; critical: number; reopened: number; missing_alert_metadata: number };
  incidents: WatchtowerIncidentView[];
};

async function readWatchtowerIncidents(): Promise<WatchtowerIncidentPayload> {
  const response = await fetch("/api/v10/web/watchtower-incidents", { credentials: "same-origin", cache: "no-store" });
  if (!response.ok) throw new Error(`WATCHTOWER_INCIDENT_API_${response.status}`);
  return (await response.json()) as WatchtowerIncidentPayload;
}

function timestamp(value: string | null): string {
  if (!value) return "не указано";
  const parsed = new Date(value);
  return Number.isNaN(parsed.valueOf()) ? value : parsed.toLocaleString("ru-RU");
}

function shortIdentity(value: string): string {
  return value.length <= 24 ? value : `${value.slice(0, 14)}…${value.slice(-8)}`;
}

function riskImpactLabel(value: WatchtowerIncidentView["risk_impact"]): string {
  if (value === "OWNER_ATTENTION_REQUIRED") return "Требуется внимание OWNER";
  if (value === "INFORMATIONAL") return "Информационный";
  return "Не определено";
}

function visible(incident: WatchtowerIncidentView, filter: IncidentFilter): boolean {
  if (filter === "active") return incident.lifecycle_state === "ACTIVE";
  if (filter === "resolved") return incident.lifecycle_state === "RESOLVED";
  if (filter === "critical") return incident.critical;
  return true;
}

function IncidentCard({ incident }: { incident: WatchtowerIncidentView }) {
  const lastTransition = incident.timeline.at(-1);
  const downstream = incident.links.decisions.length + incident.links.plans.length;
  return (
    <article className="watchtower-incident" data-severity={incident.severity}>
      <header className="watchtower-incident__header">
        <div><p className="shell-eyebrow">INCIDENT · {shortIdentity(incident.incident_id)}</p><h2>{incident.subject ?? "Субъект не верифицирован"}</h2></div>
        <div className="watchtower-incident__badges"><span className="watchtower-chip">{incident.severity.toUpperCase()}</span><span className="watchtower-chip">{incident.current_state.toUpperCase()}</span>{incident.dedup.reopened ? <span className="watchtower-chip">REOPENED</span> : null}</div>
      </header>
      <div className="watchtower-explain-grid">
        <div><span>Что произошло</span><strong>{incident.message_code ?? "Alert metadata отсутствует"}</strong></div>
        <div><span>Почему важно</span><strong>{riskImpactLabel(incident.risk_impact)} · {incident.severity.toUpperCase()}</strong></div>
        <div><span>Когда</span><strong>{timestamp(incident.alert_effective_at ?? incident.opened_at)}</strong></div>
        <div><span>Что сделала система</span><strong>{incident.requested_action ?? "Нет верифицированного действия"}</strong></div>
      </div>
      {incident.alert_metadata_state !== "VERIFIED" ? <StatePanel kind="warning" title={`Alert evidence: ${incident.alert_metadata_state}`}>Severity/subject/action не додумываются. Проверь evidence references и durable lifecycle.</StatePanel> : null}
      <div className="watchtower-section"><h3>Lifecycle timeline</h3><ol className="watchtower-timeline">{incident.timeline.map((row) => <li key={row.revision}><div><strong>rev {row.revision} · {row.state.toUpperCase()}</strong><span>{timestamp(row.at)}</span></div><small>Evidence: {row.evidence_ids.length ? row.evidence_ids.map(shortIdentity).join(", ") : "нет ссылок"}</small></li>)}</ol><p className="shell-caption">Текущее состояние: {incident.lifecycle_state}; последнее изменение: {timestamp(lastTransition?.at ?? null)}.</p></div>
      <div className="watchtower-section"><h3>Evidence</h3>{incident.evidence.length === 0 ? <StatePanel kind="warning" title="Evidence references отсутствуют">Причина инцидента не восстанавливается из canonical evidence.</StatePanel> : <div className="watchtower-evidence-list">{incident.evidence.map((evidence) => <div className="watchtower-evidence" key={evidence.evidence_id}><div><strong>{evidence.source_kind}</strong><span>{evidence.instrument?.ticker ?? evidence.instrument?.name ?? "portfolio/system"}</span></div><dl><div><dt>Evidence</dt><dd><code title={evidence.evidence_id}>{shortIdentity(evidence.evidence_id)}</code></dd></div><div><dt>Retrieved</dt><dd>{timestamp(evidence.retrieved_at)}</dd></div><div><dt>Published</dt><dd>{timestamp(evidence.published_at)}</dd></div><div><dt>Alert contract</dt><dd>{evidence.watchtower_alert_verified ? "VERIFIED" : evidence.content_available ? "INVALID / OTHER" : "MISSING"}</dd></div></dl></div>)}</div>}</div>
      <div className="watchtower-section"><h3>Dedup / downstream</h3><dl className="watchtower-definition-list"><div><dt>Dedup</dt><dd>{incident.dedup.state}</dd></div><div><dt>Fingerprint</dt><dd>{incident.dedup.fingerprint_sha256 ? <code>{shortIdentity(incident.dedup.fingerprint_sha256)}</code> : "нет единственного verified fingerprint"}</dd></div><div><dt>Reopened</dt><dd>{incident.dedup.reopened ? "YES — CLOSED → OPEN обнаружен" : "NO"}</dd></div><div><dt>Decision links</dt><dd>{incident.links.decisions.length ? incident.links.decisions.map(shortIdentity).join(", ") : "нет"}</dd></div><div><dt>Plan links</dt><dd>{incident.links.plans.length ? incident.links.plans.map(shortIdentity).join(", ") : "нет"}</dd></div></dl><p className="shell-caption">После detection: {downstream ? `${downstream} canonical Decision/Plan link(s) найдено` : "Decision/Plan link не создан или не принадлежит текущему owning contract"}.</p></div>
    </article>
  );
}

export function WatchtowerIncidentsPage() {
  const [payload, setPayload] = useState<WatchtowerIncidentPayload | null>(null);
  const [filter, setFilter] = useState<IncidentFilter>("active");
  const [loading, setLoading] = useState(true);
  const [unavailable, setUnavailable] = useState(false);
  async function refresh() {
    setLoading(true);
    try { setPayload(await readWatchtowerIncidents()); setUnavailable(false); } catch { setUnavailable(true); } finally { setLoading(false); }
  }
  useEffect(() => { void refresh(); }, []);
  const incidents = useMemo(() => payload?.incidents.filter((incident) => visible(incident, filter)) ?? [], [filter, payload]);
  return (
    <section className="shell-page watchtower-page" aria-labelledby="page-title">
      <div className="shell-page__heading watchtower-page__heading"><div><p className="shell-eyebrow">WATCHTOWER / INCIDENTS</p><h1 id="page-title">Инциденты</h1><p className="shell-muted">Каждый alert читается как проверяемый объект: что произошло, почему, когда и что система сделала после detection.</p></div><Button variant="secondary" disabled={loading} onClick={() => void refresh()}>{loading ? "Обновление…" : "Обновить"}</Button></div>
      {unavailable ? <StatePanel kind="error" title="Incident API недоступен">Пустой список не подставлен. Canonical incident state остаётся неизвестным до успешного read.</StatePanel> : loading && payload === null ? <p role="status" className="shell-muted">Загрузка canonical incident state…</p> : payload?.state === "EMPTY" ? <StatePanel kind="empty" title="Инцидентов нет">Canonical persistence не содержит incident records для текущего tenant.</StatePanel> : payload ? <>
        <div className="watchtower-metrics" aria-label="Сводка инцидентов"><Card title="Активные"><strong>{payload.counts.active}</strong></Card><Card title="Критические"><strong>{payload.counts.critical}</strong></Card><Card title="Решённые"><strong>{payload.counts.resolved}</strong></Card><Card title="Reopened"><strong>{payload.counts.reopened}</strong></Card></div>
        {payload.state === "PARTIAL" ? <StatePanel kind="warning" title="Incident view PARTIAL">{payload.truncated ? "Read limit достигнут. " : ""}{payload.counts.missing_alert_metadata} incident(s) не имеют единственного verified Watchtower alert metadata.</StatePanel> : null}
        <div className="watchtower-filters" role="group" aria-label="Фильтр инцидентов">{(["all", "active", "resolved", "critical"] as const).map((value) => <button className="watchtower-filter" aria-pressed={filter === value} data-active={filter === value} type="button" key={value} onClick={() => setFilter(value)}>{{ all: "Все", active: "Активные", resolved: "Решённые", critical: "Критические" }[value]}</button>)}</div>
        <p className="shell-caption">Generated: {timestamp(payload.generated_at)} · bounded read: {payload.counts.total}{payload.truncated ? "+" : ""}. Фильтры не меняют incident lifecycle.</p>
        {incidents.length ? <div className="watchtower-list">{incidents.map((incident) => <IncidentCard key={incident.incident_id} incident={incident} />)}</div> : <StatePanel kind="empty" title="Нет инцидентов в выбранном фильтре">Canonical records не изменялись.</StatePanel>}
      </> : null}
    </section>
  );
}
