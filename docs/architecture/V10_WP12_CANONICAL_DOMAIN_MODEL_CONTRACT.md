# V10 WP12 — Canonical Domain Model and tenant-ready IDs

Status: **WP12 IMPLEMENTATION CONTRACT / PR EVIDENCE REQUIRED**  
Block: **D — V10 Core and data**  
Program authority: `docs/master-plan/OMNI_CIO_V10_MASTER_PLAN.md`  
Accepted baseline: `f0babd6eed9720cbada018459b500c16bc3a0f56`  
Prior Exit Gate: WP11 PR #269 -> `1aa65e2420a01a5da7b5123a279a5940b3ea59d4`; Regression Shield #1452 / `31329587509` SUCCESS; status PR #270 -> `f0babd6eed9720cbada018459b500c16bc3a0f56`; Regression Shield #1453 / `31330534260` SUCCESS.

## 1. WP identity

- Block: D — V10 Core and data.
- WP: WP12.
- Title: Canonical Domain Model and tenant-ready IDs.
- Authorized by current program status: **YES**.
- Next package remains locked: **WP13 — PostgreSQL persistence and migrations**.

## 2. Accepted baseline

Protected runtime remains Omni-CIO v9.0.0 with `app:app`, `trading_methods=false`, `REAL_TRADING_ENABLED=false` and the accepted WP6–WP11 privilege/secret/recovery/Core boundaries.

Relevant authorities:

- `knowledge/17_V10_CURRENT_PROGRAM_STATUS.md`;
- `docs/master-plan/OMNI_CIO_V10_MASTER_PLAN.md` WP12 section;
- `docs/master-plan/OMNI_CIO_V10_WP_EXECUTION_TEMPLATE.md`;
- `docs/architecture/V10_SYSTEM_ARCHITECTURE.md`;
- `docs/architecture/REPOSITORY_STRUCTURE.md`;
- `docs/architecture/V10_V9_TO_V10_PARITY_LEDGER.json`;
- `docs/architecture/V10_COMPONENT_REUSE_MATRIX.json`;
- accepted V9 contract models under `omni_cio/contracts/v1/`.

## 3. Purpose

Create one strict, immutable, versioned identity/relationship model for Personal V10 so every private durable object is explicitly scoped rather than relying on hidden global singleton state. The model must be structurally ready for later tenant isolation while **only the OWNER tenant is admitted in V10 Personal**.

## 4. Inputs and prerequisites

WP12 reuses existing accepted V9 contracts instead of replacing their financial semantics:

- `omni_cio/contracts/v1/common.py` — strict immutable Pydantic base and UTC normalization conventions;
- `omni_cio/contracts/v1/portfolio.py` — reviewed financial portfolio/instrument payload semantics;
- `omni_cio/contracts/v1/investment_policy.py` — reviewed policy semantics and policy identity;
- `omni_cio/contracts/v1/research_evidence.py` — reviewed research/evidence semantics;
- `omni_cio/contracts/v1/portfolio_plan.py` — immutable plan payload/identity semantics;
- `omni_cio/contracts/v1/plan_execution.py` — protected execution record semantics;
- `omni_cio/contracts/v1/watchtower.py` — incident/event semantics;
- `omni_cio/contracts/v1/decision_journal.py` — decision/journal audit semantics;
- WP11 `omni_cio/core/` — accepted no-GPT deterministic Core facade.

No broker token, private portfolio payload, production DB or runtime secret is required to implement or test WP12.

## 5. Existing implementation to reuse

WP12 applies **WRAP_ADAPTER** to accepted V9 DTOs: the V9 financial payload contracts stay intact while WP12 adds canonical V10 identity/scope records around them. This avoids semantic rewrites and keeps V9 rollback unchanged.

Relevant parity families remain:

- `PARITY-PORTFOLIO-CORE`;
- `PARITY-IMMUTABLE-PLAN`;
- `PARITY-WATCHTOWER`;
- `PARITY-JOURNAL`;
- `PARITY-REAL-SAFETY` remains protected and is not modified by WP12.

No `REWRITE_REQUIRED` decision is introduced.

## 6. Allowed changes

WP12 may change only repository-safe contracts/tests/docs needed for the canonical domain model:

- new identity/domain contract code under `omni_cio/contracts/v1/`;
- contract exports where needed;
- deterministic tests under `tests/`;
- WP12 architecture/execution documentation;
- reuse-matrix metadata if needed to record the WP12 wrap-adapter decision.

## 7. Explicit non-goals

WP12 must not:

- create PostgreSQL tables, migrations, ORM mappings or persistence repositories — WP13 owns those;
- create durable job queues — WP14 owns those;
- create T-Invest read adapters — WP15 owns those;
- activate public/multi-user operation;
- create Web, Telegram, Cortex/AI or external ingress;
- modify `app:app` or current V9 wrappers;
- modify financial formulas;
- modify `omni_cio.real_trading` or broker-write authority;
- store full broker account identifiers, secrets or private payloads in GitHub/CI.

## 8. Interfaces and contracts

Canonical schema family: `omni_cio.contracts.v1.domain` / schema version `1.0`.

Required model concepts:

- Tenant;
- User;
- BrokerAccount;
- Portfolio;
- PortfolioSnapshot identity record;
- Position identity record;
- Instrument identity;
- Policy identity record;
- Evidence identity record;
- Incident identity record;
- Decision identity record;
- Plan identity record;
- Execution identity record;
- Journal identity record;
- one canonical domain catalog/graph that validates uniqueness and relationships.

Compatibility rule: existing V9 payload DTOs remain authoritative for their reviewed financial semantics. WP12 records contain canonical IDs, scope relationships, timestamps and content hashes/references; they do not reinterpret calculations.

