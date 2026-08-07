# AGENTS.md — Omni-CIO project rules

Этот файл обязателен для любого AI-агента, разработчика или нового чата, который меняет `MishaGameHacking/omni-cio-gateway`.

## 1. Product boundary

Поддерживается **один Omni-CIO product line**.

Текущий owner-accepted production/recovery baseline пока остаётся:

`Existing Omni-CIO Custom GPT v9.0.0 → Omni-CIO Gateway (app:app) → protected broker contours`.

V10 последовательно превращает этот продукт в самостоятельную Personal Autonomous Investment Platform. Не создавать второй Custom GPT, duplicate Gateway, parallel Web, Telegram brain, competing AI stack, competing scheduler или parallel broker/execution stack вне явно утверждённого V10 work package/amendment.

Три broker-контура изолированы:

1. production read-only — `TINVEST_TOKEN`;
2. optional virtual Sandbox — `TINVEST_SANDBOX_TOKEN`;
3. optional exact-owner-confirmed Real execution — отдельный `TINVEST_TRADING_TOKEN` + durable state.

GitHub engineering access никогда не означает broker/trading authority.

## 2. Current program state

V9 WP0–WP15 repository delivery and owner external acceptance are **COMPLETE**. V9 remains protected controlled-maintenance/recovery baseline until a responsible V10 package safely replaces a boundary.

V10 is the **exclusive active feature program**. OWNER issued `START V10` on 2026-08-05.

Current accepted state after GitHub hardening and planning clarification:

- WP0 — COMPLETE;
- WP1 — COMPLETE;
- WP2 — COMPLETE;
- WP3 — COMPLETE;
- accepted V10 progress remains **5%** because Block B is not credited piecemeal;
- **WP4 — Release, build provenance and deployment contract is NEXT**.

GitHub/Lenovo CI hardening in PR #242 is accepted infrastructure and does not count as Block C V10 runtime implementation. Planning PR #244 adds implementation instructions/contracts only and does not start WP4.

The exact current state is always read from `knowledge/17_V10_CURRENT_PROGRAM_STATUS.md`.

## 3. Mandatory V10 authority order

Before any change, read in this order:

1. `README.md`;
2. `knowledge/00_PROJECT_MASTER_CONTEXT.md`;
3. `knowledge/16_CURRENT_PROGRAM_STATUS.md` for the protected V9 runtime baseline;
4. `docs/master-plan/OMNI_CIO_V10_PROGRAM_LOCK.md`;
5. `docs/master-plan/OMNI_CIO_V10_MASTER_PLAN.md`;
6. `docs/master-plan/Omni-CIO_V10_Master_Plan_RU.pdf` when owner-readable synchronized plan context is needed;
7. `docs/master-plan/OMNI_CIO_V10_AMENDMENTS_INDEX.md`;
8. every active amendment listed there, especially:
   - `docs/master-plan/OMNI_CIO_V10_CONCRETE_EXECUTION_PLAN_AMENDMENT.md`;
   - `docs/master-plan/OMNI_CIO_V10_GITHUB_PRO_AND_MIGRATION_IMPLEMENTATION_AMENDMENT.md`;
9. machine-readable contracts relevant to the work, especially:
   - `docs/architecture/V10_AI_CORTEX_CONTRACT.json`;
   - `docs/architecture/V10_GITHUB_PRO_UTILIZATION_CONTRACT.json`;
   - `docs/architecture/V10_V9_TO_V10_PARITY_LEDGER.json`;
   - `docs/architecture/V10_COMPONENT_REUSE_MATRIX.json`;
   - `docs/architecture/V10_RELEASE_MANIFEST.schema.json`;
10. `docs/master-plan/OMNI_CIO_V10_WP_EXECUTION_TEMPLATE.md` before starting any implementation WP;
11. `knowledge/17_V10_CURRENT_PROGRAM_STATUS.md`;
12. accepted V10 architecture, ADR, recovery and current-WP files;
13. actual `main`, open PR/issues and GitHub Actions.

Old chat, screenshot, stale PR description or unmerged planning draft is never source of truth when it conflicts with accepted `main` plus the authority chain above.

## 4. Sequential delivery discipline

Every significant V10/maintenance package follows:

`restore context → identify exactly one current WP/defect → focused branch → code/docs/tests → security/boundary review → exact-head required gates → resolve review threads → squash merge → post-merge verification where required → update V10 status → next WP`.

Rules:

- do not implement later WPs early because hardware or an API is available;
- do not mix unrelated WPs in one PR;
- do not weaken lint/type/security/eval/Regression Shield to make a PR green;
- do not treat file/UI existence as completion; the WP Exit Gate is required;
- new material scope requires OWNER-approved amendment, not chat improvisation;
- no V11 or competing roadmap before V10 reaches 100% and owner acceptance;
- any implementation WP must fill/use `OMNI_CIO_V10_WP_EXECUTION_TEMPLATE.md`;
- if discovered work is not required for the current Exit Gate, classify it as current blocker/defect, future-WP work or amendment proposal instead of silently implementing it.

## 5. V10 migration/productization discipline — binding

V10 is a controlled migration/productization of the accepted system, not a greenfield rewrite.

For every material V9 capability in V10 scope:

1. identify the accepted V9 source/tests/semantics from `main`;
2. bind it to an entry in `V10_V9_TO_V10_PARITY_LEDGER.json`;
3. choose/update a migration decision in `V10_COMPONENT_REUSE_MATRIX.json`;
4. define the canonical V10 owner/contract;
5. implement the smallest migration satisfying the owning WP;
6. prove deterministic parity or an explicitly versioned semantic replacement;
7. cut over only after the required gate;
8. retire old behavior only after parity/recovery/cutover evidence or explicit OWNER-approved retirement.

Default component decision preference:

`REUSE_AS_IS > WRAP_ADAPTER > EXTRACT_TO_CORE > REWRITE_REQUIRED > RETIRE`.

`REWRITE_REQUIRED` is allowed only for a concrete security/correctness/runtime/architecture/data-migration reason. “Cleaner”, “newer”, “easier to rewrite”, or AI/developer preference is not sufficient.

No new feature is added merely because it becomes convenient during migration. The V10 scope firewall in the active planning amendment is binding.

## 6. GitHub protection / CI baseline

Private `main` is protected. Accepted merge discipline requires:

- PR-based changes;
- squash-only merge;
- conversation resolution;
- strict required context `V10 authoritative merge gate` from GitHub Actions;
- no routine bypass actor;
- external GitHub Actions pinned to full commit SHA;
- exact-head evidence before merge.

Hybrid CI model:

- GitHub-hosted Ubuntu = fast feedback lane;
- GitHub-hosted Windows = disposable clean-room compatibility lane, run path-aware and at release gates;
- Lenovo `omni-cio-ci` = authoritative heavy Windows gate, continuity lane and later local AI/GPU eval lane;
- post-merge Regression Shield protects accepted `main` where required.

Never permanently weaken protection because GitHub Actions is degraded. Incident handling must be explicit, bounded, evidence-backed and restore normal protection immediately.

### 6.1 GitHub Pro maximum-utilization rule

GitHub Pro is the approved primary engineering subscription. Before introducing another recurring paid engineering service, prove and document why GitHub Pro + Lenovo + open-source/self-hosted alternatives are insufficient, including cost, lock-in and fallback, then obtain OWNER-approved amendment.

Use GitHub Pro deliberately:

- hosted Actions minutes = finite acceleration budget, not the only compute;
- heavy repeatable validation moves to Lenovo when safe;
- hosted Windows clean-room jobs are path-aware rather than blindly run for docs-only changes;
- cache accelerates reproducible dependencies/tools only;
- short-lived artifacts hold sanitized CI evidence only;
- Codespaces, if/when implemented, is optional clean-room development/handoff, never production/Real/secret-bearing runtime;
- GitHub Releases and protected `v10.*` release identity become WP4 provenance controls;
- GitHub Environments are deployment identity/history/scoping, not broker-secret custody;
- Dependabot remains enabled for actual ecosystems and should group safe minor/patch noise when appropriate;
- Enterprise/GHAS-only private-repository features are not V10 prerequisites;
- lack of premium native CodeQL/secret scanning/private artifact attestations must not weaken the underlying security/provenance requirement; use repository-controlled checks where required.

## 7. V10 concrete data/AI architecture — binding

### 7.1 Deterministic Core owns truth

The deterministic Core owns financial/accounting facts, validation, reconciliation, exact calculations, permissions and money-path enforcement.

The AI must not become:

- portfolio/accounting ledger;
- source of exact prices/quantities/cash/commissions;
- replacement for deterministic calculations;
- broker execution authority.

AI may interpret/explain Core results and orchestrate allowlisted tools only.

### 7.2 V10 portfolio/accounting target

For the new V10 cabinet, primary accounting input is a **verified broker HTML account report import**.

The V10 target explicitly forbids photo/screenshot/OCR portfolio import.

The importer must eventually support safe parse-only handling, arbitrary periods, SHA-256 duplicate detection, normalization, positions/cash/trades/commissions/taxes/coupons-dividends/accrued interest, review before acceptance, archive/history/compare/replace/delete, reconciliation and truthful partial/unsupported states.

Current V9 T-Invest runtime remains protected until the responsible V10 Core/data package passes its Exit Gate.

