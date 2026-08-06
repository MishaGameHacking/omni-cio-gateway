# Omni-CIO V10 — Productization, OWNER Account and Broker Connection Program Amendment

**Status:** OWNER-APPROVED PROGRAM AMENDMENT / BINDING ELABORATION  
**Date:** 2026-08-06  
**Applies to:** V10 Blocks B-J; especially WP8, WP11-WP15, WP17/WP22A, WP23-WP26, WP30A-WP32C, Block H, Block I and Block J  
**Implementation sequence changed:** **NO**  
**Feature-expansion intent:** **NO — this amendment makes the already-approved V10 productization/migration scope concrete**  
**Related Web authority:** `docs/architecture/V10_WEB_PRODUCT_BLUEPRINT.md`  
**Detailed account/broker authority:** `docs/architecture/V10_OWNER_ACCOUNT_AND_TINVEST_CONNECTION_CONTRACT.md`  
**V9 -> V10 parity ledger:** `docs/architecture/V10_V9_TO_V10_PRODUCTIZATION_MATRIX.md`

## 1. Purpose

V10 is a major productization release, not a feature-collection exercise.

The primary job of V10 is to evolve the accepted Omni-CIO V9 capability set from the current GitHub + Gateway + Custom GPT operating model into one self-contained Personal Omni-CIO system with:

- one source-controlled Web application as the primary operating cabinet;
- OWNER authentication and a personal account/profile boundary;
- T-Invest portfolio connectivity;
- Telegram notifications and safe deep links to the same Web application;
- one shared Omni-CIO AI Copilot / Agent Orchestrator for Web and Telegram;
- 24/7 background portfolio monitoring, Watchtower, research and analytical workflows;
- the existing deterministic V9 financial engines preserved/evolved behind stable V10 contracts;
- optional, separately provisioned and owner-confirmed Real execution;
- GitHub as the engineering Control Plane so any authorized future ChatGPT/AI development session can restore context and continue development without relying on this chat or a specific ChatGPT account.

This amendment does not authorize adding unrelated product features. It makes the migration/product behavior explicit so later work packages do not invent the product ad hoc.

## 2. Productization invariant — V9 capability first, V10 interface/system second

V10 MUST preserve the accepted financial meaning of V9 unless a specific V10 work package intentionally replaces a boundary and proves the replacement.

The implementation priority is:

`V9 accepted capability -> canonical V10 domain contract -> persistent/job/runtime integration -> API -> Web/Telegram/AI surface -> parity evidence -> V9 interface retirement only after gate`.

A V9 capability may not silently disappear merely because the V10 UI is redesigned.

A capability may be intentionally excluded only when:

1. the canonical V10 Master Plan already excludes it; or
2. an owner-approved amendment explicitly retires it and records migration/recovery consequences.

## 3. Personal V10 account model — one active OWNER, future-ready identity

V10 Personal production remains **single-OWNER**. Public registration, mass multi-user production, billing and public delegated portfolio management remain outside V10.

However, the V10 Web application MUST have a real authenticated personal account boundary rather than treating an open browser page as identity.

The V10 OWNER account provides at minimum:

- stable internal `user_id` / OWNER identity;
- authentication credentials / secure session lifecycle;
- presentation profile and timezone/preferences;
- connection status for T-Invest and Telegram;
- notification preferences;
- AI/provider presentation preferences where safe;
- account-scoped portfolio/data ownership;
- audit actor identity;
- security/session management;
- recovery/revocation metadata.

The data model may include `tenant_id`/ownership boundaries for future migration, but V10 MUST NOT expose public tenant creation, public signup or cross-user sharing.

There must be no hidden global singleton assumption that makes future isolation impossible, but future multi-user functionality is not accepted V10 scope.

## 4. T-Invest connection contract — READ is required, TRADING is optional

### 4.1 Mandatory read-only connection

A **T-Invest read-only token** is the mandatory broker credential for portfolio-dependent Omni-CIO functionality.

Without a valid READ connection the system MAY still provide:

- login/account/security UI;
- System/Admin health;
- setup/onboarding guidance;
- connection diagnostics;
- non-portfolio documentation/help.

But it MUST NOT pretend to know the user's live portfolio and therefore MUST disable or clearly mark unavailable any capability that requires real portfolio state, including current portfolio analytics, portfolio-derived Watchtower alerts, portfolio-specific Guardian decisions and exact portfolio plans.

With a valid READ connection, V10 can provide the normal analysis/monitoring product even when no trading token exists.

