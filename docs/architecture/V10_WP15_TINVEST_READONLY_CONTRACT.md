# Omni-CIO V10 WP15 — T-Invest read-only data layer and freshness

Status: **WP15 IMPLEMENTATION CONTRACT / EXIT GATE EVIDENCE REQUIRED**  
Block: **D — V10 Core and data**  
Program authority: `docs/master-plan/OMNI_CIO_V10_MASTER_PLAN.md`  
Accepted baseline: `87d17480e6a2ad472950f4413a13a2ab5e8abe17`

## 1. WP identity

- Block: D — V10 Core and data.
- WP: WP15.
- Title: T-Invest read-only data layer and freshness.
- Authorized by current program status: **YES**.
- Prior Exit Gate: WP14 PR #275 -> `ff9bb37b6538fe9665ea0a652a0623354f0195da`; post-WP14 Regression Shield #1458 / run `31379587986` SUCCESS; status PR #276 -> `87d17480e6a2ad472950f4413a13a2ab5e8abe17`; post-status Regression Shield #1459 / run `31381217644` SUCCESS.
- Next package remains locked: **WP16 — Web Design System**.

## 2. Accepted baseline

Protected runtime remains Omni-CIO v9.0.0 with `app:app`, `trading_methods=false`, `REAL_TRADING_ENABLED=false` and the accepted WP6–WP14 privilege, secret, recovery, Core, domain, PostgreSQL and durable-job boundaries.

Relevant authorities:

- `AGENTS.md`;
- `README.md`;
- `knowledge/00_PROJECT_MASTER_CONTEXT.md`;
- `knowledge/17_V10_CURRENT_PROGRAM_STATUS.md`;
- `docs/master-plan/OMNI_CIO_V10_PROGRAM_LOCK.md`;
- `docs/master-plan/OMNI_CIO_V10_MASTER_PLAN.md` WP15 section;
- `docs/master-plan/OMNI_CIO_V10_AMENDMENTS_INDEX.md` and active amendments;
- `docs/master-plan/OMNI_CIO_V10_WP_EXECUTION_TEMPLATE.md`;
- `docs/architecture/V10_SYSTEM_ARCHITECTURE.md`;
- `docs/architecture/V10_SECURITY_BOUNDARIES.md`;
- `docs/architecture/V10_DATA_FLOW.md`;
- `docs/architecture/V10_THREAT_MODEL.md`;
- `docs/architecture/V10_WP8_SECRET_STORE_CONTRACT.json`;
- `docs/architecture/V10_WP12_CANONICAL_DOMAIN_MODEL_CONTRACT.md`;
- `docs/architecture/V10_WP13_POSTGRESQL_PERSISTENCE_CONTRACT.md`;
- `docs/architecture/V10_WP14_DURABLE_JOB_SYSTEM_CONTRACT.md`;
- `docs/architecture/V10_COMPONENT_REUSE_MATRIX.json`;
- `docs/architecture/V10_V9_TO_V10_PARITY_LEDGER.json`.

## 3. Purpose

Provide one fail-closed production **READ-only** T-Invest adapter that binds exactly to the OWNER account, retrieves current portfolio/positions and cursor-paginated operations, enriches strong instrument identity, normalizes exact Decimal/UTC data into accepted V10 contracts, persists only through accepted WP13 boundaries, and exposes explicit freshness/completeness state for later Core/Web consumers.

The T-Invest API layer is current operational state. It does **not** replace the accepted verified broker HTML report as canonical broker-period accounting truth. Where API history and broker-period accounting differ, reconciliation/report truth remains a separate owning capability.

## 4. Inputs and prerequisites

WP15 consumes rather than redefines:

- the production `broker_read` secret class from WP8;
- the accepted `t-tech-investments==1.49.3` SDK/runtime lock;
- the existing V9 read-only T-Invest Gateway behavior in `main.py` as reuse/parity evidence;
- `PortfolioSnapshotV1` and related V9 financial DTOs;
- WP12 BrokerAccount/Portfolio/Instrument/Snapshot/Position identity contracts;
- WP13 PostgreSQL persistence APIs and immutable content hashes;
- WP14 durable job semantics for a later/same-WP registered read-safe refresh handler only; WP15 does not create another queue.

