# Omni-CIO V10 — Russian Public Registration & Reachable Ingress Authority / Amendment 18

**Status:** OWNER-APPROVED / EFFECTIVE ONLY WHEN ACCEPTED ON PROTECTED `main`  
**OWNER decision:** 2026-09-21  
**Scope:** Russia-only public-user launch, Russia-reachable ingress, Timeweb production PostgreSQL end-state, and Neon production-authority retirement sequencing  
**Product progress effect:** NONE by itself  
**Runtime mutation effect:** NONE by itself  
**Owning dashboard:** issue #580  
**Database migration dashboard:** issue #559  
**Telegram activation dashboard:** issue #549

## 1. Purpose

The supported initial public-user population is users in the Russian Federation. The final
public product remains one canonical Omni-CIO Web with one account/session/tenant model,
but it must be usable from ordinary Russian Internet access without requiring a VPN.

The accepted Cloudflare public-product implementation remains valid engineering and release
evidence. It is no longer sufficient, by itself, as the only Russian-user HTTP ingress
because Cloudflare's current support documentation records systematic Russian-ISP
throttling of Cloudflare-protected sites that Cloudflare cannot remediate from its side.

The OWNER therefore approves a bounded launch direction:

- GitHub remains the engineering/source/review/release-provenance authority;
- Timeweb Cloud Managed PostgreSQL 18 in Russia becomes the intended final production
  relational provider after the existing RU-PG-B -> C -> D migration gates succeed;
- Timeweb App Platform is the first Russia-facing application-ingress candidate;
- Cloudflare remains an accepted build/release/staging/fallback platform and historical
  public-product evidence, but public launch must not depend on a Cloudflare-only client
  path when that path is not reliably reachable by the supported Russian population;
- Neon remains continuity/rollback authority only until accepted RU-PG-D cutover and is
  retired from active production authority only through RU-PG-E.

This amendment does not itself deploy App Platform, mutate DNS, change a database DSN,
activate public users, delete Neon, or authorize broker write / Real money.

## 2. Provider set and authority

The intended V10 public-launch provider set is deliberately bounded:

1. **GitHub** — source, review, exact-SHA CI evidence and release provenance;
2. **Cloudflare** — accepted current build/release/staging/fallback application platform;
3. **Timeweb Cloud** — Russian PostgreSQL provider and candidate Russian public ingress/runtime.

Render and Cloud.ru do not return as active V10 deployment paths.

The provider set is a service topology, not three independent products. Omni-CIO must keep
one canonical user identity/account/session/tenant truth and one production relational
authority at any moment.

## 3. Russia-reachability evidence

Current external evidence from Cloudflare documents that Russian ISPs can throttle
Cloudflare-protected sites to approximately the first 16 KB per connection and that
Cloudflare cannot restore reliable access from its side. Therefore:

- successful Cloudflare production release is necessary evidence for the current accepted
  platform, but is not sufficient evidence of Russian-user reachability;
- a Russia-facing candidate must be tested from the supported population without VPN;
- the canonical launch path must not proxy Russian users through Cloudflare as an
  unavoidable upstream dependency;
- availability claims require real Russian-network evidence, not only CI or foreign probes.

No claim is made that every Russian ISP behaves identically. The launch gate is empirical:
the canonical product must be proven usable from representative supported Russian access.

## 4. One product / provider-neutral application core

A Russia-facing runtime must reuse the same Omni-CIO product rather than create a second
frontend, account system, session authority, tenant model or API truth.

Before a Timeweb public runtime can be accepted, current Cloudflare-specific ASGI startup
must be decomposed so that:

- the provider-neutral product application owns account/session/tenant/database behavior;
- Cloudflare keeps a thin trusted-edge adapter for its internal proxy contract;
- Timeweb gets a separate thin ingress adapter with no Cloudflare internal-header
  assumptions;
- both adapters are built from the same accepted repository source and exact source SHA;
- no browser may select a tenant, database authority or provider-specific internal role;
- no public Timeweb route may trust arbitrary client-supplied forwarded/internal headers.

A second user-facing Omni-CIO product or authentication bypass is forbidden.

## 5. Exact-SHA Timeweb App Platform candidate

