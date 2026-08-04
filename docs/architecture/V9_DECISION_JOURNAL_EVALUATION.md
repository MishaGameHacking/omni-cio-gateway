# Omni-CIO v9 — Decision Journal, Evaluation & Learning Loop

## Purpose

WP14 adds a durable audit/evaluation layer without adding execution authority. It records exactly what the system knew and selected at decision time, records later outcomes separately, and evaluates those records deterministically. Historical expectations are never rewritten after outcomes are known.

## Architecture

The package is `omni_cio.decision_journal` and has five internal responsibilities:

1. **Production recorder** — binds the canonical `DecisionSetV1` to the exact WP8 portfolio-risk assessment and, when present, the exact WP11 immutable plan and WP12 execution session. Cross-WP SHA mismatches fail closed.
2. **Decision record** — immutable hash-bound snapshot of policy, portfolio, decision/evidence/risk/strategy/optimizer/plan/execution identities and decision-time quality/target metrics.
3. **Outcome record** — separate append-only evidence record for the evaluation horizon. It contains realized portfolio value, external flow, optional evidence-bound benchmarks and outcome quality metrics.
4. **Evaluation record** — deterministic comparison of the immutable decision and outcome. It computes period result, optional benchmark excess and quality deltas without mutating either source record.
5. **Offline replay/regression** — sanitized cases containing only hashes, expected action/completeness and benchmark labels. Candidate model/prompt/rule/config behavior can become `ready_for_review`; WP14 never applies a production change.

## Production decision audit binding

`build_production_decision_record()` is the canonical WP14 adapter for production decision objects. It deliberately reuses the identity authority that already exists upstream rather than inventing a second digest protocol:

- `DecisionSetV1` and each contained evidence row are hashed as canonical sorted-key compact UTF-8 JSON because those contracts do not expose a self digest;
- WP8 contributes its canonical `assessment_sha256` and the exact `portfolio_snapshot_sha256` / `PolicyReferenceV1` it assessed;
- WP11 contributes `plan_sha256`, `strategy_selection_sha256`, `optimizer_sha256`, its exact current-risk assessment SHA, and exact before/after risk states;
- WP12 contributes `execution_id` and must bind the exact WP11 `plan_sha256`.

When a plan is supplied, its policy, portfolio, current-risk SHA and before/after risk states must match the supplied WP8 assessment exactly. When execution is supplied, its plan SHA must match the supplied WP11 plan exactly. A decision whose preferred option is HOLD or WAIT_FOR_DATA cannot be rebound to an actionable plan.

Journal action state is evidence-derived and fail-closed:

- HOLD / WAIT_FOR_DATA when no actionable plan is bound;
- REVIEW_CHANGE when an immutable plan is present but not owner-approved for execution;
- APPROVED_PLAN only when the bound WP12 execution session records owner approval;
- EXECUTED_PLAN only when the bound WP12 execution state contains executed lots and owner approval is present.

Executed lots without owner approval are rejected. The recorder has no broker client/token and its only storage mutation is append-only `journal.put_decision()`.

## Immutable event model

`DecisionJournalRecordV1`, `DecisionOutcomeRecordV1` and `DecisionEvaluationRecordV1` are strict frozen contracts with canonical SHA-256 identities. The journal API contains append/get/integrity operations only; there is no update, patch or delete method.

A repeated append of the exact same payload is idempotent. Reuse of the same immutable identity with a different payload is a conflict and fails closed.

Outcome records require an existing decision. Evaluation records require the exact decision record hash and exact outcome record hash. This preserves provenance across restarts and prevents an evaluation from silently rebinding to revised history.

## Expected versus realized

The canonical realized period result is:

`ending portfolio value - starting portfolio value - net external flow`

This does not reinterpret deposits/withdrawals as investment performance.

Decision-time target fields such as concentration, cash weight and expected execution cost remain frozen in the decision record. Later values live only in the outcome/evaluation records.

## Counterfactual discipline

`NO_ACTION` and owner-policy benchmarks are optional evidence-bound pairs: value plus source SHA. If either is unavailable, the benchmark remains explicitly `UNAVAILABLE`; WP14 does not estimate or fabricate it.

This is particularly important for historical portfolio decisions where a complete counterfactual price path, tax treatment, coupon/accrual treatment or execution path may not exist in the available evidence.

## Quality metrics

WP14 computes deterministic quality measures when inputs exist:

- data completeness ratio;
- research coverage ratio;
- concentration reduction in basis points;
- cash-weight delta in basis points;
- actual versus expected execution-cost variance;
- execution slippage supplied by the evidence-bound outcome.

Missing optional metrics remain `None`; no synthetic precision is introduced.

## Durable storage

Production-capable persistence uses `UpstashDecisionJournalV1` with its own namespace: `omni-cio:decision-journal:v1`.

It reuses the already reviewed strict Upstash HTTPS transport rather than introducing a second network/secret stack. Rows and authenticated metadata are protected with a journal-specific HMAC key. Appends use an atomic Redis Lua compare-and-swap on authenticated metadata and immutable row identity.

Storage-administrator rollback is outside the cryptographic guarantees of a single Redis datastore; recovery therefore relies on authenticated row/meta consistency, backups/export controls and the same operational access boundary as the existing durable state systems. WP14 does not claim an external monotonic ledger that does not exist.

## Replay and learning loop

The learning loop is offline and review-gated:

1. build sanitized/synthetic/fake-broker replay cases;
2. run baseline and candidate predictions over the identical dataset;
3. compare exact expected action + abstention behavior;
4. identify cases where baseline was correct and candidate regressed;
5. candidate may become `ready_for_review` only when there are no such regressions and total match count is not worse;
6. any production model/prompt/rule/config change still requires a reviewed code/config change and the normal repository delivery gates.

There is no runtime prompt rewriting, policy mutation or autonomous deployment mechanism.

## Authority boundary

WP14 contains no T-Invest trading token/client, order submission, cancellation/replacement, transfer, withdrawal, margin, short or autonomous real-execution method. Contracts preserve explicit false safety literals for execution and production self-modification.

The applied Custom GPT remains v8.6.1 until WP15.
