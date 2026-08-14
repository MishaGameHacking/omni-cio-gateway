# V10 WP21 — Decision, Risk and Plan UI Execution Contract

Status: **WP21 implementation contract**  
Parent program: `docs/master-plan/OMNI_CIO_V10_MASTER_PLAN.md`  
Protected runtime baseline: `app:app`  
Authority expansion: **none**

## 1. Identity

- Work Package: **WP21 — Decision, Risk and Plan UI**
- Block: **E — Web Platform**
- Base: accepted `main` after WP20 status transition and post-status Regression Shield #1491.
- Branch: `v10/wp21-decision-risk-plan-ui`.

## 2. Purpose

WP21 replaces the accepted Web placeholders for `/risks`, `/decisions` and `/plans` with one read-only projection of already accepted deterministic Core objects.

The screen must show one deterministic `MAIN_DECISION`, exact risk before/after, exact targets/lots/costs/cash/staging, blockers/evidence, immutable plan identity/expiry, the exact future OWNER confirmation subject, and deterministic alternatives.

WP21 does **not** calculate a new financial decision, mutate a plan, approve a plan, submit an order or expose public ingress.

## 3. Preconditions and reuse audit

| Capability | Accepted authority | WP21 decision |
|---|---|---|
| deterministic decision alternatives | `DecisionSetV1` + `omni_cio/decision/engine_v1.py` | **REUSE_AS_IS** |
| decision action vocabulary | `DecisionAction` | **REUSE_AS_IS** |
| portfolio risk state | `PortfolioRiskStateV1` | **REUSE_AS_IS** |
| optimizer targets and exact trade legs | `OptimizerTargetPositionV1`, `OptimizerRebalanceLegV1` | **REUSE_AS_IS** |
| immutable plan identity and approval subject | `PortfolioPlanV1`, `portfolio_plan_sha256()`, `owner_approval_phrase()` | **REUSE_AS_IS** |
| durable metadata/content identity | WP13 `decisions`, `plans`, `content_blobs`, `portfolio_snapshots`, `policies` | **WRAP_ADAPTER** |
| production decision-to-plan semantics | `decision_journal/recorder_v1.py` | **REUSE_REFERENCE** |
| V9 final-decision review adapter | intent/capacity review surface | **DO_NOT_REUSE_FOR_PLAN_UI** |

No second decision engine, risk engine, optimizer, plan DTO, hash authority, database or queue is introduced.

## 4. Parity obligations

WP21 advances but does not by itself close `PARITY-RISK`, `PARITY-STRATEGY`, `PARITY-OPTIMIZER` or `PARITY-IMMUTABLE-PLAN`. Rendering accepted outputs is not parity acceptance.

## 5. Deterministic MAIN_DECISION projection

The display vocabulary is a presentation classification over canonical `DecisionSetV1` plus, where required, the exact validated `PortfolioPlanV1`:

- `HOLD` → `HOLD`;
- `WAIT_FOR_DATA` → `NO_ACTION`, while overall state remains `PARTIAL`;
- `REVIEW_STRATEGIC_REBALANCE` → `REALLOCATE`;
- `REVIEW_LIMITED_CHANGE` + sell-only plan whose affected targets all reach zero → `EXIT`;
- `REVIEW_LIMITED_CHANGE` + sell-only plan with any non-zero affected target → `REDUCE`;
- `REVIEW_LIMITED_CHANGE` + buy/mixed plan → `REALLOCATE`.

An actionable decision without a valid exact plan is `PARTIAL`; the UI does not guess.

## 6. Durable read boundary

`GET /api/v10/web/decision-plan` exists only in the accepted local/private Web app.

The read service:

1. resolves server-side session and tenant;
2. selects the latest tenant decision and latest exact scoped plan;
3. requires the decision to join the exact tenant/portfolio/canonical-policy/snapshot records;
4. binds plan `portfolio_snapshot_sha256` to durable snapshot `source_payload_sha256`;
5. binds `plan.policy_reference.policy_id` to durable policy `source_policy_id` rather than incorrectly equating it with the canonical V10 `policy_id`;
6. binds plan `created_at` to persisted plan `created_at`;
7. joins content only by same tenant and recorded payload SHA-256;
8. bounds content size and re-hashes raw bytes;
9. accepts only exact source-controlled schema references;
10. validates `DecisionSetV1` and `PortfolioPlanV1`;
11. relies on `PortfolioPlanV1` to recompute canonical `plan_sha256` and approval phrase;
12. returns no raw content blob and no broker credential.

`DecisionRecord.decided_at` is retained as durable audit time and is **not** falsely equated with `DecisionSet.metadata.retrieved_at`, because the accepted production journal permits a distinct `recorded_at`.

The response uses `Cache-Control: no-store` and `Pragma: no-cache`.

## 7. Approval and execution boundary

The future OWNER confirmation subject is display-only `PREVIEW_ONLY`:

- `can_approve=false`;
- no POST/PUT/PATCH/DELETE plan route;
- expired plans expose no approval phrase;
- invalid/mutated plans expose no approval subject;
- `execution_authorized=false`;
- `trading_methods=false`;
- `REAL_TRADING_ENABLED=false` unchanged;
- no broker write authority.

## 8. Required negative evidence

Tests must prove session denial, tenant predicate, blob/schema/canonical-plan rejection, stale internal `plan_sha256` rejection after material mutation, snapshot source-hash/source-policy mismatch rejection, `WAIT_FOR_DATA` remaining `PARTIAL`, actionable decision without plan remaining `PARTIAL`, no-change decision not binding a plan, expiry hiding approval phrase, deterministic `REDUCE`/`EXIT`, no browser approval mutation/credential storage, and exact math/alternatives browser evidence.

## 9. CI and Exit Gate

WP21 is merge-eligible only when dedicated exact-head WP21 audit, authoritative Self-Hosted Windows CI and inherited accepted Web gates are GREEN; blocking review threads are zero; full diff remains WP21-only; hosted startup/billing failures are classified separately; squash merge uses the exact reviewed head; and the exact new `main` passes post-merge Regression Shield.

Only then may official status transition to the next Master Plan WP.
