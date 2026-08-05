# AGENTS.md — Omni-CIO project rules

Этот файл обязателен для любого AI-агента, разработчика или нового чата, который меняет `Misha2304/omni-cio-gateway`.

## 1. Product boundary

Поддерживается один пользовательский продукт:

`Existing Omni-CIO Custom GPT v9.0.0 → Omni-CIO Gateway (app:app) → T-Invest API`

Applied GPT v9.0.0 owner-accepted in place on 2026-08-05. Protected rollback v8.6.1 remains in GitHub.

Три broker-контура изолированы:

1. production read-only через `TINVEST_TOKEN`;
2. optional virtual Sandbox через `TINVEST_SANDBOX_TOKEN`;
3. optional exact-owner-confirmed Real execution через отдельный `TINVEST_TRADING_TOKEN` + durable state.

Не создавать второй Custom GPT, отдельный frontend, duplicate Gateway, competing scheduler или parallel broker/execution stack вне явно утверждённой программы V10.

## 2. Program state

Completed owner-approved/program-locked v9 program:

`docs/master-plan/OMNI_CIO_V9_PORTFOLIO_AUTOPILOT_PROGRAM.md`

WP0–WP15 repository delivery and owner external acceptance are **complete**. Tracking epic #176 and WP15 #216 are closed completed.

Current accepted V9 runtime mode remains **controlled maintenance** until a future V10 work package safely replaces a specific boundary.

### 2.1 V10 is the exclusive next feature program

Owner-approved/program-locked next program:

`docs/master-plan/Omni-CIO_V10_Master_Plan_RU.pdf`

Searchable scope lock:

`docs/master-plan/OMNI_CIO_V10_PROGRAM_LOCK.md`

Progress/status authority:

`knowledge/17_V10_CURRENT_PROGRAM_STATUS.md`

Current V10 state: **PROGRAM LOCKED / DEVELOPMENT NOT STARTED / 0%**.

Mandatory V10 AI scope is part of the locked plan: migrate the existing GPT Instructions/Knowledge/Actions into versioned System Policy + Knowledge/RAG + Tool Registry; build one Omni-CIO AI Copilot/Agent Orchestrator used by Web and Telegram; support a bounded Autonomous Research Agent; keep financial sizing/execution deterministic; and do not decommission the current Custom GPT until the explicit parity gate and owner acceptance.

The V10 program lock does **not** itself authorize implementation. V10 feature work begins only after a new explicit owner instruction to start V10 development.

Once V10 development starts, all feature work must follow the canonical V10 plan sequentially. Until V10 reaches its full Definition of Done and 100% completion:

- do not start V11 or another competing version program;
- do not create a parallel frontend, Telegram architecture, AI stack, Gateway, broker/execution stack or competing roadmap outside the approved V10 program;
- do not skip directly to later V10 blocks such as public/multi-user, billing or Real execution;
- do not treat brainstormed chat ideas as approved scope when they are absent from the canonical V10 program;
- new scope goes to backlog/program-amendment review and requires explicit owner approval.

Before the owner starts V10 implementation, permitted changes remain limited to V9 security/critical maintenance, dependency maintenance, recovery and documentation correctness that do not broaden runtime authority.

Protected baseline/recovery contract:

`docs/architecture/V9_BASELINE_AND_RECOVERY_CONTRACT.md`

Protected v8.6.1 release commit:

`baba0fb73e0483fc82b3f0bc7c2f15cbd71d804e`

Protected acceptance invariant remains:

**idempotent replay verified with no second submit**.

## 3. Restore context before changes

Read in this order:

1. `README.md`;
2. `knowledge/00_PROJECT_MASTER_CONTEXT.md`;
3. `knowledge/16_CURRENT_PROGRAM_STATUS.md` for the accepted V9 runtime baseline;
4. `docs/master-plan/OMNI_CIO_V10_PROGRAM_LOCK.md`;
5. `docs/master-plan/Omni-CIO_V10_Master_Plan_RU.pdf`;
6. `knowledge/17_V10_CURRENT_PROGRAM_STATUS.md`;
7. `gpt/SETUP_INDEX.md` and `gpt/CONFIGURATION.md` for GPT-visible/recovery work;
8. `docs/architecture/SYSTEM_OVERVIEW.md`;
9. `docs/architecture/REPOSITORY_STRUCTURE.md`;
10. relevant architecture/runbook;
11. actual `main`, open PR/issues and GitHub Actions.

Use the completed V9 master plan when auditing original V9 requirements. Use `OMNI_CIO_V10_MASTER_PLAN.md` + its regenerated V10 PDF + V10 program lock as the authority for future V10 feature work.

Old chat/screenshot is not source of truth when it conflicts with current accepted `main` plus explicit owner-approved program evidence.

## 4. Broker execution boundary

### 4.1 Production read-only

`TINVEST_TOKEN` always remains read-only. It must never be promoted, replaced with the trading token, or used as fallback by Real execution.

### 4.2 Sandbox

Sandbox writes are allowed only inside `omni_cio/sandbox/` when explicitly enabled:

- fixed Sandbox host;
- `TINVEST_SANDBOX_TOKEN` only;
- `SANDBOX_TRADING_ENABLED=true`;
- `sandbox=true`, `real_money=false`;
- reviewed methods only;
- immutable proposal → exact confirmation → submit;
- UUID idempotency;
- ambiguous submit never auto-retries;
- transfer/withdraw/margin remain forbidden.

Sandbox evidence is never production portfolio mutation evidence.

### 4.3 Real execution

Real BUY/SELL is allowed only through reviewed `omni_cio.real_trading` / plan-execution lifecycle and only when server readiness is valid.

Mandatory invariants:

- separate account-scoped `TINVEST_TRADING_TOKEN` without transfer access;
- `REAL_TRADING_ENABLED=true` for Real authority;
- durable reviewed state backend; no unsafe memory fallback;
- supported cash instrument and reviewed currency/order parameters;
- own-funds BUY / own-position SELL;
- no margin/short;
- fresh trusted market/order book;
- exact price step;
- server per-order/daily hard caps;
- immutable proposal/plan context;
- exact short-lived owner confirmation from a **new** user turn;
- repeat preflight immediately before submit;
- UUID/idempotency binding;
- one possible broker submit per request identity;
- ambiguous possible-submit → unknown/do-not-resubmit, reconciliation only;
- `submitted` != `filled` without broker proof;
- account IDs masked.

Reviewed Real operationIds:

- `getRealTradingStatus`;
- `prepareRealTrade`;
- `executeRealTrade`;
- `getRealOrderState`.

Forbidden under current reviewed Real surface:

- transfer/withdraw/securities transfer;
- MARKET/BESTPRICE;
- margin/short;
- futures/options as autonomous Real execution;
- stop orders;
- replace/async submit;
- token management;
- autonomous recurring Real-money execution;
- automatic retry after possible-submit ambiguity.

`REAL_TRADING_ENABLED=false` is the master Real rollback.

## 5. Owner authorization boundary

Engineering autonomy, Watchtower alerts, portfolio-management prompts, recommendations and plans are not authorization for a new Real trade.

Every Real submit still requires the server-side reviewed confirmation/idempotency/preflight lifecycle. Never infer permission from `управляй портфелем`, maintenance instructions, V10 program approval or prior acceptance.

## 6. Internal v9 engines versus GPT Actions

WP1–WP14 internal modules are not automatically GPT Actions.

Runtime GPT Action authority is the effective production:

`https://omni-cio-gateway.onrender.com/openapi.json`

The GPT may claim a server call only when that operationId is actually published and returned evidence proves the call.

Baseline portfolio routing remains:

`getPortfolioSnapshot → getCashLiquiditySnapshot → getPortfolioAnalytics → analysis`.

Exact-action requests remain isolated: `вызови только X` must not expand to other Actions.

