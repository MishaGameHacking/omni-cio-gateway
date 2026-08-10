# Omni-CIO V10 — Identity / Multi-Tenant Account / Authentication Amendment

Status: **OWNER-APPROVED PLANNING AUTHORITY — IMPLEMENTATION STAGED BY EXISTING WP ORDER**  
Effective date: **2026-08-10**

## 1. Purpose

This amendment records the OWNER-approved product identity model for future Omni-CIO users without creating a competing product, repository, Core, Web App, broker stack, or data source of truth.

The target product must support an unbounded number of logically isolated Omni-CIO user accounts, subject to measured infrastructure, legal, broker-contract, security, capacity, and commercial gates. Public activation is not implied by this planning amendment.

A user account is an Omni-CIO identity. Telegram and VK ID are authentication providers for that identity; neither provider is itself the Omni-CIO account.

## 2. Canonical identity model

The platform identity hierarchy is:

`OmniCIOUserAccount -> Tenant -> Private Data Plane -> BrokerConnections / Portfolio / Research / Decisions / AI private state`

Rules:

- one normal Omni-CIO user account owns exactly one isolated tenant in the baseline product model;
- every tenant-scoped record is resolved from authenticated server-side session context, never trusted from a client-supplied tenant/user selector;
- one external identity binding belongs to at most one Omni-CIO user account;
- one Omni-CIO user account may bind both Telegram and VK ID;
- external provider display name, username, avatar, phone, or e-mail is never sufficient for automatic account merge;
- account linking requires proof of control of the already-authenticated Omni-CIO account and the new external identity;
- account switching is logout/re-authentication, not a client-side tenant selector;
- cross-tenant reads/writes are denied by default at API authorization and durable-storage scope boundaries.

## 3. Login methods

The ordinary user-facing login methods are exactly:

1. **Telegram Login**;
2. **VK ID**.

No Omni-CIO password database is required for the ordinary login path. Google login is not part of this target.

### 3.1 Telegram

Use the current official Telegram website authentication mechanism (OIDC / Authorization Code flow with PKCE where supported by the selected integration). The backend validates issuer/signature/audience/nonce/state/time freshness and maps the stable provider subject to an internal external-identity binding.

Do not request phone number or permission to message the user unless a later owning WP demonstrates a product requirement and records consent/privacy consequences.

### 3.2 VK ID

Use the current official VK ID Web SDK / OAuth 2.1 flow with state and PKCE. The backend treats provider tokens as authentication artefacts only and stores no broader VK profile fields unless an owning WP explicitly requires them.

## 4. Central account / identity plane

The central account plane is intentionally minimal. Its permitted baseline fields are limited to data necessary for account existence, authentication binding, session security, recovery, license/commercial state, abuse prevention, and node/data-plane routing.

Canonical conceptual relations:

- `user_accounts(user_id, status, created_at, security_state, ...)`;
- `external_identities(user_id, provider, provider_subject_binding, linked_at, last_verified_at, ...)`;
- `sessions(session_id_hash, user_id, created_at, last_seen_at, expires_at, revoked_at, ...)`;
- `recovery_credentials(user_id, credential_hash, consumed_at, ...)` when emergency recovery is enabled;
- `node_bindings(user_id, node_identity, state, ...)` when a Personal/Private Data Plane node is used.

Data minimization rules:

- do not require a local Omni-CIO password;
- do not collect/store provider phone, address, contacts, avatar, full social profile, or unrelated profile metadata by default;
- do not store raw provider access/refresh tokens longer than required by the reviewed authentication protocol;
- stable provider subjects may be stored only in a protected binding form suitable for exact account lookup and uniqueness enforcement;
- central identity records are not a portfolio/accounting source of truth.

## 5. Server-side sessions and remembered login

After successful Telegram/VK authentication, the server creates a revocable server-side session.

Rules:

- browser receives only an opaque high-entropy session identifier in a reviewed secure cookie;
- no authentication/session/refresh credentials are stored in `localStorage` or `sessionStorage`;
- production cookies use `Secure`, `HttpOnly`, appropriate `SameSite`, and host/path scoping;
- session fixation protection, rotation on authentication/privilege change, bounded idle/absolute lifetime, explicit logout, and revoke-all-sessions are required;
- remembered login means a still-valid server-side session, not permanent device trust;
- loss/replacement of a phone or browser must not delete the Omni-CIO account or authoritative private data.

## 6. Account recovery

The normal login surface remains Telegram + VK ID.

A user should be encouraged to bind both providers to the same Omni-CIO account. Either provider may then recover ordinary access if the other is lost.

Automatic merge by matching names, phone numbers, usernames, e-mail addresses, or profile photos is forbidden.

If both providers are lost, a separate emergency recovery mechanism may be implemented by the owning security WP. The preferred baseline is one-time recovery codes or an equivalent high-entropy recovery credential whose server-side representation is hashed and revocable. It is not presented as a third everyday login provider.

## 7. Tenant isolation

Multi-user readiness must be structural, not a UI convention.

Mandatory controls before public multi-user activation:

- every private record carries or is strongly related to a tenant scope;
- API derives `user_id`/`tenant_id` from authenticated session context;
- object identifiers alone never authorize access;
- PostgreSQL row-level isolation or an equivalently reviewed database-enforced policy must prevent horizontal cross-tenant access in addition to application authorization;
- cross-scope foreign keys / uniqueness rules prevent a record from being rebound to another tenant;
- background jobs carry immutable tenant scope and cannot run with an implicit/global user;
- caches, AI/RAG memory, audit events, exports, backups and notifications preserve tenant isolation;
- tests include IDOR, cross-tenant reference, stale-session, cache-key collision, job-scope, backup/restore and AI/RAG cross-scope leakage cases.

The existing OWNER-only constraints are a safe implementation baseline, not the final public-user schema.

## 8. Broker connection model

Broker credentials are attached to a tenant-owned `BrokerConnection`, not to a developer machine and not to a global application singleton.

Each logical T-Invest connection supports at most two credential roles:

1. `READ` — monitoring/portfolio/market/account data;
2. `TRADE` — optional BUY/SELL execution credential.

Transfer/withdrawal authority remains outside V10.

### 8.1 Multiple broker accounts and broad tokens

A T-Invest token may expose one account or several accounts. Omni-CIO must discover the broker accounts accessible to the presented token and create verified broker-account bindings under the authenticated tenant.

A broad READ token can therefore bind multiple broker accounts under one tenant. A narrow account-specific READ token binds only that account.

### 8.2 READ/TRADE relationship

A TRADE credential never creates an unrelated account by itself. Before enabling execution for a broker account, Omni-CIO must prove that the account is already represented in the tenant's verified READ-side broker-account set and that the TRADE credential independently exposes the same broker account with the required authority.

Execution eligibility is the intersection of verified identities:

`EXECUTABLE_ACCOUNTS = VERIFIED_READ_ACCOUNTS ∩ VERIFIED_TRADE_ACCOUNTS`

A mismatch fails closed. Full-access/trade authority is never used as a fallback for portfolio reads.

### 8.3 Web-only normal provisioning

Normal users enter/replace/revoke broker credentials only through the authenticated Omni-CIO Web settings flow.

Raw credentials:

- are submitted only to the backend over the reviewed secure transport;
- are never returned to the browser after submission;
- are never stored in browser Web Storage;
- are never committed to GitHub, CI, logs or artifacts;
- are stored only by an approved tenant-scoped secret backend;
- are inaccessible to Cortex, ordinary CI runner, update agent and unrelated tenants.

PowerShell/administrator secret provisioning remains bootstrap/recovery/owner-maintenance tooling, not the normal product UX.

## 9. Central versus private investment data

This amendment does **not** authorize a centralized T-Invest-data SaaS or central custody of all users' broker credentials/portfolios.

The accepted zero-custody/privacy model remains the production default:

- central plane may know account identity/session/license/security/node-routing state;
- private portfolio, broker reports, broker READ/TRADE secrets, private trading history, private Decision Journal payloads and private Cortex history remain in the user's approved Private Data Plane by default;
- the Private Data Plane may be a Personal Node or a later separately approved isolated deployment model;
- phone/browser is never authoritative storage;
- any future centrally hosted private-data model requires a new explicit architecture/legal/broker-terms approval and must not be inferred from this amendment.

## 10. Public multi-user activation gate

Implementation may prepare multi-tenant contracts, tests and disabled infrastructure before public launch, but public registration/service activation remains fail-closed until all owning gates pass, including:

- external Web ingress and authentication security acceptance;
- cross-tenant authorization / database-isolation acceptance;
- session/recovery abuse testing;
- privacy/personal-data inventory and localization determination;
- broker API commercial/terms compatibility determination;
- investment-advisory/autoconsulting legal determination;
- capacity/rate-limit/load/abuse controls;
- commercial production legal sign-off.

`PUBLIC_MULTI_USER_ENABLED=false` is the safe default until those gates are accepted.

## 11. Changes to existing V10 work-package interpretation

This amendment preserves the A-J block order and does not credit progress merely for planning.

### WP12 / WP13

Existing tenant-ready domain/persistence work is retained. OWNER-only hard constraints become a migration baseline. The owning future schema correction must generalize tenant/user identity without weakening scope FKs, append-only evidence, Decimal/UTC semantics or accepted recovery guarantees.

### WP15

The current T-Invest read adapter remains the broker-read implementation baseline, but its product-facing credential ownership is interpreted as `tenant -> BrokerConnection -> READ credential`, not one machine-global user credential.

The WP15 controlled live OWNER token acceptance is deferred from PowerShell to the first reviewed authenticated Web broker-provisioning flow. Until then:

- broker-read code/offline/CI/security acceptance may be completed;
- real broker credential remains unprovisioned;
- no real portfolio value is claimed as live-accepted;
- Block D progress is not falsely credited for the deferred live evidence;
- WP18 real-data acceptance remains blocked until the deferred WP15 live broker evidence passes.

### WP16

Design System proceeds after the amended WP15 code/security acceptance is formally accepted according to the updated status/exit record.

### WP17

Application Shell now owns the first authenticated account shell and Web broker-connection provisioning UX contract. It must implement Telegram/VK identity abstraction, server-side session semantics, logout/switch/revoke controls and Settings -> Broker Connections without embedding financial logic in the frontend.

Public registration remains disabled until the external/multi-user security/legal activation gates pass; OWNER/test identities may exercise the same code path earlier in local/private acceptance.

### WP18

Portfolio Dashboard may consume real broker data only after Web READ-token provisioning completes the deferred WP15 live evidence for the corresponding tenant/broker account.

### WP22 / WP22A

System/Admin owns account/session/broker-connection observability without exposing raw secrets. External Web Access gate expands from OWNER-only session testing to multi-user authentication/session/authorization and cross-tenant negative tests.

### Block I

TRADE credential provisioning is a separate Web/security flow. Real execution remains disabled by default and requires the existing immutable-plan approval/preflight/reconciliation gates plus exact READ/TRADE broker-account identity intersection.

## 12. Engineering invariants retained

This amendment does not relax:

- `app:app`;
- `trading_methods=false` until the owning execution WP explicitly and safely changes the protected contour;
- `REAL_TRADING_ENABLED=false` until accepted Real execution activation;
- no broker write authority in WP15 read adapter;
- no margin/leverage/uncovered short;
- no transfer/withdrawal authority;
- V9 protected rollback;
- GitHub/CI never stores real broker/Telegram/VK client secrets or private investment payloads;
- exact-head CI, review, recovery and post-merge acceptance discipline.

## 13. Implementation authority

This amendment is planning authority. It authorizes changes only when the current work-package/status sequence permits them.

Do not create a second website, second Core, second persistence stack, separate broker gateway or separate identity product. The implementation must remain inside `MishaGameHacking/omni-cio-gateway` and use the one source-controlled Web App.
