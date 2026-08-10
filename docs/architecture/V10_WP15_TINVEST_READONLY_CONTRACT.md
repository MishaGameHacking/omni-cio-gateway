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

Provide one fail-closed production **READ-only** T-Invest adapter that binds exactly to the OWNER account, retrieves current portfolio/positions/market/operations data, enriches strong instrument identity, normalizes exact Decimal/UTC data into accepted V10 contracts, and exposes explicit freshness/completeness state for later Core/Web consumers.

The T-Invest API layer is current operational state. It does **not** replace the accepted verified broker HTML report as canonical broker-period accounting truth. Where API history and broker-period accounting differ, reconciliation/report truth remains a separate owning capability.

## 4. Inputs and prerequisites

WP15 consumes rather than redefines:

- the production `broker_read` secret class from WP8;
- the accepted `t-tech-investments==1.49.3` SDK/runtime lock;
- the existing V9 read-only T-Invest Gateway behavior in `main.py` as reuse/parity evidence;
- `PortfolioSnapshotV1` and related V9 financial DTOs;
- WP12 BrokerAccount/Portfolio/Instrument/Snapshot/Position identity contracts;
- WP13 PostgreSQL persistence boundaries;
- WP14 durable job semantics without creating another queue.

Offline CI uses deterministic synthetic broker payloads only. Real token/account/portfolio data are OWNER-local and never GitHub/CI artifacts.

## 5. Existing implementation to reuse

### V9 T-Invest read path

- path: `main.py`;
- decision: **WRAP_ADAPTER**;
- reason: reuse proven read semantics while moving V10 normalization out of the protected FastAPI entrypoint;
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
- deterministic WP15 fixtures/tests;
- OWNER-local live-smoke/binding/evidence scripts and focused WP15 audit workflows;
- `pyproject.toml` static-analysis scope for new scripts;
- WP15 architecture/operations docs;
- parity/reuse metadata only to record final owning-WP decisions.

## 7. Explicit non-goals

WP15 must not:

- expose `orders`, `stop_orders`, PostOrder, cancel/replace, Users write calls such as pay-in/currency transfer, or any other broker-write primitive;
- accept or fall back to `TINVEST_TRADING_TOKEN` or Sandbox credentials for production reads;
- enable Real execution or change `REAL_TRADING_ENABLED=false`;
- change `trading_methods=false` or `app:app`;
- create Web/WP16, Telegram, Cortex/AI, Guardian business logic or public ingress;
- replace broker HTML report accounting/reconciliation authority;
- create a new database, queue or hosted broker-data SaaS;
- persist/log/upload the raw token, full account ID, account fingerprint, raw private portfolio payload or secret-derived material.

## 8. Interfaces and contracts

Canonical packages:

- `omni_cio.adapters.tinvest_read_v1`;
- `omni_cio.adapters.tinvest_market_v1`;
- `omni_cio.adapters.tinvest_secret_v1`.

### 8.1 Account binding and token authority

- raw T-Invest account IDs may exist only transiently in adapter memory;
- account persistence/evidence uses canonical identity, SHA-256 fingerprint where private local binding requires it, and a masked label; full account IDs are never emitted;
- production ingestion requires an expected OWNER account fingerprint; a different accessible account fails closed;
- zero or multiple accessible open accounts fail closed;
- discovery/binding is an OWNER-local step and cannot silently become acceptance;
- the production credential boundary calls token-scoped `GetAccounts` and accepts **only** accessible account records reported as `ACCOUNT_ACCESS_LEVEL_READ_ONLY`; `FULL_ACCESS`, unspecified or any other broader/unknown authority fails closed;
- `NO_ACCESS` records are not eligible for binding;
- the OWNER confirmation is additional acceptance evidence, not the sole enforcement of read-only authority.

### 8.2 Structural read-only API allowlist

The production broker client is wrapped before it reaches the adapter. The wrapper exposes only pre-extracted allowlisted read callables and does not retain a service delegate escape.

Allowed surface:

- Users: `GetAccounts`, `GetUserTariff`;
- Operations: `GetPortfolio`, `GetPositions`, `GetOperationsByCursor`;
- Instruments: `GetInstrumentBy` for strong identity enrichment;
- MarketData: `GetLastPrices`.

The proxy exposes no `orders`, `stop_orders`, Users write calls, arbitrary service passthrough, generic SDK client, or `_delegate` handle through which a caller can recover a broader service object.

### 8.3 Portfolio/positions normalization

- broker `PortfolioPosition.quantity` is exact Decimal/Quotation input;
- broker `PortfolioPosition.blocked_lots` is the numeric blocked quantity;
- broker `PortfolioPosition.blocked` is a boolean depositary-block flag, never parsed as a number;
- when the depositary-block flag is true, the adapter conservatively marks the full canonical position quantity as blocked rather than understating availability;
- malformed blocked/quantity fields fail closed;
- cash balances use reported and blocked broker money to derive explicit available cash without float conversion;
- strong instrument identity uses UID/position UID/FIGI consistency checks and metadata enrichment; missing or contradictory identity is never silently dropped in strict mode.

### 8.4 Completeness and special broker states

- `PositionsResponse.limits_loading_in_progress=true` means the snapshot cannot be called complete;
- strict mode fails closed on loading limits; explicit partial mode records a degraded/partial issue;
- non-empty `PortfolioResponse.virtual_positions` are never silently omitted while reporting COMPLETE;
- current WP12 canonical position schema does not encode the virtual-position expiry semantics, so strict mode rejects non-empty virtual positions and explicit partial mode counts them as unresolved with a degraded/partial marker;
- malformed list shapes fail closed rather than filtering invalid rows.

### 8.5 Operations cursor/idempotency

- `GetOperationsByCursor` is the canonical API history method for WP15;
- page count, page size, start cursor and returned cursor length are bounded;
- a repeated/non-advancing cursor is an error;
- bounded reads return an explicit `next_cursor` when more pages remain so a later polling cycle can resume safely;
- duplicate operations are deduplicated by a deterministic semantic fingerprint, not raw operation ID;
- the fingerprint includes the complete semantic operation payload while excluding only unstable/top-level transport/account identifiers: `cursor`, `broker_account_id`, `id`, `parent_operation_id`;
- semantically different nested trade/operation data therefore remains distinct;
- raw operation/account IDs are not propagated into normalized output;
- operation state is retained; canceled/in-progress operations are not silently counted as executed facts.

### 8.6 Freshness

Every read result records timezone-aware UTC `retrieved_at` / local receive time and an explicit freshness evaluation. Freshness thresholds are source-controlled policy defaults and bounded configuration. Missing required identity/completeness information is error or explicit PARTIAL, never silently dropped. Stale data remains identifiable and cannot be presented as fresh.

### 8.7 Retry/throttle

- only transient read failures (`UNAVAILABLE`, `DEADLINE_EXCEEDED`, `RESOURCE_EXHAUSTED`) are retryable;
- retries are bounded exponential backoff with jitter and injectable timing/random sources for deterministic tests;
- authentication, permission, invalid argument, account binding and semantic validation failures are permanent;
- dynamic T-Invest tariff data may inform pacing, but absence of tariff metadata falls back to a conservative bounded policy and never widens broker authority.

## 9. Data/persistence effects

- migration required: **NO**;
- WP15 does not create a competing persistence/queue stack;
- raw broker responses are not committed or uploaded;
- canonical records carry exact Decimal/UTC semantics and accepted identities;
- broker-period report truth is not overwritten by live API data;
- WP10 backup/recovery continues to cover accepted WP13 durable state.

## 10. Security/authority effects

WP15 activates use of the already-approved `broker_read` secret class for its owning contour and adds **no broker-write authority**.