Official Timeweb App Platform documentation supports GitHub repository integration,
Dockerfile deployment, selecting an explicit branch/commit, environment variables,
custom domains and managed Let's Encrypt TLS.

The first candidate must therefore use:

- the repository `MishaGameHacking/omni-cio-gateway`;
- a reviewed Dockerfile/runtime adapter dedicated to the provider-neutral public product;
- one exact accepted protected-`main` commit, never an unreviewed feature head;
- App Platform auto-deploy disabled for production so a later commit cannot bypass the
  Omni-CIO acceptance chain;
- provider deployment metadata recorded with the exact source SHA;
- a technical/candidate domain first; canonical `https://omnicio.ru` only after candidate
  acceptance and the owning DNS cutover;
- runtime secrets supplied only through approved provider secret/environment custody,
  never committed to GitHub.

An App Platform deployment must not be called accepted merely because the provider reports
a successful build.

## 6. Timeweb ingress security gate

Before a Timeweb runtime may receive real public-user traffic, exact evidence must prove:

1. HTTPS/TLS on the canonical hostname;
2. Host/origin/callback validation for `https://omnicio.ru`;
3. a documented and empirically verified reverse-proxy/client-IP contract;
4. forged `Forwarded`, `X-Forwarded-For`, Cloudflare internal headers and Omni-CIO
   internal edge headers cannot mint trusted client identity;
5. request/body/header limits and bounded timeout behavior;
6. secure cookie, CSRF and browser-bound pre-auth behavior remains equivalent;
7. real login, logout, revoke and outage fail-closed behavior;
8. cross-tenant negative tests remain database-enforced;
9. exact-SHA `/healthz` and release identity evidence;
10. rollback to the last-known-good candidate without changing database authority.

If provider documentation does not define a trustworthy client-IP header contract, the
application must not guess one. The ingress remains blocked until a verified provider
contract or a safer architecture is established.

## 7. PostgreSQL end-state and Neon retirement

Amendment 17 remains the owning database-migration law.

The required database sequence remains:

`RU-PG-B -> RU-PG-C -> RU-PG-D -> RU-PG-E`.

The OWNER's end-state is now explicit:

- production PostgreSQL = Timeweb Cloud Managed PostgreSQL 18 in Russia;
- Neon = no active V10 production authority after RU-PG-E;
- Neon historical evidence remains historical and must not be rewritten/deleted;
- no real Russian-user personal data is written to the Timeweb candidate before RU-PG-D
  cutover acceptance;
- Neon must not be deleted before the Timeweb production cutover, recovery proof and
  rollback boundary are accepted.

Immediately deleting Neon before cutover is forbidden because it would destroy the current
last-known-good database recovery authority.

## 8. Network evolution

RU-PG-B/RU-PG-C may continue to use the already-authorized single Timeweb public IPv4 for
Cloudflare-to-PostgreSQL TLS parity.

After the Russia-facing application runtime and production database are both accepted,
network scope must be re-evaluated:

- prefer private Timeweb application-to-database connectivity when it can satisfy the
  accepted PostgreSQL/TLS/runtime identity contract;
- do not keep a public PostgreSQL exposure merely because it was required for an earlier
  Cloudflare parity stage;
- close obsolete public database paths only after the new private/runtime path is proven
  and rollback is preserved.

## 9. Cost discipline

The OWNER authorizes necessary Timeweb services for this launch when they are actually
required, using existing prepaid provider funds before any new top-up, subject to these
rules:

- no spare capacity is purchased merely for future convenience;
- the already-observed PostgreSQL target and already-approved single public IPv4 remain
  within their owning gates;
- production backup/recovery storage and basic monitoring may be enabled when their owning
  acceptance gate makes them necessary;
- replicas, larger compute, load balancers, DDoS add-ons and other recurring services are
  not pre-provisioned without capacity/security evidence;
- the exact current recurring price of a new App Platform runtime must be known before
  purchase;
- a necessary provider service may be purchased after its owning gate proves requirement,
  exact configuration and current cost, provided it fits existing prepaid funds;
- if the required recurring configuration would exceed available prepaid funds or require
  a new payment/plan commitment, stop for fresh OWNER approval.

This amendment does not encode a private account balance, payment-card data or billing
identifier.

## 10. Release provenance

Timeweb public runtime acceptance must preserve the existing evidence principle:

`accepted main SHA -> immutable/provider candidate -> live probe -> promotion -> production verification`.

Required recorded evidence must include at least:

- exact Git commit SHA;
- provider application/deployment identifier;
- deployment status/time;
- canonical hostname;
- sanitized runtime/database role identity;
- health/release response proving the same SHA;
- rollback target.

Provider auto-deploy or dashboard state never outranks GitHub accepted main.

## 11. Public-user legal/privacy gate

A Russian data-center and Russia-reachable web runtime do not, by themselves, authorize
public registration.

Before the first real public registration, the existing Telegram legal/privacy gate still
requires, as applicable:

- accepted Russian production PostgreSQL cutover;
- Roskomnadzor processing-notification evidence;
- Telegram/Cloudflare/other actual foreign-recipient flow assessment and required
  cross-border notification;
- final public Privacy Policy on every personal-data collection surface;
- accepted Russian-hosted or in-product/Russian-stored personal-data request channel;
- public-user capacity/monitoring/incident readiness.

No private address, tax identifier, passport data, provider secret or filing credential is
placed in GitHub.

## 12. Telegram-first activation

Public launch may activate Telegram independently of VK ID.

Only after the owning database, ingress, privacy/legal, runtime and monitoring gates are
accepted may a focused activation set:

- `PUBLIC_MULTI_USER_ENABLED=true`;
- `OMNI_V10_TELEGRAM_LOGIN_ENABLED=true`.

`OMNI_V10_VK_ID_LOGIN_ENABLED` may remain `false`.

Real canonical-Web evidence must then prove ordinary USER login -> verified identity ->
`OmniCIOUserAccount -> Tenant -> server-side Session`, logout/revoke and cross-tenant
negative behavior. Login activation never authorizes broker write or Real money.

## 13. Execution-unit and split law

Issue #580 is one integrated **RU public registration launch program**, but it is not one
unbounded implementation PR.

Amendment 12 mandatory split triggers remain binding. Separate acceptance boundaries are
required for:

- RU-PG-B provider mutation/parity;
- RU-PG-C runtime/TLS/recovery parity;
- RU-PG-D production database cutover;
- RU-PG-E Neon active-authority retirement;
- Russia-facing runtime/provider spend and DNS/public-ingress cutover;
- legal/regulatory OWNER-only actions;
- final public-user activation.

This split is a recovery/security boundary, not optional bureaucracy. Reusing one dashboard,
contracts and artifacts prevents duplicated work while preserving rollback and exact
evidence.

## 14. Direct provider integration

Where Timeweb can consume the GitHub repository directly, prefer that supported provider
integration over inventing a second source-copy/deployment repository.

However, direct provider integration does not bypass code review or exact-SHA acceptance.
No provider token is pasted into chat or committed to GitHub. If a provider connection
requires an OWNER browser authorization that current engineering tools cannot perform, that
single authorization remains OWNER-only.

## 15. Protected invariants

Until their owning gates accept a transition:

- `PUBLIC_MULTI_USER_ENABLED=false`;
- `OMNI_V10_TELEGRAM_LOGIN_ENABLED=false`;
- `OMNI_V10_VK_ID_LOGIN_ENABLED=false`;
- broker write OFF;
- `trading_methods=false`;
- `REAL_TRADING_ENABLED=false`;
- protected V9 `app:app` remains intact;
- no Render or Cloud.ru active V10 deployment path;
- no dual-primary database, account, tenant or session authority;
- no secret/private payload disclosure.

## 16. Acceptance and immediate execution effect

This amendment is governance/authority only.

After it is accepted on protected `main`:

- current RU-PG-B remains the immediate execution stage until `CERTIFIED_GREEN`;
- issue #580 becomes the umbrella launch dashboard;
- the next Russia-ingress implementation package remains blocked until its own source/runtime
  authority gate is reached;
- WEB-VISUAL and WP23+ remain independently locked;
- no database cutover, DNS mutation, App Platform purchase, public registration or Neon
  deletion occurs merely because this amendment is merged.

Acceptance requires DRAFT exact-head applicable SUCCESS, review with zero unresolved
blocking threads, fresh READY exact-head applicable SUCCESS, squash merge, then exact-new-main
Regression Shield and V10 Engineering Governance SUCCESS.
