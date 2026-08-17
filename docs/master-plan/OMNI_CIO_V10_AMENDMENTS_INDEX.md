# Omni-CIO V10 — Amendments Index

Status: **ACTIVE PROGRAM INDEX**

This index exists so future engineering/AI sessions can restore OWNER-approved V10 clarifications from GitHub instead of depending on chat memory.

Documentation lifecycle: `../DOCUMENTATION_AUTHORITY_AND_LIFECYCLE.md`.

## Authority rule

The synchronized V10 Master Plan remains the canonical base program:

- `OMNI_CIO_V10_MASTER_PLAN.md`;
- `Omni-CIO_V10_Master_Plan_RU.pdf`;
- `OMNI_CIO_V10_MASTER_PLAN.sha256`.

Accepted amendments supplement/narrow the base plan without silently renumbering blocks or changing block weights. When an accepted amendment intentionally resolves an ambiguity, the amendment governs that implementation choice until a later OWNER-approved consolidation or superseding amendment.

Unmerged/closed draft PR text is not an accepted amendment. Current progress/current-next WP is read only from `../../knowledge/17_V10_CURRENT_PROGRAM_STATUS.md`.

## Active amendments

### 1. Account Independence / Deployment Portability

`OMNI_CIO_V10_ACCOUNT_INDEPENDENCE_AMENDMENT.md`

Historical owner-approved amendment already consolidated into the canonical Master Plan. Retained for audit/provenance.

### 2. Concrete Execution Plan / AI Cortex / local-first autonomy

`OMNI_CIO_V10_CONCRETE_EXECUTION_PLAN_AMENDMENT.md`

Machine-readable companion:

`../architecture/V10_AI_CORTEX_CONTRACT.json`

Locks the concrete 2026-08-07 OWNER decisions:

- deterministic Core is the source of financial truth;
- V10 accounting/portfolio target is verified broker HTML report import; no photo/OCR workflow;
- MOEX is current-market enrichment and must not overwrite broker-period accounting facts;
- local-first AI baseline is Qwen3.5-4B + Ollama;
- no paid AI/search/agent SaaS is required for V10 Definition of Done;
- AI is specialized as Omni-CIO Cortex rather than a general-purpose assistant;
- tool authority is typed/allowlisted/fail-closed;
- Web research is evidence-based, SearXNG-first and browser-fallback bounded;
- 24/7 autonomy is event-driven with durable checkpoints, not an endless LLM loop;
- LangGraph OSS is the initial orchestration candidate;
- QLoRA is considered only after System Policy + tools + RAG + evals demonstrate a persistent gap;
- AI never receives direct broker-write/admin/bypass authority;
- OWNER local participation is minimized to reviewed PowerShell operations only when GitHub/code/CI cannot perform the action remotely.

### 3. GitHub Pro Maximum Utilization / V10 Migration Implementation Contract

`OMNI_CIO_V10_GITHUB_PRO_AND_MIGRATION_IMPLEMENTATION_AMENDMENT.md`

Machine-readable companions:

- `../architecture/V10_GITHUB_PRO_UTILIZATION_CONTRACT.json`;
- `../architecture/V10_V9_TO_V10_PARITY_LEDGER.json`;
- `../architecture/V10_COMPONENT_REUSE_MATRIX.json`;
- `../architecture/V10_RELEASE_MANIFEST.schema.json`.

Locks the OWNER-approved rule that GitHub Pro is the V10 engineering Control Plane and that V10 is a controlled productization/migration of the accepted V9 system, not a greenfield rewrite or feature-expansion program. It defines CI compute routing across GitHub-hosted runners and the Lenovo self-hosted runner, Actions-minute/cache/artifact budgets, Codespaces clean-room use, Releases/tag provenance, environment usage, dependency automation, parity/reuse rules, canonical acceptance oracles, WP execution format, cutover discipline, scope firewall, and a subscription-minimization policy.

### 4. Telegram Product / Interaction / Delivery Contract

