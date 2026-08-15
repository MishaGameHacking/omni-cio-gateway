# Omni-CIO V10 — Amendments Index

Status: **ACTIVE PROGRAM INDEX**

This index exists so future engineering/AI sessions can restore OWNER-approved V10 clarifications from GitHub instead of depending on chat memory.

## Authority rule

The synchronized V10 Master Plan remains the canonical base program:

- `OMNI_CIO_V10_MASTER_PLAN.md`;
- `Omni-CIO_V10_Master_Plan_RU.pdf`;
- `OMNI_CIO_V10_MASTER_PLAN.sha256`.

Accepted amendments supplement/narrow the base plan without silently renumbering blocks or changing block weights. When an accepted amendment intentionally resolves an ambiguity, the amendment governs that implementation choice until a later OWNER-approved consolidation or superseding amendment.

Unmerged/closed draft PR text is not an accepted amendment.

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

Locks the OWNER-approved product behavior for Block F before implementation:

- Telegram is an OWNER-only private companion interface, not a second Core/Web/AI product;
- long polling is the initial transport; public webhook ingress is not required;
- the compact command surface is `/start`, `/help`, `/status`, `/portfolio`, `/alerts`, `/system`, `/app`;
- Telegram consumes canonical Core DTOs and never owns financial calculations or broker-write logic;
- BotFather/manual OWNER work is minimized to creating/confirming the bot and locally storing/rotating its token;
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

This amendment locks the OWNER-approved product definition across the existing A-J program without renumbering blocks or crediting implementation progress:

- the central product is autonomous portfolio governance, not a dashboard/chat/trading robot;
- the deterministic system operates 24/7; Cortex is an on-demand bounded research/interpretation/negotiation specialist that the system or OWNER may invoke;
- every held asset receives explicit health/freshness/trend state and monitoring intensity is risk/materiality based;
- the system dynamically screens the supported broker universe through a Russian-market-only policy, sanctions/custody hard gates, eligibility, liquidity/data-quality and asset-class rules;
- sanctions `BLOCKED` assets cannot be new BUY candidates; naive name-only screening is insufficient;
- diversification is multi-dimensional and optimizer output may be `NO_CHANGE`, one-to-one replacement, one-to-many split or multi-position rebalance;
- the normal user output is one ranked concrete primary proposal rather than an unordered idea catalogue;
- proposal rejection/revision creates a bounded OWNER dialogue and versioned soft preference/constraint update; hard safety policy cannot be overridden by chat;
- Real execution remains cash-only BUY/SELL after immutable OWNER approval and fresh preflight; no margin/leverage/uncovered short/transfers/withdrawals;
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
- WP15 live credential evidence is moved from ordinary PowerShell UX to the reviewed authenticated Web broker-provisioning flow; WP18 real-data acceptance remains blocked until that deferred evidence passes.

This amendment changes product/account interpretation and selected acceptance sequencing only where explicitly stated. It does not start Block E implementation before the amended WP15 code/security acceptance is formally accepted.


### 7. Cloud Personal Node / Phone-First Migration

`OMNI_CIO_V10_CLOUD_PERSONAL_NODE_MIGRATION_AMENDMENT.md`

Planning checklist:

`OMNI_CIO_V10_CLOUD_PERSONAL_NODE_MIGRATION_CHECKLIST.md`

Machine-readable companion:

`../architecture/V10_CLOUD_PERSONAL_NODE_MIGRATION_CONTRACT.json`

Locks the OWNER-directed 2026-08-15 transition from a laptop-dependent runtime to a private cloud Personal Node without changing block weights or claiming implementation credit:

- WP22B is a zero-weight transition gate after accepted WP22A and before WP23;
- the initial replaceable baseline is one Timeweb Cloud Moscow Ubuntu LTS node at 2 vCPU / 4 GB / 50 GB, billed hourly/month-to-month;
- normal recurring spend targets about 1,309 RUB/month and no more than 1,400 RUB/month, with a 1,800 RUB/month hard cap including transient migration compute/snapshots and excluding the already-owned GitHub Pro subscription;
- no annual prepayment, domain, managed database, Kubernetes, GPU, paid AI/search, paid bot middleware or public application ingress is required;
- the private entry path is Tailscale Serve with Funnel off; Telegram later uses long polling and `/app` opens the same Web/Mini App with server-side `initData` validation;
- the production Personal Node is never a general CI runner; Linux releases are manifest/digest verified and CI uses a separate ephemeral runner;
- Windows DPAPI blobs are not migrated; secrets are re-provisioned into the Linux secret boundary and never enter GitHub/chat/artifacts;
- encrypted off-node backups, a clean restore, reboot/crash/release/database rollback drills, single-writer/scheduler/poller proof and a 72-hour soak are mandatory;
- Lenovo becomes a cold rollback node for a bounded retention window and is not destructively decommissioned without a later OWNER gate;
- the financial safety posture remains read-only with `trading_methods=false`, `REAL_TRADING_ENABLED=false` and no broker write/withdrawal/transfer authority.

This is planning authority only. It does not alter the currently active WP22A PR, start cloud implementation, change the current accepted completion percentage or unlock WP23 by itself.

## Draft/superseded planning material

Open or historical PR descriptions must not be treated as active plan authority merely because they contain V10 ideas. In particular, any older unmerged planning PR that conflicts with an accepted amendment must be closed/superseded rather than merged as a competing roadmap.

## Required reading order for new V10 engineering sessions

1. `../../AGENTS.md`;
2. `../../knowledge/00_PROJECT_MASTER_CONTEXT.md`;
3. `OMNI_CIO_V10_PROGRAM_LOCK.md`;
4. `OMNI_CIO_V10_MASTER_PLAN.md`;
5. this Amendments Index;
6. all active amendments listed here;
7. `../../knowledge/17_V10_CURRENT_PROGRAM_STATUS.md`;
8. current-WP architecture/runbook;
9. current `main`, open PR/issues and GitHub Actions.
