# Omni-CIO — external secrets, Render, Upstash and QStash boundary

> **PROTECTED V9 RECOVERY ONLY — NOT CURRENT V10 AUTHORITY.** This file preserves the accepted Custom GPT v9.0.0 / `app:app` recovery surface. Current V10 implementation authority is the Timeweb + Telegram path defined by Amendments 18–21 and `knowledge/17_V10_CURRENT_PROGRAM_STATUS.md`.

This file records only **roles and environment variable names**. Secret values never belong in GitHub, GPT Instructions, GPT Knowledge or user-facing responses.

## 1. Single production service

- Render service: `omni-cio-gateway`;
- base URL: `https://omni-cio-gateway.onrender.com`;
- entrypoint: `app:app`;
- current project instance: Render Free.

Read-only, optional Sandbox, confirmed Real execution and hidden Watchtower routes remain in this single Gateway. Do not create a second v9 service.

## 2. Broker credential separation

### Production read-only

`TINVEST_TOKEN`

Read-only production credential. Never upgrade its role and never use it as a real-execution fallback.

### Sandbox

`TINVEST_SANDBOX_TOKEN`

Separate Sandbox credential; virtual money only.

### Real execution

`TINVEST_TRADING_TOKEN`

Separate account-scoped real-execution credential without transfer authority. Used only by the reviewed real-trading contour; never stored in GPT or execution journal.

## 3. GPT → Gateway authentication

`GATEWAY_API_KEY`

- exists in external server configuration;
- GPT Action Authentication uses API Key → Bearer with the same externally managed value;
- value is never written to GitHub/Knowledge/Instructions.

If this credential is rotated, GPT Action authentication must also be updated. Follow the durable-state migration implications before rotating because existing journal authentication may depend on it.

## 4. TLS

`SSL_TBANK_VERIFY=True`

Do not disable broker TLS verification. Upstash/QStash connections use HTTPS and fail closed on invalid endpoint/transport state.

## 5. Sandbox switches

Relevant names:

- `SANDBOX_TRADING_ENABLED`;
- `SANDBOX_CONFIRMATION_TTL_SECONDS`;
- `TINVEST_SANDBOX_TOKEN`.

Rollback: set `SANDBOX_TRADING_ENABLED=false`, redeploy/restart, then refresh OpenAPI if the public Action surface changed.

## 6. Real execution switches / durable state

Relevant names:

- `REAL_TRADING_ENABLED`;
- `REAL_TRADING_JOURNAL_BACKEND`;
- `UPSTASH_REDIS_REST_URL`;
- `UPSTASH_REDIS_REST_TOKEN`;
- `REAL_TRADING_MAX_ORDER_RUB`;
- `REAL_TRADING_MAX_DAILY_RUB`;
- `REAL_TRADING_CONFIRMATION_TTL_SECONDS`;
- `REAL_TRADING_MARKET_MAX_AGE_SECONDS`;
- `TINVEST_TRADING_TOKEN`.

Selected production durable backend remains Upstash over HTTPS. Process memory and ordinary Render Free ephemeral filesystem are not production real-execution journals.

Master real-money kill switch:

`REAL_TRADING_ENABLED=false`

This disables the Real mutation surface; it never authorizes a trade when true. Every real order still requires the reviewed proposal/owner-confirmation/idempotency/reconciliation lifecycle.

## 7. Watchtower / QStash names

When Watchtower is intentionally enabled, the reviewed WP13 runtime uses:

- `WATCHTOWER_ENABLED`;
- `WATCHTOWER_PUBLIC_BASE_URL` or the existing external Render URL;
- `WATCHTOWER_QSTASH_SCHEDULE_ID`;
- `WATCHTOWER_JOURNAL_SECRET`;
- `WATCHTOWER_CRON`;
- `QSTASH_TOKEN`;
- `QSTASH_CURRENT_SIGNING_KEY`;
- `QSTASH_NEXT_SIGNING_KEY`;
- shared Upstash REST endpoint/credential names above.

Operational authority/source: `docs/operations/V9_WATCHTOWER_RUNBOOK.md`.

The three Watchtower routes remain internal/hidden from GPT OpenAPI. QStash delivery signatures protect them; these scheduler credentials are never GPT Action credentials.

Watchtower rollback:

`WATCHTOWER_ENABLED=false`

It does not require changing broker execution secrets and never authorizes real trading.

## 8. Durable namespaces / role isolation

The project may reuse one reviewed Upstash database/transport while keeping separate logical namespaces and HMAC roles for real execution, Watchtower and decision/evaluation state.

Do not assume one HMAC secret can safely substitute for another package-specific secret. Missing/wrong integrity material fails closed.

WP14 decision journal/replay code stores hashes/safe audit state, not reusable GPT secrets or private broker payloads.

## 9. Correct topology

```text
EXISTING Omni-CIO GPT
      │ Bearer Gateway authentication only
      ▼
Omni-CIO Gateway / Render
      ├─ read-only broker credential ─► Production read-only
      ├─ Sandbox credential ─────────► Sandbox / virtual only
      ├─ real execution credential ──► Confirmed real BUY/SELL contour
      ├─ HTTPS ──────────────────────► Upstash durable state
      └─ signed hidden callbacks ◄───► QStash Watchtower schedule
```

The GPT receives none of the broker/storage/scheduler credentials.

## 10. Rotation principles

- Read-only credential: rotate only its external value, then read-only smoke.
- Sandbox credential: disable Sandbox first, rotate externally, redeploy, virtual smoke, re-enable deliberately.
- Real execution credential: set `REAL_TRADING_ENABLED=false`, rotate only the real credential, redeploy, verify status/account binding before deliberate re-enable.
- Upstash credential: disable affected write/scheduler contours, preserve database/state, rotate externally, verify integrity before re-enable.
- QStash token/signing keys: keep Watchtower disabled while rotating, verify signed fake delivery + schedule reconciliation, then re-enable deliberately.
- Gateway bearer credential: coordinate Gateway and GPT Action authentication and existing durable-state migration requirements; never rotate casually during unresolved real execution state.

## 11. Never store as configuration artifacts

Do not commit or upload secret values, Authorization headers, full broker account identifiers, private positions/operations/reports, private keys/certificates or external secret exports.

Permanent GPT Knowledge is reusable reference content only. Current account facts are retrieved through authenticated Actions.

## 12. WP15 recovery boundary

WP15 changes the **existing GPT configuration**, not server secret values. The owner applies only the Gateway Bearer authentication in the GPT Editor; all other secrets remain external.

Repository merge does not modify Render/Upstash/QStash/GPT Editor automatically. Full upgrade/Preview/rollback steps: `gpt/MY_GPT_SETUP_RUNBOOK.md`.
