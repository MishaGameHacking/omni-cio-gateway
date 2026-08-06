# Omni-CIO V10 — V9 to V10 Productization / Parity Matrix

**Status:** OWNER-APPROVED MIGRATION CONTRACT / LIVING PARITY LEDGER  
**Date:** 2026-08-06  
**Program authority:** `docs/master-plan/OMNI_CIO_V10_PRODUCTIZATION_AND_OWNER_ACCOUNT_AMENDMENT.md`

## 1. Purpose

V10 is not allowed to declare success merely because a new Web site, Telegram bot and AI chat exist.

The release must prove that the material accepted V9 capabilities have been migrated into the V10 system architecture or intentionally retired through owner-approved evidence.

This file begins the canonical parity ledger. Exact module/route/tool identifiers are filled/verified during their owning work packages after code-level inventory.

Status vocabulary:

- `BASELINE_IDENTIFIED` — accepted V9 behavior/owner is known;
- `V10_CONTRACT_DEFINED` — target V10 owner/interface is specified;
- `IMPLEMENTED` — V10 implementation exists but parity not fully proven;
- `PARITY_PROVEN` — deterministic/E2E evidence proves required behavior;
- `INTENTIONALLY_RETIRED` — explicit owner-approved retirement with reason/recovery;
- `BLOCKED` — cannot safely claim migration yet.

## 2. Migration matrix

| V9 capability/domain | V10 canonical owner | Primary Web destination | Telegram role | AI role | Parity requirement | Initial status |
|---|---|---|---|---|---|---|
| T-Invest portfolio/account read | Block D broker read adapter / PortfolioSnapshot | Overview, Portfolio, Asset Detail, Account/Connections | portfolio summary / safe status | read/explain through allowlisted tool | same intended account, completeness/freshness visible, no write from READ | V10_CONTRACT_DEFINED |
| Cash/liquidity state | Core portfolio/liquidity contract | Overview, Portfolio | optional summary | explain deterministic figures | Decimal/currency semantics preserved; source/as-of visible | BASELINE_IDENTIFIED |
| Portfolio analytics / concentration | deterministic Core analytics | Overview, Analytics, Risk | alert/summary only | explain calculations | golden V9 meaning preserved or intentionally versioned | BASELINE_IDENTIFIED |
| Instrument identity mapping | Core identity/reference data | Asset Detail / hidden shared component | no independent logic | uses canonical IDs only | UID/ISIN/FIGI/class binding; no ticker/name-only authority | V10_CONTRACT_DEFINED |
| Research | Research Collector + Evidence/Claims | Research Dossier | material alert/deep link | read/summarize with citations | provenance/freshness/contradictions preserved and strengthened | V10_CONTRACT_DEFINED |
| Credit analysis | deterministic/structured Credit engine | Risk / Asset Detail / Decision evidence | material credit alert | explain result; no invented rating | V9 financial meaning regression + evidence binding | BASELINE_IDENTIFIED |
| Risk engine | deterministic Risk engine | Risk / Overview / Decision | material risk alert | explain contributors | same or reviewed improved formulas; before/after reproducible | BASELINE_IDENTIFIED |
| Strategy | deterministic Strategy domain | Decision / Analytics | alert only when material | explain strategy output | no LLM replacement of deterministic strategy authority | BASELINE_IDENTIFIED |
| Optimizer / sizing | deterministic Optimizer | Decision / Plan | concise proposal + deep link | explain constraints/results | exact Decimal/lot/cash constraints; no AI sizing authority | BASELINE_IDENTIFIED |
| Immutable plan | Plan domain | Plans / Decision / Execution | open exact plan | explain plan | stable plan ID/version/hash/expiry; mutation invalidates approval | V10_CONTRACT_DEFINED |
| Safe execution preflight | Block I execution controller | Execution / Plan | status only | no broker-write tool | all V9 safety gates preserved and extended | V10_CONTRACT_DEFINED |
| Real order submit primitive | isolated Real execution contour | Execution | status/deep link only | prohibited | one possible submit per idempotent identity; exact owner confirmation | BASELINE_IDENTIFIED |
| Broker reconciliation | execution/reconciliation domain | Execution / Journal | material status | explain canonical state | `submitted != filled`; ambiguous -> reconcile/no retry | V10_CONTRACT_DEFINED |
| Watchtower | durable Watchtower jobs/incidents | Watchtower / Overview | primary alert channel | explain incident / research request | dedup/reopen/materiality/evidence lifecycle durable | V10_CONTRACT_DEFINED |
| Decision Journal | PostgreSQL Journal/Audit | Journal / linked details | no full payload | explain safe records | append/audit-sensitive history preserved | V10_CONTRACT_DEFINED |
| Existing Gateway/OpenAPI contracts | V10 Core/API adapters during migration | hidden backend; compatibility until retired | adapter uses V10 API | Tool Registry uses reviewed V10 tools | no silent break before consuming V10 surface accepted | BASELINE_IDENTIFIED |
| Custom GPT Instructions/Knowledge | System Policy + Knowledge/RAG | AI Copilot behavior | same Orchestrator policy | canonical policy/knowledge | inventory/diff every current required asset; no secret migration | V10_CONTRACT_DEFINED |
| Custom GPT conversational portfolio workflow | AI Copilot / Agent Orchestrator + Tool Registry | `/copilot` + deep links | compact same-agent surface | primary | portfolio answers grounded in current Core/evidence; no invented execution | V10_CONTRACT_DEFINED |
| Current GPT Action tool access | V10 Tool Registry / internal API contracts | AI tool activity summary | same allowlist via Orchestrator | primary | explicit allowlist/schema/audit; broker-write absent | V10_CONTRACT_DEFINED |
| Existing alert/scheduler behavior | Durable Job System + Watchtower | System jobs + Watchtower | delivery target | AI optional | reboot-safe/idempotent/observable, not dependent on open chat | V10_CONTRACT_DEFINED |
| Existing V9 controlled maintenance/rollback | GitHub releases + V9 protected baseline | System release info | none | none | V9 recoverable until V10 final acceptance | BASELINE_IDENTIFIED |

