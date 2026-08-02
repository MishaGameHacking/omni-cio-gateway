# Real trading v1 — durable execution journal

Status: implementation gate for issue #164.

## Decision

The first real-money release uses a single SQLite execution journal stored on a
Render persistent disk mounted at `/var/data`.

Production path is fixed in code:

`/var/data/omni-cio-real-trading.sqlite3`

The application does not accept a production journal path from GPT input. A
relative path, missing mount directory, unsupported schema, or failed row
integrity check makes the real execution contour unavailable.

## Why persistence is mandatory

Real order proposals must survive process restarts so the gateway can preserve:

- proposal state;
- broker request UUID/idempotency key;
- confirmation-bound order parameters;
- submitted/unknown state;
- daily hard-limit accounting;
- broker reconciliation state.

An in-memory store or ordinary ephemeral filesystem is insufficient because a
restart could otherwise erase evidence that a request may already have crossed
the broker boundary.

## Integrity and concurrency

Each proposal row is serialized canonically and authenticated with an HMAC key
derived from `GATEWAY_API_KEY`. The token itself is never stored in SQLite.
Offline modification of a proposal row therefore fails closed during recovery.

SQLite writes use `BEGIN IMMEDIATE`, WAL mode, `synchronous=FULL`, and an atomic
daily-cap reservation. Concurrent confirmations cannot independently consume
the same remaining daily budget.

States counted against the daily budget are `submitting`, `submitted`, and
`unknown`. A definitive broker rejection transitions to `failed` and is not
counted as submitted notional. `unknown` remains reserved because the broker may
already have accepted the request.

## Deployment gate

Do not enable real trading until all of the following are true:

1. PR/CI for the durable journal and conditional Action surface is green and
   merged.
2. A Render persistent disk is attached to the existing gateway service and
   mounted at `/var/data`.
3. The existing read-only `TINVEST_TOKEN` remains unchanged.
4. A separate account-scoped full-access, non-transfer
   `TINVEST_TRADING_TOKEN` is configured.
5. Small positive `REAL_TRADING_MAX_ORDER_RUB` and
   `REAL_TRADING_MAX_DAILY_RUB` values are configured below the immutable code
   ceilings.
6. Owner acceptance first proves readiness, account masking, negative
   confirmation cases, kill-switch behavior, and read-only regression without
   sending a real order.

`REAL_TRADING_ENABLED` remains false until that acceptance stage.

## Rollback

At any anomaly set `REAL_TRADING_ENABLED=false` and restart/deploy the existing
service. With the flag false, real-money routes are not registered and therefore
are absent from OpenAPI. The read-only token and Sandbox contour are independent
of this switch.
