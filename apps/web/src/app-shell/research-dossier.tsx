import { useEffect, useState } from "react";
import { Card, Skeleton, StatePanel } from "../design-system/components";
import { readResearchDossiers } from "./research-dossier-api";
import type {
  ResearchDossierCollectionView,
  ResearchDossierView,
  ResearchFactView,
} from "./research-dossier-contracts";

function displayTime(value: string | null): string {
  if (!value) return "не указано";
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? value : parsed.toLocaleString("ru-RU");
}

function FactCard({ fact }: { fact: ResearchFactView }) {
  const sourceName = `${fact.source.provider} · ${fact.source.source_class} · ${fact.source.authority}`;
  return (
    <article className="research-fact" data-authority="source-evidence">
      <div className="research-fact__heading">
        <div>
          <span className="research-kicker">SOURCE FACT</span>
          <h4>{fact.fact_key}</h4>
        </div>
        <div className="research-fact__badges">
          <span className="research-chip" data-state={fact.freshness}>{fact.freshness}</span>
          <span className="research-chip" data-confidence={fact.confidence_state}>{fact.confidence_state}</span>
        </div>
      </div>
      <p className="research-fact__value">{fact.value.canonical}{fact.value.currency ? ` ${fact.value.currency}` : ""}</p>
      <dl className="research-meta-grid">
        <div><dt>Источник</dt><dd>{sourceName}</dd></div>
        <div><dt>Получено</dt><dd><time dateTime={fact.source.retrieved_at}>{displayTime(fact.source.retrieved_at)}</time></dd></div>
        <div><dt>Опубликовано</dt><dd>{fact.source.published_at ? <time dateTime={fact.source.published_at}>{displayTime(fact.source.published_at)}</time> : "не указано"}</dd></div>
        <div><dt>Effective</dt><dd>{fact.source.effective_at ? <time dateTime={fact.source.effective_at}>{displayTime(fact.source.effective_at)}</time> : "не указано"}</dd></div>
        <div><dt>Использование</dt><dd>{fact.evidence_use}</dd></div>
        <div><dt>Материальность записи</dt><dd>{fact.material ? "material" : "context"}</dd></div>
      </dl>
      <div className="research-source-location">
        <strong>Source location: </strong>
        {fact.source.href ? (
          <a href={fact.source.href} target="_blank" rel="noreferrer">{fact.source.location_text ?? fact.source.href}</a>
        ) : (
          <span>{fact.source.location_text ?? "не указано"}</span>
        )}
      </div>
    </article>
  );
}