`OMNI_CIO_V10_TELEGRAM_PRODUCT_AND_INTERACTION_AMENDMENT.md`

Planning checklist:

`OMNI_CIO_V10_TELEGRAM_IMPLEMENTATION_CHECKLIST.md`

Machine-readable companions:

- `../architecture/V10_TELEGRAM_PRODUCT_CONTRACT.json`;
- `../architecture/V10_TELEGRAM_MESSAGE_REGISTRY.json`.

Locks the OWNER-approved product behavior for Block F before implementation, as corrected by Amendment 9 below:

- Telegram is a private **USER-scoped** companion interface to the same Omni-CIO account/tenant model, not a second Core/Web/AI product; the PROJECT OWNER is only the first controlled acceptance USER;
- long polling is the initial transport; public webhook ingress is not required;
- the compact command surface is `/start`, `/help`, `/status`, `/portfolio`, `/alerts`, `/system`, `/app`;
- Telegram consumes canonical Core DTOs and never owns financial calculations or broker-write logic;
- BotFather/manual PROJECT OWNER work is minimized to project-wide bot bootstrap and locally storing/rotating its token; this infrastructure authority is not product-user authority;
- Mini App identity requires server-side validation of Telegram `initData`, freshness/replay controls and a short-lived V10 session;
- message families, privacy levels and buttons are versioned in a registry;
- alert delivery is durable, idempotent, deduplicated and edits an existing incident message when practical;
- callback/deep-link values are opaque, server-validated and never authority by possession alone;
- Telegram Mini App is the same Web frontend/codebase, not a second UI implementation;
- AI conversation is not implemented early in Block F; WP32C later activates the same shared Omni-CIO Cortex for Web and Telegram after AI prerequisites/evals;
- degraded modes preserve deterministic commands where Core remains available;
- no recurring paid Telegram/bot middleware/SaaS is required for V10 Definition of Done.

This amendment is planning authority only and does not start Block F or change the current implementation sequence by itself.

### 5. Autonomous Portfolio Governance / Zero-Custody / Commercial Model

`OMNI_CIO_V10_AUTONOMOUS_PORTFOLIO_GOVERNANCE_AND_COMMERCIAL_MODEL_AMENDMENT.md`

Machine-readable / legal companions:

- `../architecture/V10_AUTONOMOUS_PORTFOLIO_GOVERNANCE_CONTRACT.json`;
- `../architecture/V10_RUSSIAN_MARKET_UNIVERSE_AND_SANCTIONS_POLICY.json`;
- `../architecture/V10_ZERO_CUSTODY_LICENSE_UPDATE_CONTRACT.json`;
- `../legal/V10_RU_COMMERCIAL_LEGAL_GATES.md`.

This amendment locks the OWNER-approved product definition across the existing A-J program without renumbering blocks or crediting implementation progress. Product-domain OWNER wording is interpreted through Amendment 9 as authenticated USER authority for that USER's own tenant:

- the central product is autonomous portfolio governance, not a dashboard/chat/trading robot;
- the deterministic system operates 24/7; Cortex is an on-demand bounded research/interpretation/negotiation specialist that the system or USER may invoke;
- every held asset receives explicit health/freshness/trend state and monitoring intensity is risk/materiality based;
- the system dynamically screens the supported broker universe through a Russian-market-only policy, sanctions/custody hard gates, eligibility, liquidity/data-quality and asset-class rules;
- sanctions `BLOCKED` assets cannot be new BUY candidates; naive name-only screening is insufficient;
- diversification is multi-dimensional and optimizer output may be `NO_CHANGE`, one-to-one replacement, one-to-many split or multi-position rebalance;
- the normal user output is one ranked concrete primary proposal rather than an unordered idea catalogue;
- proposal rejection/revision creates a bounded USER dialogue and versioned soft preference/constraint update; hard safety policy cannot be overridden by chat;
- Real execution remains cash-only BUY/SELL after immutable authenticated USER approval for that USER's own tenant and fresh preflight; no margin/leverage/uncovered short/transfers/withdrawals;
- private investment state and broker secrets remain Personal Node zero-custody by default;
- commercial access uses a full 7-day trial then fixed 1/3/6/12 month manual prepaid periods; no auto-renewal/recurring charge;
- supported Personal Nodes automatically converge to approved STABLE releases through a signed/verified/rollback-safe updater;
- commercial launch is fail-closed on explicit Russian-law personal-data, consumer, payment/KKT, broker-terms, investment-advisory/autoconsulting and production legal gates.

