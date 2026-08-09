# Omni-CIO V10 — WP11 V9 Core Extraction Execution Contract

Status: **IMPLEMENTATION CONTRACT / WP11 ACTIVE**  
Block: **D — V10 Core and data**  
Accepted baseline: `21e3af40aed4a0e7fcb25783db5f90e22a86a18f`  
Protected runtime: **V9 `app:app` remains rollback/production baseline**

## 1. WP identity

- WP: **WP11 — V9 Core Extraction**.
- Authorized by current program status: **YES**.
- Prior gate: WP10 + Block C accepted after exact-head WP10 gates, squash merge, and post-merge Regression Shield `31317709162`; status acceptance itself was merged only after exact-head PR #264 authoritative gate and post-merge Regression Shield `31318484626`.

## 2. Purpose

Expose a stable, presentation-independent Python Core planning interface over the already accepted V9 deterministic engines without rewriting their financial semantics.

The required proof path is:

`PortfolioRiskInputV1 -> risk -> optimizer -> immutable plan`

with deterministic policy/strategy inputs and no dependency on Custom GPT, OpenAI, FastAPI, `app.py`, or a broker-write surface.

## 3. Existing implementation to reuse

The accepted V9 WP1–WP14 packages are inventoried in `V10_WP11_CORE_INVENTORY.json`. The default decision for their already isolated deterministic financial logic is **REUSE_AS_IS**. WP11 adds only a narrow **WRAP_ADAPTER** facade under `omni_cio/core/`.

No accepted financial formula is copied into the facade. No component may be rewritten merely because a newer implementation is available.

## 4. Allowed changes

WP11 may change only what is required to prove extraction/parity:

- `omni_cio/core/` — new presentation-independent composition facade;
- `omni_cio/contracts/v1/` — versioned Core facade result DTO when necessary;
- deterministic parity/source-boundary tests;
- WP11 architecture/inventory documentation;
- WP11-owned entries in the parity ledger and component reuse matrix;
- repository/type-check guards only if required to protect the new Core package.

Existing V9 engine internals may be changed only if a reproduced WP11 blocker proves that a presentation assumption is embedded inside them. Such a change requires deterministic parity evidence and must not change financial semantics silently.

## 5. Explicit non-goals

WP11 does **not** authorize:

- WP12 canonical tenant/data model;
- WP13 production PostgreSQL schema/migrations;
- WP14 durable job system;
- WP15 replacement broker read layer;
- Web, Telegram, Cortex, Ollama, RAG, or AI runtime activation;
- broker trading, order submit/cancel/replace, transfer/withdrawal, margin/short, or authority expansion;
- changes to the effective public GPT Actions/OpenAPI surface unless a separately proven compatibility blocker requires it;
- replacement of `app:app`;
- enabling `trading_methods` or `REAL_TRADING_ENABLED`;
- removal of the V9 rollback path.

## 6. Core interface and DTO rule

WP11 defines a versioned Python-only service boundary. Its inputs and outputs are existing strict V1 Pydantic contracts wherever possible. A facade result DTO may aggregate existing immutable V1 results but must not redefine their financial fields.

The initial facade consumes:

- `PortfolioRiskInputV1`;
- `InvestmentPolicyStatementV1` + `InvestmentPolicyAssessmentV1`;
- `MetaStrategySelectionV1`;
- `OptimizerAssetV1[]`;
- optional existing risk/optimizer/plan settings;
- one explicit evaluation timestamp used consistently through the deterministic chain.

It returns the exact existing V1 results for:

- current portfolio risk;
- optimizer result;
- immutable portfolio plan.

Compatibility rule: direct V9 engine calls remain available and unchanged while the facade is validated.

## 7. Data and persistence effects

- migration required: **NO**;
- new production persistence: **NO**;
- private portfolio payloads in GitHub/CI: **NO**;
- backup/recovery format change: **NO**.

WP11 tests use synthetic deterministic fixtures only.

## 8. Security and authority effects

WP11 changes **none** of the following authorities:

- secret access;
- broker write authority;
- OS/runtime privilege;
- GitHub permission;
- Web/Telegram ingress;
- AI tool authority;
- Real execution path.

The new Core facade must not import the protected Gateway entrypoint, FastAPI, OpenAI, Real trading, plan execution, broker-submit modules, or environment/secret loaders.

## 9. Normal-path acceptance tests

1. **Golden parity** — the same accepted synthetic V9 inputs produce exactly equivalent risk, optimizer and plan objects through direct V9 calls and through the new facade.
2. **No-GPT integration** — `portfolio -> risk -> optimizer -> plan` completes through `omni_cio.core` without importing Custom GPT/OpenAI/FastAPI/app wrappers.
3. **No-action parity** — the accepted V9 `NO_ACTION` path remains exactly equivalent.
4. Existing V9 regression tests remain green.

## 10. Negative/failure tests

- source-import guard rejects presentation/OpenAI imports from the Core facade;
- source-import guard rejects broker-write/Real-execution imports from the facade;
- wrong upstream bindings continue to fail through existing V9 contracts/engines rather than being normalized or guessed by the facade;
- no secret/private runtime values are required by tests;
- no public API route is added.

## 11. Observability/evidence

WP11 itself adds no runtime daemon or persistent log stream. Acceptance evidence is repository-controlled:

- deterministic test output;
- parity ledger bindings;
- exact-head CI/security run IDs;
- zero unresolved review threads;
- post-merge Regression Shield before WP12 starts.

## 12. CI routing

- Fast hosted checks: use when GitHub-hosted capacity is available.
- Hosted clean-room compatibility: no new Windows-specific behavior is introduced by the Python facade; existing repository routing remains authoritative.
- Lenovo authoritative gate: **REQUIRED**.
- GPU AI eval: **NO** — WP11 activates no AI model.
- recovery matrix: existing Regression Shield/recovery invariants remain protected; WP11 adds no migration.

Hosted billing/capacity failure is never reclassified as a source PASS. Only an already accepted continuity rule may classify it as degraded acceleration while authoritative safety gates remain enabled.

## 13. Rollback/recovery

Before merge: discard the WP11 branch and return to accepted `main`.

After merge, if post-merge validation discovers a real regression: stop WP12, repair or revert through a new focused PR. Do not force-reset protected `main` and do not discard broker/reconciliation truth.

The existing V9 `app:app` path remains unchanged throughout WP11.

## 14. Binary WP11 Exit Gate

WP11 = **PASS** only when all of the following are true on the exact PR head:

- the Core planning facade executes the required deterministic path without Custom GPT/OpenAI/FastAPI/app wrappers;
- direct V9 path and facade path have deterministic golden parity for normal and NO_ACTION fixtures;
- accepted V9 rollback/public Gateway behavior remains unchanged;
- no broker/security/secret/runtime authority expands;
- WP11 inventory/reuse/parity metadata is complete and truthful;
- all required exact-head CI/security gates pass;
- unresolved review threads = 0.

Anything less is **FAIL / NOT VERIFIED** and must not be merged.

## 15. Next WP unlock

WP12 is locked until:

1. WP11 exact-head Exit Gate = PASS;
2. WP11 is squash-merged;
3. mandatory post-merge Regression Shield on the resulting `main` SHA = SUCCESS;
4. `knowledge/17_V10_CURRENT_PROGRAM_STATUS.md` records WP11 acceptance.

## 16. Scope-discovery rule

Discovered work not required for this Exit Gate is classified as a WP11 blocker, future-WP work, or an OWNER-approved amendment proposal. It is not silently implemented inside WP11.
