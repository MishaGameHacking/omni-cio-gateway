# Omni-CIO V10 — Amendment 21: Timeweb Full Production Delivery in PR #584

Status: **OWNER-APPROVED BRANCH-LOCAL IMPLEMENTATION AUTHORITY / ACCEPTANCE PENDING**

Decision date: 2026-09-24  
Owning System Update: `TIMEWEB-PLATFORM-CONSOLIDATION-INTEGRATED`  
Owning issue: #580  
Owning PR: #584  
Branch: `system/timeweb-platform-consolidation-tw-b`

## 1. OWNER decision

The OWNER explicitly authorized the remaining production-delivery implementation to be
developed in the existing PR #584 rather than creating competing implementation branches.

PR #584 may therefore contain the complete repository-side implementation for these six
ordered internal milestones:

1. source/runtime and V9-to-V10 convergence;
2. exact-SHA Timeweb App Platform candidate/release control;
3. Timeweb PostgreSQL 18 production cutover/recovery control;
4. canonical `omnicio.ru` DNS/TLS/public-ingress acceptance;
5. Telegram-only production login readiness and activation control;
6. exact-main post-merge production acceptance and rollback proof.

This amendment widens **branch-local implementation scope** only. It does not fabricate
external evidence and it does not make an irreversible external action safe merely
because the source code for that action exists in the branch.

## 2. One branch, multiple hard gates

One integrated branch and one final PR remain the default delivery unit. The following
boundaries stay independently fail-closed even while their automation, contracts,
verifiers and runbooks live in the same branch:

- paid provider resource creation or capacity expansion;
- immutable App Platform network selection;
- production database migration/cutover and recovery acceptance;
- production DNS/custom-domain/TLS mutation;
- production secret provisioning;
- Telegram BotFather/Allowed-URL registration;
- legal/privacy/regulatory OWNER actions;
- public-user activation;
- destructive legacy-provider cleanup;
- PR merge and post-merge production promotion.

A later milestone may be implemented before an earlier external action is physically
performed, but its mutation path must refuse to execute until the earlier gate has
verifiable accepted evidence.

## 3. Exact-SHA release law

Production identity is:

`accepted GitHub main SHA -> exact Timeweb deploy -> runtime /livez SHA -> runtime /healthz database READY -> accepted production`.

Autodeploy is not production authority. Production deployment must target one explicit
40-character Git commit SHA. A Timeweb deploy whose `commit_sha`, runtime
`OMNI_V10_RELEASE_SHA`, and accepted GitHub main SHA are not identical is
`OUT_OF_SYNC / DEPLOYMENT_BLOCKED`.

The last-known-good production deployment remains the rollback target until the new
exact-main candidate passes all owning acceptance gates.

## 4. Timeweb App Platform boundary

The canonical deployment source is the repository-root `Dockerfile`. The application
listens on port 8080, exposes process-only `/livez`, and keeps database-aware
`/healthz` separate.

App creation is a material provider/payment/network boundary. Source automation may
discover, validate, deploy and verify an explicitly identified Timeweb application.
Creating a billable application or choosing its immutable private-network placement
requires the owning explicit confirmation/evidence and must never be guessed by CI.

App Platform variables/secrets remain provider-side runtime inputs; real secret values
must not enter source, PR text, CI artifacts or logs.

The production App and production PostgreSQL must use one explicitly selected Timeweb
private network. The portable PostgreSQL DSN retains the Timeweb technical hostname for
TLS `verify-full` identity; the runtime receives the private PostgreSQL address and
exact private-network CIDR as separate provider-side bindings. The application must prove
that private route through HTTPS `/healthz` with `database=READY` and
`synthetic_preview=false` before the candidate is accepted. A successful process-only
`/livez` check is not database reachability evidence.

## 5. PostgreSQL 18 production cutover

Timeweb PostgreSQL 18 is the canonical relational target. Production cutover requires:

- canonical migrations and deterministic schema identity;
- least-privilege runtime role;
- PostgreSQL RLS and FORCE RLS;
- same-tenant positive and cross-tenant negative tests;
- backup/restore and bounded recovery rehearsal;
- old/new data reconciliation where migration applies;
- exact release/DB evidence before DSN promotion.

The runtime role must not be widened merely to make a readiness probe pass.

## 6. Canonical public ingress

The canonical public origin is exactly `https://omnicio.ru`.

Production ingress acceptance requires:

- Timeweb application custom-domain attachment;
- valid TLS for `omnicio.ru`;
- no unavoidable Cloudflare/Render/Neon/Cloud.ru hop;
- canonical Host/Origin/cookie/CSRF behavior;
- process and database readiness evidence;
- representative Russian ordinary-Internet/no-VPN evidence where that evidence cannot
  be proven from repository source alone;
- a tested rollback/last-known-good path before destructive DNS cleanup.

No undocumented provider endpoint is invented for domain attachment. If the current
official Timeweb API does not expose the required mutation, the runbook must stop at a
bounded OWNER panel action and resume with sanitized evidence.

## 7. Telegram-only public activation

The only ordinary human login provider is Telegram Login OIDC.

Canonical registration values:

- origin: `https://omnicio.ru`;
- callback: `https://omnicio.ru/api/v10/web/auth/telegram/callback`.

Public activation requires the production Timeweb release, production PostgreSQL,
canonical DNS/TLS, runtime secret custody, privacy/legal/capacity/monitoring gates and
real end-to-end login evidence.

`PUBLIC_MULTI_USER_ENABLED` and `OMNI_V10_TELEGRAM_LOGIN_ENABLED` must transition
together. A partial transition is invalid. VK ID remains absent from deployed product
composition.

## 8. Product/session isolation proof

Real activation acceptance must prove:

`Telegram USER -> verified identity -> OmniCIOUserAccount -> Tenant -> server-side Session`.

It must also prove logout/revoke/re-login and a USER-A versus USER-B cross-tenant
negative. Browser payloads, URL parameters and provider identities never select Tenant
authority directly.

## 9. Protected boundaries

This amendment does not authorize:

- broker write;
- order submission;
- transfer or withdrawal;
- margin/leverage/uncovered short;
- `REAL_TRADING_ENABLED=true`;
- `trading_methods=true`;
- WEB-VISUAL;
- WP23+;
- a merge of PR #584 without the required exact-head landing confirmation.

Production/public activation is not accepted merely because its repository-side
automation is implemented. External state must be observed and recorded without
secret disclosure.

## 10. Completion condition

This branch-local amendment is complete only when PR #584 contains the complete
fail-closed implementation/evidence machinery for all six milestones, every applicable
exact-head check is terminal `success`, the full diff/authority/secret review is clean,
and the PR reaches the normal explicit landing-decision gate.

Physical provider actions that can occur only after accepted `main` remain post-merge
execution steps of the same System Update, not reasons to create a competing source
branch.
