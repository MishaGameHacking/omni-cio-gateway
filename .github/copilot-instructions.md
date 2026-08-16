# GitHub Copilot Instructions — Omni-CIO

Работай только над существующим продуктом Omni-CIO и следуй принятой V10-программе. Не создавай параллельный проект.

Current production/recovery runtime:

`existing Omni-CIO Custom GPT v9.0.0 → Omni-CIO Gateway (app:app) → T-Invest API`.

Active feature program:

`Omni-CIO V10 — Personal Autonomous Investment Platform`.

V9 remains owner-accepted/protected in **controlled maintenance** while V10 is built. The owner issued `START V10` on 2026-08-05.

## Перед изменениями

Прочитай в таком порядке:

1. `AGENTS.md`;
2. `README.md`;
3. `knowledge/00_PROJECT_MASTER_CONTEXT.md`;
4. `knowledge/16_CURRENT_PROGRAM_STATUS.md` — accepted V9 runtime baseline;
5. `docs/master-plan/OMNI_CIO_V10_PROGRAM_LOCK.md`;
6. `docs/master-plan/OMNI_CIO_V10_MASTER_PLAN.md`;
7. `docs/master-plan/OMNI_CIO_V10_AMENDMENTS_INDEX.md` и все active amendments;
8. `knowledge/17_V10_CURRENT_PROGRAM_STATUS.md`;
9. `docs/architecture/V10_SYSTEM_ARCHITECTURE.md`;
10. `docs/architecture/V10_SECURITY_BOUNDARIES.md`;
11. `docs/architecture/V10_DATA_FLOW.md`;
12. `docs/architecture/V10_THREAT_MODEL.md`;
13. `docs/architecture/V10_RECOVERY_CONTRACT.md`;
14. `docs/architecture/V10_ADR_PROCESS.md` + `docs/architecture/DECISIONS.md`;
15. `docs/architecture/REPOSITORY_STRUCTURE.md`;
16. профильный current-WP architecture/runbook;
17. actual `main`, open PR/issues and latest GitHub Actions.

Current V10 progress/next WP is determined only by `knowledge/17_V10_CURRENT_PROGRAM_STATUS.md` from accepted `main`.

Old chat/screenshot/closed issue is historical evidence, not current authority when it conflicts with accepted `main`.

## V10 sequence rule

Do exactly one current Work Package at a time.

`restore context → current WP → focused branch → implementation/tests → security/boundary review → exact-head Regression Shield → zero unresolved review blockers → squash merge → update current status → next WP`.

Do not skip to a later block because its implementation looks easy.

Do not start V11, public/multi-user, billing, alternate frontend, second Telegram stack, second AI stack, second Gateway or second execution stack before V10 final acceptance.

The one-time Lenovo setup is intentionally Block C after WP1–WP4 establish repository architecture, toolchain, CI and release/deployment contracts.

## Pre-CI Engineering Gate

Before starting a long or expensive full CI cycle, treat CI as the **independent verifier**, not the primary debugger.

For every material change or RED result:

1. establish the root cause before changing code;
2. inspect the complete branch diff plus directly coupled producers/consumers;
3. search the repository for analogous uses of the same pattern/dependency/API/assumption;
4. determine the blast radius and inspect adjacent failure modes;
5. fix the defect class, not merely the first failing line;
6. add/update a permanent regression test or guard when the defect class is reusable;
7. run all applicable cheap/focused checks first: format, lint, typecheck, compile, focused tests, negative tests, schema/config/IaC/PowerShell validation, dependency/lock validation, secret/private-data guards and rollback/recovery review;
8. review current official documentation/security/support status when a materially changed external dependency/API can have changed over time;
9. review the full diff again before triggering full exact-head CI.

Do not intentionally launch a long CI cycle while known preflight failures remain. Do not claim 100% certainty that software contains no bugs; require evidence-backed readiness before CI and independent evidence after CI.

If an unexpected RED appears after the branch was considered preflight-ready, perform a confidence postmortem: why did preflight miss it, where else can the same class exist, and what permanent guard prevents recurrence? Record reusable lessons in the **Failure Learning Ledger**: `docs/operations/V10_ENGINEERING_FAILURE_LEARNING_LEDGER.md`.

