# AGENTS.md — Omni-CIO project rules

Этот файл обязателен для любого AI-агента, разработчика или нового чата, который меняет `MishaGameHacking/omni-cio-gateway`.

## 1. Product boundary

Поддерживается **один Omni-CIO product line**.

Текущий owner-accepted production/recovery baseline пока остаётся:

`Existing Omni-CIO Custom GPT v9.0.0 → Omni-CIO Gateway (app:app) → protected broker contours`.

V10 последовательно превращает этот продукт в самостоятельную Personal Autonomous Investment Platform. Не создавать второй Custom GPT, duplicate Gateway, parallel Web, Telegram brain, competing AI stack, competing scheduler или parallel broker/execution stack вне явно утверждённого V10 execution unit/amendment.

Три protected V9 broker-контура изолированы:

1. production read-only — `TINVEST_TOKEN`;
2. optional virtual Sandbox — `TINVEST_SANDBOX_TOKEN`;
3. optional exact-user-confirmed Real execution — отдельный `TINVEST_TRADING_TOKEN` + durable state.

For public V10, broker credentials are **not global application credentials**: they belong only to the authenticated tenant's `BrokerConnection` according to the active Identity and Public Free Multi-User Hosted Runtime amendments.

GitHub engineering access никогда не означает broker/trading authority.

## 2. Current program state

V9 WP0–WP15 repository delivery and owner external acceptance are **COMPLETE**. V9 remains protected controlled-maintenance/recovery baseline until a responsible V10 package safely replaces a boundary.

V10 is the **exclusive active feature program**. OWNER issued `START V10` on 2026-08-05.

The exact current state is always read from `knowledge/17_V10_CURRENT_PROGRAM_STATUS.md`; this file must not be treated as a competing progress ledger.

Current accepted snapshot:

- V10 WP0–WP22A are accepted COMPLETE according to the current-status/evidence chain;
- accepted V10 progress is **54%** because Block E has now passed the complete `WP22A — External Web Access / Product Authentication Security Gate` technical Exit Gate;
- **WEB-VISUAL-INTEGRATED — Premium Spatial Financial OS A→G System Update / OWNER START REQUIRED** is the next prepared functional execution unit under Amendment 12;
- **PRODUCT IMPLEMENTATION PAUSED** until the exact OWNER command `START V10 WEB VISUAL SYSTEM UPDATE` is explicitly issued after Amendment 12 acceptance;
- WP22A technical acceptance remains separate from the later public-production activation gate;
- WP23+ remains LOCKED behind acceptance of the complete visual System Update and Master Plan authorization;
- public multi-user/global browser service is the approved target, but `PUBLIC_MULTI_USER_ENABLED=false` remains the safe implementation default until the separate production-activation/security/privacy/broker/legal/capacity gates are accepted;
- final public production must not depend on PROJECT OWNER home IP/Wi-Fi/router/LAN/Lenovo; the selected final managed-cloud provider remains Cloud.ru Evolution and final provider apply is still locked;
- initial registered-user access is free: billing/trial/subscription enforcement/premium gating are disabled for initial launch;
- broker-write / Real execution authority remains unchanged and not authorized by this status or Amendment 12.

The PROJECT OWNER is not a special Omni-CIO product role. When using Omni-CIO, the PROJECT OWNER is an ordinary USER on the same `OmniCIOUserAccount -> Tenant -> Session` path as supported users. GitHub/cloud-provider/Windows/CI authority stays outside product identity.

The OWNER-approved Engineering Quality / Pre-CI / Green-Merge governance package is accepted and active. The OWNER-approved **Integrated System Update Execution Law / Amendment 12** changes delivery granularity only; it does not advance V10 product progress or unlock another major System Update.

Documentation lifecycle and the distinction between current authority and historical WP records are defined in `docs/DOCUMENTATION_AUTHORITY_AND_LIFECYCLE.md`.

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
   - `docs/master-plan/OMNI_CIO_V10_ENGINEERING_QUALITY_AND_GREEN_MERGE_AMENDMENT.md`;
   - `docs/master-plan/OMNI_CIO_V10_PRODUCT_USER_AND_ENGINEERING_AUTHORITY_BOUNDARY_AMENDMENT.md`;
   - `docs/master-plan/OMNI_CIO_V10_PUBLIC_FREE_MULTI_USER_HOSTED_RUNTIME_AMENDMENT.md`;
   - `docs/master-plan/OMNI_CIO_V10_WP22A_TECHNICAL_CLOSEOUT_AND_PUBLIC_ACTIVATION_SEPARATION_AMENDMENT.md`;
   - `docs/master-plan/OMNI_CIO_V10_INTEGRATED_SYSTEM_UPDATE_EXECUTION_AMENDMENT.md`;