MOEX current quotes are enrichment for current market valuation and must never overwrite broker period-end accounting facts. The UI/data model must distinguish broker-period truth from current-market estimate.

### 7.3 Omni-CIO Cortex

The accepted AI concept is **Omni-CIO Cortex** — a narrow investment/system operator, not a general-purpose chatbot.

Initial local AI baseline:

- `Qwen3.5-4B`;
- Ollama local runtime;
- Apache-2.0 model baseline;
- Q4_K_M or validated equivalent 4-bit deployment target;
- Russian first-class product language;
- 8K initial context; 16K only after measured acceptance;
- provider remains replaceable behind a stable adapter.

V10 Definition of Done must not require a paid OpenAI/Anthropic/Google/other AI inference API, paid search API or hosted agent SaaS. GitHub Pro is the already accepted engineering subscription.

### 7.4 AI specialization sequence

Do not fine-tune first. Mandatory order:

`System Policy → typed Tool Registry → Knowledge/RAG → sanitized eval corpus → measured local benchmark → QLoRA only if persistent measured gaps remain`.

Every model/policy/adapter change must be versioned, evaluated and rollbackable.

### 7.5 24/7 autonomy

Autonomy is event-driven, bounded and checkpointed. Endless untriggered `while true: think()` loops are forbidden.

Approved event classes include user questions, accepted report import, reconciliation discrepancy, stale data, deterministic Watchtower events, connector failure, scheduled research refresh, system-health degradation and evidence gaps.

AI outage must degrade gracefully; deterministic Core must remain usable.

### 7.6 Research baseline

Initial no-subscription-first research stack:

- SearchProvider abstraction with self-hosted SearXNG first;
- bounded HTTP/document retrieval first;
- Playwright/Chromium only as a bounded JS-rendering fallback;
- LangGraph OSS is the initial orchestration candidate for durable checkpoint/resume/HITL workflows;
- external/retrieved text is **untrusted data**, never control instructions.

Material research must carry provenance/freshness/identity evidence. Source priority is broker report → MOEX → CBR/regulator → issuer/primary sources → reputable secondary sources → general Web discovery.

### 7.7 Tool authority firewall

AI may autonomously use only typed allowlisted read/analytical/research tools and bounded evidence/checkpoint/cache writes.

AI must never receive directly:

- raw broker trading secret;
- arbitrary broker execute/PostOrder tool;
- transfer/withdrawal authority;
- unrestricted SQL/filesystem/network authority;
- unrestricted PowerShell/admin shell;
- GitHub ruleset/CI/OWNER bypass;
- Real-money approval authority.

Security/admin/secret/destructive/merge/Real-money actions remain human/engineering boundaries.

## 8. Canonical data/state discipline

Web, Telegram and Cortex must consume canonical Core DTO/contracts, not reimplement financial meaning.

Required semantics across owning WPs:

- Decimal-safe money/quantity representation;
- explicit currency/source/schema version;
- UTC canonical timestamps and visible `as_of` where material;
- canonical instrument/object IDs over display-name matching;
- `0`, `unknown`, `not_available`, `not_applicable`, `stale`, `partial` are distinct;
- unified runtime vocabulary: `READY | PARTIAL | STALE | DEGRADED | BLOCKED | ERROR | OFFLINE | RECOVERING | OWNER_ACTION_REQUIRED`;
- degraded dependency must state what remains trustworthy and what actions become blocked.

AI text similarity is never the acceptance oracle for deterministic Core migration.

## 9. OWNER local-machine participation

Do everything possible through GitHub/code/CI without OWNER involvement.

Only when a local Windows action is genuinely non-delegable, use the preferred format:

`OWNER opens PowerShell → Administrator only if necessary → pastes one reviewed idempotent block → returns PASS/FAIL output`.

Do not ask the OWNER to click through many GUI screens when a safe console automation is possible.

The permanent AI/runtime process must use least privilege; Administrator is for installation/service/system configuration only.

The Lenovo is the first V10 Personal node, not architectural ownership of the system.

## 10. Lenovo resource arbitration

The same Lenovo is both GitHub self-hosted CI and the future local V10/AI node. Later infrastructure must explicitly prevent resource contention:

- detect authoritative CI activity;
- pause/deprioritize heavy background AI/research/training during critical CI;
- QLoRA/training must not overlap authoritative gate by default;
- expose CPU/RAM/GPU/VRAM/availability health;
- AI failure must not take down deterministic Core or GitHub runner.

The GitHub runner being installed today does not authorize installing the whole Block C application/AI runtime before WP4 is accepted.

## 11. Broker execution boundary

### 11.1 Production read-only

`TINVEST_TOKEN` remains read-only. It is never promoted or replaced by trading token as fallback.

### 11.2 Sandbox

