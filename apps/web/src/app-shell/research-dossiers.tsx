import { useEffect, useMemo, useState } from "react";
import { Button, Card, StatePanel } from "../design-system/components";

type ResearchState = "EMPTY" | "PARTIAL" | "STALE" | "READY";
type FactFreshness = "FRESH" | "STALE" | "UNKNOWN";
type FactConfidence = "DECISION_GRADE" | "LIMITED" | "CONTEXT_ONLY" | "REJECTED";

type SourceView = {
  provider: string;
  class: string;
  authority: string;
  source_id: string;
  location: string | null;
  location_rejected: boolean;
  retrieved_at: string;
  published_at: string | null;
  effective_at: string | null;
};

type ResearchFactView = {
  record_sha256: string;
  fact_type: string;
  fact_key: string;
  value: { type: string; canonical: string; currency: string | null };
  use: string;
  confidence: FactConfidence;
  freshness: FactFreshness;
  source: SourceView;
  contradiction: {
    severity: string;
    comparison_period: string | null;
    distinct_values: string[];
  } | null;
};

type ResearchDossierView = {
  cache_key: string;
  source_identity: string;
  content_sha256: string;
  cache_retrieved_at: string;
  cache_expires_at: string;
  cache_freshness: "FRESH" | "STALE";
  dossier_sha256: string;
  assessed_at: string;
  state: "PARTIAL" | "STALE" | "READY";
  decision_ready: boolean;
  strong_recommendation_allowed: boolean;
  security: {
    instrument_id: string | null;
    instrument_uid: string;
    instrument_type: string;
    ticker: string | null;
    name: string | null;
    figi: string | null;
    isin: string | null;
  };
  facts: ResearchFactView[];
  contradictions: Array<{
    fact_key: string;
    comparison_period: string | null;
    severity: string;
    record_sha256s: string[];
    distinct_values: string[];
    unresolved: boolean;
  }>;
  unknowns: Array<{
    requirement_id: string;
    fact_type: string;
    importance: string;
    reason: string;
  }>;
  timeline: Array<{
    record_sha256: string;
    fact_type: string;
    fact_key: string;
    value: string;
    currency: string | null;
    at: string;
    source_label: string;
    confidence: FactConfidence;
  }>;
  links: { credit: string; fund: string | null };
  ai_summary: {
    state: "NOT_AVAILABLE" | "AVAILABLE";
    non_authoritative: true;
    text: string | null;
    generated_at: string | null;
    model_label: string | null;
    confidence: string | null;
  };
};

type ResearchDossierPayload = {
  schema_version: "1.0.0";
  generated_at: string;
  state: ResearchState;
  truncated: boolean;
  invalid_dossier_count: number;
  duplicate_dossier_count: number;
  dossiers: ResearchDossierView[];
};

async function readResearchDossiers(): Promise<ResearchDossierPayload> {
  const response = await fetch("/api/v10/web/research-dossiers", {
    credentials: "same-origin",
    cache: "no-store",
  });
  if (!response.ok) throw new Error(`RESEARCH_DOSSIER_API_${response.status}`);
  return (await response.json()) as ResearchDossierPayload;
}

function timestamp(value: string | null): string {
  if (!value) return "не указано";
  const parsed = new Date(value);
  return Number.isNaN(parsed.valueOf()) ? value : parsed.toLocaleString("ru-RU");
}

function shortIdentity(value: string | null): string {
  if (!value) return "не указано";
  return value.length <= 30 ? value : `${value.slice(0, 16)}…${value.slice(-10)}`;
}

function factValue(fact: ResearchFactView): string {
  return fact.value.currency ? `${fact.value.canonical} ${fact.value.currency}` : fact.value.canonical;
}

function SourceFact({ fact }: { fact: ResearchFactView }) {
  return (
    <article className="research-fact" data-origin="canonical-source-fact">
      <header className="research-fact__header">
        <div>
          <p className="shell-eyebrow">SOURCE FACT · {fact.fact_type}</p>
          <h3>{fact.fact_key}</h3>
        </div>
        <div className="research-chip-row" aria-label="Fact state">
          <span className="research-chip">{fact.use}</span>
          <span className="research-chip">{fact.confidence}</span>
          <span className="research-chip">{fact.freshness}</span>
        </div>
      </header>
      <p className="research-fact__value">{factValue(fact)}</p>
      <dl className="research-definition-list">
        <div><dt>Source</dt><dd>{fact.source.provider} · {fact.source.class} · {fact.source.authority}</dd></div>
        <div><dt>Published</dt><dd>{timestamp(fact.source.published_at)}</dd></div>
        <div><dt>Retrieved</dt><dd>{timestamp(fact.source.retrieved_at)}</dd></div>
        <div><dt>Effective</dt><dd>{timestamp(fact.source.effective_at)}</dd></div>
        <div><dt>Evidence hash</dt><dd><code>{shortIdentity(fact.record_sha256)}</code></dd></div>
      </dl>
      {fact.source.location ? (
        <a className="research-source-link" href={fact.source.location} target="_blank" rel="noreferrer noopener">Открыть источник</a>
      ) : fact.source.location_rejected ? (
        <p className="shell-caption">Source location отклонён Web allowlist; факт остаётся привязан к canonical evidence metadata.</p>
      ) : null}
      {fact.contradiction ? (
        <StatePanel kind="warning" title={`Contradiction · ${fact.contradiction.severity.toUpperCase()}`}>
          Для этого факта есть несовместимые decision-grade значения. UI не выбирает «правильное» значение сам.
        </StatePanel>
      ) : null}
    </article>
  );
}

