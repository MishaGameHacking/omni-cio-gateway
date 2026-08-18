# Omni-CIO V10 — WP22A Phase 2 Product Auth / Tenant Security Plan

Status: **CURRENT IMPLEMENTATION PLAN / PHASE 2 ONLY / PUBLIC ACTIVATION DISABLED**  
Owning package: **WP22A — External Web Access / Product Authentication Security Gate**

## 1. WP identity

- Block: E — Omni-CIO Web Platform.
- WP: WP22A Phase 2.
- Title: Product-auth / tenant-security correction.
- Authorized by current program status: YES, after accepted Phase 1 evidence on exact main `51dbe41ad1e63ddb4c0b101f573b70254a5255b8`.
- Prior Exit Gate: PR #333 merged to that exact main plus OWNER-supplied Regression Shield #1505 SUCCESS evidence with both required post-merge jobs GREEN.

## 2. Accepted baseline

- Accepted main: `51dbe41ad1e63ddb4c0b101f573b70254a5255b8`.
- Protected V9 remains `app:app` with rollback preserved.
- `trading_methods=false`; `REAL_TRADING_ENABLED=false`; `PUBLIC_MULTI_USER_ENABLED=false`.
- Reuse accepted `apps/web`, `apps/api`, `omni_cio.web.session_v1`, Web broker provisioning/repository contracts, PostgreSQL migration machinery and existing request-security controls.

Authority: V10 Master Plan, active identity/multi-tenant and public-hosted amendments, `V10_WP22A_EXECUTION_CONTRACT.md`, security boundaries and threat model.

## 3. Purpose

Create the source-controlled product identity and tenant-security boundary required for a public multi-user Omni-CIO Web product without activating public registration or requiring real Telegram/VK/provider secrets.

The product path is:

`verified Telegram/VK identity -> internal Omni-CIO account -> tenant -> revocable server-side session -> tenant-scoped product APIs`

Cloudflare/GitHub/cloud-provider/Windows/CI identities are excluded from product-session authority.

## 4. Inputs and prerequisites

- accepted Phase-1 managed-cloud decision;
- existing Telegram/VK provider abstraction;
- existing hashed server-side session registry;
- existing tenant-scoped broker connection repository;
- PostgreSQL 18 migration contract;
- current official Telegram OIDC and VK ID OAuth 2.1 protocol review.

### 4.1 Pre-CI readiness

Before full exact-head CI:

- migration discovery/checksum and SQL contract tests;
- focused identity/session/cross-tenant tests;
- Python compile/type/static checks for changed modules;
- Web frontend type/lint/build if login UI changes;
- secret/private-data guard;
- full diff and rollback review;
- preserved V9 and broker-authority invariants.

### 4.2 OWNER-only prerequisite

None for Phase-2 source acceptance. Real Telegram/VK application credentials, provider accounts, DNS and public deployment are later-phase prerequisites and are not to be requested during this source increment.

## 5. Existing implementation to reuse

- `omni_cio/web/session_v1.py`: opaque server sessions, hashed token storage, idle/absolute expiry, revoke/revoke-all.
- `omni_cio/web/identity_v1.py`: exact provider registry for Telegram and VK ID.
- `omni_cio/web/api_v1.py`: session-derived tenant scope for private APIs; client tenant selector is not authority.
- `omni_cio/web/persistence_v1.py`: durable sessions and tenant-scoped broker connections.
- `omni_cio/persistence/migrations/0003_web_identity_connections.sql`: strong `(user_id, tenant_id)` and `(connection_id, tenant_id)` foreign-key baselines.
- `omni_cio/web/external_access_v1.py`: reusable Host/Origin/CSRF/rate-limit/security-header logic; its historical Cloudflare OWNER -> product-session coupling is not reusable.

## 6. Allowed changes

- `omni_cio/web/**` product-auth/account/session persistence boundary;
- additive PostgreSQL migration(s) needed for product-account identity and removal of conflicting OWNER-only Web constraints;
- focused tests and Phase-2 audit/guard scripts;
- login-shell text/behavior needed to remove OWNER/provider identity as a product login path;
- WP22A/security/status documentation directly coupled to this phase.

## 7. Explicit non-goals

- no WP23 Telegram Bot Foundation;
- no AI/Cortex work;
- no Cloud.ru/provider apply;
- no real public registration;
- no real Telegram/VK client secret in source/CI;
- no T-Invest public connector activation;
- no broker-write/Real authority;
- no second Web App/Core/database/identity stack.

## 8. Interfaces/contracts

### 8.1 Verified external identity

Only a cryptographically/protocol-verified provider subject reaches the internal identity binder. Display name, username, phone, email and avatar are not account identity or merge keys.