Offline CI uses deterministic synthetic broker payloads only. Real token/account/portfolio data are OWNER-local and never GitHub/CI artifacts.

## 5. Existing implementation to reuse

### V9 T-Invest read path

- path: `main.py` (`get_open_account`, portfolio/positions/enriched snapshot and cursor operations behavior);
- decision: **WRAP_ADAPTER**;
- reason: reuse proven SDK call shapes and read semantics while moving V10 normalization out of the protected FastAPI entrypoint;
- parity rule: V9 `app:app` remains untouched and operational until later V10 cutover.

### V10 canonical financial/domain contracts

- paths: `omni_cio/contracts/v1/portfolio.py`, `omni_cio/contracts/v1/domain.py`;
- decision: **REUSE_AS_IS / WRAP_ADAPTER**;
- rule: WP15 maps broker data into accepted contracts; it does not change financial formulas or identity rules.

### Persistence

- path: `omni_cio/persistence/`;
- decision: **REUSE_AS_IS**;
- rule: no second database and no silent overwrite of immutable canonical identities.

### Durable jobs

- path: `omni_cio/jobs/`;
- decision: **REUSE_AS_IS**;
- rule: broker reads are retry-safe only for requests that cannot create broker-side mutations. Generic WP14 retry semantics never authorize broker write.

No material component receives `REWRITE_REQUIRED` in WP15.

## 6. Allowed changes

WP15 may change only what is required for the read layer and its evidence:

- `omni_cio/adapters/` T-Invest read-only adapter/normalization code;
- narrowly scoped contract exports if needed;
- `omni_cio/persistence/` read helpers only if required to consume accepted BrokerAccount binding without schema changes;
- deterministic WP15 fixtures/tests;
- OWNER-local live-smoke/binding/evidence scripts and a focused WP15 audit workflow;
- `pyproject.toml` static-analysis scope for new scripts;
- WP15 architecture/operations docs;
- parity/reuse metadata only to record final owning-WP decisions.

## 7. Explicit non-goals

WP15 must not:

- expose `orders`, `stop_orders`, PostOrder, cancel/replace or any broker-write primitive;
- accept or fall back to `TINVEST_TRADING_TOKEN` or Sandbox credentials for production reads;
- enable Real execution or change `REAL_TRADING_ENABLED=false`;
- change `trading_methods=false` or `app:app`;
- create Web/WP16, Telegram, Cortex/AI, Guardian business logic or public ingress;
- replace broker HTML report accounting/reconciliation authority;
- create a new database, queue or hosted broker-data SaaS;
- persist/log/upload the raw token, full account ID, raw private portfolio payload or secret-derived material.

## 8. Interfaces and contracts

Canonical package: `omni_cio.adapters.tinvest_read_v1`.

### Account binding

- raw T-Invest account IDs may exist only transiently in adapter memory;
- account persistence uses WP12 SHA-256 account fingerprint + canonical BrokerAccount ID + masked label;
- production ingestion requires an expected OWNER account fingerprint; a different accessible account fails closed;
- zero or multiple open accounts fail closed;
- discovery/binding is a separate OWNER-local step and cannot silently become acceptance.

### Read-only API allowlist

The adapter may call only read methods needed by WP15:

- Users `GetAccounts` and `GetUserTariff` where useful for current limits;
- Operations `GetPortfolio`, `GetPositions`, `GetOperationsByCursor`;
- Instruments read methods required to bind broker UID/FIGI/ISIN/ticker/class-code/lot/name metadata.

No generic client passthrough is exposed.

### Operations cursor/idempotency

- `GetOperationsByCursor` is the canonical API history method for WP15;
- page count and page size are bounded;
- a repeated/non-advancing cursor is an error;
- duplicate operations are deduplicated by a deterministic semantic fingerprint, not raw operation ID;
- operation state is retained; canceled/in-progress operations are not silently counted as executed facts.

### Freshness/completeness