Hidden Watchtower/QStash routes stay excluded from GPT OpenAPI.

V10 migration rule: the current GPT Instructions/Knowledge/Actions/configuration are source assets for migration and fallback. Do not delete or weaken them merely because a local model or Web Copilot exists; removal from the required runtime path happens only after the V10 Custom GPT parity/decommission gate.

## 7. Maintenance and future V10 delivery discipline

Every significant maintenance package and, once started, every V10 work package follows:

1. restore the current source of truth and identify exactly one current WP/defect;
2. one focused branch/PR;
3. do not implement work outside the current approved V10 WP;
4. update architecture/data/threat/recovery docs when a boundary changes;
5. deterministic tests/guards for new behavior or repaired defects;
6. preserve prior safety/recovery behavior where relevant;
7. review secrets/private-data exposure;
8. exact-head Regression Shield + security;
9. zero unresolved review threads;
10. squash merge with expected-head protection where available;
11. update `knowledge/17_V10_CURRENT_PROGRAM_STATUS.md` only from merged evidence when V10 is active;
12. begin the next WP only after the current WP exit gate is satisfied.

Do not weaken CI, safety checks or type/lint/security policy just to make a dependency, maintenance or V10 PR green.

## 8. Dependency policy

Canonical dependency sources remain at repository root because Render/CI consume them directly:

- `requirements.in` — runtime direct constraints;
- `requirements.txt` — generated/hash-locked runtime set;
- `requirements-dev.in` — CI/test/security direct constraints;
- `requirements-dev.txt` — generated/hash-locked dev set.

Rules:

- edit `.in` sources, not generated locks by hand;
- regenerate/verify locks deterministically;
- generated Windows projection files are ephemeral CI artifacts and must not be committed;
- Dependabot PRs are proposals, not merge authorization;
- patch/minor/major updates all require current-main exact-head CI;
- major runtime/SDK updates get explicit compatibility review;
- known-incompatible toolchain versions are held narrowly/documented, never forced by disabling lock verification;
- external GitHub Actions remain pinned to full commit SHA.

Maintenance policy: `docs/operations/DEPENDENCY_MAINTENANCE.md` when present on accepted `main`.

## 9. Secrets and private data

Never persist/publish values of:

- `TINVEST_TOKEN`;
- `TINVEST_SANDBOX_TOKEN`;
- `TINVEST_TRADING_TOKEN`;
- `UPSTASH_REDIS_REST_TOKEN`;
- `GATEWAY_API_KEY`;
- QStash/Watchtower signing/scheduling secrets;
- future Telegram bot tokens or local V10 runtime secret values;
- Authorization headers;
- full broker account ID;
- private positions/operations/reports as repository configuration;
- private keys/certificates.

Use only env/role names, safe placeholders and masked IDs.

## 10. Runtime/deployment

Until a future V10 WP explicitly replaces a runtime boundary and passes its exit gate:

- production service: `omni-cio-gateway`;
- endpoint: `https://omni-cio-gateway.onrender.com`;
- entrypoint: `app:app`;
- deployment contract: `render.yaml`;
- durable state uses reviewed external Upstash paths where configured;
- `app_v371.py`, `app_v360.py`, `main.py` remain current dependencies until a separate compatibility refactor proves replacement.

Conditional execution routes must disappear/fail closed according to their kill switches/readiness contracts.

## 11. Applied Custom GPT configuration

Current applied UI:

`Omni-CIO API | Управляющий и аналитик v9.0.0`

Applied Instructions:

`gpt/CUSTOM_GPT_INSTRUCTIONS_V9_0_0_COMPACT.txt`

Applied Knowledge:

`gpt/KNOWLEDGE_MANIFEST_V9_0_0.md` — exactly 10 files, once each.

Protected rollback Instructions:

`gpt/CUSTOM_GPT_INSTRUCTIONS_V8_6_1_COMPACT.txt`

OpenAPI:

`https://omni-cio-gateway.onrender.com/openapi.json`