## 3. Required inventory procedure

At the owning migration work package, the development agent must inspect accepted V9 `main` rather than relying on this high-level table alone.

For each domain it records:

- exact V9 module/class/function;
- exact current API/operationId where user-visible;
- current tests that encode semantics;
- current GPT Instructions/Knowledge/Action dependency where applicable;
- current runtime state dependency;
- V10 replacement/adapter;
- data migration requirement;
- regression/equivalence tests;
- rollback path.

The ledger is updated in the same reviewed branch as the migration implementation or its dedicated parity package.

## 4. User-journey parity

V10 must eventually prove these user-level transitions without requiring Custom GPT as the only interface:

### Portfolio understanding

`login -> portfolio sync -> Overview -> Portfolio -> Asset Detail -> source/freshness explanation`.

### Material event

`24/7 Watchtower -> Incident -> Evidence/Research -> Risk impact -> Decision -> Telegram alert -> exact Web drill-down`.

### Natural-language analysis

`Web/Telegram question -> shared Agent Orchestrator -> allowed Core/Evidence tools -> grounded answer -> deep link`.

### Plan without trading token

`Decision -> immutable Plan -> owner can inspect all calculations -> broker write impossible -> manual execution remains possible outside Omni-CIO`.

### Optional Real execution

`accepted Shadow readiness -> optional trading credential -> exact plan -> owner confirmation -> preflight -> submit -> reconcile -> Journal`.

## 5. Parity rules

1. UI equivalence is not financial parity evidence.
2. AI response similarity is not deterministic Core parity evidence.
3. A new database schema is not parity until restored/migrated data produces the required behavior.
4. A V10 capability can be better than V9, but the changed financial meaning must be explicit and tested.
5. No current V9 money-safety invariant can be retired silently.
6. Custom GPT decommission is blocked until the required V9 -> V10 rows are `PARITY_PROVEN` or explicitly retired.
7. V9 protected rollback remains available through V10 final acceptance.

## 6. Final parity gate

Before V10.0.0 final acceptance, the matrix must have no material row left in `BASELINE_IDENTIFIED`, `V10_CONTRACT_DEFINED`, `IMPLEMENTED` or `BLOCKED` unless the Master Plan explicitly marks it as a post-V10 capability.

Every material row must end as either:

- `PARITY_PROVEN`; or
- `INTENTIONALLY_RETIRED` with owner-approved evidence.
