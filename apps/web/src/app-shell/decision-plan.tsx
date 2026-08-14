import { useEffect, useMemo, useState } from "react";
import { Card, DataTable, StatePanel } from "../design-system/components";

type ViewState = "EMPTY" | "PARTIAL" | "READY" | "EXPIRED" | "INVALID";
type Focus = "risks" | "decisions" | "plans";

type EvidenceView = {
  evidence_id: string;
  kind: string;
  statement: string;
  source_schema: string;
  source_id: string | null;
  observed_value: string | null;
  limit_value: string | null;
  currency: string | null;
  instrument_key: string | null;
};

type OptionView = {
  option_id: string;
  kind: string;
  status: string;
  action: string;
  title: string;
  rationale: string;
  confidence: string;
  blockers: string[];
  review_conditions: string[];
  evidence_ids?: string[];
  evidence?: EvidenceView[];
};

type RiskStateView = {
  total_value_base: string;
  cash_base: string;
  cash_weight: string;
  policy_compliant: boolean;
  blockers: string[];
  concentration: {
    top_1_weight: string;
    top_3_weight: string;
    top_5_weight: string;
  };
  vectors: Array<{
    kind: string;
    severity: string;
    hard_breach: boolean;
    metrics: string[];
    evidence_codes: string[];
  }>;
};

type PlanView = {
  schema_version: string;
  object_type: "PORTFOLIO_PLAN";
  created_at: string;
  expires_at: string;
  expired: boolean;
  plan_sha256: string;
  selected_regime: string;
  approval_required: boolean;
  approval_subject: {
    state: "PREVIEW_ONLY" | "EXPIRED" | "NOT_REQUIRED";
    phrase: string | null;
    can_approve: false;
    mutation_invalidates: true;
  };
  upstream: Record<string, string>;
  values: Record<string, string>;
  risk: { before: RiskStateView; after: RiskStateView };
  targets: Array<{
    stable_key: string;
    component: string;
    current_lots: number;
    target_lots: number;
    lot_size: number;
    desired_weight: string;
    current_value_base: string;
    target_value_base: string;
    target_weight: string;
  }>;
  legs: Array<{
    sequence: number;
    action: string;
    trade: null | {
      trade_id: string;
      stable_key: string;
      component: string;
      side: string;
      current_lots: number;
      target_lots: number;
      quantity_lots: number;
      lot_size: number;
      reference_clean_unit_price_base: string;
      gross_notional_base: string;
      accrued_interest_base: string;
      settlement_notional_base: string;
      commission_base: string;
      estimated_tax_base: string;
      cash_delta_base: string;
      required_execution_days: number;
      staged_execution_required: boolean;
    };
  }>;
  cancellation_conditions: Array<{ code: string; hard_cancel: true }>;
  execution_authorized: false;
  trading_methods: false;
};

type DecisionPlanPayload = {
  schema_version: "1.0.0";
  generated_at: string;
  state: ViewState;
  reason?: string | null;
  main_decision: "NO_ACTION" | "HOLD" | "REDUCE" | "EXIT" | "REALLOCATE" | null;
  record?: {
    decision_id: string;
    portfolio_id: string;
    policy_id: string;
    snapshot_id: string;
    decision_payload_sha256: string;
    decided_at: string;
    plan_id: string | null;
    plan_payload_sha256: string | null;
  };
  decision: null | {
    decision_set_sha256: string;
    decided_at: string;
    abstain: boolean;
    recommendation_ready: boolean;
    confidence: string;
    global_blockers: string[];
    preferred: OptionView;
    alternatives: OptionView[];
    evidence: EvidenceView[];
    trading_methods: false;
  };
  plan: PlanView | null;
  execution_authorized: false;
  trading_methods: false;
};

async function readDecisionPlan(): Promise<DecisionPlanPayload> {
  const response = await fetch("/api/v10/web/decision-plan", {
    credentials: "same-origin",
    cache: "no-store",
  });
  if (!response.ok) throw new Error(`DECISION_PLAN_API_${response.status}`);
  return (await response.json()) as DecisionPlanPayload;
}

function timestamp(value: string | null | undefined): string {
  if (!value) return "—";
  const parsed = new Date(value);
  return Number.isNaN(parsed.valueOf()) ? value : parsed.toLocaleString("ru-RU");
}

function shortHash(value: string | null | undefined): string {
  if (!value) return "—";
  return value.length <= 28 ? value : `${value.slice(0, 14)}…${value.slice(-10)}`;
}

function percent(value: string): string {
  const numeric = Number(value);
  return Number.isFinite(numeric) ? `${(numeric * 100).toFixed(2)}%` : value;
}