Persisted provider binding is a keyed digest derived with a runtime-only identity binding key; raw provider subject is not persisted by the binding repository.

### 8.2 Internal account scope

Internal result is exactly `(user_id, tenant_id)`. Client-provided `user_id`/`tenant_id` never overrides it.

### 8.3 Product session

Successful product authentication creates/rotates an opaque server-side session. Existing session IDs are revoked during auth rotation. Logout/revoke-all/idle/absolute expiry stay fail-closed.

## 9. Data/persistence effects

Migration required: YES.

Forward migration:

- generalize only the `tenants`, `users`, Web session and broker-connection persistence constraints needed for product accounts;
- preserve OWNER rows and all existing data;
- add protected external-identity bindings with uniqueness preventing one external identity from belonging to multiple accounts;
- retain tenant-scoped foreign keys and compound scope constraints.

Rollback: schema migration is forward-only under the existing checksum discipline. Operational rollback is to prior accepted application release with `PUBLIC_MULTI_USER_ENABLED=false`; no real product account is admitted before later public activation, so Phase-2 source acceptance creates no irreversible tenant-private production data.

## 10. Security/authority effects

This phase changes product identity semantics but does not increase broker, OS, GitHub, provider, AI or Real authority.

Threats explicitly covered: stolen/fixed sessions, cross-tenant IDOR, provider identity becoming product identity, raw external-subject leakage, account-link collision, client tenant-selector confusion.

## 11. Normal-path acceptance tests

- Telegram and VK verified identity abstractions derive protected binding keys.
- Known external binding resolves exactly one internal account/tenant.
- Product authentication mints a server-side session only from resolved internal account scope.
- Two tenants can hold independent sessions and broker connections.
- revoke-all for USER A does not revoke USER B.

## 12. Negative/failure tests

- unknown provider/identity denied;
- registration disabled -> unknown identity denied;
- wrong binding key cannot resolve another account;
- same external identity cannot bind to two accounts;
- display/profile fields cannot merge accounts;
- Cloudflare/provider engineering identity cannot mint a product session;
- forged client tenant/user selector cannot cross scope;
- cross-tenant broker connection ID cannot read/replace/revoke another tenant;
- expired/revoked session denied;
- no raw subject/session/broker secret appears in responses/log fixtures.

## 13. Observability

Expose only provider kind, authentication availability/state, session status and sanitized failure classes. Do not log raw provider subjects, auth codes/tokens, session tokens, broker secrets or private tenant payloads.

Identity/security uncertainty fails closed while deterministic Core and already-authorized non-authenticated health surfaces remain independently diagnosable.

## 14. CI routing

Focused preflight:

- Phase-2 identity/session/unit tests;
- migration-series tests plus PostgreSQL rehearsal where available;
- accepted Web/API security tests;
- repository/public-product/security guards;
- frontend type/lint/build if touched.

Full exact-head CI starts only after focused preflight is clean. Project GREEN means actual `success` for every applicable check; red/queued/pending/cancelled/skipped is not merge evidence.

## 15. Rollback/recovery

- no production activation occurs in Phase 2;
- prior accepted main remains rollback source;
- product registration flag remains off;
- migration is additive/generalizing and must preserve existing OWNER data/FKs;
- protected V9 rollback remains untouched.

## 16. Exit Gate

PASS only when:

- provider/engineering identity cannot mint/select product tenant;
- verified external identity maps through internal account/tenant scope;
- session scope is server-side only and rotation/revoke/expiry tests pass;
- necessary OWNER-only Web persistence constraints are removed without weakening tenant FKs;
- deterministic cross-tenant negatives pass;
- no real secrets/private payloads are present;
- exact-head applicable CI is all SUCCESS;
- zero unresolved blocking review threads;
- full diff/security/rollback review is clean;
- squash merge and post-merge Regression Shield are GREEN.

## 17. Required acceptance evidence

- exact implementation PR head;
- focused unit/security/migration test results;
- exact-head CI run IDs and conclusions;
- zero blocking review threads;
- squash merge SHA;
- exact-main post-merge Regression Shield.

No OWNER product walkthrough is required for this source-only phase.

## 18. Documentation/status updates

Update the WP22A execution contract/current status only when Phase-2 acceptance evidence exists. Do not mark Phase 2 accepted from code existence alone.

Unexpected material RED after preflight-ready state requires root-cause/blast-radius analysis and a reusable failure-ledger entry when applicable.

## 19. Next phase unlock

**WP22A Phase 3 — Hosted runtime/data/secret/recovery implementation** remains locked until Phase 2 is squash-merged and its required exact-main Regression Shield is GREEN.

## 20. Scope-discovery rule

Out-of-scope work is classified as current-phase blocker, future WP22A phase, future WP or OWNER/amendment decision. It is not silently implemented.
