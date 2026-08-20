# Omni-CIO V10 — WP22A Phase 3 Hosted Readiness Contract

Status: **SOURCE-ONLY / PUBLIC INGRESS OFF / PROVIDER APPLY OFF**  
Owning package: **WP22A Phase 3 — Hosted runtime/data/secret/recovery implementation**

## Purpose

This contract closes the remaining source-only readiness boundary that must exist
before any protected provider bootstrap or public-preview apply can be reviewed.
It does not create a URL, provider resource, database, secret, certificate or
recurring charge.

The machine-readable authority is:

`infrastructure/cloudru/wp22a/hosted-readiness-contract.json`

The reusable fail-closed validator and state reducer are:

`omni_cio/observability/hosted_readiness_v1.py`

## Edge trust

Later hosted activation must provide one canonical HTTPS origin and must not
trust arbitrary client-supplied forwarding headers. The accepted source boundary
requires:

- exactly one reviewed proxy hop before the application;
- a provider-injected canonical host;
- a Host allowlist;
- forwarded protocol equal to `https` only after the trusted proxy boundary;
- no direct public origin access;
- no production dependency on OWNER home Internet, power or Lenovo;
- HSTS and strict response hardening;
- Origin/Referer plus CSRF verification for unsafe requests;
- deny-by-default CORS;
- no unsafe private-response caching;
- Secure and HttpOnly session cookies;
- no session material in browser Web Storage.

Phase 3 records and validates these invariants while keeping public ingress off.
Provider-specific header names, canonical host values and certificate material
belong to the later protected apply boundary.

## Health and incident domains

A single undifferentiated `healthy=false` signal is insufficient. Sanitized
hosted evidence must classify these exact domains:

1. `application`;
2. `cloud_provider`;
3. `database`;
4. `product_auth`;
5. `broker_external`;
6. `recovery`.

The platform can remain READY when `broker_external` is `NOT_APPLICABLE`, because
public Web/account availability and broker activation are separate gates.
Any required core domain (`application`, `cloud_provider`, `database`,
`product_auth` or `recovery`) in OFFLINE state makes the hosted runtime OFFLINE.
A DEGRADED core domain makes the runtime DEGRADED. The optional broker domain can
reduce READY to DEGRADED but cannot by itself make the public account platform
OFFLINE.

Migration-state, runtime-ACL or tenant-boundary mismatch always reduces to
OFFLINE regardless of the dependency labels.

## Evidence safety and provenance

Evidence is accepted only when it:

- uses the exact evidence schema and dependency allowlist;
- contains a canonical server-generated UUIDv4 correlation identifier;
- matches the exact accepted release SHA supplied by the verifier;
- is fresh, UTC and not materially from the future;
- contains only bounded reason codes, not arbitrary diagnostic text;
- carries no raw tenant ID, user ID, broker account ID, credential value or
  private payload;
- confirms that public ingress is still off during this Phase-3 source gate.

The reducer is intended for later readiness endpoints and sanitized deployment
acceptance evidence. It is not a logging sink for exceptions or provider
responses.

## Capacity and cost

The current authority remains zero recurring owner spend. Source acceptance
therefore requires:

- no automatic paid overage;
- explicit OWNER budget approval before any paid apply;
- scaling only from measured evidence;
- bounded request rates, database pools and backup sizes;
- no private tenant data or broker credential in a synthetic free preview.

Free-tier availability never overrides security, recovery, legal or data-boundary
requirements.

## Release and rollback

A later provider mutation may run only from an exact accepted `main` release
through a separately reviewed privileged workflow. Health must be checked before
traffic is accepted, and rollback to the last accepted release must remain
available.

This Phase-3 contract records `provider_mutation_performed=false` and does not
consume provider secrets in pull-request workflows.

## Locked authority

The following remain unchanged:

- `provider_apply_authorized=false`;
- public ingress/DNS/HTTPS activation is off;
- authorized recurring infrastructure cost is `0 RUB/month`;
- `PUBLIC_MULTI_USER_ENABLED=false`;
- protected V9 `app:app` remains available;
- `trading_methods=false`;
- `REAL_TRADING_ENABLED=false`;
- WP23 remains locked.