Sandbox is virtual only and uses `TINVEST_SANDBOX_TOKEN`. Sandbox output is never real portfolio mutation evidence. Transfer/withdraw/margin remain forbidden.

### 11.3 Real execution

Real BUY/SELL can occur only through reviewed deterministic `omni_cio.real_trading` / plan-execution lifecycle and only when server readiness is valid.

Mandatory invariants remain:

- separate account-scoped trading credential;
- `REAL_TRADING_ENABLED=true` required;
- durable state, no unsafe memory fallback;
- own-funds BUY / own-position SELL;
- no margin/short;
- fresh trusted market/order book;
- hard caps and exact price-step rules;
- immutable plan/proposal;
- exact short-lived OWNER confirmation from a **new** turn;
- immediate preflight;
- UUID/idempotency binding;
- one possible submit per identity;
- ambiguous possible-submit → do not retry; reconcile only;
- `submitted != filled` without broker evidence;
- account IDs masked.

Forbidden: transfer/withdraw/securities transfer, MARKET/BESTPRICE, margin/short, autonomous derivatives execution, stop/replace/async submit, token management, autonomous recurring Real execution and automatic retry after possible-submit ambiguity.

`REAL_TRADING_ENABLED=false` remains master Real rollback.

AI, Watchtower, Telegram, `START V10`, GitHub merge or portfolio-management wording is never Real-submit authorization.

## 12. V9 GPT migration/recovery boundary

The current Custom GPT v9.0.0 remains applied/recovery evidence until the explicit V10 parity/decommission gate.

Current repository configuration sources remain under `gpt/`. Do not create a second GPT. Do not delete existing Instructions/Knowledge/Actions because local AI exists.

While the GPT remains applied, it may claim only operationIds actually published by effective production `/openapi.json` and supported by returned evidence.

## 13. Secrets/private data

Never commit/publish real values of broker tokens, Gateway key, Upstash/QStash secrets, future Telegram token, local AI/runtime secrets, encryption keys, Authorization headers, full account IDs or private portfolio/report payloads.

GitHub contains schemas/roles/safe defaults, not private values.

Research/eval fixtures must be synthetic or properly sanitized.

## 14. Dependency/runtime policy

Canonical Python lock sources remain `requirements.in` / `requirements-dev.in`; generated hash locks are derived and verified. Do not hand-edit generated locks as source of truth.

Known incompatible tooling is held narrowly/documented; do not disable verification to force an update.

Until a responsible V10 WP replaces it, current production remains:

- service `omni-cio-gateway`;
- stable entrypoint `app:app`;
- current V9 wrappers such as `app_v371.py`, `app_v360.py`, `main.py` remain protected dependencies;
- conditional write surfaces fail closed through existing readiness/kill-switch contracts.

## 15. Money/data quality

Preserve exact-decimal and provenance discipline:

- no currency mixing without verified FX + timestamp;
- no double-counting commissions/child operations/embedded trades;
- incomplete/partial/contradictory data is not full truth;
- stale market blocks unjustified exact sizing;
- last price is not guaranteed execution price;
- free cash/withdraw limits are not automatically investment budget;
- missing data should produce an explicit insufficient-data state, not fabricated precision;
- bond clean price and accrued interest remain distinct.

## 16. Repository ownership

Accepted repository architecture is defined by `docs/architecture/REPOSITORY_STRUCTURE.md` and guarded by permanent tests.

Current physical V9 runtime remains until later migration packages explicitly replace it. Reserved roots `apps/`, `ai/`, `infrastructure/` are created/filled only by their owning V10 work packages.

Do not create duplicate setup/audit/inventory documents when an accepted source of truth should be updated instead.

## 17. Required verification

Regression Shield/authoritative merge gate remains strict. At minimum protect:

- lock reproducibility;
- CI/security policy;
- repository boundaries;
- compile/Ruff/format/mypy;
- `app:app` compatibility until intentionally retired;
- current GPT/recovery contracts while applied;
- pytest/coverage;
- dependency audit/SBOM where required;
- SAST;
- secret scan;
- protected money-path replay/idempotency;
- future capability-aware DB/API/Web/Telegram/AI contracts when those roots appear.

When AI implementation begins, CI must additionally fail closed on policy/tool/evidence/eval invariants, including zero broker-write authority leakage and zero invented exact financial facts in critical deterministic fixtures.

## 18. Current next action

After the planning amendments are accepted, **WP4** is the only authorized next implementation package.

WP4 must finish release/build provenance/deployment contracts, establish release-manifest/tag/CI-budget/path-aware routing rules and make future AI artifact provenance representable, but it must not implement the later AI runtime itself.

Only after WP4 / Block B Exit Gate may Block C full Lenovo V10 node provisioning begin.