9. machine-readable contracts relevant to the work, especially:
   - `docs/architecture/V10_INTEGRATED_SYSTEM_UPDATE_EXECUTION_CONTRACT.json`;
   - `docs/architecture/V10_PUBLIC_FREE_MULTI_USER_HOSTED_RUNTIME_CONTRACT.json`;
   - `docs/architecture/V10_AI_CORTEX_CONTRACT.json`;
   - `docs/architecture/V10_GITHUB_PRO_UTILIZATION_CONTRACT.json`;
   - `docs/architecture/V10_V9_TO_V10_PARITY_LEDGER.json`;
   - `docs/architecture/V10_COMPONENT_REUSE_MATRIX.json`;
   - `docs/architecture/V10_RELEASE_MANIFEST.schema.json`;
   - `docs/architecture/V10_ENGINEERING_QUALITY_GATE_CONTRACT.json`;
10. `docs/master-plan/OMNI_CIO_V10_WP_EXECUTION_TEMPLATE.md` before starting any implementation execution unit/member milestone;
11. `knowledge/17_V10_CURRENT_PROGRAM_STATUS.md`;
12. accepted V10 architecture, ADR, recovery and current execution-unit files/Execution Ledger when authorized;
13. actual `main`, open PR/issues and GitHub Actions.

Old chat, screenshot, stale PR description, package-local historical status heading or unmerged planning draft is never source of truth when it conflicts with accepted `main` plus the authority chain above.

## 4. Integrated System Update Execution Law and engineering-quality discipline

Every material V10 change uses exactly one execution unit:

- `FOCUSED_CHANGE` — a genuinely isolated defect, governance/documentation correction, maintenance item, independent migration step or mandatory split boundary;
- `INTEGRATED_SYSTEM_UPDATE` — one coherent OWNER-authorized system/subsystem outcome with ordered member WP/increments.

For `INTEGRATED_SYSTEM_UPDATE`:

- one integrated branch and one final PR are the default;
- member WP/increments remain mandatory ordered internal milestones and keep Master Plan dependency order;
- internal milestone PASS is branch-local only and never advances accepted V10 percentage, changes accepted `main`, unlocks the next major System Update, activates public production or authorizes broker/Real execution;
- every integrated update uses `docs/updates/INTEGRATED_SYSTEM_UPDATE_EXECUTION_LEDGER_TEMPLATE.md` and the GitHub System Update dashboard issue template;
- both working-state records must say `BRANCH-LOCAL EXECUTION STATE — NOT ACCEPTED MAIN AUTHORITY`;
- before first external verification publication, all required member milestones, known focused failures, full-diff review, directly coupled producer/consumer/config/workflow review, analogous-pattern search where material, adjacent failure review, deterministic regression guards, security/recovery review and mandatory split-trigger review must pass; only then mark `INTEGRATION_READY`.

CI is an independent verifier, not the normal interactive debugger.

After a verification SHA is published, **HEAD FREEZE** applies while the current safe independent verification batch reaches terminal state. A first ordinary RED is not a signal to immediately push another symptom-fix commit. Where safe and technically possible:

1. allow independent applicable checks to reach terminal state;
2. collect available GitHub Actions, authoritative Windows CI, Sonar, Gitar, SAST/security, browser/E2E and owning-gate findings;
3. create one consolidated finding inventory;
4. group findings by root cause/defect class;
5. perform root-cause, blast-radius, analogous-pattern, coupled-surface, adjacent-failure and security/recovery analysis;
6. add permanent regression guards for reusable defect classes;
7. publish one coherent correction batch only after complete focused/local preflight.

`continue-on-error` must never make a required RED look GREEN. Safety abort overrides diagnostic completeness if continued execution could expose real secrets/private data, reach broker-write/Real-money authority, perform destructive migration/provider mutation, create uncontrolled paid-resource mutation or expose another tenant.