function MainDecision({ payload }: { payload: DecisionPlanPayload }) {
  return (
    <section className="decision-main" data-origin="deterministic-main-decision">
      <p className="shell-eyebrow">DETERMINISTIC CORE · MAIN_DECISION</p>
      <strong>{payload.main_decision ?? "UNAVAILABLE"}</strong>
      <span>{payload.decision?.preferred.title ?? "Canonical decision отсутствует"}</span>
      <p>{payload.decision?.preferred.rationale ?? payload.reason ?? "Нет данных"}</p>
      <div className="decision-chip-row">
        <span className="decision-chip">STATE {payload.state}</span>
        <span className="decision-chip">CONFIDENCE {payload.decision?.confidence ?? "UNKNOWN"}</span>
        <span className="decision-chip">READ ONLY</span>
      </div>
    </section>
  );
}

function RiskColumn({ title, state }: { title: string; state: RiskStateView }) {
  return (
    <Card title={title}>
      <dl className="decision-dl">
        <div><dt>Portfolio value</dt><dd>{state.total_value_base}</dd></div>
        <div><dt>Cash</dt><dd>{state.cash_base} · {percent(state.cash_weight)}</dd></div>
        <div><dt>Top 1</dt><dd>{percent(state.concentration.top_1_weight)}</dd></div>
        <div><dt>Top 3</dt><dd>{percent(state.concentration.top_3_weight)}</dd></div>
        <div><dt>Top 5</dt><dd>{percent(state.concentration.top_5_weight)}</dd></div>
        <div><dt>Policy</dt><dd>{state.policy_compliant ? "COMPLIANT" : "BREACH"}</dd></div>
      </dl>
      {state.blockers.length ? <p className="shell-caption">Blockers: {state.blockers.join(", ")}</p> : null}
      <div className="decision-vector-list">
        {state.vectors.map((vector) => (
          <div className="decision-vector" key={vector.kind}>
            <strong>{vector.kind}</strong>
            <span>{vector.severity}{vector.hard_breach ? " · HARD BREACH" : ""}</span>
            <small>{vector.metrics.join(" · ") || "no metric labels"}</small>
          </div>
        ))}
      </div>
    </Card>
  );
}

function RiskMath({ plan }: { plan: PlanView }) {
  return (
    <section className="decision-section" data-origin="canonical-risk-before-after">
      <div className="decision-section__heading">
        <div><p className="shell-eyebrow">EXACT PLAN MATH</p><h2>Risk before / after</h2></div>
        <span className="decision-chip">NO FORECAST INFERENCE</span>
      </div>
      <div className="decision-risk-grid">
        <RiskColumn title="Before" state={plan.risk.before} />
        <RiskColumn title="After" state={plan.risk.after} />
      </div>
    </section>
  );
}

function PlanMath({ plan }: { plan: PlanView }) {
  const targets = plan.targets.map((row) => [
    row.stable_key,
    row.component,
    `${row.current_lots} → ${row.target_lots}`,
    String(row.lot_size),
    percent(row.target_weight),
    row.target_value_base,
  ]);
  const legs = plan.legs.map((row) => [
    String(row.sequence),
    row.action.toUpperCase(),
    row.trade?.stable_key ?? "NO_ACTION",
    row.trade ? String(row.trade.quantity_lots) : "0",
    row.trade?.reference_clean_unit_price_base ?? "—",
    row.trade?.commission_base ?? "0",
    row.trade?.cash_delta_base ?? "0",
    row.trade?.staged_execution_required ? `${row.trade.required_execution_days} days` : "single stage",
  ]);
  return (
    <section className="decision-section" data-origin="immutable-plan-math">
      <div className="decision-section__heading">
        <div><p className="shell-eyebrow">IMMUTABLE PORTFOLIO PLAN</p><h2>Targets, lots, costs, cash</h2></div>
        <span className="decision-chip">{plan.selected_regime}</span>
      </div>
      <div className="decision-value-grid">
        {Object.entries(plan.values).map(([key, value]) => (
          <Card title={key.replaceAll("_", " ")} key={key}><strong>{value}</strong></Card>
        ))}
      </div>
      <DataTable
        caption="Exact target positions"
        headers={["Instrument", "Component", "Lots", "Lot size", "Target weight", "Target value"]}
        rows={targets}
      />
      <DataTable
        caption="Exact immutable plan legs"
        headers={["#", "Action", "Instrument", "Lots", "Reference", "Commission", "Cash delta", "Staging"]}
        rows={legs}
      />
    </section>
  );
}

function ApprovalSubject({ plan }: { plan: PlanView }) {
  return (
    <section className="decision-approval" data-origin="immutable-plan-approval-subject">
      <div>
        <p className="shell-eyebrow">FUTURE OWNER CONFIRMATION SUBJECT · PREVIEW ONLY</p>
        <h2>{plan.approval_subject.state}</h2>
      </div>
      {plan.approval_subject.phrase ? <code>{plan.approval_subject.phrase}</code> : <span>Approval phrase скрыта или не требуется.</span>}
      <p>Этот экран ничего не подтверждает и не отправляет брокеру. Любая существенная мутация плана меняет immutable hash и аннулирует этот subject.</p>
      <dl className="decision-dl">
        <div><dt>Plan hash</dt><dd><code>{shortHash(plan.plan_sha256)}</code></dd></div>
        <div><dt>Created</dt><dd>{timestamp(plan.created_at)}</dd></div>
        <div><dt>Expires</dt><dd>{timestamp(plan.expires_at)}</dd></div>
        <div><dt>Can approve here</dt><dd>NO</dd></div>
      </dl>
    </section>
  );
}