The amendment also narrows the AI contract: the **system** is the primary 24/7 autonomous actor, not an endlessly-running LLM.

This is planning authority only. It does not start billing, updater, Portfolio Guardian, Real execution or any later block.

### 6. Identity / Multi-Tenant Account / Authentication

`OMNI_CIO_V10_IDENTITY_MULTI_TENANT_ACCOUNT_AND_AUTHENTICATION_AMENDMENT.md`

Architecture / machine-readable companions:

- `../architecture/ADR-0010-identity-multitenant-authentication.md`;
- `../architecture/V10_IDENTITY_AUTHENTICATION_CONTRACT.json`;
- `../operations/V10_IDENTITY_AND_BROKER_CONNECTION_SECURITY_NOTES.md`.

Locks the OWNER-approved 2026-08-10 identity/account direction while preserving existing safety/legal gates:

- an internal Omni-CIO user account is authoritative; Telegram and VK ID are authentication providers, not business/account IDs;
- ordinary login methods are Telegram Login and VK ID; no Omni-CIO password database or Google login is required for the ordinary path;
- one user account owns one isolated tenant in the baseline model and may link both Telegram and VK identities after proof of both;
- server-side revocable sessions provide remembered login without making a phone/browser authoritative state;
- provider display names/profile data are never sufficient for automatic account merge;
- public multi-user readiness requires API plus database-enforced tenant isolation and cross-scope tests across jobs/cache/AI/backups;
- broker credentials belong to tenant-owned `BrokerConnection` objects and normal provisioning occurs only through authenticated Web settings;
- T-Invest READ and optional TRADE credentials remain separate; execution is allowed only for the exact broker-account intersection independently verified through both credentials;
- a broad token may bind multiple broker accounts, while an account-specific token binds only the account exposed by the broker;
- transfer/withdrawal authority remains outside V10;
- the central Identity/Commercial plane is minimal and is not authorized to become a centralized portfolio/broker-secret/private-history database;
- public multi-user activation remains disabled until external-Web security, cross-tenant isolation, broker-terms, personal-data, investment-advisory, capacity and commercial legal gates are accepted;
- WP15 live credential evidence was moved from ordinary PowerShell UX to the reviewed authenticated Web broker-provisioning flow.

This amendment changed product/account interpretation and selected acceptance sequencing only where explicitly stated. Historical references to then-future Block E work are interpreted at the amendment's acceptance time; current implementation state comes from the canonical status file. Amendment 9 makes explicit that the PROJECT OWNER is an ordinary USER in this product identity model and has no special application role merely because of repository/infrastructure ownership.

### 7. Browser-Only Phone Engineering / Headless Personal Node Operations

`OMNI_CIO_V10_PHONE_ONLY_ENGINEERING_AND_HEADLESS_NODE_OPERATIONS_AMENDMENT.md`

Machine-readable / operations companions:

- `../architecture/V10_PHONE_ONLY_ENGINEERING_CONTRACT.json`;
- `../operations/V10_PHONE_ENGINEERING_RUNBOOK.md`.

Locks the OWNER-approved 2026-08-15 operating model without renumbering WPs or bypassing WP22A, as clarified by Amendment 9:

- the PROJECT OWNER's normal **engineering** control surface is the phone browser only; when using Omni-CIO as a product, the PROJECT OWNER uses the same ordinary USER product path as supported users;
- GitHub remains engineering source of truth and the primary automation hub; routine code, PR, CI, deployment and supported provider operations are performed directly through GitHub/Actions/APIs rather than recurring PROJECT OWNER dashboard work;
- native phone applications are not required for normal PROJECT OWNER engineering operation or ordinary browser product use;
- external-service signup/login for engineering providers should use GitHub social login when the provider supports it, while runtime/workload automation prefers federated or narrowly scoped machine credentials; such provider identity is not Omni-CIO USER identity;
- Lenovo/the replacement Personal Node operates headlessly; local PowerShell is a physical/admin recovery exception, not routine product UX;
- significant external services require a documented service-selection gate covering security, WP fit, GitHub automation, browser-only UX, reliability/recovery, privacy/data custody, price, lock-in, operational burden, legal/broker constraints and performance;
- free/already-paid options are preferred only when they satisfy the owning V10 security/reliability requirements; paid service remains allowed after documented insufficiency and PROJECT OWNER approval;
- Cloudflare Access + Tunnel is an **initial WP22A clientless candidate**, not accepted product authentication merely because the amendment exists;
- Tailscale may remain useful for machine/CI/private infrastructure, but a phone path that requires a native device client does not satisfy the browser-only product requirement;
- no second Web App/control plane, public unauthenticated ingress, broker-write authority, Real execution authority, GitHub bypass or arbitrary remote PowerShell is created by this amendment;
- `app:app`, `trading_methods=false`, `REAL_TRADING_ENABLED=false`, zero-custody boundaries and protected V9 rollback remain unchanged.

This amendment changes the operational/access design constraint only. WP22A remains the current functional package and must separately pass its full security/recovery/product-auth/acceptance Exit Gate before WP23 can start.

### 8. Engineering Quality / Pre-CI / Green Merge

`OMNI_CIO_V10_ENGINEERING_QUALITY_AND_GREEN_MERGE_AMENDMENT.md`

Machine-readable / operations / engineering-memory companions:

- `../architecture/V10_ENGINEERING_QUALITY_GATE_CONTRACT.json`;
- `../operations/V10_OWNER_ACTION_HANDOFF_STANDARD.md`;
- `../operations/V10_CI_COST_CONTROL_STANDARD.md`;
- `../operations/V10_ENGINEERING_FAILURE_LEARNING_LEDGER.md`;
- `../../.github/instructions/owner-handoff-and-runtime.instructions.md`;
- `../../.github/workflows/v10-engineering-governance.yml`.

Locks the OWNER-approved 2026-08-16 engineering discipline for all remaining V10 work:

- CI is the independent verifier, not the normal interactive debugger;
- every material RED requires root-cause analysis, repository-wide analogous-pattern/blast-radius review and a permanent regression/guard where reusable;
- expensive full CI starts only after applicable cheap/focused preflight and full-diff review are clean;
- material dependency/API changes require current official support/security/compatibility review; `latest` is not automatically best and accepted code is not rewritten merely for novelty;
- new programming languages are allowed only for concrete component-level correctness/security/isolation/performance/systems-integration reasons; polyglot sprawl is forbidden;
- Omni-CIO components should form bounded failure domains with explicit degraded states while money/security authority remains fail-closed;
- every **applicable** exact-head check must actually run and conclude `success` before merge; skipped/neutral/cancelled/pending/infrastructure-red checks are not GREEN project evidence;
- irrelevant workflows must be fixed at routing/trigger level rather than left as misleading skipped/cancelled PR checks;
- any commit after final GREEN invalidates the old final evidence and requires a fresh exact-head cycle;
- normal PR closure is GREEN -> full review -> squash merge; unmerged/superseded work is never accepted implementation;
- PROJECT OWNER product acceptance (phone/browser/UX/login/logout/portfolio comparison) occurs only after implementation merge and required post-merge Regression Shield GREEN and must exercise the same USER product path intended for supported users;
- pre-merge PROJECT OWNER involvement is limited to genuinely non-delegable prerequisites such as external consent/account bootstrap, domain/payment decision, narrow credential bootstrap or physical/admin action;
- PROJECT-OWNER-only engineering handoffs require a verified direct official target link when stable, exact scope/action/result/STOP contract and no vague page discovery;
- V10 Web/API runtime remains on the approved Personal Node; a new Render.com V10 host is not authorized by convenience;
- PROJECT-OWNER-controlled GitHub Actions budget/payment state is never silently changed; current zero-budget hard stop is handled by truthful zero-cost routing without fake clean-room PASS;
- unexpected material RED after declared preflight readiness requires a confidence postmortem and reusable learning is persisted in the Failure Learning Ledger.