Identity rules:

- IDs are versioned and typed by prefix;
- OWNER tenant is the only admitted Tenant object in Personal V10;
- private records carry `tenant_id` and, when portfolio/policy scoped, explicit `portfolio_id` and `policy_id`;
- broker account records store only an internal ID, masked label and SHA-256 fingerprint — never a full raw account identifier;
- instrument canonical identity is anchored to a strong broker UID/FIGI/ISIN primary identity; class code and ticker may provide a secondary board alias, while name/ticker alone never establish canonical identity;
- instrument alias collision across two canonical IDs is rejected;
- identity/display labels are separate.

Temporal rules:

- every persisted timestamp is timezone-aware and normalized to UTC by the contract;
- display timezone is outside Core/domain persistence semantics;
- evidence distinguishes `published_at`, `retrieved_at` and `local_received_at`;
- broker-derived snapshots additionally distinguish `broker_server_at` and `local_received_at`.

## 9. Data/persistence effects

- migration required: **NO**;
- database schema change: **NO**;
- durable write path: **NO**;
- private-data handling: tests use synthetic IDs/hashes only;
- backup consequence: none until WP13 binds these contracts to persistence.

WP12 defines future persistence shape but does not implement persistence early.

## 10. Security and authority effects

WP12 changes no runtime authority:

- secret access: unchanged;
- broker authority: unchanged;
- OS/runtime privileges: unchanged;
- GitHub permissions: unchanged;
- Web/Telegram ingress: none;
- AI tool authority: none;
- Real execution path: unchanged.

Cross-tenant references and non-OWNER tenant admission fail closed at contract validation. Full raw account identifiers are not represented by the canonical BrokerAccount model.

## 11. Normal-path acceptance tests

Tests must prove:

- every required model produces a strict JSON schema;
- an OWNER-scoped synthetic domain graph validates;
- all timestamps normalize to UTC;
- strong instrument identities remain stable when display name/ticker changes;
- canonical positions bind by instrument ID rather than name similarity;
- all private decision/plan/execution/journal/evidence/incident records bind explicitly to tenant/portfolio/policy scope;
- existing V9 financial contract modules remain unchanged and usable.

## 12. Negative/failure tests

Tests must reject at minimum:

- public/non-OWNER Tenant creation;
- naive persisted timestamps;
- full/unmasked account labels;
- ticker/name-only instrument identity;
- duplicate primary IDs;
- conflicting broker UID/FIGI/ISIN or ticker+class-code aliases mapped to different instrument IDs;
- duplicate position identity within one snapshot;
- missing referenced account/portfolio/policy/snapshot/instrument;
- cross-tenant or cross-portfolio relationships;
- evidence/decision/plan/execution/journal references crossing scope;
- extra unversioned schema fields.

## 13. Observability

WP12 is a contract-only package and creates no background runtime. Acceptance evidence is deterministic test/CI output plus reviewed JSON schema behavior. Validation errors must identify the violated relationship without printing private payloads.

## 14. CI routing

- Fast hosted checks: normal path-aware PR feedback when GitHub hosted billing permits;
- Hosted clean-room compatibility: normal repository policy only; no new runtime dependency;
- Lenovo authoritative checks: **required** exact-head `V10 authoritative merge gate`;
- GPU AI eval: **NO**;
- release/recovery matrix: inherited Regression Shield/security, no new physical recovery rehearsal.

GitHub-hosted startup billing failures are infrastructure failures, never PASS. They do not justify weakening the authoritative Lenovo gate.

## 15. Rollback/recovery

Rollback is source-only: revert the WP12 commit/PR. No DB migration, secret, runtime provisioning or private data is created. Protected V9 and accepted WP11 Core remain unchanged.

## 16. Exit Gate

WP12 PASS requires on the exact reviewed PR head:

1. all required canonical models exist;
2. OWNER-only tenant admission is fail closed;
3. schema/UTC/identity/uniqueness/collision/cross-scope tests pass;
4. no persistence or later-WP runtime is introduced;
5. `app:app`, `trading_methods=false`, `REAL_TRADING_ENABLED=false` and V9 rollback remain unchanged;
6. authoritative Self-Hosted Windows CI is GREEN;
7. dependency audit, SAST and tracked-content secret scan are GREEN through the authoritative gate;
8. zero unresolved blocking review threads;
9. full PR diff reviewed;
10. squash merge completes;
11. post-merge Regression Shield succeeds on the exact resulting `main` SHA.

## 17. Required acceptance evidence

Record:

- exact PR head SHA;
- deterministic WP12 test evidence;
- exact authoritative Self-Hosted Windows CI run;
- hosted-lane infrastructure classification if applicable;
- zero blocking review threads;
- merge SHA;
- exact post-merge Regression Shield run.

No OWNER physical action or secret input is required for WP12.

## 18. Documentation/status updates

Implementation PR owns this contract and any reuse-matrix clarification required by the code. Official `knowledge/17_V10_CURRENT_PROGRAM_STATUS.md` is advanced only in a separate post-merge status synchronization after the post-WP12 Regression Shield is GREEN.

## 19. Next WP unlock

Only **WP13 — PostgreSQL persistence and migrations** may be unlocked, and only after all WP12 Exit Gate evidence above is accepted. WP13 must then bind these contracts to durable PostgreSQL state without changing their identity/scope semantics silently.

## 20. Scope-discovery rule

Any persistence, job-system, broker-read, Web, Telegram, AI or Real-execution work discovered during WP12 is future-WP work unless it is strictly required to make the WP12 canonical model correct and testable. It must not be implemented opportunistically.