### 4.2 Optional trading connection

A second, separately provisioned **account-scoped full-access trading token without transfer authority** is optional.

The trading token:

- is never required for portfolio monitoring/analysis;
- is never a fallback for READ;
- is never exposed to AI, GitHub, browser storage, logs or ordinary diagnostics;
- is never interpreted as blanket autonomous trading permission;
- becomes usable only after the owning Block I safety gates, Shadow evidence and owner acceptance;
- is bound to the reviewed account/authority scope;
- is revoked/disabled independently from READ;
- may not enable transfer/withdrawal, margin/short or any authority excluded by the Master Plan.

If only READ exists, Omni-CIO still produces evidence, risk analysis, decisions and plans; execution remains manual outside Omni-CIO.

If TRADING is also provisioned and all Real gates are green, Omni-CIO may execute **only the exact immutable plan explicitly approved by OWNER** through the deterministic execution lifecycle.

### 4.3 No “edit portfolio” shortcut

The product must never model the trading token as generic “edit my portfolio” authority.

The correct authority chain is:

`READ facts -> deterministic analysis/risk -> Decision -> immutable Plan -> OWNER exact approval -> preflight -> bounded broker orders -> reconciliation -> Journal`.

The plan approval is permission for that exact plan, not permission for future autonomous discretionary trading.

## 5. First-run / onboarding journey

The normal V10 first-run journey is defined before implementation:

1. **Install/bootstrap V10 runtime** through reviewed deployment evidence.
2. **Create/initialize the single OWNER identity** through the approved local/private bootstrap path.
3. **Login** to the Web application; anonymous access receives no private portfolio data.
4. Open **Account / Connections** and provision the mandatory T-Invest READ token.
5. Backend validates token authenticity/scope/account binding without persisting the raw value in browser state or logs.
6. OWNER selects/binds the intended broker account when more than one account is available; full account IDs stay masked in UI/logs.
7. Initial portfolio/instrument/operations synchronization runs as observable jobs.
8. Data-quality/freshness checks complete before Dashboard claims live readiness.
9. Dashboard transitions from onboarding/partial state to normal portfolio monitoring.
10. Telegram may be connected when Block F is ready and is linked to the same OWNER identity.
11. AI Copilot may be enabled when Block G is ready; deterministic Core remains usable without AI.
12. Trading token is **not** requested during ordinary first-run. It is optional and appears only after the separate Shadow/Real readiness path.

OWNER should never need to manually edit repository files or paste secrets into GitHub to complete onboarding.

## 6. Credential provisioning UX and secret custody

The Web account page may offer a reviewed secure provisioning flow, but raw secret values remain runtime-only.

Rules:

- raw tokens are accepted only by a dedicated authenticated provisioning path on the approved runtime;
- external provisioning requires the external Web security gate/TLS/session protections to be accepted first;
- token values are write-only from the user perspective and are never returned by API after provisioning;
- frontend never stores tokens in `localStorage`, IndexedDB or persisted client state;
- request/exception/access logs redact or omit credential payloads;
- runtime stores the secret in the WP8 local secret store / credential-protected mechanism;
- UI shows only safe metadata: connection type, masked account, permission class, last validation time, health, rotation/expiry state;
- revoke/replace is explicit and independently available for READ and TRADING;
- failed/expired/permission-mismatched credentials fail closed and downgrade capability state rather than silently switching credentials.

A local administrative provisioning fallback may exist for recovery, but it is not allowed to become undocumented operational knowledge.

## 7. Capability modes visible to the user

The product must make these modes explicit:

### MODE A — SETUP / NO READ CONNECTION

- account/system UI available;
- real portfolio analysis unavailable;
- clear onboarding action: connect T-Invest READ;
- no fake portfolio/demo truth.

### MODE B — ANALYSIS / READ-ONLY

- portfolio synchronization;
- analytics/risk;
- Watchtower;
- Research/Evidence;
- Guardian Decisions;
- plan generation/preview;
- AI Copilot over allowed read/analytical tools;
- Telegram alerts;
- **no broker write**.

This is a complete supported V10 operating mode, not an error condition.

### MODE C — SHADOW

- all READ capabilities;
- execution plan evaluation/simulation;
- no real broker write;
- explicit Shadow labeling and evaluation history.

### MODE D — REAL-ELIGIBLE / OWNER-CONFIRMED

- requires optional TRADING credential plus every Block I readiness gate;
- exact immutable plan shown to OWNER;
- explicit short-lived confirmation;
- deterministic preflight;
- bounded submit/reconciliation;
- no autonomous plan substitution or retry after ambiguous possible submit.