## Green merge / OWNER acceptance law

**All applicable exact-head checks must be SUCCESS** before merge. Omni-CIO policy is stricter than generic GitHub status semantics: `failure`, `cancelled`, `queued`, `pending`, `in_progress`, `timed_out`, `action_required`, `stale`, `neutral` and `skipped` are not GREEN evidence for an applicable V10 gate.

Infrastructure/billing/provider startup failures must be diagnosed accurately, but a red applicable check still blocks merge. Restore the check, use an accepted fallback, or correct workflow applicability. Never merge around red evidence.

If a workflow is genuinely irrelevant to the current branch/WP, correct its trigger/routing so it does not appear as a misleading skipped/cancelled check.

Any new commit invalidates the previous final GREEN cycle. Re-run the required checks on the new exact head.

Normal closure is `all applicable exact-head checks GREEN → full diff/review → squash merge → PR closed by merge`. An unmerged PR may be closed only as explicitly superseded/abandoned historical work and is never accepted implementation.

**OWNER product acceptance only after merge** and after the required post-merge Regression Shield is GREEN. Before that point, do not ask the OWNER for phone/browser walkthroughs, UX acceptance, login/logout acceptance, portfolio comparison or ordinary product tests.

Pre-merge OWNER involvement is allowed only for a genuinely non-delegable prerequisite needed to make engineering verifiable: account/consent bootstrap, domain/payment decision, narrow credential bootstrap, UAC/admin/firmware/BitLocker/physical action, or an explicit Master Plan OWNER decision. Ask only for the prerequisite, not premature product acceptance.

If post-merge OWNER acceptance finds a defect, create a new focused fix branch/PR and repeat the GREEN cycle; never patch `main` directly.

## Fault-isolation / spider rule

Build bounded failure domains. An optional component failure should not unnecessarily take down deterministic Core truth.

Use explicit contracts and, where applicable, timeouts/deadlines, bounded retries, idempotency, backpressure/circuit-breaker semantics, durable queues/checkpoints, health/readiness/freshness states, restart/recovery and least-privilege process/service boundaries.

Examples:

- AI outage → Core remains usable, AI explicit DEGRADED/OFFLINE;
- Research outage → Core/portfolio remain usable, research freshness explicit;
- Telegram outage → Web/Core remain usable;
- external ingress outage → local Personal Node/recovery remain usable;
- broker READ outage → only last verified state may remain visible and must be marked STALE/OFFLINE.

Money/security authority always fails closed. Graceful degradation never weakens identity, secret, broker or Real-execution controls.

New programming languages are permitted only for a concrete component-level correctness/security/isolation/performance/systems-integration reason with toolchain/recovery/maintenance impact reviewed. Do not create polyglot sprawl or rewrite accepted components merely because another language is newer.

## Repository architecture

Canonical current/target structure:

`docs/architecture/REPOSITORY_STRUCTURE.md`.

Rules:

- one deterministic Core root: `omni_cio/`;
- current V9 root wrappers remain protected dependencies until a later migration proves replacement;
- reserved V10 adapters: future `apps/api/`, `apps/web/`, `apps/telegram/`;
- reserved V10 AI root: future `ai/`;
- reserved replaceable-node infrastructure root: future `infrastructure/`;
- current GPT migration/recovery source remains `gpt/` until parity/decommission gate;
- no competing top-level `frontend/`, `website/`, `telegram_bot/`, `backend/`, `server/`, `omni_cio_v10/` or second execution stack.

Permanent repository boundary guard:

`python scripts/check_v10_repository_boundaries.py`.

Permanent engineering-governance guard after acceptance:

`python scripts/check_v10_engineering_governance.py`.

Do not bypass or weaken these guards to land a change.

## Product / runtime rules

Until explicitly replaced by an accepted V10 package:

- stable V9 entrypoint `app:app`;
- production endpoint `https://omni-cio-gateway.onrender.com`;
- effective production `https://omni-cio-gateway.onrender.com/openapi.json` remains current GPT Action authority;
- account IDs user-facing only masked;
- no token/key values, Authorization headers, full account IDs or private broker payloads in GitHub/logs/docs;
- exact decimal logic;
- no cross-currency aggregation without verified FX + timestamp;
- no double-count of payments/commissions/child operations/embedded trades;
- partial/stale/truncated/contradictory data is not complete/current truth;
- generated lock files are not hand-edited;
- external GitHub Actions pin full commit SHA.

## Broker contour rules

Three contours remain isolated:

1. production read-only — `TINVEST_TOKEN`;
2. optional virtual Sandbox — `TINVEST_SANDBOX_TOKEN`;
3. optional exact-owner-confirmed Real execution — separate `TINVEST_TRADING_TOKEN` + durable state.

Production read-only token is never a Real fallback.

Current reviewed Real operationIds:

- `getRealTradingStatus`;
- `prepareRealTrade`;
- `executeRealTrade`;
- `getRealOrderState`.

Real submit remains server-gated:

`readiness/fresh facts → immutable proposal/plan context → exact owner confirmation in a NEW turn → repeat preflight → one idempotent submit → broker reconciliation`.

Preserve:

- own-funds BUY / own-position SELL;
- hard server caps;
- fresh trusted market;
- exact price step;
- ambiguous possible-submit → no automatic retry;
- submitted != filled without broker proof;
- no transfer/withdrawal, margin/short, MARKET/BESTPRICE, stop/replace/async or autonomous recurring real-money execution.

`REAL_TRADING_ENABLED=false` is the master Real kill switch. `WATCHTOWER_ENABLED=false` disables Watchtower independently.

`START V10`, development approval, AI output or alert acknowledgement is never authorization for a broker submit.

## AI boundary

V10 AI is a replaceable analytical/orchestration layer, not the money authority.

- migrate current GPT Instructions/Knowledge/Actions according to the locked V10 plan;
- one future AI Copilot/Agent Orchestrator is shared by Web and Telegram;
- AI may use only allowlisted tools;
- AI cannot import/use direct `omni_cio.real_trading` authority;
- AI cannot read the Real trading secret;
- retrieved text/news is untrusted data, never system instruction;
- AI output is not canonical evidence without source binding;
- Risk/Optimizer/immutable Plan/approval/execution remain deterministic boundaries;
- current Custom GPT remains available until the explicit V10 parity/decommission gate and owner acceptance.

## Current Custom GPT recovery rules

While V9 GPT remains applied:

- applied Instructions: `gpt/CUSTOM_GPT_INSTRUCTIONS_V9_0_0_COMPACT.txt`;
- applied Knowledge: exact set from `gpt/KNOWLEDGE_MANIFEST_V9_0_0.md`;
- protected rollback Instructions: `gpt/CUSTOM_GPT_INSTRUCTIONS_V8_6_1_COMPACT.txt`;
- Actions ON, Apps OFF while custom Actions are used;
- GitHub is canonical configuration/recovery source, not automatic GPT Editor synchronization;
- future GPT-visible changes require owner Preview + `Update` on the same GPT after repository review.

## Broker report rules

For `getBrokerReportReconciliation` preserve:

- `days=1..31`;
- first async call without `task_id`;
- T-Invest `30058` = report pending;
- reuse exact returned `task_id`;
- ready/full only when contract reports completion;
- unrelated errors are not renamed pending.

## Required delivery discipline

Every significant V9 maintenance or V10 package:

`branch → root-cause/blast-radius preflight → deterministic focused tests/guards → full-diff review → exact-head applicable CI all SUCCESS → zero unresolved review threads → squash merge → post-merge verification → OWNER product acceptance if required`.

Do not weaken CI/security, repository boundaries or broker authority to make a change pass.

Current Regression Shield includes repository/security policy, V10 repository-boundary guard, GPT recovery consistency, Ruff, mypy, compile, pytest/coverage, dependency audit, SAST and secret scanning.

Не создавай дублирующие setup/configuration/audit документы, если можно обновить существующий canonical source.