function Alternatives({ payload }: { payload: DecisionPlanPayload }) {
  const decision = payload.decision;
  if (!decision) return null;
  return (
    <section className="decision-section" data-origin="deterministic-alternatives">
      <div className="decision-section__heading"><h2>Alternatives</h2><span>Core-generated, not OWNER guesswork</span></div>
      <div className="decision-alternatives">
        {decision.alternatives.map((option) => (
          <Card title={option.title} key={option.option_id}>
            <p>{option.rationale}</p>
            <div className="decision-chip-row">
              <span className="decision-chip">{option.status}</span>
              <span className="decision-chip">{option.action}</span>
              <span className="decision-chip">{option.confidence}</span>
            </div>
            {option.blockers.length ? <p className="shell-caption">Blockers: {option.blockers.join(", ")}</p> : null}
            {option.review_conditions.length ? <p className="shell-caption">Review: {option.review_conditions.join(" · ")}</p> : null}
          </Card>
        ))}
      </div>
    </section>
  );
}

function Evidence({ payload }: { payload: DecisionPlanPayload }) {
  const evidence = payload.decision?.evidence ?? [];
  return (
    <section className="decision-section" data-origin="canonical-decision-evidence">
      <h2>Constraints, blockers, evidence</h2>
      {payload.decision?.global_blockers.length ? (
        <StatePanel kind="warning" title="Global blockers">{payload.decision.global_blockers.join(", ")}</StatePanel>
      ) : null}
      {evidence.length ? (
        <div className="decision-evidence-list">
          {evidence.map((row) => (
            <article className="decision-evidence" key={row.evidence_id}>
              <strong>{row.kind} · {row.evidence_id}</strong>
              <span>{row.statement}</span>
              <small>{row.source_schema}{row.source_id ? ` · ${row.source_id}` : ""}</small>
            </article>
          ))}
        </div>
      ) : <StatePanel kind="empty" title="Evidence отсутствует">UI не подставляет синтетическое объяснение.</StatePanel>}
    </section>
  );
}

export function DecisionPlanPage({ focus }: { focus: Focus }) {
  const [payload, setPayload] = useState<DecisionPlanPayload | null>(null);
  const [unavailable, setUnavailable] = useState(false);

  useEffect(() => {
    let active = true;
    void readDecisionPlan()
      .then((value) => { if (active) { setPayload(value); setUnavailable(false); } })
      .catch(() => { if (active) setUnavailable(true); });
    return () => { active = false; };
  }, []);

  const title = useMemo(() => ({
    risks: "Риски",
    decisions: "Решения",
    plans: "Планы",
  })[focus], [focus]);

  return (
    <section className="shell-page decision-page" aria-labelledby="page-title">
      <div className="shell-page__heading">
        <div>
          <p className="shell-eyebrow">DECISION / RISK / PLAN</p>
          <h1 id="page-title">{title}</h1>
          <p className="shell-muted">Один deterministic decision, exact before/after и immutable plan subject без execution authority.</p>
        </div>
      </div>
      {unavailable ? (
        <StatePanel kind="error" title="Decision API недоступен">Никакой optimistic decision или approval state не подставлен.</StatePanel>
      ) : payload === null ? (
        <p role="status" className="shell-muted">Загрузка canonical Decision / Risk / Plan…</p>
      ) : payload.state === "EMPTY" ? (
        <StatePanel kind="empty" title="Canonical decision пока не сохранён">WP21 не создаёт решение в Web и не запускает второй decision engine.</StatePanel>
      ) : (
        <>
          <MainDecision payload={payload} />
          {payload.state === "INVALID" || payload.state === "PARTIAL" ? (
            <StatePanel kind="warning" title={`Decision view ${payload.state}`}>{payload.reason ?? "Canonical binding incomplete."}</StatePanel>
          ) : null}
          {payload.state === "EXPIRED" ? (
            <StatePanel kind="warning" title="Immutable plan EXPIRED">План остаётся видимым для аудита, но approval subject более не действителен.</StatePanel>
          ) : null}
          {payload.plan ? <ApprovalSubject plan={payload.plan} /> : null}
          {payload.plan ? <RiskMath plan={payload.plan} /> : <StatePanel kind="empty" title="Risk before/after не привязан">Для no-change decision план не выдумывается; для actionable decision отсутствие плана остаётся PARTIAL.</StatePanel>}
          {payload.plan ? <PlanMath plan={payload.plan} /> : null}
          <Alternatives payload={payload} />
          <Evidence payload={payload} />
          <p className="shell-caption">Generated: {timestamp(payload.generated_at)} · decision payload: {shortHash(payload.record?.decision_payload_sha256)} · plan payload: {shortHash(payload.record?.plan_payload_sha256)} · execution_authorized=FALSE · trading_methods=FALSE</p>
        </>
      )}
    </section>
  );
}
