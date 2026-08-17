# Omni-CIO V10 — Product User / Engineering Authority Boundary Amendment

Status: **OWNER-APPROVED PLANNING AUTHORITY — EFFECTIVE ON MERGE TO PROTECTED `main`**  
Effective decision date: **2026-08-17**  
Scope: V10 product identity, Web/Telegram interaction, WP22/WP22A interpretation, Real-approval terminology, engineering/operations authority separation.

## 1. Purpose

This amendment removes an ambiguity that can otherwise create a wrong product architecture: the PROJECT OWNER is **not** a special Omni-CIO end-user role and must not receive a separate investment/admin product experience merely because the same person owns the repository, infrastructure, domain or engineering accounts.

When the PROJECT OWNER uses Omni-CIO as a customer, the PROJECT OWNER is an **ordinary Omni-CIO USER** and follows the same product authentication, tenant isolation, portfolio, decision, broker-connection, AI, Telegram and session flows as any other supported user.

This amendment does not create a second product, second Web App, second account system, competing control plane, new repository or new Work Package. It clarifies the existing V10 plan and supersedes earlier OWNER-specific product wording where that wording could be interpreted as a permanent product role.

## 2. Canonical terminology

Future V10 engineering must distinguish these concepts explicitly.

### 2.1 `USER`

An authenticated Omni-CIO product user represented by `OmniCIOUserAccount -> Tenant`.

A USER owns only their tenant-scoped product state and receives only permissions defined by the product authorization model.

The PROJECT OWNER is also a USER when using Omni-CIO.

### 2.2 `PROJECT OWNER`

The human authority for repository/program/business decisions, GitHub ownership, infrastructure bootstrap, provider/legal/commercial decisions and other explicitly OWNER-reserved engineering actions.

`PROJECT OWNER` is **not** an Omni-CIO product RBAC role.

PROJECT OWNER authority must never automatically grant:

- access to another user's tenant or portfolio;
- a special product session;
- a product authentication bypass;
- broker-secret access through the UI;
- Real-money approval on behalf of another user;
- cross-tenant administrator access;
- a separate privileged investment dashboard.

### 2.3 `ENGINEERING / OPERATIONS AUTHORITY`

Authority over GitHub, CI, deployment, Cloudflare/provider configuration, Windows Administrator actions, runtime-secret bootstrap, recovery, release management and other infrastructure operations.

This authority exists **outside the normal product identity plane**. It is not evidence of product identity and does not become an Omni-CIO account permission.

### 2.4 `PRODUCT ADMINISTRATION`

V10 does not assume a special PROJECT-OWNER product administrator account.

If a future commercial operating model genuinely requires support/operator functions, they must be separately designed, least-privilege, audited, privacy-minimized and explicitly authorized by the owning Work Package/amendment. Such support authority must not be inferred from GitHub/Cloudflare/Windows ownership and must not silently provide portfolio/broker-secret access.

## 3. One product path for the PROJECT OWNER and all users

The product invariant is:

`PROJECT OWNER using Omni-CIO == ordinary USER using Omni-CIO`

Therefore:

- the PROJECT OWNER signs in through the same ordinary product-authentication mechanisms as supported users;
- the PROJECT OWNER receives the same user account/tenant/session model;
- the PROJECT OWNER uses the same portfolio, alerts, research, decision, plan, broker-connection, AI and Telegram product surfaces;
- the PROJECT OWNER does not get an OWNER-only product homepage, OWNER-only portfolio cabinet, OWNER-only investment controls or OWNER-only product session;
- any acceptance test performed by the PROJECT OWNER must exercise the same product code path that a normal user will exercise, except where the test specifically concerns engineering/recovery authority outside the product.

The PROJECT OWNER may be the **first acceptance user** before public activation. That is an acceptance/testing fact, not a product-role distinction.

## 4. Product authentication invariant

Canonical Omni-CIO product authentication remains the internal Omni-CIO account model governed by `OMNI_CIO_V10_IDENTITY_MULTI_TENANT_ACCOUNT_AND_AUTHENTICATION_AMENDMENT.md`.

Ordinary product identity is derived from reviewed product authentication providers and server-side Omni-CIO session state. GitHub ownership, Cloudflare account membership, Windows identity, CI runner identity or provider-dashboard login are not product user identities.

The product path must not require a normal user to possess:

- GitHub repository access;
- membership in the PROJECT OWNER's Cloudflare account;
- Windows/Lenovo credentials;
- CI access;
- infrastructure/provider credentials.

