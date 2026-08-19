# WP22A Phase 2 — Product Authentication / Tenant Security Execution Plan

Status: **IMPLEMENTATION IN PROGRESS — PUBLIC REGISTRATION / PROVIDER APPLY / WP23 LOCKED**  
Accepted base `main`: `67223469e0031b94d0ada7c5c0d92e3e4efb8d22`  
Implementation branch: `v10/wp22a-phase2-product-auth-tenancy`

## Purpose

Implement the accepted WP22A Phase-2 security correction without jumping to hosted deployment or real provider credentials:

`verified Telegram/VK identity -> OmniCIOUserAccount -> Tenant -> opaque server-side session -> tenant-scoped broker state`

The PROJECT OWNER remains ordinary USER in the product. GitHub, cloud-provider, Windows, CI and historical edge identities are engineering/staging authority only and are not USER tenant authority.

## Root cause being corrected

WP12–WP22 were intentionally implemented on an OWNER-only migration baseline. The later accepted public/multi-user amendments changed the final product identity model, so the following accepted implementation assumptions are now too narrow for the current WP22A phase:

- `tenants` / `users` permit only historical OWNER identities;
- `web_sessions` permit only the OWNER account;
- broker persistence rejects non-OWNER tenants;
- the public identity abstraction exists but durable external-identity bindings do not;
- the existing application shell and session presentation still contain historical OWNER product-role assumptions.

The correction must not remove unrelated OWNER-only guards before their owning hosted/private-state phase.

## In-scope change surface

Phase 2 owns only:

1. internal product account + tenant creation/binding from an already verified Telegram/VK identity;
2. protected provider-subject lookup binding using keyed HMAC-SHA256 (no raw subject and no enumerable unkeyed subject hash in PostgreSQL);
3. one external identity -> at most one USER account;
4. one USER account -> at most one binding per provider, while Telegram + VK may both bind to that account;
5. public registration **disabled by default**;
6. server-side session issuance/rotation/revocation from verified identity only;
7. `web_sessions` generalization while retaining the `(user_id, tenant_id)` database FK;
8. broker connection/account persistence generalization to arbitrary valid tenant scope;
9. application-side tenant binding with transaction-local PostgreSQL tenant context;
10. PostgreSQL RLS on generalized broker relations and a restricted-role negative rehearsal;
11. removal of historical remote OWNER login and OWNER/Personal session labels from the normal Web product boundary;
12. deterministic unit/static/PostgreSQL evidence that client `user_id` / `tenant_id` selectors do not override server-side session scope and that cross-tenant/IDOR access fails closed.

## Deliberately out of scope / locked

Phase 2 does **not** authorize:

- real Telegram client/secret configuration;
- real VK client/secret configuration;
- public registration activation;
- final public hostname, DNS, TLS or cloud deployment;
- provider/cloud resource mutation;
- centralized migration of portfolio/research/decision/job private state;
- T-Invest public connector activation;
- broker write authority;
- WP23 Telegram Bot work.

Historical OWNER-only constraints on portfolio/research/decision/job/content state remain in force during Phase 2. This is deliberate fail-closed staging, not incomplete evidence disguised as PASS.

### Legacy canonical OWNER graph compatibility

`CanonicalDomainCatalogV1` / `load_catalog()` remain the accepted OWNER-only WP12/WP13 canonical private-state graph during Phase 2. They are **not** silently converted into a public multi-tenant portfolio model in this package. Public registration and hosted private-state activation remain off, so accepted runtime does not create real product-user rows that are then consumed by that legacy graph.

Phase 2 instead establishes the separate account/session/broker boundary required before Phase 3. Before hosted real-user activation, Phase 3 must either tenant-scope/replace the legacy canonical reader where its private-state tables are generalized or prove an equivalent tenant-preserving compatibility boundary. This prevents Phase 2 from pulling portfolio/research/decision migration work forward while making the future dependency explicit.

## PostgreSQL RLS staging decision

Phase 2 enables RLS policies on:

- `broker_accounts`;
- `broker_connections`;
- `broker_connection_accounts`.