function AiSummary({ dossier }: { dossier: ResearchDossierView }) {
  const summary = dossier.ai_summary;
  return (
    <section className="research-ai-zone" data-origin="ai-inference" aria-labelledby={`ai-${dossier.dossier_sha256}`}>
      <div className="research-ai-zone__header">
        <div>
          <p className="shell-eyebrow">AI / INFERENCE · NON-AUTHORITATIVE</p>
          <h3 id={`ai-${dossier.dossier_sha256}`}>AI summary</h3>
        </div>
        <span className="research-chip">НЕ ИСТОЧНИК ФАКТОВ</span>
      </div>
      {summary.state === "AVAILABLE" && summary.text ? (
        <>
          <p className="research-ai-zone__text">{summary.text}</p>
          <dl className="research-definition-list">
            <div><dt>Model</dt><dd>{summary.model_label ?? "не указано"}</dd></div>
            <div><dt>Generated</dt><dd>{timestamp(summary.generated_at)}</dd></div>
            <div><dt>Confidence</dt><dd>{summary.confidence ?? "UNKNOWN"}</dd></div>
          </dl>
        </>
      ) : (
        <StatePanel kind="empty" title="AI summary пока отсутствует">
          WP20 не запускает Block G вне очереди. Canonical evidence выше остаётся полным источником истины для этого экрана.
        </StatePanel>
      )}
      <p className="shell-caption">AI может интерпретировать evidence, но не становится canonical financial truth и не заменяет source provenance.</p>
    </section>
  );
}

function DossierCard({ dossier }: { dossier: ResearchDossierView }) {
  const title = dossier.security.ticker ?? dossier.security.name ?? shortIdentity(dossier.security.instrument_uid);
  return (
    <article className="research-dossier">
      <header className="research-dossier__header">
        <div>
          <p className="shell-eyebrow">RESEARCH DOSSIER · CANONICAL EVIDENCE</p>
          <h2>{title}</h2>
          <p className="shell-muted">{dossier.security.name ?? "Название инструмента не указано"}</p>
        </div>
        <div className="research-chip-row">
          <span className="research-chip">{dossier.state}</span>
          <span className="research-chip">CACHE {dossier.cache_freshness}</span>
          <span className="research-chip">{dossier.decision_ready ? "DECISION READY" : "NOT READY"}</span>
        </div>
      </header>

      <div className="research-identity-grid">
        <Card title="Security identity">
          <dl className="research-definition-list">
            <div><dt>Instrument UID</dt><dd><code>{shortIdentity(dossier.security.instrument_uid)}</code></dd></div>
            <div><dt>Type</dt><dd>{dossier.security.instrument_type}</dd></div>
            <div><dt>FIGI</dt><dd>{dossier.security.figi ?? "—"}</dd></div>
            <div><dt>ISIN</dt><dd>{dossier.security.isin ?? "—"}</dd></div>
          </dl>
        </Card>
        <Card title="Research state">
          <dl className="research-definition-list">
            <div><dt>Assessed</dt><dd>{timestamp(dossier.assessed_at)}</dd></div>
            <div><dt>Cache expires</dt><dd>{timestamp(dossier.cache_expires_at)}</dd></div>
            <div><dt>Coverage gaps</dt><dd>{dossier.unknowns.length}</dd></div>
            <div><dt>Contradictions</dt><dd>{dossier.contradictions.length}</dd></div>
          </dl>
        </Card>
      </div>

      <nav className="research-links" aria-label="Связанные модели">
        <a href={dossier.links.credit}>Credit / Risk</a>
        {dossier.links.fund ? <a href={dossier.links.fund}>Fund / Assets</a> : null}
      </nav>

      {dossier.state === "STALE" ? (
        <StatePanel kind="warning" title="Research dossier STALE">Cache expiry достигнут. Старые факты не маскируются как свежие.</StatePanel>
      ) : null}
      {dossier.unknowns.length ? (
        <section className="research-section" data-origin="canonical-unknowns">
          <h3>Unknowns / coverage gaps</h3>
          <ul className="research-unknown-list">
            {dossier.unknowns.map((gap) => (
              <li key={gap.requirement_id}><strong>{gap.importance}</strong><span>{gap.fact_type} · {gap.reason}</span><code>{gap.requirement_id}</code></li>
            ))}
          </ul>
        </section>
      ) : null}

      {dossier.contradictions.length ? (
        <section className="research-section" data-origin="canonical-contradictions">
          <h3>Contradictions</h3>
          <div className="research-contradiction-list">
            {dossier.contradictions.map((item) => (
              <div className="research-contradiction" key={`${item.fact_key}-${item.comparison_period ?? "none"}`}>
                <strong>{item.severity.toUpperCase()} · {item.fact_key}</strong>
                <span>{item.distinct_values.join(" ↔ ")}</span>
                <small>Unresolved: {item.unresolved ? "YES" : "NO"} · evidence records: {item.record_sha256s.length}</small>
              </div>
            ))}
          </div>
        </section>
      ) : null}

      <section className="research-section" data-origin="canonical-source-facts">
        <div className="research-section__heading"><div><p className="shell-eyebrow">CANONICAL</p><h3>Structured facts + provenance</h3></div><span>{dossier.facts.length} fact(s)</span></div>
        {dossier.facts.length ? <div className="research-fact-list">{dossier.facts.map((fact) => <SourceFact key={fact.record_sha256} fact={fact} />)}</div> : <StatePanel kind="empty" title="Structured facts отсутствуют">Coverage state выше остаётся authoritative.</StatePanel>}
      </section>

      <section className="research-section" data-origin="canonical-event-timeline">
        <h3>Event timeline</h3>
        {dossier.timeline.length ? (
          <ol className="research-timeline">
            {dossier.timeline.map((event) => (
              <li key={event.record_sha256}>
                <time>{timestamp(event.at)}</time>
                <div><strong>{event.fact_type} · {event.fact_key}</strong><span>{event.value}{event.currency ? ` ${event.currency}` : ""}</span><small>{event.source_label} · {event.confidence}</small></div>
              </li>
            ))}
          </ol>
        ) : <StatePanel kind="empty" title="Event timeline пуст">Нет canonical event-type facts для этого dossier.</StatePanel>}
      </section>

      <AiSummary dossier={dossier} />
      <p className="shell-caption">Dossier hash: {shortIdentity(dossier.dossier_sha256)} · source identity: {dossier.source_identity}</p>
    </article>
  );
}