A deployment-edge mechanism may protect a pre-production/internal environment, but it cannot replace Omni-CIO account authentication or become the permanent reason a user receives tenant access.

## 5. WP17 / account-shell interpretation

WP17's authenticated application shell is a **user account shell**, not a PROJECT-OWNER shell.

Settings, broker connections, session revoke/logout, account linking and future user preferences belong to the authenticated USER/tenant.

Any historical OWNER/test identity used before public activation is interpreted as the first controlled USER exercising the same code path.

## 6. WP22 `System/Admin UI` interpretation

The historical Work Package title `System/Admin UI` does **not** create an Omni-CIO administrator product role.

The accepted `/system` surface is interpreted as a USER-facing **System / Diagnostics** view for the user's own Omni-CIO deployment/tenant context. Its purpose is product observability and safe diagnostics, not privileged administration over other users.

For ordinary USER use it may expose sanitized, relevant state such as:

- application/service health;
- release/build identity;
- connection state;
- backup/recovery freshness relevant to that user's private data plane;
- bounded resource/runtime status;
- safe recent jobs/errors;
- read-only safety state.

It must not imply that the PROJECT OWNER has a special product identity or cross-tenant authority.

Infrastructure operations that require GitHub, provider credentials, Windows Administrator, deployment secrets, global service maintenance or recovery authority stay in the engineering/operations plane unless a later Work Package explicitly designs a safe typed product operation.

## 7. WP22A correction — external access must serve the product, not an OWNER-only cabinet

WP22A remains the current package and keeps its security purpose: external Web access must not expose the Personal/Private Data Plane unsafely.

However, the product-facing interpretation is corrected from an OWNER-specific login gate to:

**WP22A — External Web Access / Product Authentication Security Gate.**

The synchronized base-plan numbering is unchanged; this amendment governs the implementation meaning.

WP22A must satisfy all of the following:

1. the PROJECT OWNER's acceptance browser uses the same Omni-CIO USER authentication/session path intended for supported users;
2. an OWNER-only Cloudflare/GitHub/provider identity must not become the canonical Omni-CIO login or tenant authority;
3. a normal supported USER must not need PROJECT-OWNER infrastructure membership to use the product;
4. the external transport may use Cloudflare Tunnel or another accepted transport, but product authentication remains Omni-CIO authentication;
5. if Cloudflare Access or another edge identity gate is retained for an engineering/staging surface, it is an infrastructure pre-auth layer only and must be clearly separated from product identity;
6. final product ingress architecture must be re-evaluated so edge protection does not create a second mandatory end-user account system competing with Telegram/VK/Omni-CIO identity;
7. server-side sessions, CSRF, Host/Origin checks, rate limiting, tenant isolation, direct-API denial, session expiry/revocation and other WP22A security controls remain mandatory;
8. public multi-user activation remains separately fail-closed until its security/legal/capacity gates pass.

A PROJECT-OWNER-only external access path may be used temporarily as **pre-production acceptance containment**, but it cannot by itself satisfy the final product-authentication meaning of WP22A if normal future users would require a different architecture.

## 8. Cloudflare / provider boundary

Provider administration and product authentication are separate concerns.

PROJECT OWNER GitHub/Cloudflare identity may legitimately authorize **provider mutation** such as DNS/Tunnel configuration because that is engineering/operations authority.

That same identity must not automatically authorize an Omni-CIO product session.

Therefore a source-controlled workflow or protected local controller may remain PROJECT-OWNER-bound for infrastructure mutation while the Web product itself remains USER-authenticated.

The rule is:

`engineering authority to publish/operate the service != product authority to read/use a tenant`

## 9. Telegram / Block F correction

Earlier V10 wording that calls Telegram an `OWNER-only` product companion is superseded for the final multi-user product meaning.

Block F must implement a **USER-scoped Telegram companion** to the same Omni-CIO account/tenant model.

The PROJECT OWNER may be the first controlled Telegram acceptance user, but the final architecture must support supported users without converting the PROJECT OWNER's Telegram identity into global product authority.

Accordingly:

- Telegram identity binds to the authenticated Omni-CIO USER account;
- a Telegram user receives only their own tenant-scoped data;
- an unlinked/unauthorized Telegram identity receives no private data;
- Telegram does not create a second Core, second financial identity model or PROJECT-OWNER-only business logic;
- Mini App and ordinary Web remain one frontend/product codebase where already planned.

Existing WP23+ sequence remains unchanged.

## 10. Real-plan approval terminology