Every read result records timezone-aware UTC `retrieved_at` / local receive time and an explicit freshness evaluation. Freshness thresholds are source-controlled policy defaults and runtime-overridable within bounded validation. Missing required instrument/account/position identity is `INCOMPLETE`/error, never silently dropped. Stale data remains identifiable and cannot be presented as fresh.

### Retry/throttle

- only transient read failures (`UNAVAILABLE`, `DEADLINE_EXCEEDED`, `RESOURCE_EXHAUSTED`) are retryable;
- retries are bounded exponential backoff with jitter and an injectable sleeper/random source for deterministic tests;
- authentication, permission, invalid argument, account binding and semantic validation failures are permanent;
- dynamic T-Invest tariff data may inform pacing, but absence of tariff metadata does not widen limits.

## 9. Data/persistence effects

- migration required: **NO** by default; accepted WP13 tables already cover BrokerAccount/Portfolio/Instrument/Snapshot/Position/content references;
- any discovered schema requirement must be justified as a current-WP blocker before adding a forward migration;
- raw broker responses are not committed or uploaded;
- canonical persisted records carry hashes/identities and exact Decimal/UTC semantics;
- broker-period report truth is not overwritten by live API data;
- WP10 backup/recovery automatically covers accepted WP13 durable state; no second recovery stack is added.

## 10. Security/authority effects

WP15 activates use of the already-approved `broker_read` secret class for its owning contour and adds **no broker-write authority**.

- secret access: `broker_read` only, through the WP8 local secret boundary;
- broker authority: READ only;
- `broker_trading` secret access: forbidden;
- OS/runtime privileges: ordinary runtime identity; OWNER admin only for one-time secret provisioning/binding actions already owned by WP8/WP15 runbooks;
- GitHub permissions: unchanged;
- Web/Telegram ingress: none;
- AI tool authority: none;
- Real execution: unchanged/disabled.

## 11. Normal-path acceptance tests

Deterministic tests must prove at minimum:

- exactly one expected open OWNER account binds to a canonical masked BrokerAccount identity;
- portfolio and positions normalize to an exact `PortfolioSnapshotV1` with Decimal-safe quantities and explicit quality/provenance;
- strong instrument identities remain stable across display-name/ticker changes;
- cash/blocked quantities reconcile where broker fields are available;
- cursor operations paginate to completion, deduplicate semantic repeats and preserve operation states;
- identical broker payload + explicit timestamps produce deterministic canonical hashes/records;
- freshness transitions from fresh to stale deterministically;
- transient read failures follow bounded backoff/jitter and then recover or fail;
- read layer exposes no broker-write method.

## 12. Negative/failure tests

Tests must reject/prove at minimum:

- no open account;
- multiple open accounts;
- wrong expected account fingerprint;
- inaccessible/no-access account;
- missing/contradictory strong instrument identity;
- duplicate conflicting position identity;
- malformed Decimal/Quotation data;
- partial/unresolved enrichment incorrectly marked complete;
- stale data incorrectly marked fresh;
- cursor loop/non-advancing cursor;
- retry beyond bound;
- auth/permission/validation failure retry;
- presence/use of trading token fallback or order service;
- token/full account/private portfolio leakage into logs/evidence.

## 13. Observability

Repository/CI evidence is sanitized and may contain only:

- adapter contract/version;
- PASS/FAIL reason codes;
- record/page/count totals from synthetic fixtures;
- freshness/completeness labels;
- retry attempt counts/timing classes;
- exact code/Git fingerprints where required.

OWNER-local live smoke may display private values on the local console for visual comparison, but persisted/uploaded acceptance evidence records only booleans/count classes and implementation binding. It never stores token/full account ID/raw portfolio payload.

## 14. CI routing

- Fast hosted checks: normal path-aware static/unit feedback when account capacity permits.
- Hosted clean-room compatibility: existing repository policy; a hosted startup billing failure is infrastructure failure, not PASS.
- Lenovo authoritative checks: exact-head `V10 authoritative merge gate` plus focused WP15 deterministic read-only audit.
- Controlled live broker smoke: OWNER-local only; never runs from arbitrary PR code or GitHub Actions with the real read token.
- GPU AI eval required: **NO**.
- Release/recovery matrix required: no new physical recovery rehearsal; accepted WP10/WP13 recovery remains regression-protected.

