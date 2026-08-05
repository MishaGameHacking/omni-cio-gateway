# Omni-CIO security policy

Omni-CIO работает с финансовыми данными. Production read-only, Sandbox и conditional Real execution — отдельные contours с разными credentials и independent kill switches.

Applied GPT: **v9.0.0**, owner-accepted in place on 2026-08-05. Protected v8.6.1 rollback evidence remains valid.

Real execution exists only as a narrow server-gated surface. Without valid dedicated token, durable state, limits, fresh market and exact owner confirmation, submit must fail closed.

## Secrets and private data

Never publish values of:

- `TINVEST_TOKEN`;
- `TINVEST_SANDBOX_TOKEN`;
- `TINVEST_TRADING_TOKEN`;
- `UPSTASH_REDIS_REST_TOKEN`;
- `GATEWAY_API_KEY`;
- QStash/Watchtower signing or scheduling secret values;
- Authorization/Bearer headers;
- full broker account ID;
- private broker reports/positions/operations as configuration;
- Render/GPT/Upstash credentials;
- private keys/certificates.

Use only env/role names, placeholders and masked IDs.

## Credential isolation

### Read-only

`TINVEST_TOKEN`:

- remains read-only;
- never promoted to full-access;
- never used as fallback by Real execution.

### Sandbox

`TINVEST_SANDBOX_TOKEN`:

- Sandbox only;
- fixed Sandbox host;
- virtual money only;
- never presented as proof of production mutation.

### Real execution

`TINVEST_TRADING_TOKEN`:

- separate account-scoped trading token;
- **without transfer access**;
- only for reviewed `omni_cio.real_trading` OrdersService allowlist;
- never stored in durable journal;
- never returned to GPT/user.

## Production runtime invariants

- stable `app:app` entrypoint;
- secrets via external environment/GPT secret storage only;
- account IDs masked before user-facing output;
- errors sanitized;
- analytics/research/optimizer/Watchtower never authorize an order by themselves;
- withdrawal/transfer/securities-transfer surface absent;
- Real MARKET/BESTPRICE absent;
- margin/short/stop/replace/async/autonomous recurring execution absent;
- `REAL_TRADING_ENABLED=false` removes Real mutation authority and is master rollback;
- Real feature flag alone is insufficient: invalid token/policy/journal/preflight fails closed;
- Real submit only after immutable proposal/plan context + exact short-lived owner phrase in a **new** user turn;
- `submitted` never means `filled` without broker proof;
- possible-submit ambiguity never auto-retries;
- internal v9 engine documentation is never treated as evidence that a server Action ran.

## Sandbox boundary

Sandbox mutation requires `SANDBOX_TRADING_ENABLED=true` and fixed `sandbox-invest-public-api.tbank.ru` host.

Required:

- separate token;
- `sandbox=true`, `real_money=false`;
- allowlisted methods only;
- no transfer/withdrawal;
- `confirmMarginTrade=false`;
- BUY own-funds / SELL own-position limits;
- immutable proposal + exact short-lived confirmation;
- repeat preflight before submit;
- UUID idempotency;
- no duplicate submit;
- ambiguous submit no retry;
- masked account.

## Real execution boundary

Reviewed operationIds:

- `getRealTradingStatus`;
- `prepareRealTrade`;
- consequential `executeRealTrade`;
- `getRealOrderState`.

The server may publish status-only while fail-closed, or the complete reviewed Real surface when readiness is valid.

Allowed v1 execution characteristics:

- BUY/SELL;
- supported cash share/ETF;
- RUB;
- LIMIT / CURRENCY / DAY only;
- own-funds BUY;
- own-position SELL;
- exact price step;
- fresh trusted order book;
- server per-order/daily hard caps.

Prepare/execute separation:

1. bind exactly one trading account to the read-only account;
2. check instrument identity + fresh market;
3. broker affordability/order-price preflight;
4. create durable immutable proposal/plan execution context;
5. return exact phrase and stop;
6. phrase must arrive in a new owner turn;
7. repeat account/market/financial/risk preflight;
8. durable atomic reservation/idempotency before submit;
9. submit once with UUID identity;
10. reconcile broker state by original request UUID.

Wrong/expired phrase, changed preflight, insufficient own funds/position, account mismatch, stale market, hard-limit failure, journal outage/tamper/integrity failure all fail closed before submit.

## Durable state

Selected production real journal backend:

```text
REAL_TRADING_JOURNAL_BACKEND=upstash
UPSTASH_REDIS_REST_URL=<HTTPS *.upstash.io endpoint>
UPSTASH_REDIS_REST_TOKEN=<Render secret>
```

Security requirements:

- HTTPS Upstash host restriction;
- REST token only in external environment;
- redirects disabled / no proxy-env trust for journal client;
- no unsafe fallback to memory;
- HMAC-authenticated durable records where defined;
- integrity recomputation;
- atomic compare-and-swap/reservation semantics;
- secrets excluded from records;
- tamper/missing/corrupt state blocks readiness/submission.

