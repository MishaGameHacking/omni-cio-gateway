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

The screen must show:

- one deterministic `MAIN_DECISION` presentation;
- exact risk before/after mathematics when an immutable plan is bound;
- exact targets, lots, reference values, costs, cash effects and staging;
- blockers and source evidence;
- immutable plan hash/version/expiry and the exact future OWNER confirmation subject;
- deterministic alternatives without requiring OWNER to invent allocation manually.

WP21 does **not** calculate a new financial decision, mutate a plan, approve a plan, submit an order or expose public ingress.

## 3. Preconditions and reuse audit

The dependency audit was completed against accepted `main` before implementation.

| Capability | Accepted authority | WP21 decision |
|---|---|---|
| deterministic decision alternatives | `DecisionSetV1` + `omni_cio/decision/engine_v1.py` | **REUSE_AS_IS** |
| decision action vocabulary | `DecisionAction` | **REUSE_AS_IS** |
| portfolio risk state | `PortfolioRiskStateV1` | **REUSE_AS_IS** |
| optimizer targets and exact trade legs | `OptimizerTargetPositionV1`, `OptimizerRebalanceLegV1` | **REUSE_AS_IS** |
| immutable plan identity and approval subject | `PortfolioPlanV1`, `portfolio_plan_sha256()`, `owner_approval_phrase()` | **REUSE_AS_IS** |
| durable decision/plan metadata and content hashes | WP13 `decisions`, `plans`, `content_blobs`, `portfolio_snapshots` | **WRAP_ADAPTER** |
| production decision-to-risk/plan binding semantics | `decision_journal/recorder_v1.py` | **REUSE_REFERENCE** |
| V9 final-decision review adapter | intent/capacity review surface | **DO_NOT_REUSE_FOR_PLAN_UI** |

No second decision engine, risk engine, optimizer, plan DTO, hash authority, database or queue is introduced.

## 4. Parity obligations

WP21 advances but does not by itself close these seed-ledger capabilities:

- `PARITY-RISK`;
- `PARITY-STRATEGY`;
- `PARITY-OPTIMIZER`;
- `PARITY-IMMUTABLE-PLAN`.

The UI consumes their accepted deterministic outputs. It does not change their semantics or mark ledger parity complete merely because they are rendered.

## 5. Deterministic MAIN_DECISION projection

The Master Plan display vocabulary is a presentation classification over canonical `DecisionSetV1` plus, where required, the exact validated `PortfolioPlanV1`:

- preferred `HOLD` → `HOLD`;
- preferred `WAIT_FOR_DATA` → `NO_ACTION`, but the overall Web state remains `PARTIAL` because the canonical decision abstains;
- preferred `REVIEW_STRATEGIC_REBALANCE` → `REALLOCATE`;
- preferred `REVIEW_LIMITED_CHANGE` + sell-only exact plan whose affected targets all reach zero → `EXIT`;
- preferred `REVIEW_LIMITED_CHANGE` + sell-only exact plan with any non-zero affected target → `REDUCE`;
- preferred `REVIEW_LIMITED_CHANGE` + any buy/mixed exact plan → `REALLOCATE`.

An actionable decision without a valid exact plan is `PARTIAL`; the UI does not guess the missing classification.

## 6. Durable read boundary

`GET /api/v10/web/decision-plan` is installed only in the accepted local/private Web app.

The read service:

1. resolves server-side session and tenant;
2. selects the latest tenant decision and latest exact scoped plan;
3. requires the decision to join the exact tenant/portfolio/policy/snapshot record;
4. binds the plan's `portfolio_snapshot_sha256` to that durable snapshot's `source_payload_sha256`;
5. binds the plan policy reference to the persisted decision policy and the plan timestamp to the persisted plan timestamp;
6. binds the persisted decision timestamp to `DecisionSetV1.metadata.retrieved_at`;
7. joins content only by the same tenant and recorded payload SHA-256;
8. bounds content size;
9. re-hashes raw bytes and rejects hash mismatch;
10. accepts only exact source-controlled schema references;
11. Pydantic-validates `DecisionSetV1` and `PortfolioPlanV1`;
12. relies on `PortfolioPlanV1` to recompute and validate its internal canonical `plan_sha256` and approval phrase;
13. returns no raw content blob and no broker credential.

The response uses `Cache-Control: no-store` and `Pragma: no-cache`.

## 7. Approval and execution boundary

WP21 may display the future OWNER confirmation subject only as `PREVIEW_ONLY`.

Hard rules:

- `can_approve=false`;
- no POST/PUT/PATCH/DELETE plan route;
- expired plans do not expose an approval phrase;
- invalid/mutated plans expose no approval subject;
- `execution_authorized=false`;
- `trading_methods=false`;
- `REAL_TRADING_ENABLED=false` remains unchanged;
- broker write authority is not added.

The later Real execution contour remains locked behind its own Master Plan WPs and OWNER approval gates.

## 8. Required negative evidence

WP21 tests must prove at least:

- no session → 401;
- tenant predicate is always present;
- blob SHA mismatch / wrong schema / invalid canonical plan fail closed;
- material plan mutation with a newly valid outer blob hash but stale internal `plan_sha256` is rejected;
- decision timestamp or snapshot source-hash binding mismatch fails closed;
- preferred `WAIT_FOR_DATA` is `NO_ACTION` presentation but never `READY`;
- actionable decision without plan is `PARTIAL`;
- no-change decision does not silently bind an actionable plan;
- expiry hides the approval phrase;
- `REDUCE` and `EXIT` are deterministic plan classifications;
- Web contains no approval mutation and no browser credential storage;
- exact targets/lots/costs/risk and alternatives render in browser evidence.

## 9. CI and Exit Gate

WP21 is merge-eligible only when:

1. dedicated exact-head `V10 WP21 Decision Risk Plan Audit` is GREEN;
2. authoritative Self-Hosted Windows CI is GREEN;
3. inherited accepted Web gates remain GREEN;
4. review threads/comments contain no unresolved blocker;
5. full diff remains within WP21 scope;
6. hosted startup/billing failures, if any, are classified separately and never called PASS;
7. squash merge uses the exact reviewed head;
8. exact new `main` passes post-merge Regression Shield.

Only after that post-merge gate may the official program status transition to the next Master Plan WP.