The policies use transaction-local `omni_cio.tenant_id` populated only from authenticated server session scope by repository code. A restricted `NOSUPERUSER NOBYPASSRLS` role rehearsal proves default-deny, exact-tenant SELECT visibility and cross-tenant write rejection.

`FORCE ROW LEVEL SECURITY` is intentionally **not** enabled in Phase 2 because the accepted legacy OWNER persistence/recovery role still owns these tables and must remain regression-compatible. Phase 3 must create/use the final least-privilege hosted runtime database role (not table owner, not `BYPASSRLS`) before any public activation. Public multi-user activation remains fail-closed until that runtime-role evidence exists.

## Blast radius

Potential regression areas:

- WP13 migration replay / PostgreSQL restore because migration series gains `0004`;
- WP15/WP17 broker connection creation/list/replace/revoke;
- server-side session persistence and session-view presentation;
- Application Shell unauthenticated login surface;
- legacy OWNER acceptance paths;
- accepted OWNER-only `CanonicalDomainCatalogV1` reader semantics if future hosted private-state work is started early;
- backup/state-digest behavior if RLS is applied too broadly;
- secret scanning if synthetic binding keys resemble credentials.

Mitigations:

- migration generalizes only identity/session/broker relations;
- unrelated private tables and the accepted OWNER canonical graph retain their existing scope in Phase 2;
- existing composite tenant FKs/uniqueness are retained;
- broker repository always sets tenant context inside the same transaction as private SQL;
- Web API tests prove non-OWNER product sessions ignore client-supplied user/tenant selectors;
- HMAC key is dependency-injected and required; Phase-2 tests use an obvious synthetic key only;
- real provider/broker secrets are forbidden from tests/evidence;
- existing WP13 recovery rehearsal remains an inherited gate.

## Pre-CI readiness

Before final exact-head CI:

- review migration constraints against `0001`/`0003` exact names;
- static/syntax check all changed Python/PowerShell/YAML;
- run focused product-identity and product-session API tests;
- run isolated PostgreSQL 18 Phase-2 tenant-security rehearsal;
- run WP13 migration/recovery regression rehearsal;
- inspect full branch diff for accidental widening of unrelated OWNER guards;
- verify `app:app`, `trading_methods=false`, `REAL_TRADING_ENABLED=false` unchanged.

## Required Phase-2 acceptance evidence

Phase 2 is not complete unless all applicable exact-head checks conclude `success` and the evidence proves:

- unknown external identity cannot register while registration is disabled;
- keyed external-identity binding is stable and not raw/unkeyed provider identity storage;
- same identity resolves to one stable internal USER/tenant;
- second provider can link only from authenticated account scope;
- identity already bound elsewhere cannot be stolen/merged;
- login rotates/revokes the prior server session;
- plaintext session token is not persisted;
- product session presentation exposes no historical OWNER/Personal authority label or raw user/tenant IDs;
- private API authority comes from the resolved server session and ignores client user/tenant selectors;
- broker CRUD uses server tenant scope and cross-tenant object IDs fail closed;
- PostgreSQL RLS restricted-role probe sees only its tenant and rejects cross-tenant INSERT;
- unrelated private tables remain OWNER-locked;
- no real secrets/private portfolio payload used;
- inherited WP13/WP17/WP22A regression gates remain GREEN;
- zero unresolved blocking review threads;
- squash merge exact reviewed head;
- post-merge Regression Shield GREEN on exact new `main`.

## Rollback

Before merge: abandon/close this branch/PR; accepted `main` remains unchanged.

After merge but before Phase-3 activation: protected V9 rollback remains untouched; migration `0004` is forward-only and therefore any rollback of V10 durable state must follow the existing backup/restore recovery procedure rather than mutating migration history.

## Safety invariants

Unchanged:

- `app:app`;
- `trading_methods=false`;
- `REAL_TRADING_ENABLED=false`;
- no broker write authority;
- no transfer/withdrawal authority;
- no real secrets/private payloads in GitHub/CI/artifacts;
- protected V9 rollback;
- WP23+ locked until WP22A Exit Gate.
