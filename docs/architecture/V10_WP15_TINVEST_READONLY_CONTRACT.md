# Omni-CIO V10 WP15 — T-Invest read-only data layer and freshness

Status: **WP15 AMENDED IMPLEMENTATION CONTRACT / CODE+SECURITY ACCEPTANCE**  
Block: **D — V10 Core and data**

## 1. Authority

This contract is governed by:

- `docs/master-plan/OMNI_CIO_V10_MASTER_PLAN.md`;
- `docs/master-plan/OMNI_CIO_V10_IDENTITY_MULTI_TENANT_ACCOUNT_AND_AUTHENTICATION_AMENDMENT.md`;
- `docs/architecture/ADR-0010-identity-multitenant-authentication.md`;
- `docs/architecture/V10_IDENTITY_AUTHENTICATION_CONTRACT.json`;
- accepted WP8/WP12/WP13/WP14 contracts.

The identity amendment was accepted on `main` as `cbf6a7adba78fa56d23e90ce2cfe2952d21a5e5b` and passed post-merge Regression Shield #1460.

## 2. Purpose

WP15 provides a fail-closed production READ-only T-Invest data layer for current portfolio, positions, market and operations data. It normalizes exact Decimal/UTC data, strong instrument identities, freshness and completeness into accepted V10 contracts.

The T-Invest API is current operational state. It does not replace verified broker-report period accounting truth.

## 3. BrokerConnection interpretation

The product-facing ownership model is:

`authenticated tenant -> BrokerConnection -> READ credential -> verified broker account bindings`.

The old machine-global `broker_read` lifecycle remains bootstrap/recovery/admin compatibility only. Normal product credential provisioning is owned by the authenticated Web settings flow in WP17 and is not implemented in WP15.

A READ credential may expose one or many T-Invest accounts. WP15 therefore distinguishes:

- credential-level discovery: all accessible OPEN accounts reported with READ_ONLY authority;
- account-level ingestion: exactly one expected canonical account fingerprint selected from that discovered set.

A broad READ token is valid only when every broker account with access other than `NO_ACCESS` reports `READ_ONLY` authority; only OPEN accounts are returned as selectable bindings. A narrow token is the same model with one discovered account.

## 4. Account discovery and binding

Canonical connection-scoped entry point: `omni_cio.adapters.tinvest_connection_v1.TInvestConnectionReadAdapter`.

Rules:

- raw broker account IDs exist only transiently inside the adapter boundary;
- outward discovery returns only canonical broker-account identity, SHA-256 fingerprint and masked label;
- `NO_ACCESS` accounts are ignored;
- any account with authority other than `READ_ONLY` or `NO_ACCESS` — including a closed account — rejects the READ credential entirely;
- duplicate provider account identity rejects the credential;
- account ingestion requires one preselected expected fingerprint;
- expected account absent from the credential set fails `EXPECTED_ACCOUNT_NOT_ACCESSIBLE`;
- the selected account is the only raw account ID used for portfolio/positions/operations reads in that adapter instance;
- a broad credential never authorizes cross-tenant account selection; tenant/BrokerConnection ownership is supplied by the authenticated server-side context in the owning Web/API WP.

The pre-amendment `TInvestReadAdapter` remains the proven low-level single-account engine and compatibility surface. New product code must use the connection-scoped adapter.

## 5. Structural read-only authority

The accepted production client proxy remains narrow and exposes only:

- Users: `GetAccounts`, `GetUserTariff`;
- Operations: `GetPortfolio`, `GetPositions`, `GetOperationsByCursor`;
- Instruments: `GetInstrumentBy`;
- MarketData: `GetLastPrices`.

No Orders/StopOrders, Users write calls, raw SDK client, service delegate escape, trading-token fallback, transfer/withdrawal path or broker-write primitive is permitted.

`app:app`, `trading_methods=false` and `REAL_TRADING_ENABLED=false` remain unchanged.

## 6. Portfolio/positions normalization

- exact Decimal/Quotation semantics; no float financial arithmetic;
- `PortfolioPosition.blocked_lots` is numeric blocked quantity;
- `PortfolioPosition.blocked=true` conservatively marks the full position blocked;
- strong UID/position-UID/FIGI identity is conflict checked;
- cash reported/blocked/available state is explicit;
- `limits_loading_in_progress=true` cannot be COMPLETE;
- non-empty virtual positions cannot be silently omitted as COMPLETE;
- unresolved identity is fail-closed in strict mode or explicit PARTIAL in partial mode.

## 7. Operations, cursors and idempotency