Any new published commit invalidates previous final exact-head GREEN evidence.

Mandatory split triggers are evidence-based, not WP-number-based:

1. DB/migration ordering;
2. security/authority transition;
3. dependency/toolchain boundary;
4. genuinely non-delegable OWNER/provider action;
5. live/temporal evidence such as soak/Shadow Mode;
6. production cutover;
7. Real-money authority;
8. reviewability limit.

For `FOCUSED_CHANGE`, the protected lifecycle remains a focused branch/PR. For `INTEGRATED_SYSTEM_UPDATE`, the protected lifecycle is:

`restore authority → exact OWNER-authorized System Update → integrated branch → ordered internal milestones → INTEGRATION_READY → one coherent published head → DRAFT exact-head verification → HEAD FREEZE → independent review → coherent correction batch if required → fresh final exact-head verification → READY → fresh applicable READY SUCCESS → zero blockers → squash merge → exact new main → Regression Shield/owning post-merge gates → accepted status transition`.

Binding rules:

- do not implement a later major System Update early because hardware or an API is available;
- do not silently absorb unrelated scope into an integrated update;
- do not weaken lint/type/security/eval/Regression Shield to make a PR green;
- do not treat file/UI existence or an internal milestone checkbox as accepted completion;
- new material scope requires OWNER-approved amendment, not chat improvisation;
- no V11 or competing roadmap before V10 reaches 100% and owner acceptance;
- implementation execution units/member milestones must fill/use `OMNI_CIO_V10_WP_EXECUTION_TEMPLATE.md`;
- if discovered work is not required for the current execution-unit outcome, classify it as current blocker/defect, future work, mandatory split or amendment proposal instead of silently implementing it;
- before an expensive full cycle, establish root cause where applicable, inspect the complete changed surface and directly coupled consumers/producers, search analogous repository patterns, inspect adjacent failure modes, add a permanent regression guard when the defect class is reusable, and run available cheap/focused checks;
- a one-line patch is acceptable only when evidence proves the defect class is genuinely local;
- an unexpected material RED after declared preflight readiness requires a confidence postmortem and reusable lesson in `docs/operations/V10_ENGINEERING_FAILURE_LEARNING_LEDGER.md`;
- every **applicable** exact-head V10 check must actually execute and conclude `success`; `failure`, `cancelled`, `queued`, `pending`, `in_progress`, `timed_out`, `action_required`, `stale`, `neutral` and `skipped` are not V10 GREEN evidence for an applicable gate;
- infrastructure/billing/provider failures must be classified truthfully, but a RED applicable check still blocks merge;
- normal PR closure is GREEN exact head → final diff/review → squash merge; an unmerged superseded PR is historical work, never accepted implementation.

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
- external GitHub Actions pinned to full commit SHA where used;
- exact-head evidence before merge.

Hybrid CI model:

- GitHub-hosted runners are acceleration/disposable compatibility evidence when OWNER-controlled hosted capacity is actually available;
- Lenovo `omni-cio-ci` is the authoritative heavy Windows gate and continuity lane;
- post-merge Regression Shield protects accepted `main` where required;
- no green capacity/routing check may be described as hosted clean-room PASS unless the hosted clean-room workload actually executed.

Current OWNER-observed GitHub Actions budget/payment state is an external condition and must not be silently changed. While the accepted machine-readable quality contract records a zero-budget hard stop:

- do not silently increase budget, alter payment settings or disable the hard stop;
- do not repeatedly trigger hosted jobs already known to be unable to start;
- use Lenovo for deterministic checks where semantics are equivalent;
- keep `V10 authoritative merge gate` mandatory;
- capacity-deferred compatibility jobs must execute a real routing/capacity contract and report truthfully instead of becoming job-level `skipped` GREEN evidence;
- absence of disposable hosted compatibility does not fabricate compatibility PASS;
- STABLE release provenance may not claim clean-room evidence that was not produced;
- when hosted capacity changes, re-verify current external state and restore hosted lanes only through a focused GREEN CI/governance PR.

Canonical current details are in:

- `docs/architecture/V10_REGRESSION_SHIELD.md`;
- `docs/V10_GITHUB_PRO_HYBRID_CI.md`;
- `docs/operations/V10_CI_COST_CONTROL_STANDARD.md`.