Watchtower and Decision Journal use separate reviewed namespaces/contracts; one subsystem must not reinterpret another subsystem's records.

## Ambiguous broker submit

Timeout/connection break/5xx after broker submit may mean the broker received the request.

Required behavior:

- proposal/stage → unknown / do-not-resubmit;
- reserved limit remains protected until reconciliation semantics release it;
- second submit forbidden;
- reconcile original UUID through broker state;
- unresolved ambiguity blocks automatic continuation.

Definitive broker rejection may move to failed/release reservation only through the reviewed atomic lifecycle.

## Custom GPT boundary

Applied GPT Editor Instructions:

`gpt/CUSTOM_GPT_INSTRUCTIONS_V9_0_0_COMPACT.txt`

Protected rollback Instructions:

`gpt/CUSTOM_GPT_INSTRUCTIONS_V8_6_1_COMPACT.txt`

- OpenAPI only from production Gateway;
- Authentication = API Key → Bearer using external `GATEWAY_API_KEY`;
- broker/Upstash/QStash tokens never enter Instructions/Knowledge;
- ordinary portfolio management/advisory wording is not trade confirmation;
- consequential UI never replaces server-side exact-confirmation gate;
- Apps remain OFF while custom Actions are used;
- GitHub does not sync GPT Editor/Render/Upstash/QStash automatically;
- effective production `/openapi.json` is Action authority;
- internal v9 modules are not invented as Actions.

Owner acceptance confirmed the existing GPT was upgraded in place to v9.0.0 and post-Update Action routing worked without submitting a live order during configuration acceptance.

## Data integrity

- exact decimal logic;
- verified FX + timestamp before currency mixing;
- partial/truncated/stale/contradictory data fail closed;
- no commission/operation double count;
- last price not executable guarantee;
- fresh market required for Real proposal/market-sensitive sizing;
- Sandbox fill is not production fill evidence;
- durable journal is not broker state; after submit broker reconciliation is mandatory;
- expected decision state is not rewritten with hindsight; outcome/evaluation records remain separate.

## Watchtower security

Watchtower is read-only monitoring/orchestration. Hidden signed scheduler/callback routes are not GPT Actions. Alerts/review triggers never authorize real execution.

Default rollback:

`WATCHTOWER_ENABLED=false`.

QStash signing/scheduling credentials and Watchtower journal secret values remain external and never enter GPT Knowledge/Instructions.

## Live Gateway Authority Acceptance

The scheduled live check performs only public GET requests to:

- `/health`;
- `/openapi.json`.

It does not send a Gateway/Broker token and never calls a protected Action. It validates the deployed schema against the reviewed baseline/Sandbox/Real allowlists, canonical methods/paths, consequential markers and forbidden path classes.

The previous production-wide GET-only live check is retired because reviewed v9 may conditionally publish protected Sandbox/Real POST Actions. Baseline GET-only contract tests remain useful for safe-mode verification.

## CI / dependency security

- direct dependency constraints live in `requirements.in` / `requirements-dev.in`;
- generated locks are exact/hash-locked and not hand-edited;
- generated Windows projections are ephemeral CI artifacts;
- external GitHub Actions pin full SHA;
- Regression Shield covers lock reproducibility, repository/security policy, compile, lint, formatting, types, entrypoint/contracts, tests/coverage, dependency audit, SAST and secret scan;
- tests use fake/mock transports and never submit live broker orders;
- Dependabot updates are proposals only;
- known-incompatible toolchain releases are held narrowly/documented rather than bypassing a gate.

Required regression evidence includes wrong/expired confirmation, own-funds/own-position guards, hard caps, account mismatch, stale market, replay single-submit, ambiguous-submit no-retry, masking/redaction, durable persistence/integrity and conditional OpenAPI.

## Owner acceptance state

Protected v8.6.1 real BUY/SELL acceptance is **100% complete**, including broker/portfolio/operations reconciliation and the canonical invariant:

**idempotent replay verified with no second submit**.

Applied v9.0.0 Custom GPT acceptance is also complete. It verified, without a new live order:

- existing GPT upgraded rather than duplicated;
- exact v9 Instructions/Knowledge/OpenAPI/authentication applied;
- exact `gatewayHealth` isolation;
- read-only portfolio/cash/analytics routing;
- advisory SBER request did not prepare/execute a real order;
- Watchtower/journal explanation did not fabricate server execution;
- Real readiness check called only `getRealTradingStatus` and did not call prepare/execute;
- recovery documentation remains available.

Issues #216 and #176 are completed.

## Maintenance security rule

WP0–WP15 is complete. Maintenance changes must not silently broaden broker/GPT authority.

Required path:

`branch → focused tests/guards → exact-head Regression Shield/security → zero unresolved review threads → squash merge`.

If a future change modifies the applied GPT configuration or reviewed Action surface, owner Preview/Update acceptance on the same GPT is required again.

At any Real safety anomaly: set `REAL_TRADING_ENABLED=false`, preserve durable/broker evidence and reconcile before further action.

Full Real procedure: `docs/operations/REAL_TRADING_RELEASE_RUNBOOK.md`.
