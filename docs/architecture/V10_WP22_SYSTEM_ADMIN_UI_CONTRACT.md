# V10 WP22 — System/Admin UI Contract

Status: **implementation contract**

## Canonical boundary

`/system` is the single OWNER-facing local/private operating surface for ordinary V10 diagnostics. It projects accepted state; it does not own service lifecycle, persistence, broker authority, backups, Telegram, AI or execution.

The browser never obtains a broker credential, recovery key, private backup payload, raw PostgreSQL content blob or full account identifier in order to render system state.

## Required sections

The page renders, when available:

- overall operational state and freshness;
- Web build version/Git SHA plus bounded runtime release/deploy identity;
- service health for local Web, PostgreSQL, T-Invest READ, Watchtower, Telegram and AI/Cortex;
- current/expected PostgreSQL migration state;
- latest successful durable backup observation and accepted RPO/RTO;
- free disk and bounded temperature observation;
- read-only safety/kill-switch state;
- bounded recent durable jobs;
- bounded recent sanitized errors.

## Failure vocabulary

The page preserves first-class unavailable/degraded states:

- `AVAILABLE` — current observation was obtained;
- `NOT_CONFIGURED` — a current allowed capability has no configured state;
- `NOT_AVAILABLE` — current observation cannot be proven;
- `LOCKED_FUTURE_WP` — the capability belongs to a later Master Plan package.

Missing telemetry is displayed as `UNAVAILABLE`/`NOT_AVAILABLE`; it is never replaced by an invented value. Telegram remains future-locked until WP23+, and AI/Cortex remains future-locked until WP27+.

A diagnostics API failure must leave the authenticated shell usable while making the uncertainty visible. The browser may retain accepted build identity, but it must not present the missing system snapshot as READY.

## Security and privacy

The system DTO/UI excludes:

- broker/Telegram/API tokens;
- authorization headers or secret references;
- full broker account identifiers;
- private portfolio rows or content blobs;
- backup mount points or raw backup contents;
- BitLocker recovery material;
- raw exception messages/stack traces;
- worker identity strings.

Recent errors show only the accepted WP14 sanitized `error_class` vocabulary and bounded job metadata.

## Safety controls

WP22 displays kill-switch/safety state only. There is no enable/disable control and no POST/PUT/PATCH/DELETE system route.

The required safety boundary remains:

- `trading_methods=false`;
- `REAL_TRADING_ENABLED=false`;
- no Web broker-write authority;
- no public ingress before WP22A.

A contradictory observable runtime safety state is a blocker, not something the UI masks.

The accepted `/settings` surface continues to own authenticated T-Invest READ provisioning and session revocation. WP22 does not duplicate those flows.

## Responsive/browser evidence

Synthetic Playwright evidence must show the complete operating surface and a separate diagnostics-unavailable case. The page must remain responsive under the accepted Web viewport contract and expose no mutation control that can enable Real trading, broker write, public ingress, Telegram or AI.
