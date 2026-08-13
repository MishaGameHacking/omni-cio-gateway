# Omni-CIO V10 — WP19 Watchtower / Incident UI Execution Contract

## 1. WP identity

- Block: E — Omni-CIO Web Platform
- WP: WP19
- Title: Watchtower / Incident UI
- Authorized by current program status: YES
- Prior Exit Gate proven by: WP18 PR #303 accepted on `main`, status transition PR #304 squash-merged, and post-transition Regression Shield #1487 SUCCESS on exact `main` `1edfc9ed6b8d81eeb236097d1ac5d8e8bd2044d1`.

## 2. Accepted baseline

- Accepted `main` SHA: `1edfc9ed6b8d81eeb236097d1ac5d8e8bd2044d1`
- Protected V9/V10 runtime baseline: V9 rollback remains protected; V10 Web remains local/private, READ-only, OWNER-scoped, `app:app`, `trading_methods=false`, `REAL_TRADING_ENABLED=false`.
- Relevant Master Plan/amendment sections: Block E / WP19; Program Lock; Concrete Execution Plan; V10 V9-to-V10 reuse/migration map.
- Relevant ADRs/contracts: WP16 Design System, WP17 Application Shell/session boundary, WP18 Portfolio Dashboard, WP12 canonical domain, WP13 PostgreSQL persistence, V9 Watchtower data contract/threat model, `omni_cio.contracts.v1.watchtower`.

## 3. Purpose

Make every persisted incident understandable as a verifiable read-only Web object: what happened, why, when, its current lifecycle state, the evidence references, risk/severity context when canonical Watchtower alert evidence exists, dedup/reopen state, and any already-owned Decision/Plan links.

## 4. Inputs and prerequisites

- accepted WP12 `IncidentRecordV1`, `EvidenceRecordV1`, `JournalRecordV1` identities and OWNER scope;
- accepted WP13 PostgreSQL tables `incidents`, append-only `incident_revisions`, `incident_evidence`, `evidence`, `content_blobs`, `journal`;
- accepted V9 `WatchtowerAlertV1` deterministic alert identity, semantic fingerprint, severity, subject, evidence hashes, message code and action;
- accepted WP16 visual components and state semantics;
- accepted WP17 server-side session and tenant scope;
- accepted WP18 single source-controlled Web App/API runtime and local/private ingress boundary;
- mandatory Self-Hosted Windows CI and Regression Shield.

## 5. Existing implementation to reuse

### Watchtower alert semantics

- path/module: `omni_cio/contracts/v1/watchtower.py`, `omni_cio/watchtower/engine_v1.py`;
- accepted behavior: deterministic alert identity, semantic fingerprint, severity, subject, evidence hashes, UTC timestamp, replay/dedup semantics, hard-disabled execution/trading;
- protecting tests: existing V9 Watchtower contracts/tests and repository boundary guards;
- parity ledger ID: `PARITY-WATCHTOWER`;
- reuse matrix decision: REUSE / DO NOT REWRITE.

### Canonical incident and journal persistence

- path/module: `omni_cio/contracts/v1/domain.py`, `omni_cio/persistence/*`, migration `0001_initial.sql`;
- accepted behavior: tenant/portfolio/policy-scoped incidents, append-only revisions, revision-scoped evidence, immutable journal links;
- protecting tests: WP12 canonical-domain and WP13 persistence/recovery suites;
- parity ledger ID: `PARITY-JOURNAL` plus accepted Block D persistence;
- reuse matrix decision: REUSE READ-ONLY / NO SECOND INCIDENT STORE.

### Web platform

- path/module: `apps/web`, `omni_cio/web`, `apps/api/app.py`;
- accepted behavior: one Web App, server-side session, tenant scope, local/private TrustedHost boundary, explicit degraded states;
- protecting tests: WP16/WP17/WP18 focused audits;
- parity ledger ID: V10 productization layer;
- reuse matrix decision: EXTEND EXISTING WEB APP ONLY.

## 6. Allowed changes

- add a WP19 read-only incident presentation/API module under `omni_cio/web`;
- install that read-only route in `apps/api/app.py` using the existing PostgreSQL connection and session registry;
- add Watchtower page/types/API calls/styles/tests inside the existing `apps/web` source tree;
- add deterministic WP19 Python/Web fixtures and focused audit workflow;
- add WP19 architecture/operations documentation required for acceptance.

## 7. Explicit non-goals

- no new Watchtower risk/credit/research engine;
- no scheduler/QStash/Upstash redesign or activation;
- no Telegram delivery;
- no AI research/Cortex work;
- no incident mutation/acknowledge/close controls in this WP;
- no public Internet ingress or public multi-user activation;
- no broker credential or broker-write changes;
- no Real execution, trade submission, transfer, withdrawal or autonomous plan execution;
- no WP20 Research implementation and no WP21 Decision/Risk/Plan implementation beyond read-only links that already exist in accepted journal contracts.

## 8. Interfaces/contracts

### `GET /api/v10/web/watchtower-incidents`

- version: WP19 Web view schema `1.0.0`;
- producer: local/private FastAPI Web runtime;
- consumer: existing React Application Shell;
- compatibility: additive Web view; accepted domain/watchtower contracts are not mutated;
- null/unknown semantics: missing alert-content evidence remains explicit as `MISSING`/`UNKNOWN`; no inferred severity/subject is fabricated;
- source/time semantics: lifecycle timestamps come from canonical `incidents.opened_at` and append-only `incident_revisions.revised_at`; evidence source/retrieval/publication timestamps are exposed as metadata only; raw content is never returned.