If TRADING becomes unavailable, the system automatically degrades to READ-only analysis rather than failing the whole product.

## 8. V9 -> V10 migration and parity ledger

Before the current Custom GPT can stop being a required user interface, V10 must maintain a repository-controlled parity ledger for accepted V9 behavior.

For every material V9 capability, the ledger records:

- V9 source/module/operation or GPT-facing behavior;
- financial meaning that must be preserved;
- V10 domain owner;
- V10 API/tool contract;
- V10 Web surface;
- Telegram surface if applicable;
- AI Tool Registry exposure if applicable;
- migration test/evidence;
- fallback/rollback;
- final status: `NOT_MIGRATED | PARTIAL | PARITY_PROVEN | INTENTIONALLY_RETIRED`.

No “the new site looks complete” decision can replace this parity evidence.

The current Custom GPT remains recovery/reference until the explicit GPT parity/decommission gate.

## 9. 24/7 operating loop

The intended autonomous V10 loop is:

```text
T-Invest READ / market data
        -> durable refresh jobs
        -> PortfolioSnapshot / market freshness
        -> Watchtower triggers
        -> Research/Evidence where required
        -> deterministic Risk/Credit/Strategy/Optimizer
        -> Decision / immutable Plan
        -> Journal
        -> Telegram/Web notification when material
        -> OWNER investigation / AI Copilot explanation
        -> optional exact plan approval
        -> optional Real execution/reconciliation
        -> Journal / new portfolio state
```

The system works continuously without an open ChatGPT conversation.

AI may assist autonomous research/classification/explanation through allowlisted read-only tools, but deterministic monitoring and money safety do not depend on the AI provider being online.

## 10. One AI brain, two presentation surfaces

V10 must not implement separate conflicting AI systems for Web and Telegram.

One Omni-CIO AI Copilot / Agent Orchestrator serves both surfaces and uses:

- the same System Policy;
- the same Knowledge/RAG authority;
- the same Tool Registry;
- the same OWNER authorization context;
- the same portfolio/evidence/decision objects;
- the same audit/correlation model.

Web provides the full conversational workspace. Telegram provides concise interaction/alerts and deep links to the appropriate Web object.

The AI is allowed to:

- answer portfolio/system questions from canonical state;
- explain incidents, evidence, risk and decisions;
- request/coordinate allowed research;
- summarize system status;
- explain deterministic plans;
- propose safe analytical next actions.

The AI is not allowed to:

- receive/store raw broker secrets;
- alter deterministic financial limits;
- convert arbitrary free text into a broker submit;
- grant itself a new tool;
- approve a Real plan on behalf of OWNER.

## 11. Autonomous AI developer / ChatGPT handoff contract

V10 engineering must remain operable by **any authorized ChatGPT/AI development session with GitHub access**, not by this chat history or a specific ChatGPT account.

GitHub is the engineering memory.

Before any implementation session, the development agent must restore context from repository authority, including:

- `AGENTS.md`;
- V10 Program Lock / Master Plan / amendments index;
- `knowledge/17_V10_CURRENT_PROGRAM_STATUS.md`;
- relevant architecture/blueprint/runbook;
- accepted `main`;
- current PR/issues;
- current CI evidence.

The development agent is expected to perform autonomously wherever the connected tools allow:

1. identify the one authorized current WP;
2. formulate implementation/acceptance criteria from the plan;
3. create/use a focused branch;
4. implement backend/frontend/DB/AI/Telegram/infrastructure work owned by that WP;
5. write/update deterministic tests;
6. self-review for safety, data, secrets and architecture drift;
7. open/update the PR;
8. inspect CI/review feedback;
9. fix code/tests until the exact-head gate is green;
10. keep documentation/status evidence synchronized;
11. move to the next WP only after acceptance.

The owner should not be asked to perform routine coding, copy code between files, debug ordinary CI, choose arbitrary implementation details already governed by the plan, or manually maintain duplicate project memory.

### Owner participation is limited to genuinely non-delegable actions

Examples:

- subscription/billing or account-level GitHub settings unavailable to the agent;
- UAC/physical machine access;
- creating Telegram BotFather identity;
- entering/rotating broker/Telegram secrets through the reviewed runtime flow;
- providing backup hardware/location;
- explicit owner acceptance/security decisions required by a gate;
- exact Real plan confirmation during actual use.

A ChatGPT/AI development session must never request or persist secret values merely to reduce owner interaction.

