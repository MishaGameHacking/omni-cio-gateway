# V10 WP22 — System/Admin UI Contract

Status: **implementation contract**

## Product-role clarification

The historical Work Package title `System/Admin UI` names a diagnostics/operations product surface; it does **not** create a special PROJECT-OWNER Omni-CIO account or an application administrator RBAC role.

The PROJECT OWNER uses this page as an ordinary authenticated Omni-CIO USER through the same `OmniCIOUserAccount -> Tenant -> Session` product path as supported users. GitHub, Cloudflare, Windows Administrator or other engineering authority does not grant a product session or cross-tenant access.

This interpretation is governed by `docs/master-plan/OMNI_CIO_V10_PRODUCT_USER_AND_ENGINEERING_AUTHORITY_BOUNDARY_AMENDMENT.md` after that amendment is accepted on protected `main`.

## Canonical boundary

`/system` is the single authenticated USER-facing local/private **System / Diagnostics** surface for ordinary V10 diagnostics in that USER's deployment/tenant context. It projects accepted state; it does not own service lifecycle, persistence, broker authority, backups, Telegram, AI or execution.

The browser never obtains a broker credential, recovery key, private backup payload, raw PostgreSQL content blob or full account identifier in order to render system state.

`/system` is not a cross-tenant operator console. Any future support/operator capability that can affect other users requires a separately reviewed least-privilege engineering/product-support authority and is not inferred from PROJECT OWNER infrastructure ownership.

## Required sections

The page renders, when available and relevant to the authenticated USER/private data plane:

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

Every private value remains scoped to the authenticated USER/tenant. PROJECT OWNER engineering authority is not a tenant-isolation bypass.

## Safety controls

WP22 displays kill-switch/safety state only. There is no enable/disable control and no POST/PUT/PATCH/DELETE system route.

The required safety boundary remains:

- `trading_methods=false`;
- `REAL_TRADING_ENABLED=false`;
- no Web broker-write authority;
- no public ingress before WP22A.

A contradictory observable runtime safety state is a blocker, not something the UI masks.

The accepted `/settings` surface continues to own authenticated T-Invest READ provisioning and session revocation. WP22 does not duplicate those flows.

## Engineering/operations separation

GitHub, CI, Cloudflare/provider mutation, Windows Administrator actions, runtime-secret bootstrap, deployment and recovery belong to the engineering/operations plane unless a later owning Work Package explicitly exposes a safe typed product operation.

The System / Diagnostics page must not become an unrestricted administrator shell, provider dashboard proxy, secret export path or hidden PROJECT-OWNER-only cabinet.

## Responsive/browser evidence

Synthetic Playwright evidence must show the complete operating surface and a separate diagnostics-unavailable case. The page must remain responsive under the accepted Web viewport contract and expose no mutation control that can enable Real trading, broker write, public ingress, Telegram or AI.

When the PROJECT OWNER performs product acceptance, that acceptance must exercise the same USER-facing diagnostics code path intended for supported users; PROJECT-OWNER infrastructure privileges are not part of the product acceptance path.