Authentication: API Key → Bearer using external `GATEWAY_API_KEY` only.

Apps stay OFF while custom Actions are used. Secret values never enter Instructions/Knowledge.

GitHub does not synchronize GPT Editor automatically. Current v9 owner acceptance is complete. Future GPT-visible changes require review → Preview → `Update` on the **same** GPT → non-secret evidence unless a later owner-accepted V10 WP explicitly retires that interface.

## 12. Money/data quality

- exact decimal logic;
- do not mix currencies without verified FX + timestamp;
- do not double-count commissions/child operations/embedded trades;
- incomplete/partial/truncated/contradictory data is not full truth;
- last price is not guaranteed execution price;
- stale market blocks unjustified exact sizing/Real proposal;
- `withdraw_limits` is not automatically buying budget;
- technical affordability is not personal sizing;
- free cash alone is not a reason to buy;
- BUY uses own funds, SELL own position under reviewed Real lifecycle.

## 13. Broker-report integrity

For `getBrokerReportReconciliation` preserve the async contract:

- `days=1..31`;
- first request without `task_id`;
- `wait_seconds=0` may return `pending` + real `task_id`;
- follow-up uses same `task_id`;
- T-Invest `30058` means pending;
- unrelated errors are not renamed pending;
- ready/full result only when contract says complete.

## 14. Repository structure

Current V9 structure remains authoritative until changed by the appropriate future V10 WP:

- root wrappers/runtime + `omni_cio/`;
- Sandbox: `omni_cio/sandbox/`;
- Real: `omni_cio/real_trading/`;
- safe plan execution: `omni_cio/plan_execution/`;
- Watchtower: `omni_cio/watchtower/`;
- decision journal/evaluation: `omni_cio/decision_journal/`;
- GPT config/recovery: `gpt/`;
- engineering memory: `knowledge/`;
- architecture: `docs/architecture/`;
- master programs: `docs/master-plan/`;
- runbooks/maintenance: `docs/operations/`;
- tests: `tests/`;
- CI/security: `scripts/`, `.github/`.

One-time bootstrap payloads and generated CI projections must not remain in accepted `main` after their task is complete.

Do not create duplicate setup/audit/inventory docs instead of updating existing sources of truth.

## 15. Required verification

Regression Shield is the merge gate and must remain strict. It covers at minimum:

- lock reproducibility;
- CI/security policy;
- repository structure/boundaries;
- source compilation;
- Ruff lint/format;
- mypy baseline;
- `app:app` stability until intentionally retired by accepted V10 work;
- GPT Action/recovery contracts while GPT remains applied;
- pytest/coverage;
- dependency audit;
- SAST;
- secret scan.

The separate live Gateway authority workflow may perform public `/health` + `/openapi.json` GET verification only. It must never send secrets or call protected broker Actions.

## 16. Cleanup discipline

Before deleting/moving anything:

1. search imports/references;
2. inspect tests/CI/scripts;
3. inspect Render/GPT/recovery docs;
4. prove replacement/retirement;
5. add a regression guard where appropriate;
6. use a focused branch/PR;
7. pass exact-head Regression Shield/security.

Versioned filenames are not proof of obsolescence. Conversely, one-time bootstrap/generated artifacts should not be kept forever once their references are proven retired.

## 17. Current status

- applied GPT: **v9.0.0 owner-accepted**;
- V9 WP0–WP15: complete;
- protected v8.6.1 rollback: retained;
- production read-only: accepted;
- Sandbox: conditional/virtual;
- Real BUY/SELL lifecycle: accepted/protected;
- current V9 runtime mode: controlled maintenance;
- V10: **owner-approved program locked, development not started, 0%**;
- successor versions: **not authorized until V10 reaches 100% and final acceptance**.

Current V9 runtime status: `knowledge/16_CURRENT_PROGRAM_STATUS.md`.  
Current V10 program status: `knowledge/17_V10_CURRENT_PROGRAM_STATUS.md`.