### Watchtower alert projection

- a content blob is treated as Watchtower alert metadata only if it successfully validates as canonical `WatchtowerAlertV1`;
- raw blob payload is never returned to the browser;
- severity taxonomy remains existing `info|warning|error`;
- semantic `fingerprint_sha256` is used only as a safe dedup identity;
- multiple conflicting alert fingerprints for one incident are displayed as a conflict/degraded state, not silently merged.

## 9. Data/persistence effects

- migration required: NO;
- forward migration: none;
- rollback/forward-recovery rule: remove/revert WP19 read surface; canonical incidents/evidence/journal remain unchanged;
- private-data handling: read only OWNER tenant rows, return bounded safe metadata, never raw content blobs, broker secrets, provider account IDs or portfolio payloads;
- backup/recovery consequence: none; WP19 consumes already-covered WP13/WP10 durable state.

## 10. Security/authority effects

- secret access: NO;
- broker authority: NO;
- OS/runtime privileges: NO;
- GitHub permissions: NO;
- Web/Telegram ingress: no new ingress; existing authenticated local/private Web GET only;
- AI tool authority: NO;
- Real execution path: NO.

Threat controls reused from V9 Watchtower threat model: semantic dedup, evidence-only references, no raw source payload, no broker-write authority. Cross-tenant access continues to be resolved server-side from the session.

## 11. Normal-path acceptance tests

- authenticated incident list renders active/resolved/critical filters;
- incident detail shows lifecycle timeline in durable revision order;
- canonical Watchtower alert blob projects verified severity, subject, message code, action and semantic fingerprint;
- evidence rows show source and time metadata without raw payload;
- journal links expose already-existing Decision/Plan IDs only when linked to that incident;
- closed then open transition is visibly classified as reopened;
- deterministic golden fixture covers open, acknowledged, resolved and reopened views.

## 12. Negative/failure tests

- unauthenticated API request returns 401;
- foreign-tenant scope cannot be requested or injected by client parameters;
- malformed/non-Watchtower content blob is never interpreted as alert metadata;
- missing blob/evidence metadata is displayed explicitly and does not fabricate subject/severity;
- conflicting semantic fingerprints fail to a visible degraded dedup state;
- duplicate/replayed identical metadata does not create duplicate browser incidents;
- unsupported filter fails closed or is rejected;
- database/read failure produces explicit unavailable UI, never an empty-success substitute;
- source/browser contract contains no broker token, secret reference, raw provider account ID, private portfolio payload or broker-write surface.

## 13. Observability

- health/status: API response includes generated timestamp and aggregate state/counts; UI has loading/empty/unavailable/degraded states;
- logs: no new raw payload logging;
- metrics/job state: out of scope; this WP reads persisted incident state only;
- correlation IDs: canonical incident ID and safe Watchtower alert ID/fingerprint provide deterministic correlation;
- user-visible degraded state: missing/invalid alert evidence and DB/API failure are explicit;
- evidence retained for acceptance: deterministic test output and browser golden fixture only; no private production data.

## 14. CI routing

- Fast hosted checks: existing Fast PR lane, truthfully reported if billing prevents startup;
- Hosted clean-room compatibility required: existing repository lane remains unchanged; no new dependency;
- Lenovo authoritative checks: focused WP19 Windows gate plus existing authoritative Self-Hosted Windows CI and Regression Shield;
- GPU AI eval required: NO — no AI behavior;
- Release/recovery matrix required: NO new persistence/runtime authority; existing Regression Shield and WP13/WP10 coverage remain authoritative.

## 15. Rollback/recovery

Revert the WP19 Web/API commit or PR. Since this WP is read-only and adds no migration, canonical incidents, revisions, evidence, journal, broker state and recovery material remain untouched. Protected V9 rollback is unaffected.

## 16. Exit Gate

PASS only if, on exact reviewed PR head, deterministic Python + Web tests and focused WP19 audit are GREEN, authoritative Self-Hosted Windows CI is GREEN, review has zero unresolved blocking threads, full diff is reviewed, and the UI proves for every represented incident/alert: what happened, why, when, current state, evidence status and what downstream system linkage exists. Missing evidence must be visibly identified rather than inferred.

## 17. Required acceptance evidence

- exact PR head SHA;
- focused WP19 audit run ID and result;
- exact-head authoritative Self-Hosted Windows CI result;
- Web typecheck/lint/test/build and deterministic golden fixture;
- Python incident read-model tests including auth, lifecycle, reopen, dedup/conflict and missing evidence;
- zero unresolved blocking review threads;
- squash merge SHA and post-merge Regression Shield before WP19 can be recorded COMPLETE.

No OWNER physical/secret action is expected for this WP unless an unexpected gate explicitly requires it.

## 18. Documentation/status updates in the same PR

- `docs/architecture/V10_WP19_EXECUTION_CONTRACT.md`;
- WP19 product/read contract documenting fields and fail-closed semantics;
- focused workflow/tests/fixtures.

Program status is not advanced to WP20 inside implementation code merely because tests pass; final status follows the repository acceptance sequence.

## 19. Next WP unlock

WP20 remains LOCKED until WP19 implementation is squash-merged and exact post-merge required gates are GREEN, followed by the required status transition according to the Master Plan.

## 20. Scope-discovery rule

Any discovered work outside this Exit Gate is classified as a current-WP blocker/defect, future-WP backlog, or OWNER-approved architecture/program amendment. It is never silently implemented.
