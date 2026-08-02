# Real trading v1 — durable execution journal

Status: implemented default-off storage gate for issue #164.

## Decision — free production path

The default real-money execution journal uses **Upstash Redis over HTTPS REST**.
This keeps the existing Render Web Service on the **Free** instance type and does
not require a Render Persistent Disk.

Production backend selector:

```text
REAL_TRADING_JOURNAL_BACKEND=upstash
UPSTASH_REDIS_REST_URL=<Upstash HTTPS endpoint>
UPSTASH_REDIS_REST_TOKEN=<Upstash REST token>
```

The backend is server configuration only. GPT input cannot choose the journal
provider, URL, namespace, or token.

Upstash's current Free Redis tier is sufficient for this narrow journal workload
and can be created without a payment card. Current public limits and setup are
documented by Upstash:

- https://upstash.com/pricing/redis
- https://upstash.com/docs/redis/features/restapi

Provider pricing/limits can change, so the runtime never assumes entitlement to
a paid tier. If storage is unavailable or credentials are invalid, real mutation
routes fail closed.

## Why external persistence is mandatory

Real order proposals must survive Render Free sleep, deploys and process
restarts so the gateway can preserve:

- proposal state;
- broker request UUID/idempotency key;
- confirmation-bound order parameters;
- submitted/unknown state;
- daily hard-limit accounting;
- broker reconciliation state.

The ordinary Render Free filesystem is ephemeral and therefore is not used for
real-money execution state.

## Upstash integrity model

The journal stores:

- HMAC-authenticated journal metadata;
- HMAC-authenticated proposal envelopes;
- HMAC-authenticated per-Moscow-day notional counters.

The HMAC key is derived server-side from `GATEWAY_API_KEY`. Neither the Gateway
key nor broker tokens are stored inside Redis.

A metadata count is authenticated and compared with the Redis proposal hash
length. Proposal rows carry revision-bound MACs. Daily counters carry their own
revision-bound MACs and are reconstructed from verified proposals during
`integrity_check()`.

If a row, metadata value or daily counter is modified without the Gateway secret,
startup/readiness fails closed.

## Atomic concurrency model

Upstash REST `EVAL` is used for short compare-and-swap Lua scripts. The scripts
do not make investment decisions and do not contain broker credentials. They
only atomically compare exact authenticated values and replace them.

`reserve_submission()` atomically updates both:

1. the proposal from `prepared` to `submitting`; and
2. the signed daily-notional counter.

A competing confirmation that read an older counter loses the compare-and-swap,
re-reads the new signed counter, and is blocked if the configured daily limit
would be exceeded. This preserves the same invariant previously provided by
SQLite `BEGIN IMMEDIATE`.

Upstash documents Lua `EVAL` as an atomic operation over its REST API:

https://upstash.com/blog/lua-scripting-on-upstash-redis-atomic-operations-over-http

## Failure semantics

Storage availability affects **availability, not authorization**:

- storage unavailable before reserve → no broker submit;
- storage conflict/tamper → no broker submit;
- successful durable reserve happens before `PostOrder`;
- timeout/5xx after possible broker submit remains `unknown_do_not_resubmit`;
- storage loss after a broker request cannot authorize an automatic retry;
- reconciliation continues to use the original UUID request id.

States counted against the daily budget are `submitting`, `submitted`, and
`unknown`. A definitive broker rejection transitions to `failed` and atomically
releases its reserved daily notional. `unknown` remains reserved because the
broker may already have accepted the request.

## Free-tier deployment gate

Do not enable real trading until all of the following are true:

1. real-trading backend/OpenAPI PRs and this free-storage migration are green and
   merged;
2. a permanent Upstash Free Redis database exists (not an unclaimed temporary
   72-hour scratch database);
3. `REAL_TRADING_JOURNAL_BACKEND=upstash`;
4. `UPSTASH_REDIS_REST_URL` and `UPSTASH_REDIS_REST_TOKEN` are configured only
   in Render Environment;
5. the existing read-only `TINVEST_TOKEN` remains unchanged;
6. a separate account-scoped full-access **non-transfer**
   `TINVEST_TRADING_TOKEN` is configured;
7. small positive `REAL_TRADING_MAX_ORDER_RUB` and
   `REAL_TRADING_MAX_DAILY_RUB` values are configured below immutable code
   ceilings;
8. owner acceptance proves readiness, masking, negative confirmation cases,
   kill-switch behavior and read-only regression before any real order.

`REAL_TRADING_ENABLED=false` remains the safe default.

## Optional SQLite compatibility backend

SQLite remains available only as an explicit compatibility/test option:

```text
REAL_TRADING_JOURNAL_BACKEND=sqlite
```

It still requires an actual persistent filesystem such as a paid Render disk at
`/var/data/omni-cio-real-trading.sqlite3`. It is **not** the recommended path for
the current project because the owner requested a zero-cost deployment.

## Rollback

At any anomaly:

1. set `REAL_TRADING_ENABLED=false`;
2. restart/redeploy the existing Render service;
3. verify real mutation routes disappear from OpenAPI;
4. keep the production read-only token unchanged;
5. do not delete the Upstash database until every `submitting`/`unknown` proposal
   is reconciled;
6. revoke only the dedicated trading token if credential compromise is suspected.

The read-only contour and Sandbox contour remain independent of the Upstash
journal and real-trading switch.