- secret access: `broker_read` only, through the WP8 local DPAPI/ACL boundary;
- broker authority: technically enforced READ_ONLY based on token-scoped account access level plus structural method allowlist;
- broader/full-access credential: rejected before portfolio/market/operations use;
- broker write services/methods: structurally unavailable from the production WP15 client proxy;
- `broker_trading` secret access: forbidden;
- OS/runtime privileges: ordinary runtime identity; OWNER admin only for local secret provisioning and reviewed OWNER acceptance wrapper;
- GitHub permissions: unchanged/read-only for audits;
- Web/Telegram ingress: none;
- AI tool authority: none;
- Real execution: unchanged/disabled.

## 11. Normal-path acceptance tests

Deterministic tests must prove at minimum:

- exactly one expected open OWNER account binds to a canonical masked BrokerAccount identity;
- token-scoped account authority is READ_ONLY;
- portfolio and positions normalize to exact `PortfolioSnapshotV1` values with Decimal-safe quantities and explicit quality/provenance;
- official `blocked` boolean / `blocked_lots` numeric semantics are respected;
- strong instrument identities remain stable and conflict-checked;
- cash/blocked quantities reconcile where broker fields are available;
- cursor operations paginate/resume, deduplicate semantic repeats and preserve semantic differences;
- identical broker payload + explicit timestamps produce deterministic canonical results;
- freshness transitions from fresh to stale deterministically;
- transient read failures follow bounded backoff/jitter and then recover or fail;
- production read proxy exposes only the approved read callables and no underlying service escape.

## 12. Negative/failure tests

Tests must reject/prove at minimum:

- no open account;
- multiple open accounts;
- wrong expected account fingerprint;
- inaccessible/no-access account;
- full-access or unknown-access production credential;
- missing/contradictory strong instrument identity;
- malformed Decimal/Quotation/bool data;
- `limits_loading_in_progress` incorrectly marked complete;
- non-empty virtual positions silently omitted as complete;
- partial/unresolved enrichment incorrectly marked complete;
- stale data incorrectly marked fresh;
- cursor loop/non-advancing/oversized cursor;
- retry beyond bound;
- auth/permission/validation failure retry;
- semantic operation collision caused by ignoring nested trade data;
- presence/use of trading token fallback, order service, Users write service or raw service delegate;
- token/full account/private portfolio leakage into logs/evidence.

## 13. Observability

Repository/CI evidence is sanitized and may contain only:

- adapter contract/version;
- PASS/FAIL reason codes;
- record/page/count totals from synthetic fixtures;
- freshness/completeness labels;
- retry attempt counts/timing classes;
- exact code/Git fingerprints where required.

OWNER-local live smoke may display private values on the local console for visual comparison, but persisted/uploaded acceptance evidence records only booleans/count classes and implementation binding. It never stores token/full account ID/account fingerprint/raw portfolio payload.

## 14. CI routing and exact-head binding

- Fast hosted checks: path-aware static/unit feedback when account capacity permits; billing/spending-limit startup failures are infrastructure failures, never PASS.
- Lenovo authoritative gate: full repository integration/security/regression coverage.
- Focused WP15 deterministic and OWNER-evidence audits explicitly checkout `pull_request.head.sha`, not GitHub's synthetic merge ref, so implementation/evidence binding is against the exact reviewed branch head.
- Controlled live broker smoke: OWNER-local only; never runs from GitHub Actions with the real read token.
- CI runner must not see/read the `broker_read` DPAPI ciphertext or private OWNER account binding; only sanitized evidence is readable after OWNER execution.
- GPU AI eval required: **NO**.
- No new physical recovery rehearsal is introduced; accepted WP10/WP13 recovery remains regression-protected.

## 15. Rollback/recovery

Before production WP15 state exists, rollback is source-only to accepted WP14 baseline. After OWNER binding/live evidence exists, rollback keeps private binding/durable truth and disables the WP15 reader rather than deleting private history. Revoke/rotate the read token through WP8 if compromised. V9 remains protected rollback while Block D is incomplete.

## 16. Exit Gate

WP15 PASS requires on the exact reviewed PR head:

1. production client structurally exposes only allowlisted T-Invest reads and has no service-delegate escape;
2. the broker reports the production credential/account authority as READ_ONLY; broader/unknown authority fails closed;
3. expected OWNER account binding is fail closed and wrong-account tests pass;
4. portfolio/positions normalize to accepted canonical contracts with strong identity and exact Decimal semantics, including correct `blocked`/`blocked_lots` interpretation;
5. loading limits, virtual positions and unresolved identities cannot be mislabeled COMPLETE;
6. cursor operations/dedupe/resume/idempotency are bounded and deterministic;
7. explicit freshness/completeness/stale/partial handling passes;
8. transient retry/backoff/jitter/throttle behavior is bounded and tested;
9. WP13 persistence and WP14 job boundaries are reused without a competing stack;
10. no Web/WP16/Telegram/Cortex/Real work or broker-write authority is introduced;
11. `app:app`, `trading_methods=false`, `REAL_TRADING_ENABLED=false` and V9 rollback remain unchanged;
12. authoritative Self-Hosted Windows CI and focused WP15 deterministic audit are GREEN;
13. dependency audit, SAST and tracked-secret scan are GREEN through the authoritative gate;
14. controlled OWNER-local live read-only smoke proves the expected account and acceptable current data;
15. OWNER confirms locally that portfolio summary matches the intended broker account, one sample position quantity/value matches the broker view under the same snapshot basis, and displayed data age is acceptable;
16. live evidence is sanitized and bound to the exact PR head plus implementation fingerprint; no secret/full account/private payload is uploaded;
17. zero unresolved blocking review threads;
18. full PR diff reviewed;
19. squash merge completes;
20. post-merge Regression Shield succeeds on the exact resulting `main` SHA;
21. only then may a separate status synchronization mark Block D COMPLETE and unlock WP16.

## 17. Required acceptance evidence

Record:

- exact PR head SHA;
- deterministic offline fixture result;
- wrong-account/read-only/static authority result;
- completeness/freshness/retry/cursor/dedupe/official-shape result;
- exact authoritative Self-Hosted Windows CI run;
- exact focused WP15 deterministic audit run;
- sanitized OWNER live-smoke PASS/FAIL with implementation binding and confirmation booleans only;
- hosted-lane infrastructure classification if applicable;
- zero blocking review threads;
- merge SHA;
- exact post-merge Regression Shield run.

## 18. Documentation/status updates

The implementation PR owns this contract, adapter/tests, focused audits and OWNER-local runbook. Official `knowledge/17_V10_CURRENT_PROGRAM_STATUS.md` advances only in a separate post-merge status synchronization after post-WP15 Regression Shield and Block D acceptance are GREEN.

## 19. Next WP unlock

Only **WP16 — Web Design System** may be unlocked, and only after every WP15/Block D Exit Gate item above is accepted. Code existing before OWNER live evidence does not unlock WP16.

## 20. Scope-discovery rule

Broker HTML report implementation, Web, Telegram, AI, Guardian business logic, Real execution, public ingress and commercial runtime work discovered during WP15 are future-WP work unless strictly required to make the read adapter safe/correct. They must not be implemented opportunistically.

## Reviewed external technical references

- T-Bank Invest API account/token documentation: account `access_level` is token-dependent and distinguishes FULL_ACCESS, READ_ONLY and NO_ACCESS; read-only credentials cannot place trading orders.
- T-Bank Invest Operations schemas: `PortfolioPosition.blocked` is a boolean depositary-block flag, numeric blocked quantity is `blocked_lots`, `PositionsResponse.limits_loading_in_progress` signals incomplete loading, and `PortfolioResponse.virtual_positions` may be present.
- T-Bank Invest Operations documentation: `GetOperationsByCursor` is the paginated operations method; broker operation IDs can change, so WP15 semantic idempotency does not use them as stable identity.
- T-Bank Invest account/tariff documentation: `GetAccounts` returns token-accessible accounts and `GetUserTariff` exposes current request limits.
