# Omni-CIO V10 — Product User / Engineering Authority Boundary Amendment

Status: **OWNER-APPROVED PLANNING AUTHORITY — EFFECTIVE ON MERGE TO PROTECTED `main`**  
Decision date: **2026-08-17**, reaffirmed and consolidated **2026-08-18**.

## Purpose

The PROJECT OWNER is not a special Omni-CIO product user, tenant, administrator or authentication role. When the PROJECT OWNER uses Omni-CIO, the PROJECT OWNER is an ordinary authenticated **USER** and follows the same product path as every supported user.

Canonical product identity:

`OmniCIOUserAccount -> Tenant -> Session -> tenant-scoped product state`

Canonical engineering authority is separate:

`GitHub / CI / cloud provider / deployment / recovery / legal-business decisions != Omni-CIO product identity`

## Binding terminology

- **USER** — authenticated Omni-CIO account that owns exactly its own tenant-scoped product state.
- **PROJECT OWNER** — repository/program/business/infrastructure authority outside normal product authorization.
- **ENGINEERING / OPERATIONS AUTHORITY** — GitHub, CI, cloud-provider, deployment, runtime-secret, recovery and release authority outside normal USER sessions.

PROJECT OWNER authority never automatically grants a product session, cross-tenant read/write, broker-secret access, Real-money approval for another user, or a hidden privileged investment cabinet.

## One product path

The product invariant is:

`PROJECT OWNER using Omni-CIO == ordinary USER using Omni-CIO`

Therefore the PROJECT OWNER uses the same registration/login, account, tenant, session, portfolio, broker-connection, research, decisions, plans, AI/Cortex and Telegram flows as supported users. The PROJECT OWNER may be the first acceptance USER; that does not create a special product role.

Normal users must never require GitHub repository access, membership in the PROJECT OWNER's Cloudflare/provider account, Windows/Lenovo credentials, CI access, or engineering credentials to use Omni-CIO.

## Authentication

Product authentication remains the internal Omni-CIO account model governed by the Identity / Multi-Tenant amendment. Telegram Login and VK ID are product authentication providers; GitHub, Cloudflare, Windows and CI identities are not product authentication providers.

Server-side Omni-CIO session state determines product authority. Provider/edge pre-auth may protect engineering or staging surfaces, but may not substitute for the USER account/session path in the public product.

## WP17 / WP22 / WP22A interpretation

WP17 is a USER account shell, not an OWNER cabinet.

The historical WP22 title `System/Admin UI` does not create a global product administrator. `/system` is a USER-facing System / Diagnostics surface scoped to the authenticated USER/tenant and sanitized operational state. It is not a cross-tenant operator shell.

WP22A is interpreted as:

**WP22A — External Web Access / Product Authentication Security Gate**

WP22A must preserve server-side sessions, secure cookies, session rotation/revocation, CSRF protection, Host/Origin/Referer controls, rate limiting, direct-API denial, tenant isolation, TLS, abuse controls and recovery. Edge/provider identity and product identity must remain separate.

## Telegram and future interaction surfaces

Telegram is USER-scoped in the final product. A Telegram identity binds only to that Omni-CIO USER account and tenant. An unlinked or unauthorized Telegram identity receives no private data. Mini App and ordinary Web remain one product/frontend codebase where planned.

## Real-money terminology

Historical product-domain phrases such as `OWNER approval`, `OWNER confirmation`, `recent OWNER authentication` and `OWNER negotiation` are interpreted as the authenticated **USER acting for that USER's own tenant/account**, unless the context explicitly means a project/business/infrastructure decision.

This does not weaken immutable-plan approval, step-up/recent authentication, exact broker-account binding, fresh preflight, idempotency, reconciliation, cash-only restrictions or the ban on transfer/withdrawal authority.

## Provider administration

PROJECT OWNER GitHub/cloud-provider identity may authorize infrastructure mutation. That infrastructure authority must never automatically mint an Omni-CIO USER session or select a tenant.

`engineering authority to operate the service != product authority to read/use a tenant`

## Public product precedence

Public multi-user target, public production hosting, free initial access and tenant-scoped broker-credential custody are governed by `OMNI_CIO_V10_PUBLIC_FREE_MULTI_USER_HOSTED_RUNTIME_AMENDMENT.md`.

That superseding launch amendment intentionally replaces earlier assumptions that the final product remains OWNER-only, Personal-Node-only or permanently private. This role-boundary amendment remains fully binding within the public product.

## Safety retained

This amendment does not itself enable broker write, Real execution, public deployment or provider mutation. It preserves:

- one repository / one source-controlled Web App / one deterministic Core;
- `app:app` protected V9 baseline;
- `trading_methods=false`;
- `REAL_TRADING_ENABLED=false`;
- no margin/leverage/uncovered short;
- no transfer/withdrawal authority;
- tenant isolation;
- no secrets/private payloads in GitHub/CI;
- protected V9 rollback;
- exact-head CI / review / squash-merge / post-merge acceptance discipline.

## Precedence

After merge, this amendment supersedes conflicting OWNER-specific **product-role** wording in earlier V10 documents while preserving genuine PROJECT OWNER engineering/business authority and historical evidence.