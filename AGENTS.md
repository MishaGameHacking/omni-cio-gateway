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

Не создавать второй Custom GPT, отдельный frontend, duplicate Gateway, competing scheduler или parallel broker/execution stack без отдельного owner-approved program.

## 2. Program state

Owner-approved/program-locked v9 program:

`docs/master-plan/OMNI_CIO_V9_PORTFOLIO_AUTOPILOT_PROGRAM.md`

WP0–WP15 repository delivery and owner external acceptance are **complete**. Tracking epic #176 and WP15 #216 are closed completed.

Current repository mode: **controlled maintenance**.

Feature work outside maintenance/security/dependency/recovery requires a new explicit owner-approved program. Do not reinterpret the completed v9 master plan as an unfinished queue.

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
3. `knowledge/16_CURRENT_PROGRAM_STATUS.md`;
4. `gpt/SETUP_INDEX.md` and `gpt/CONFIGURATION.md` for GPT-visible/recovery work;
5. `docs/architecture/SYSTEM_OVERVIEW.md`;
6. `docs/architecture/REPOSITORY_STRUCTURE.md`;
7. relevant architecture/runbook;
8. actual `main`, open PR/issues and GitHub Actions.

Use the completed master plan when auditing original v9 requirements or considering a new owner-approved program.

Old chat/screenshot is not source of truth when it conflicts with current accepted `main` plus explicit external owner evidence.

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

Every Real submit still requires the server-side reviewed confirmation/idempotency/preflight lifecycle. Never infer permission from `управляй портфелем`, maintenance instructions or prior acceptance.

## 6. Internal v9 engines versus GPT Actions

WP1–WP14 internal modules are not automatically GPT Actions.

Runtime GPT Action authority is the effective production:

`https://omni-cio-gateway.onrender.com/openapi.json`

The GPT may claim a server call only when that operationId is actually published and returned evidence proves the call.

Baseline portfolio routing remains:

`getPortfolioSnapshot → getCashLiquiditySnapshot → getPortfolioAnalytics → analysis`.

Exact-action requests remain isolated: `вызови только X` must not expand to other Actions.

Hidden Watchtower/QStash routes stay excluded from GPT OpenAPI.

## 7. Maintenance delivery discipline

Every significant maintenance package follows:

1. identify current source of truth and exact defect;
2. one focused branch/PR;
3. update architecture/data/threat/recovery docs only when boundary changes;
4. deterministic tests/guards for the defect;
5. preserve old behavior/safety where relevant;
6. review secrets/private-data exposure;
7. exact-head Regression Shield + security;
8. zero unresolved review threads;
9. squash merge with expected-head protection where available;
10. external Preview/Update only if applied GPT configuration/Action contract changed.

Do not weaken CI, safety checks or type/lint/security policy just to make a dependency or maintenance PR green.

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
- Authorization headers;
- full broker account ID;
- private positions/operations/reports as repository configuration;
- private keys/certificates.

Use only env/role names, safe placeholders and masked IDs.

## 10. Runtime/deployment

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

GitHub does not synchronize GPT Editor automatically. Current v9 owner acceptance is complete. Future GPT-visible changes require review → Preview → `Update` on the **same** GPT → non-secret evidence.

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

- root wrappers/runtime + `omni_cio/`;
- Sandbox: `omni_cio/sandbox/`;
- Real: `omni_cio/real_trading/`;
- safe plan execution: `omni_cio/plan_execution/`;
- Watchtower: `omni_cio/watchtower/`;
- decision journal/evaluation: `omni_cio/decision_journal/`;
- GPT config/recovery: `gpt/`;
- engineering memory: `knowledge/`;
- architecture: `docs/architecture/`;
- completed v9 program spec: `docs/master-plan/`;
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
- `app:app` stability;
- GPT Action/recovery contracts;
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
- WP0–WP15: complete;
- protected v8.6.1 rollback: retained;
- production read-only: accepted;
- Sandbox: conditional/virtual;
- Real BUY/SELL lifecycle: accepted/protected;
- repository mode: controlled maintenance.

Current exact status: `knowledge/16_CURRENT_PROGRAM_STATUS.md`.