In V10 **product-domain** requirements, historical phrases such as `OWNER approval`, `OWNER confirmation`, `recent OWNER authentication` or `OWNER negotiation` must be interpreted as:

**the authenticated USER authorizing an action for that USER's own tenant/account under the required step-up/session/preflight controls.**

The PROJECT OWNER does not approve trades for other users merely because they own the project.

This terminology correction does not weaken any Real-money safeguard. Immutable plan, step-up/recent authentication, fresh preflight, exact account binding, idempotency, reconciliation, cash-only BUY/SELL restrictions and no transfer/withdrawal authority remain mandatory.

PROJECT OWNER approval remains distinct where the plan actually means a project/business/engineering decision, for example:

- plan/amendment approval;
- paid-service/budget decision;
- legal/commercial launch gate;
- infrastructure bootstrap;
- protected recovery/physical action;
- merge/governance authority where explicitly reserved.

## 11. Public multi-user activation

This amendment does **not** activate public registration or public multi-user service.

It requires only that the architecture being built now does not hard-code the PROJECT OWNER as a permanent special product user.

`PUBLIC_MULTI_USER_ENABLED=false` remains the safe default until all existing authentication, tenant-isolation, security, privacy, legal, broker-terms, capacity and commercial gates pass.

Before public activation, the PROJECT OWNER/test account is simply the first controlled USER account used to prove the same product path.

## 12. Superseded wording rule

For V10 product-facing documents accepted before this amendment:

- `OWNER-only user`, `OWNER session`, `OWNER product authentication`, `OWNER-facing cabinet`, `OWNER-only bot` and similar wording are **not** authority for creating a special PROJECT-OWNER application role;
- when the context is an end-user investment/product action, read `OWNER` as the authenticated tenant USER unless the document explicitly refers to repository/business/infrastructure ownership;
- when the context is GitHub, provider mutation, Windows admin, recovery, legal/commercial approval or other infrastructure/governance action, `PROJECT OWNER` retains its engineering/business meaning;
- historical evidence remains historical and is not rewritten merely to erase the fact that the PROJECT OWNER was the first acceptance user.

If a current implementation contract conflicts with this separation, that contract must be corrected before its Work Package can pass the Exit Gate.

## 13. Impact on current WP22A work

This amendment is a planning correction discovered before WP22A completion.

Therefore:

- WP22A remains **IN PROGRESS**;
- WP23+ remains **LOCKED**;
- existing accepted Phase-A external-access code is not automatically invalid, but any OWNER-specific product-auth assumption must be re-reviewed against this amendment;
- any open Phase-B PR must not be merged merely because its infrastructure boundary is secure if the resulting product path still makes the PROJECT OWNER a special user;
- provider/Windows engineering authority may remain PROJECT-OWNER-restricted where appropriate, but product user authentication must remain separate;
- no real Cloudflare/provider credential or public activation is authorized by this planning change.

## 14. Engineering guardrail for future sessions

Before implementing any feature described with the word `OWNER`, engineers/agents must classify the meaning:

- **PRODUCT USER action** -> implement against normal `OmniCIOUserAccount` / tenant / session authority;
- **PROJECT OWNER engineering/business action** -> keep it outside normal product identity and behind the applicable GitHub/provider/admin/legal control plane.

If the classification is ambiguous, implementation stops and the plan/contract wording is corrected before coding.

Do not solve ambiguity by giving the PROJECT OWNER both authorities in one account/session.

## 15. Safety invariants retained

This amendment does not change:

- one Omni-CIO product/repository/Web App;
- `app:app`;
- `trading_methods=false` until its owning accepted execution gate changes it;
- `REAL_TRADING_ENABLED=false` until accepted Real execution activation;
- no broker-write expansion in WP22A;
- no margin/leverage/uncovered short;
- no transfer/withdrawal authority;
- tenant isolation requirements;
- zero-custody/private-data boundaries;
- protected V9 rollback;
- GitHub/CI secret restrictions;
- exact-head CI, PR, squash-merge and post-merge acceptance discipline;
- existing A-J block order and Work Package numbering.

## 16. Acceptance and precedence

This amendment is explicitly requested and OWNER-approved on 2026-08-17 to prevent future confusion between the PROJECT OWNER and an Omni-CIO USER.

It becomes active repository authority only after merge to protected `main` through the normal documentation/governance PR process.

After acceptance it supersedes conflicting OWNER-specific **product-role** interpretations in earlier V10 plan/amendment/current-WP wording while preserving historical evidence and genuine PROJECT OWNER engineering/business authority.