## 15. Rollback/recovery

Before production WP15 state exists, rollback is source-only to accepted WP14 baseline. After OWNER binding/live data exists, rollback keeps private PostgreSQL/account-binding truth and disables the WP15 reader rather than deleting private history. Revoke/rotate the read token through WP8 if compromised. V9 remains protected rollback while Block D is incomplete.

## 16. Exit Gate

WP15 PASS requires on the exact reviewed PR head:

1. production adapter structurally exposes read-only T-Invest methods only;
2. expected OWNER account binding is fail closed and wrong-account tests pass;
3. portfolio/positions normalize to accepted canonical contracts with strong identity and exact Decimal semantics;
4. cursor operations/dedupe/idempotency are bounded and deterministic;
5. explicit freshness/completeness/stale/partial handling passes;
6. transient retry/backoff/jitter/throttle behavior is bounded and tested;
7. WP13 persistence and WP14 job boundaries are reused without a competing stack;
8. no Web/WP16/Telegram/Cortex/Real work or broker-write authority is introduced;
9. `app:app`, `trading_methods=false`, `REAL_TRADING_ENABLED=false` and V9 rollback remain unchanged;
10. authoritative Self-Hosted Windows CI and focused WP15 deterministic audit are GREEN;
11. dependency audit, SAST and tracked-secret scan are GREEN through the authoritative gate;
12. controlled OWNER-local live read-only smoke proves the expected account and acceptable current data;
13. OWNER confirms locally that portfolio summary matches the intended broker account, one sample position quantity/value is plausible/equal to the broker view under the same snapshot basis, and displayed data age is acceptable;
14. live evidence is sanitized and implementation-bound; no secret/full account/private payload is uploaded;
15. zero unresolved blocking review threads;
16. full PR diff reviewed;
17. squash merge completes;
18. post-merge Regression Shield succeeds on the exact resulting `main` SHA;
19. only then may a separate status synchronization mark Block D COMPLETE and unlock WP16.

## 17. Required acceptance evidence

Record:

- exact PR head SHA;
- deterministic offline fixture test result;
- wrong-account/read-only/static authority test result;
- freshness/partial/retry/cursor/dedupe test result;
- exact authoritative Self-Hosted Windows CI run;
- exact focused WP15 deterministic audit run;
- sanitized OWNER live-smoke PASS/FAIL with implementation binding and confirmation booleans only;
- hosted-lane infrastructure classification if applicable;
- zero blocking review threads;
- merge SHA;
- exact post-merge Regression Shield run.

## 18. Documentation/status updates

The implementation PR owns this contract, adapter/tests, focused audit, OWNER-local runbook and any strictly necessary persistence/job integration. Official `knowledge/17_V10_CURRENT_PROGRAM_STATUS.md` advances only in a separate post-merge status synchronization after post-WP15 Regression Shield and Block D acceptance are GREEN.

## 19. Next WP unlock

Only **WP16 — Web Design System** may be unlocked, and only after every WP15/Block D Exit Gate item above is accepted. Code existing before OWNER live evidence does not unlock WP16.

## 20. Scope-discovery rule

Broker HTML report implementation, Web, Telegram, AI, Guardian business logic, Real execution, public ingress and commercial runtime work discovered during WP15 are future-WP work unless strictly required to make the read adapter safe/correct. They must not be implemented opportunistically.

## Reviewed external technical references

- T-Bank T-Invest token documentation: read-only token can retrieve portfolio/market information and cannot place trading orders; account-scoped read-only tokens are supported.
- T-Invest Operations documentation: `GetOperationsByCursor` is the preferred paginated operations method; operation IDs may change; corporate-action history can be incomplete and broker reports are recommended for exact accounting history.
- T-Invest account documentation: `GetAccounts` returns accounts accessible to the token; `GetUserTariff` exposes current dynamic request limits.