Never weaken protection because GitHub Actions is degraded. Incident handling must be explicit, bounded, evidence-backed and restore the reviewed normal/available-capacity mode through source control.

### 6.1 GitHub Pro maximum-utilization rule

GitHub Pro is the approved primary engineering subscription. Before introducing another recurring paid engineering service, prove and document why GitHub Pro + Lenovo + open-source/self-hosted alternatives are insufficient, including cost, lock-in and fallback, then obtain OWNER-approved amendment.

Use GitHub Pro deliberately:

- hosted Actions minutes = finite acceleration budget, not the only compute;
- heavy repeatable validation moves to Lenovo when safe;
- hosted Windows clean-room jobs are path-aware rather than blindly run for docs-only changes;
- cache accelerates reproducible dependencies/tools only;
- short-lived artifacts hold sanitized CI evidence only;
- Codespaces, if/when implemented, is optional clean-room development/handoff, never production/Real/secret-bearing runtime;
- GitHub Releases and protected `v10.*` release identity remain provenance controls;
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

Initial AI model/runtime assumptions remain governed by their owning amendment/WP. The public hosted-runtime amendment may require a later service/runtime selection when the AI WP unlocks; no AI hosting implementation is started early.

V10 Definition of Done must not require a paid OpenAI/Anthropic/Google/other AI inference API, paid search API or hosted agent SaaS unless a later explicit owning decision proves it necessary. GitHub Pro is the already accepted engineering subscription.

### 7.4 AI specialization sequence

Do not fine-tune first. Mandatory order:

`System Policy → typed Tool Registry → Knowledge/RAG → sanitized eval corpus → measured benchmark → QLoRA only if persistent measured gaps remain`.

Every model/policy/adapter change must be versioned, evaluated and rollbackable.

### 7.5 24/7 autonomy

Autonomy is event-driven, bounded and checkpointed. Endless untriggered `while true: think()` loops are forbidden.

Approved event classes include user questions, accepted report import, reconciliation discrepancy, stale data, deterministic Watchtower events, connector failure, scheduled research refresh, system-health degradation and evidence gaps.

AI outage must degrade gracefully; deterministic Core must remain usable.

### 7.6 Research baseline

Initial no-subscription-first research stack:

- SearchProvider abstraction with self-hosted/open-source path first;
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

## 9. OWNER participation / handoff law

Do everything possible through GitHub/code/CI without OWNER involvement.

Before an implementation PR is merged and its required post-merge Regression Shield is GREEN, do **not** ask the OWNER for ordinary product acceptance such as phone/browser walkthrough, UX/login/logout test, portfolio comparison or manual runtime checks that engineering/CI can perform.

Pre-merge OWNER participation is allowed only for a genuinely non-delegable prerequisite: external account/consent bootstrap, domain/payment decision, narrowly scoped credential bootstrap, UAC/admin/firmware/BitLocker/physical action, or an explicit Master Plan OWNER decision.

When OWNER action is genuinely needed, follow `docs/operations/V10_OWNER_ACTION_HANDOFF_STANDARD.md`:

- give a direct official HTTPS link to the exact stable target page when such a stable link exists;
- if no stable deep link can be verified, say so and give the closest verified official start URL plus exact click path;
- identify exact account/repository/workspace/service/device scope;
- request one bounded action at a time;
- state exact expected result, STOP conditions, adjacent actions that must not be taken, and minimum safe non-secret return;
- disclose cost/authority consequence before any paid/public/credential/irreversible action;
- never require the OWNER to discover the target page from vague navigation instructions;
- never request secret-bearing screenshots/links or raw secrets in chat.

Only when a local Windows action is genuinely non-delegable, use the preferred format:

`OWNER opens PowerShell → Administrator only if necessary → pastes one reviewed idempotent block → returns PASS/FAIL output`.

The permanent AI/runtime process must use least privilege; Administrator is for installation/service/system configuration only.

Lenovo is an engineering/self-hosted-CI/controlled-acceptance/recovery asset. It is not architectural ownership of public production and must not be required for ordinary public USER availability.

## 10. Lenovo resource arbitration and hosted-production separation

The same Lenovo may run GitHub self-hosted CI and engineering/acceptance workloads. Infrastructure must explicitly prevent resource contention:

- detect authoritative CI activity;
- pause/deprioritize heavy background AI/research/training during critical CI;
- QLoRA/training must not overlap authoritative gate by default;
- expose CPU/RAM/GPU/VRAM/availability health;
- AI failure must not take down deterministic Core or GitHub runner.

For the **final public product**, V10 Web/API and required hosted private-data services must run on an approved managed-cloud production runtime independent of OWNER home IP/Wi-Fi/router/LAN/Lenovo. The provider is selected through the owning service-selection/security/recovery gate; do not choose a new provider merely for novelty or convenience.

A Cloudflare Tunnel whose sole origin is the OWNER's home Lenovo/network is not valid final public production. Cloudflare may still be accepted for DNS/TLS/WAF/DDoS/edge or non-production transport. The existing Render.com `app:app` remains the protected V9 production/recovery baseline until its owning parity/decommission gate; a V10 cloud deployment must be the same source-controlled product, not a competing Web App.

## 11. Broker execution boundary

### 11.1 Production read-only

Protected V9 `TINVEST_TOKEN` remains read-only and is never promoted/replaced by a trading token as fallback.

For public V10, normal users provision their own tenant-scoped READ credential only through authenticated Web settings. It is stored under that tenant's `BrokerConnection`, never as a shared/global USER credential and never returned to browser storage.

### 11.2 Sandbox

Sandbox is virtual only and uses an isolated Sandbox credential/connection. Sandbox output is never real portfolio mutation evidence. Transfer/withdraw/margin remain forbidden.

### 11.3 Real execution

Real BUY/SELL can occur only through reviewed deterministic `omni_cio.real_trading` / plan-execution lifecycle and only when server readiness is valid.

Mandatory invariants remain:

- separate tenant-scoped/account-verified trading credential;
- `REAL_TRADING_ENABLED=true` required only after owning activation gate;
- durable state, no unsafe memory fallback;
- own-funds BUY / own-position SELL;
- no margin/short;
- fresh trusted market/order book;
- hard caps and exact price-step rules;
- immutable plan/proposal;
- exact short-lived authenticated USER confirmation for that USER's own tenant from a **new** turn/session step-up as required;
- immediate preflight;
- UUID/idempotency binding;
- one possible submit per identity;
- ambiguous possible-submit → do not retry; reconcile only;
- `submitted != filled` without broker evidence;
- account IDs masked;
- `EXECUTABLE_ACCOUNTS = VERIFIED_READ_ACCOUNTS ∩ VERIFIED_TRADE_ACCOUNTS` for the same tenant.

Forbidden: transfer/withdraw/securities transfer, MARKET/BESTPRICE where prohibited by accepted contract, margin/short, unauthorized autonomous derivatives execution, unsafe stop/replace/async submit, token management by AI, autonomous recurring Real execution and automatic retry after possible-submit ambiguity.

`REAL_TRADING_ENABLED=false` remains master Real rollback until accepted Real activation.

AI, Watchtower, Telegram, `START V10`, GitHub merge or portfolio-management wording is never Real-submit authorization.

## 12. V9 GPT migration/recovery boundary

The current Custom GPT v9.0.0 remains applied/recovery evidence until the explicit V10 parity/decommission gate.

Current repository configuration sources remain under `gpt/`. Do not create a second GPT. Do not delete existing Instructions/Knowledge/Actions because V10 exists.

While the GPT remains applied, it may claim only operationIds actually published by effective production `/openapi.json` and supported by returned evidence.

## 13. Secrets/private data

Never commit/publish real values of broker tokens, Gateway key, Upstash/QStash secrets, future Telegram/VK/provider secrets, AI/runtime secrets, encryption/recovery keys, Authorization headers, full account IDs or private portfolio/report payloads.

GitHub contains schemas/roles/safe defaults, not private values.

Research/eval fixtures must be synthetic or properly sanitized.

For the hosted public baseline, tenant-private state and encrypted broker credentials may exist only inside the approved cloud data/secret boundary after its owning security/privacy/legal gates; they remain forbidden from GitHub/CI/artifacts and inaccessible across tenants.

## 14. Dependency/runtime policy

Canonical Python lock sources remain `requirements.in` / `requirements-dev.in`; generated hash locks are derived and verified. Do not hand-edit generated locks as source of truth.

