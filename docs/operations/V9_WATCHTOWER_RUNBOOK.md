# Omni-CIO v9 Portfolio Watchtower — Operations Runbook

## Release posture

WP13 code is feature-flagged. The applied Custom GPT and protected real-money release remain v8.6.1 until WP15.

Do not enable Watchtower until a canonical WP8/WP6/market evidence provider has been explicitly installed. Route registration itself is inert and hidden from OpenAPI when disabled.

## Required environment

Gateway runtime when enabled:

- `WATCHTOWER_ENABLED=true`;
- `WATCHTOWER_PUBLIC_BASE_URL=https://<gateway-origin>` or existing `RENDER_EXTERNAL_URL`;
- `WATCHTOWER_QSTASH_SCHEDULE_ID=omni-cio-watchtower-primary-v1` unless a reviewed replacement is used;
- `QSTASH_CURRENT_SIGNING_KEY`;
- `QSTASH_NEXT_SIGNING_KEY`;
- `UPSTASH_REDIS_REST_URL`;
- `UPSTASH_REDIS_REST_TOKEN`;
- `WATCHTOWER_JOURNAL_SECRET` — dedicated HMAC key, separate from broker/Gateway tokens.

Schedule reconciliation additionally requires:

- `QSTASH_TOKEN`;
- `WATCHTOWER_CRON` — explicit reviewed QStash cron expression.

Secrets must remain environment-only. Do not log tokens, signing keys, raw holdings or broker source payloads.

## Provider installation

Gateway startup registers an empty `WatchtowerEvidenceProviderRegistryV1` and three hidden routes. A release-owned source wiring step must call `install_watchtower_canonical_provider(...)` with lazy loaders for:

- canonical WP8 `PortfolioRiskAssessmentV1`;
- canonical WP6 `CreditPassportV1` objects;
- canonical market research bundles;
- optional normalized data-quality codes.

Installation invokes no loader and performs no broker call. The scheduled run invokes the loaders only after QStash signature verification succeeds.

If no provider is installed, enabled execution fails closed with `WATCHTOWER_PROVIDER_NOT_REGISTERED`; no alert or plan is created.

## Internal routes

All routes are POST and `include_in_schema=False`:

- `/internal/watchtower/run`;
- `/internal/watchtower/callback`;
- `/internal/watchtower/failure-callback`.

They never appear in GPT Actions OpenAPI. Authentication is QStash signature verification over the exact raw body and exact configured URL, supporting both current and next signing keys.

## Canonical schedule

Check current schedule without changing it:

```bash
python scripts/reconcile_watchtower_schedule.py
```

A non-zero exit means the schedule is missing or drifted.

After reviewing environment/configuration, reconcile explicitly:

```bash
python scripts/reconcile_watchtower_schedule.py --ensure
```

The reconciler prints only safe schedule identity and next execution timestamp. It never prints `QSTASH_TOKEN`.

Schedule policy:

- one canonical custom schedule ID;
- POST to the internal run route;
- at most 3 delivery retries;
- 1 callback retry and 1 failure-callback retry;
- callback/failure callback restricted to the same Gateway host;
- body redacted in QStash dashboard;
- body contains only the fixed Watchtower trigger envelope.

## Delivery deduplication

Two independent controls are required:

1. QStash `Upstash-Message-Id` is recorded in bounded durable state so exact transport replay is silent.
2. Economic conditions use semantic fingerprints so a new delivery or new source SHA does not repeat the same unchanged alert.

Active fingerprints are not a permanent suppression list. When a condition resolves it disappears from active state; if it later recurs, it may alert again.

## Durable state

Watchtower uses a separate Upstash namespace:

`omni-cio:watchtower:v1`

State and authenticated metadata are HMAC-protected. Compare-and-swap prevents stale/concurrent delivery overwrite. Integrity checks verify authenticated row count and every state envelope.

The journal stores hashes, safe identifiers and reducer state only. It does not persist raw portfolio/source payloads or broker credentials.

## Recovery

1. Keep `WATCHTOWER_ENABLED=false` while diagnosing.
2. Confirm protected `app:app` and v8.6.1 release invariants remain intact.
3. Verify Upstash credentials and `WATCHTOWER_JOURNAL_SECRET` against existing durable state. A wrong secret intentionally fails integrity checks.
4. Verify current/next QStash signing keys.
5. Run the schedule reconciler in check mode.
6. Reinstall the canonical provider wiring without invoking loaders at startup.
7. Run unit/shadow acceptance with signed fake QStash delivery.
8. Reconcile schedule with `--ensure` only after configuration review.
9. Enable Watchtower.
10. Confirm a clean run is silent and duplicate delivery is replay-safe before treating alerts as operational.

## Rollback

Set:

`WATCHTOWER_ENABLED=false`

This disables scheduled route execution without changing the protected read-only, Sandbox or real-money contours. The QStash schedule may then be deleted or left disabled/reconciled separately. No Watchtower rollback requires changing real-trading secrets or the Custom GPT configuration.

## Real-money boundary

Watchtower may request review/recommendation and later may produce a proposed immutable WP11 plan. It cannot authorize or submit an order. All real-money activity remains inside the exact WP11/WP12 owner-confirmed, idempotent, broker-reconciled lifecycle.