function DossierCard({ dossier, index }: { dossier: ResearchDossierView; index: number }) {
  const factsTitle = `research-facts-${index}`;
  const aiTitle = `research-ai-${index}`;
  return (
    <article className="research-dossier" aria-labelledby={`research-dossier-${index}`}>
      <header className="research-dossier__header">
        <div>
          <span className="research-kicker">CANONICAL DOSSIER</span>
          <h2 id={`research-dossier-${index}`}>{dossier.identity.instrument_type} · {dossier.identity.instrument_uid}</h2>
          <p>Оценено: <time dateTime={dossier.assessed_at}>{displayTime(dossier.assessed_at)}</time></p>
        </div>
        <span className="research-state" data-state={dossier.state}>{dossier.state}</span>
      </header>

      <section className="research-identity" aria-label="Идентичность исследования">
        <dl className="research-meta-grid">
          <div><dt>Candidate</dt><dd>{dossier.identity.candidate_id}</dd></div>
          <div><dt>Issuer identity</dt><dd>{dossier.identity.issuer_identity_state}</dd></div>
          <div><dt>Decision ready</dt><dd>{dossier.decision_ready ? "YES" : "NO"}</dd></div>
          <div><dt>Strong recommendation</dt><dd>{dossier.strong_recommendation_allowed ? "ALLOWED" : "BLOCKED"}</dd></div>
        </dl>
      </section>

      {dossier.contradictions.length ? (
        <section className="research-alert-panel" aria-label="Противоречия evidence">
          <h3>Противоречия</h3>
          {dossier.contradictions.map((item, contradictionIndex) => (
            <div key={`${item.fact_key}-${contradictionIndex}`} className="research-contradiction">
              <strong>{item.fact_key} · {item.severity}</strong>
              <span>{item.unresolved ? "UNRESOLVED" : "RESOLVED"}</span>
              <p>{item.distinct_values.join(" ↔ ")}</p>
            </div>
          ))}
        </section>
      ) : null}

      {dossier.unknowns.length ? (
        <section className="research-unknown-panel" aria-label="Неизвестные и пробелы evidence">
          <h3>Неизвестно / coverage gaps</h3>
          <ul>
            {dossier.unknowns.map((item) => (
              <li key={item.requirement_id}><strong>{item.fact_type}</strong> · {item.importance} · {item.reason}</li>
            ))}
          </ul>
        </section>
      ) : null}

      <section aria-labelledby={factsTitle}>
        <div className="research-section-heading">
          <div><span className="research-kicker">AUTHORITATIVE EVIDENCE CHANNEL</span><h3 id={factsTitle}>Факты из источников</h3></div>
          <span>{dossier.counts.facts} facts</span>
        </div>
        <div className="research-facts">
          {dossier.facts.length ? dossier.facts.map((fact) => <FactCard key={fact.record_sha256} fact={fact} />) : <StatePanel kind="empty" title="Нет source facts">Канонические факты пока не представлены.</StatePanel>}
        </div>
      </section>

      <section className="research-timeline" aria-label="Research event timeline">
        <h3>Event timeline</h3>
        <ol>
          {dossier.timeline.map((item) => (
            <li key={item.record_sha256}><time dateTime={item.event_at}>{displayTime(item.event_at)}</time><strong>{item.fact_key}</strong><span>{item.source_class}</span></li>
          ))}
        </ol>
      </section>

      <aside className="research-ai" data-authority="ai-non-authoritative" aria-labelledby={aiTitle}>
        <div className="research-ai__heading">
          <div><span className="research-kicker">AI / INFERENCE CHANNEL</span><h3 id={aiTitle}>AI-generated summary</h3></div>
          <span className="research-ai__badge">НЕ ИСТОЧНИК ФАКТА</span>
        </div>
        {dossier.ai_summary.state === "AVAILABLE" ? (
          <>
            <p className="research-ai__notice">Non-authoritative interpretation. Канонические факты находятся только в секции «Факты из источников» выше.</p>
            <p className="research-ai__text">{dossier.ai_summary.text}</p>
            <small>Сгенерировано: <time dateTime={dossier.ai_summary.generated_at}>{displayTime(dossier.ai_summary.generated_at)}</time></small>
          </>
        ) : (
          <p className="research-ai__notice">AI summary недоступен. WP20 не запускает Block G AI runtime.</p>
        )}
      </aside>

      <section className="research-related" aria-label="Связанные Credit и Fund материалы">
        <h3>Credit / Fund links</h3>
        {dossier.related_links.length ? (
          <ul>{dossier.related_links.map((link) => <li key={`${link.kind}-${link.path}`}><a href={link.path}>{link.label}</a><span>{link.kind}</span></li>)}</ul>
        ) : <p>Связанные аналитические материалы пока не опубликованы.</p>}
      </section>
    </article>
  );
}

export function ResearchDossierPage() {
  const [view, setView] = useState<ResearchDossierCollectionView | null>(null);
  const [unavailable, setUnavailable] = useState(false);

  useEffect(() => {
    let active = true;
    void readResearchDossiers()
      .then((value) => {
        if (!active) return;
        setView(value);
        setUnavailable(false);
      })
      .catch(() => {
        if (!active) return;
        setView(null);
        setUnavailable(true);
      });
    return () => { active = false; };
  }, []);

  if (unavailable) {
    return <StatePanel kind="error" title="Research API недоступен">Источник dossier view не ответил. Факты не подменяются пустым успешным состоянием.</StatePanel>;
  }
  if (view === null) return <Skeleton label="Загрузка Research Dossier" />;

  return (
    <div className="research-page">
      <header className="research-page__header">
        <div><span className="shell-eyebrow">WP20 · RESEARCH DOSSIER</span><h1>Research: provenance before interpretation</h1><p>Источники, время, freshness, contradictions и unknowns отображаются отдельно от AI/inference.</p></div>
        <div className="research-page__counts"><strong>{view.counts.dossiers}</strong><span>dossiers</span><strong>{view.counts.partial}</strong><span>partial</span></div>
      </header>

      <Card title="Правило доверия">
        <p className="research-trust-rule"><strong>SOURCE FACT</strong> — канонический evidence channel. <strong>AI / INFERENCE</strong> — отдельная non-authoritative интерпретация и никогда не заменяет source fact.</p>
      </Card>

      {view.state === "EMPTY" ? (
        <StatePanel kind="empty" title="Research dossiers пока отсутствуют">WP20 UI готов, но Block G producer ещё не запущен. Никакие факты или AI summary не фабрикуются.</StatePanel>
      ) : (
        <div className="research-dossiers">{view.dossiers.map((dossier, index) => <DossierCard key={dossier.dossier_sha256} dossier={dossier} index={index} />)}</div>
      )}
    </div>
  );
}