export function ResearchDossiersPage() {
  const [payload, setPayload] = useState<ResearchDossierPayload | null>(null);
  const [loading, setLoading] = useState(true);
  const [unavailable, setUnavailable] = useState(false);

  async function refresh() {
    setLoading(true);
    try {
      setPayload(await readResearchDossiers());
      setUnavailable(false);
    } catch {
      setUnavailable(true);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { void refresh(); }, []);
  const factCount = useMemo(() => payload?.dossiers.reduce((total, dossier) => total + dossier.facts.length, 0) ?? 0, [payload]);

  return (
    <section className="shell-page research-page" aria-labelledby="page-title">
      <div className="shell-page__heading research-page__heading">
        <div>
          <p className="shell-eyebrow">RESEARCH / DOSSIERS</p>
          <h1 id="page-title">Research Dossier</h1>
          <p className="shell-muted">Факты, provenance, freshness, contradictions и unknowns показаны отдельно от любой AI-интерпретации.</p>
        </div>
        <Button variant="secondary" disabled={loading} onClick={() => void refresh()}>{loading ? "Обновление…" : "Обновить"}</Button>
      </div>

      {unavailable ? (
        <StatePanel kind="error" title="Research API недоступен">Пустой success не подставлен. Evidence state неизвестен до успешного read.</StatePanel>
      ) : loading && payload === null ? (
        <p role="status" className="shell-muted">Загрузка canonical research evidence…</p>
      ) : payload?.state === "EMPTY" ? (
        <StatePanel kind="empty" title="Research dossiers ещё не сохранены">WP20 не запускает Research Collector/AI runtime вне порядка Master Plan.</StatePanel>
      ) : payload ? (
        <>
          <div className="research-metrics" aria-label="Research summary">
            <Card title="Dossiers"><strong>{payload.dossiers.length}</strong></Card>
            <Card title="Facts"><strong>{factCount}</strong></Card>
            <Card title="Invalid"><strong>{payload.invalid_dossier_count}</strong></Card>
            <Card title="Duplicates"><strong>{payload.duplicate_dossier_count}</strong></Card>
          </div>
          {payload.state !== "READY" ? (
            <StatePanel kind="warning" title={`Research view ${payload.state}`}>
              {payload.truncated ? "Bounded read limit достигнут. " : ""}Stale, missing, contradictory или invalid evidence не скрывается.
            </StatePanel>
          ) : null}
          <p className="shell-caption">Generated: {timestamp(payload.generated_at)} · source facts и AI/inference имеют разные origin markers и presentation zones.</p>
          <div className="research-dossier-list">{payload.dossiers.map((dossier) => <DossierCard key={dossier.dossier_sha256} dossier={dossier} />)}</div>
        </>
      ) : null}
    </section>
  );
}