Known incompatible tooling is held narrowly/documented; do not disable verification to force an update.

Before introducing or materially upgrading a language/runtime/framework/package/provider/Action, verify current official support, security, license, platform compatibility where relevant, reproducible lock/install, fallback/rollback and measurable benefit. `latest` is not automatically `best`; accepted code is not rewritten merely for novelty. New languages require a concrete component-level correctness/security/isolation/performance/systems-integration reason and may not create polyglot sprawl.

Until a responsible V10 WP replaces it, current protected V9 compatibility remains:

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

## 16. Repository ownership / fault isolation

Accepted repository architecture is defined by `docs/architecture/REPOSITORY_STRUCTURE.md` and guarded by permanent tests.

Accepted/active V10 adapter roots currently include `apps/api/` and `apps/web/`; accepted engineering/Personal-Node infrastructure lives under `infrastructure/`. `apps/telegram/` and `ai/` remain later lifecycle-gated roots until their owning Work Packages are authorized. The protected V9 root wrappers remain until a responsible migration explicitly replaces them.

Do not create duplicate setup/audit/inventory documents when an accepted source of truth should be updated instead. Follow `docs/DOCUMENTATION_AUTHORITY_AND_LIFECYCLE.md` so historical records remain evidence without becoming competing current-state ledgers.

V10 should form bounded failure domains rather than one fragile monolith. Where applicable use explicit contracts, timeouts/deadlines, bounded retries with idempotency, backpressure/circuit breakers, durable queues/checkpoints, health/readiness/freshness states, restart/recovery behavior and least-privilege process/service boundaries. Failure of optional AI/Research/Telegram/external ingress should not unnecessarily take down deterministic Core when safe degradation is possible. Money/security/identity/secret/broker authority always fails closed.

## 17. Required verification

Regression Shield/authoritative merge gate remains strict. At minimum protect:

- lock reproducibility;
- CI/security policy;
- repository boundaries;
- engineering-governance, Integrated System Update governance, documentation-consistency and CI cost-control contracts;
- compile/Ruff/format/mypy;
- `app:app` compatibility until intentionally retired;
- current GPT/recovery contracts while applied;
- pytest/coverage;
- dependency audit/SBOM where required;
- SAST;
- secret scan;
- protected money-path replay/idempotency;
- tenant isolation / no cross-tenant secret or data access;
- future capability-aware DB/API/Web/Telegram/AI contracts when those roots appear.

Permanent guards include:

- `python scripts/check_v10_repository_boundaries.py`;
- `python scripts/check_v10_engineering_governance.py`;
- `python scripts/check_v10_integrated_system_update_governance.py`;
- `python scripts/check_v10_documentation_consistency.py`.

Do not bypass or weaken these guards to land a change.

When AI implementation begins, CI must additionally fail closed on policy/tool/evidence/eval invariants, including zero broker-write authority leakage and zero invented exact financial facts in critical deterministic fixtures.

## 18. Current next action

Current functional authorization is read only from `knowledge/17_V10_CURRENT_PROGRAM_STATUS.md`.

The WP22A technical gate is complete only through its accepted Phase-5 evidence chain. Public production remains independently inactive: `PUBLIC_MULTI_USER_ENABLED=false`, final Cloud.ru provider apply/cutover remains unauthorized, public T-Invest remains fail-closed, broker write remains OFF, `trading_methods=false` and `REAL_TRADING_ENABLED=false` remain protected.

**PRODUCT IMPLEMENTATION PAUSED.** The next prepared execution unit is **WEB-VISUAL-INTEGRATED — Premium Spatial Financial OS A→G System Update / OWNER START REQUIRED**. Amendment 12 does not itself start product work.

Do not create the integrated visual branch or modify `apps/web` for the refresh until the OWNER explicitly issues:

`START V10 WEB VISUAL SYSTEM UPDATE`

When started, `WEB-VISUAL-A -> B -> C -> D -> E -> F -> G` remain ordered branch-local member milestones. The complete System Update still follows `INTEGRATION_READY` → exact-head DRAFT GREEN → HEAD FREEZE / independent review → coherent correction batch if required → fresh READY GREEN → squash merge → exact-main post-merge verification. WP23+ remains locked until the complete visual System Update is accepted.