## 12. Concrete block-level elaboration

This amendment does not add new blocks. It adds acceptance detail to the existing sequence.

### Block B — GitHub / CI/CD

- repository must contain the productization contracts/parity ledger as durable AI-readable authority;
- CI gates prevent product-facing code from silently bypassing existing safety contracts;
- Web visual/E2E gates become active only when the real Web root appears;
- GitHub Pro branch protection remains the server-side merge gate for private `main` once enabled.

### Block C — Personal Node / secrets

- create separate runtime identities and local secret store;
- support independent READ and TRADING credential references;
- bootstrap creates OWNER account/security prerequisites without embedding secrets;
- recovery documents how OWNER identity and broker connections are restored/reprovisioned.

### Block D — Core / data

- create explicit OWNER/account ownership boundaries;
- BrokerConnection metadata and capability state are domain objects, while raw token values remain secret-store only;
- READ broker adapter is the canonical real portfolio source;
- absence of TRADING does not impair normal analytical Core;
- no global singleton that prevents future ownership isolation.

### Block E — Web

- Login, personal account/profile and Connections are real product surfaces;
- T-Invest READ onboarding is first-class;
- TRADING setup is optional and separately guarded;
- every page is capability-aware and state-complete under `V10_WEB_PRODUCT_BLUEPRINT.md`;
- no production demo data/dead controls.

### Block F — Telegram

- Bot identity maps to the same OWNER account;
- Telegram is notification/deep-link/conversational adapter, not a second business logic stack;
- no broker token ever enters Telegram.

### Block G — AI / GPT migration

- inventory all V9 GPT-visible capabilities;
- migrate useful policy/knowledge/tool contracts;
- prove V10 Copilot parity for approved analytical interactions;
- one shared Agent Orchestrator for Web/Telegram;
- AI remains detached from broker-write authority.

### Block H — Guardian / Watchtower

- run the 24/7 material-event loop from real READ portfolio state;
- create incidents/decisions/plans as durable objects;
- notify only when material according to policy;
- no portfolio connection means portfolio-specific Guardian output is blocked/unknown, not invented.

### Block I — Personal Real Execution

- optional TRADING connection only;
- full READ-only product remains valid without it;
- Shadow precedes Real;
- exact plan + exact owner confirmation + idempotency + reconciliation remain mandatory;
- loss/revocation of TRADING downgrades to safe READ-only mode.

### Block J — Integration / release

Final acceptance must prove at least these user journeys:

1. fresh installation -> OWNER login -> READ connection -> first live portfolio -> Dashboard;
2. READ-only 24/7 monitoring -> Watchtower incident -> Research -> Decision -> notification -> Web drill-down;
3. AI provider unavailable -> deterministic portfolio/Watchtower remains usable;
4. TRADING absent -> plans remain analyzable but broker write impossible;
5. TRADING provisioned after gate -> Shadow -> exact plan approval -> safe reconciliation;
6. credential expired/revoked -> clear downgrade without secret leakage;
7. reboot/recovery -> OWNER account/session security -> read-only safe state -> reconnection/restore;
8. clean-room development handoff to a different authorized AI/developer session using GitHub only.

## 13. Definition of Done for this productization contract

V10 is not accepted merely because Web, Telegram and AI pages exist.

The productization goal is complete only when:

- accepted V9 material capabilities have `PARITY_PROVEN` or explicit owner-approved retirement;
- OWNER can operate the normal analytical system through Web without depending on Custom GPT;
- mandatory READ connection drives real portfolio state and can be safely rotated/revoked;
- optional TRADING is strictly separated and not needed for normal analysis;
- Telegram and AI reuse the same Core/identity/data contracts;
- 24/7 background monitoring survives browser/ChatGPT closure and reboot according to the plan;
- no critical Web control is decorative;
- all private state/secrets stay outside GitHub;
- another authorized ChatGPT/AI development session can restore engineering context from GitHub and continue work;
- current Custom GPT is decommissioned from required-path status only after explicit parity evidence and owner acceptance;
- final V10 release passes the existing security/recovery/soak/clean-room gates.

## 14. Non-goals preserved

This clarification does **not** add:

- public/mass user registration;
- billing/subscriptions;
- public multi-tenant production;
- multiple brokers;
- autonomous unconfirmed Real trading;
- transfer/withdrawal/margin/short authority;
- a second website, second Core, second AI brain or second Telegram business logic stack.

Those remain future-version concerns unless a later owner-approved program explicitly changes scope.