- `GetOperationsByCursor` is used for bounded history reads;
- page count, page size, start cursor and returned cursor length are bounded;
- non-advancing/repeated cursor fails closed;
- truncated bounded reads expose an explicit resume cursor;
- semantic dedupe excludes only unstable top-level transport/account identifiers while retaining nested trade semantics;
- raw operation/account IDs are not propagated into normalized output.

## 8. Freshness, retries and throttling

Every read carries explicit UTC receive/evaluation time and freshness state. Missing/partial/stale data is visible and cannot silently become fresh/complete.

Only transient read failures (`UNAVAILABLE`, `DEADLINE_EXCEEDED`, `RESOURCE_EXHAUSTED`) receive bounded exponential backoff+jitter. Authentication, permission, binding and semantic validation failures are permanent. Broker tariff metadata may reduce request pacing; absence falls back to conservative bounded pacing and never widens authority.

## 9. Persistence/job boundaries

WP15 introduces no new database or queue. It reuses accepted WP12 identity contracts, WP13 PostgreSQL boundaries and WP14 durable-job semantics. The connection-scoped adapter is safe for read-only retry semantics only; no durable retry can create broker-write authority.

## 10. Deferred live acceptance

The pre-amendment PowerShell OWNER token workflow is superseded for normal product UX.

During WP15 code/security acceptance:

- no real broker token is requested from OWNER;
- `broker_read` may remain UNPROVISIONED;
- CI and deterministic offline evidence prove adapter correctness and secret-boundary isolation;
- the repository must explicitly record `LIVE_EVIDENCE_STATUS=DEFERRED_TO_WEB_PROVISIONING`;
- no real portfolio value/account is claimed as live-accepted;
- Block D remains uncredited while live evidence is deferred.

The actual controlled live evidence is produced only after WP17 provides the reviewed authenticated Web broker-provisioning flow. It must then prove, for the authenticated tenant/BrokerConnection:

1. READ credential accepted only with READ_ONLY authority;
2. intended broker account is present in the credential's discovered account set;
3. portfolio summary matches the intended broker view;
4. one sample position quantity/value matches the same snapshot basis;
5. freshness is acceptable;
6. evidence is sanitized and bound to reviewed implementation identity.

WP18 real-data acceptance is blocked until that deferred evidence passes.

## 11. Required deterministic tests

At minimum prove:

- single-account READ credential remains supported;
- broad READ credential can discover multiple masked account bindings;
- broad READ credential selects the exact expected account fingerprint;
- expected account absent fails closed without raw IDs in errors;
- duplicate account binding fails closed;
- `NO_ACCESS` is not selectable;
- any account with authority other than `READ_ONLY` or `NO_ACCESS`, including a closed account, rejects the READ credential;
- full account IDs never appear in outward account discovery;
- wrong-account, partial identity, loading limits, virtual positions, stale data, cursor loops, retry bounds and semantic dedupe failure paths remain protected;
- production read proxies expose no broker-write surface or raw delegate escape.

## 12. CI and evidence

WP15 requires:

- exact-head focused deterministic audit;
- authoritative Lenovo repository/security/Regression Shield gate;
- dependency audit, SAST and tracked-secret scan GREEN;
- CI/private-boundary proof that ordinary runner cannot read broker secrets/private bindings;
- a deferred-live evidence audit that passes only when the deferral marker is exact, source-controlled and consistent with the accepted identity amendment.

Hosted billing/spending-limit startup failures remain infrastructure failures and are never called PASS.

## 13. Amended WP15 code/security Exit Gate

WP15 implementation may be accepted and WP16 may become NEXT only when the exact reviewed head proves all of the following:

1. connection-scoped broad/narrow READ account discovery/binding is fail closed;
2. read credential authority is structurally READ_ONLY;
3. no broker-write/transfer/withdrawal authority is introduced;
4. portfolio/positions/market/operations normalization, identity, Decimal, freshness, completeness, cursors, dedupe, retry and throttle tests pass;
5. WP13/WP14 boundaries are reused without competing persistence/queue stacks;
6. authoritative CI, focused WP15 audit, dependency/SAST/secret scan are GREEN;
7. CI cannot read real broker credential/private account binding;
8. no real token/private portfolio data is requested or uploaded;
9. live acceptance is explicitly and audibly deferred to authenticated Web provisioning;
10. Block D remains 26%-program-uncredited until deferred live evidence is later completed;
11. WP18 real-data acceptance remains locked behind the deferred evidence;
12. `app:app`, `trading_methods=false`, `REAL_TRADING_ENABLED=false` and V9 rollback remain unchanged.

This amended gate does not claim live broker acceptance and does not authorize public registration, public ingress, Web implementation inside WP15, or Real execution.
