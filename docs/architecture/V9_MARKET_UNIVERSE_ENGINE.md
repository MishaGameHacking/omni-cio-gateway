# Omni-CIO v9 — Market Universe Engine

Status: **WP3 implementation contract**  
Parent program: `docs/master-plan/OMNI_CIO_V9_PORTFOLIO_AUTOPILOT_PROGRAM.md`  
Protected production baseline: **Omni-CIO v8.6.1**

## 1. Purpose

WP3 creates the deterministic instrument universe consumed by later candidate-funnel, research, risk and optimizer packages.

The universe is a read-only broker fact layer. It does not recommend securities, calculate personal sizing, submit orders or expand the real-money execution surface.

## 2. Authoritative source

Primary source is T-Invest `InstrumentsService`.

WP3 enumerates exactly these instrument categories:

- `Shares`;
- `Bonds`;
- `Etfs`.

Every list request uses `INSTRUMENT_STATUS_BASE`.

T-Bank documents `INSTRUMENT_STATUS_BASE` as the base list of instruments tradable through T-Invest API. The API also exposes per-instrument eligibility evidence such as `api_trade_available_flag`, buy/sell flags, qualification requirement, missing required tests, IIS availability, TCA blocking and real execution exchange.

Canonical references:

- https://developer.tbank.ru/invest/services/instruments/faq_instruments
- https://developer.tbank.ru/invest/services/instruments/methods
- https://developer.tbank.ru/invest/api/instruments-service-shares
- https://developer.tbank.ru/invest/api/instruments-service-bonds
- https://developer.tbank.ru/invest/api/instruments-service-etfs

`FindInstrument` is not a universe-enumeration mechanism. WP3 never brute-forces ticker/name search through an LLM loop.

## 3. Identity contract

Every broker row must include instrument `uid` and the normalized `InstrumentIdentity` shared by portfolio contracts.

Aliases retained when available:

- UID;
- position UID;
- FIGI;
- ISIN;
- ticker + class code.

Exact duplicate rows are removed deterministically. Materially different payloads for the same UID are conflicts. Any stable alias that maps to more than one UID is also a conflict.

Identity conflicts make the snapshot fail closed (`decision_ready=false`). Later packages must not silently choose one conflicting identity.

## 4. Account eligibility without identity leakage

WP3 refreshes T-Invest `GetInfo` on every load and retains only eligibility evidence required by the universe:

- qualified-investor status;
- qualification/work permissions returned by the broker;
- account type supplied by already-verified owner policy/context.

It deliberately does not persist:

- `user_id`;
- full broker account ID;
- tariff or unrelated profile data.

An unknown account type or unavailable qualification status makes the personal universe not decision-ready.

## 5. Deterministic exclusion gates

A broker row is excluded from the buy-candidate universe when any applicable gate is true:

- API trading unavailable;
- buying unavailable;
- blocked by TCA;
- account is IIS and instrument is unavailable for IIS;
- instrument requires qualified-investor status and that status is not verified true;
- broker reports missing mandatory tests.

The T-Invest `required_tests` field already accounts for completed tests and returns only tests still required for that client. WP3 therefore treats a non-empty list as a deterministic blocker.

`sell_available_flag`, OTC and liquidity flags are retained as evidence but are not used to invent a current-session trading status. Current trading-session readiness remains a separate market-data/pre-trade concern.

## 6. Source completeness and quality

A ready catalog requires all three BASE operations (`Shares`, `Bonds`, `Etfs`) to complete without source errors and without invalid source rows.

The snapshot is fail closed when any of the following is true:

- one or more source operations fail;
- the source set is incomplete;
- SDK rows fail contract validation;
- account eligibility cannot be verified;
- account type or qualification status is unknown;
- identity conflicts exist;
- no eligible instrument remains.

No partial broker response is silently promoted to a complete universe.

## 7. Reproducibility

`content_sha256` is calculated from canonical normalized content, not retrieval order or wall-clock retrieval timestamp.

Therefore:

- reordering broker rows does not change the fingerprint;
- reordering completed operation values does not change it;
- a material identity/eligibility/source-state change does change it.

Later candidate and plan artifacts can bind themselves to this universe fingerprint.

## 8. Cache architecture

Full BASE instrument lists are expensive and slow-changing compared with user eligibility. WP3 therefore separates:

1. **catalog** — Shares/Bonds/Etfs BASE rows, cached in process with a bounded TTL (default six hours);
2. **account eligibility** — refreshed on every universe load.

Only a catalog with all required operations, zero source errors and zero invalid rows is cached. Partial/degraded catalogs are never cached. Forced refresh bypasses TTL.

This keeps client-specific qualification evidence fresh without repeatedly downloading the entire instrument directory.

## 9. Security boundary

WP3 is read-only.

Allowed broker calls:

- `UsersService/GetInfo`;
- `InstrumentsService/Shares`;
- `InstrumentsService/Bonds`;
- `InstrumentsService/Etfs`.

Not used:

- order services;
- stop-order services;
- sandbox mutation methods;
- withdrawal/transfer APIs;
- `FindInstrument` loops for enumeration.

WP3 adds no public FastAPI route, no OpenAPI Action, no Render secret and no GPT Editor change.

## 10. Exit gate

WP3 is complete only when:

1. versioned contracts exist;
2. deterministic builder exists;
3. fake-client tests prove BASE Shares/Bonds/Etfs calls;
4. identity duplicates/conflicts are covered;
5. account eligibility and privacy boundaries are covered;
6. source failure/invalid row paths fail closed;
7. catalog cache reuse/expiry/force refresh are covered;
8. content fingerprint is order-invariant and mutation-sensitive;
9. repository guard and mypy scope protect the new package;
10. exact-head Regression Shield is fully green and the PR is squash-merged.