**Acceptance evidence:** governance PR #322 was accepted into exact `main` `1c05390d9cf31b8cc68a90a5d7cbd6428ffe7791`; post-merge Regression Shield #1498 / run `31959959791` completed **SUCCESS** on that exact main. The amendment is therefore **ACTIVE**. Its acceptance did not change WP numbering/progress, complete WP22A, open public ingress, add broker-write authority or unlock WP23.

### 9. Product User / Engineering Authority Boundary

`OMNI_CIO_V10_PRODUCT_USER_AND_ENGINEERING_AUTHORITY_BOUNDARY_AMENDMENT.md`

OWNER-approved 2026-08-17 clarification that prevents the repository/business owner from becoming a special Omni-CIO product user.

It establishes the terminology and precedence rule:

- `USER` is an ordinary authenticated `OmniCIOUserAccount -> Tenant` product user;
- the PROJECT OWNER uses the same USER account/session/product path as supported customers;
- PROJECT OWNER GitHub/provider/Windows/business authority is an engineering/operations authority outside normal product identity;
- GitHub ownership, Cloudflare membership or Windows/CI identity never grants an Omni-CIO product session or cross-tenant product authority;
- WP22 `System/Admin` means user-facing System/Diagnostics, not a special PROJECT-OWNER account/admin cabinet;
- WP22A is interpreted product-facing as **External Web Access / Product Authentication Security Gate** without renumbering the base plan;
- an OWNER-only edge identity may contain a pre-production environment but cannot become the canonical product login or tenant authority;
- Telegram/Block F is user-scoped in the final product; the PROJECT OWNER is only the first controlled acceptance user, not a globally privileged Telegram product identity;
- product-domain historical `OWNER approval/authentication/dialogue` wording means the authenticated USER acting for that USER's own tenant unless the context explicitly concerns project/business/infrastructure authority;
- public multi-user activation remains OFF until its existing security/legal/capacity gates pass;
- current WP22A implementation must be re-reviewed against this separation before Exit Gate; WP23+ remains locked.

After this amendment is merged, it supersedes conflicting OWNER-specific **product-role** interpretations in earlier V10 planning/current-WP wording while preserving genuine PROJECT OWNER engineering/business authority and historical evidence.

## Draft/superseded planning material

Open or historical PR descriptions must not be treated as active plan authority merely because they contain V10 ideas. In particular, any older unmerged planning PR that conflicts with an accepted amendment must be closed/superseded rather than merged as a competing roadmap.

## Required reading order for new V10 engineering sessions

1. `../../AGENTS.md`;
2. `../../README.md`;
3. `../DOCUMENTATION_AUTHORITY_AND_LIFECYCLE.md`;
4. `../../knowledge/00_PROJECT_MASTER_CONTEXT.md`;
5. `OMNI_CIO_V10_PROGRAM_LOCK.md`;
6. `OMNI_CIO_V10_MASTER_PLAN.md`;
7. this Amendments Index;
8. all active amendments listed here;
9. `../../knowledge/17_V10_CURRENT_PROGRAM_STATUS.md`;
10. current-WP architecture/runbook;
11. current `main`, open PR/issues and GitHub Actions.
