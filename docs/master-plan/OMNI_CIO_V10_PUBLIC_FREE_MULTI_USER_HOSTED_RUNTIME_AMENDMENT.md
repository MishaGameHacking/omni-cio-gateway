# Omni-CIO V10 — Public Free Multi-User Hosted Runtime Amendment

Status: **OWNER-APPROVED PLANNING AUTHORITY — EFFECTIVE ON MERGE TO PROTECTED `main`**  
Decision date: **2026-08-18**.  
Scope: public product target, production hosting, global browser access, account/tenant isolation, broker-credential ownership, free initial launch, commercial deferral, WP22A interpretation and legal/broker activation gates.

## 1. Product target

Omni-CIO V10 is to become a **public, modern, multi-user Web product**.

A supported user with ordinary Internet access must be able to open the Omni-CIO public HTTPS hostname from a normal modern phone or desktop browser, register/sign in through the supported product authentication flow, and use only that user's own tenant-scoped Omni-CIO state.

Canonical product path:

`Internet -> public HTTPS edge -> cloud-hosted Omni-CIO Web/API -> product authentication -> OmniCIOUserAccount -> Tenant -> tenant-scoped private state`

The user must not need a VPN, Tailscale client, GitHub account, Cloudflare account membership, Windows credentials, PROJECT OWNER infrastructure membership, the OWNER's phone, or physical proximity to any OWNER device/network.

## 2. Explicit no-home-production dependency

The final public production service must **not depend on the PROJECT OWNER's home infrastructure for availability or user reachability**.

The following are forbidden as required production dependencies for ordinary users:

- PROJECT OWNER home public IP address;
- home Wi-Fi;
- home cable/fiber/mobile Internet uplink;
- home router/NAT/port-forwarding;
- Lenovo laptop as the public production origin;
- OWNER LAN/private subnet;
- an outbound tunnel whose only production origin is the OWNER's home Lenovo/network;
- any browser path that fails for all users merely because the OWNER's home loses power or Internet.

Lenovo remains valuable for engineering, self-hosted CI, controlled acceptance, recovery rehearsal and protected rollback. It is **not** the public-product availability anchor.

A home/Lenovo tunnel may exist only for explicitly non-production engineering/staging/recovery use and must never be represented as satisfying this public-hosted requirement.

## 3. Public production hosting model

The V10 public Web/API and the private state required for the supported hosted multi-user product run on an **approved managed cloud production runtime**, selected through the V10 service-selection process.

The exact provider is not hard-coded by this amendment. Selection must evaluate security, data location/legal suitability, managed PostgreSQL/storage/secrets, encrypted backup/recovery, availability, observability, GitHub automation, rollback, cost, lock-in and measured capacity.

The deployment remains one source-controlled Omni-CIO Web App in `MishaGameHacking/omni-cio-gateway`. A cloud deployment is not permission to create a second website, competing Core, competing identity system or competing broker stack.

Cloudflare may be used for DNS, TLS, WAF/DDoS/edge controls or other reviewed ingress functions. Cloudflare/provider identity remains engineering authority and must not become Omni-CIO product identity.

## 4. Global browser access

The supported product access contract is:

- public DNS/HTTPS hostname;
- reachable over ordinary Internet from supported countries/networks subject to lawful/provider restrictions;
- responsive ordinary browser UX on modern phones and desktops;
- no native app required for basic registration/login/product use;
- no dependency on OWNER LAN routing;
- no exposure of origin credentials or private infrastructure details to the browser.

The normal requirement for product use is an Internet connection plus successful product authentication and authorization. Loss of Internet naturally prevents remote Web access; loss of the OWNER's home Internet must not take the public service down.

## 5. Account and tenant model

The accepted identity model remains authoritative:

`OmniCIOUserAccount -> Tenant -> Private Data Plane`

For the hosted public baseline:

- one normal account owns one isolated tenant;
- tenant scope comes only from authenticated server-side session context;
- client-supplied `tenant_id`/`user_id` never grants authority;
- object IDs alone never grant authority;
- API authorization plus database-enforced isolation must prevent cross-tenant reads/writes;
- jobs, queues, caches, RAG/AI memory, notifications, exports, backups, audit events and recovery must preserve tenant scope;
- cross-tenant IDOR, cache collision, stale-session, job-scope, backup/restore and AI/RAG leakage tests are mandatory before public activation.

The PROJECT OWNER is an ordinary USER when using the product, as defined by the Product User / Engineering Authority Boundary Amendment.

## 6. Product authentication

Ordinary product authentication remains:

1. Telegram Login;
2. VK ID.

Both map to an internal Omni-CIO account; neither provider identity is itself the business tenant identifier. Account linking requires proof of both identities and the authenticated account. Automatic merging by display name, phone, username, email or avatar is forbidden.

Production sessions remain server-side and revocable. Cookies must be `Secure`, `HttpOnly`, appropriately `SameSite`-scoped and protected against fixation. Bounded idle/absolute expiry, rotation, logout and revoke-all-sessions remain mandatory.

## 7. Tenant-owned broker credentials

Broker credentials are **personal to the authenticated USER's tenant**. There is no application-global READ token and no application-global TRADE token for public users.

Canonical ownership:

`USER -> Tenant -> BrokerConnection -> credential role -> verified broker account binding`

Supported T-Invest credential roles remain:

- `READ` — monitoring/portfolio/market/account information;
- `TRADE` — optional credential capable of supported BUY/SELL execution only after the owning Real-execution gates pass.

Rules:

- credentials are entered/replaced/revoked only through authenticated USER settings over reviewed HTTPS transport;
- a credential submitted by USER A is stored under Tenant A and must be cryptographically/logically inaccessible to Tenant B;
- credentials are never returned to the browser after submission;
- credentials are never stored in browser Web Storage;
- credentials are never committed to GitHub, CI, logs or artifacts;
- credentials are encrypted at rest using an approved cloud secret/data-protection boundary;
- runtime decryption authority is least-privilege and tenant-scoped by application authorization;
- Cortex/LLM, ordinary CI, frontend code and unrelated jobs/tenants never receive raw broker credentials;
- broad tokens may expose multiple broker accounts, but every discovered account binding remains within the submitting tenant;
- account-specific tokens bind only the account exposed by the broker;
- no credential may be silently reused across tenants, copied into a global singleton, or inherited from the PROJECT OWNER's environment.

## 8. READ / TRADE separation and execution safety

A `TRADE` credential never substitutes for READ authority and never creates an unrelated executable account.

Execution eligibility remains:

`EXECUTABLE_ACCOUNTS = VERIFIED_READ_ACCOUNTS ∩ VERIFIED_TRADE_ACCOUNTS`

The exact broker account must independently appear in both verified sets for the same tenant. Mismatch fails closed.

This amendment does not enable Real trading. Existing invariants remain:

- `trading_methods=false` until the owning accepted execution package changes the protected contour;
- `REAL_TRADING_ENABLED=false` until accepted Real activation;
- exact authenticated USER approval for that USER's own immutable plan;
- fresh preflight;
- own cash / owned quantity only;
- no margin/leverage/uncovered short;
- no transfer/withdrawal authority;
- idempotent possible submit and reconciliation after ambiguity;
- Cortex never receives raw TRADE credentials.

## 9. Hosted private-data model

This amendment intentionally supersedes the earlier assumption that public V10 must keep every user's investment-private state on a Personal Node.

For the public hosted baseline, the approved cloud runtime may store/process the authenticated tenant's private investment state and encrypted broker credentials **only after** the required security, privacy, personal-data, broker-terms and legal gates accept the exact design.

Required boundaries include:

- tenant-enforced PostgreSQL/data isolation;
- encryption in transit and at rest;
- secrets separated from ordinary application rows where appropriate;
- least-privilege runtime identities;
- auditable secret access/rotation/revocation;
- bounded retention;
- encrypted backups with tenant-preserving restore tests;
- no secret/private payload in CI or source control;
- privacy firewall/redaction before public research/telemetry;
- documented data inventory, location, processors, retention and deletion/recovery semantics.

The older Personal-Node zero-custody model remains useful historical/recovery architecture but is no longer the mandatory final public-product topology where it conflicts with this amendment.

## 10. Free initial public launch

Initial public USER access is **free**.

The launch contract is:

- `BILLING_ENABLED=false`;
- `TRIAL_ENABLED=false`;
- `SUBSCRIPTION_ENFORCEMENT=false`;
- `PREMIUM_FEATURE_GATING=false`;
- no subscription expiry disables ordinary product functionality;
- no payment method is required to register/sign in;
- no 7-day trial clock;
- no 1/3/6/12-month entitlement required for initial access;
- supported registered users receive the same allowed product feature set, subject only to security, legal, broker, capacity, abuse and owning-WP capability gates.

This supersedes the V10 amendment #5 paid-access/trial behavior **for the initial public launch**.

The prior commercial architecture is not deleted. Future monetization is `DEFERRED_OPTIONAL` and requires a later explicit OWNER-approved amendment/product decision plus applicable consumer/payment/KKT/legal implementation. Core financial behavior must not depend on monetization.

Infrastructure/provider costs paid by the PROJECT OWNER are not the same thing as charging users and are governed separately by engineering/budget decisions.

## 11. Public activation is a target, not an unsafe bypass

This amendment changes the target from permanently private/OWNER-only to public multi-user. It does **not** authorize immediate exposure before security/legal acceptance.

`PUBLIC_MULTI_USER_ENABLED=false` remains the safe implementation default while WP22A and dependent launch gates are unfinished.

The accepted target after all launch gates is `PUBLIC_MULTI_USER_ENABLED=true` for the public hosted product.

Before that transition, all of the following must be accepted on the real public architecture:

- WP22A external Web/product-authentication security;
- TLS/hostname/proxy/WAF/Host/Origin/CSRF/session/rate-limit controls;
- database-enforced tenant isolation and cross-tenant negative tests;
- session/recovery/abuse testing;
- secrets and backup/recovery design;
- privacy/personal-data inventory, location and legal basis;
- capacity/load/rate-limit/DoS controls;
- incident/monitoring/rollback/recovery;
- broker API terms compatibility for any broker-backed public feature;
- investment-advisory/autoconsulting/regulatory determination for personalized investment functionality;
- applicable production legal sign-off.

Payment/KKT gates are not required merely to provide free access; they become applicable if/when monetization is later enabled.

## 12. T-Invest public-service constraint

Current official T-Invest API documentation states that a public service based on T-Invest API is not permitted because the API is provided to T-Invest clients without data-retransmission rights.

Therefore public Omni-CIO account/Web activation and public T-Invest connector activation are separate gates.

Until the PROJECT OWNER obtains a contractually valid broker/partner permission or another reviewed architecture that complies with broker terms:

- the public site/account system may be developed and accepted;
- T-Invest-backed public production functionality must remain fail-closed/not generally activated;
- no code or UI may claim broker-terms approval that has not been obtained;
- user-supplied tokens do not by themselves waive the broker's service/retransmission restrictions.

A later accepted broker-terms decision may unlock the connector without weakening tenant credential isolation.

## 13. WP22A corrected objective

WP22A remains the current package, but its final meaning becomes:

**External Web Access / Product Authentication Security Gate for the eventual public hosted product.**

WP22A implementation must no longer optimize for an OWNER-only home Personal Node as the final public origin.

Required outcome before WP22A completion includes a reviewed migration/cutover design from accepted Phase-A OWNER/home assumptions to the hosted public target, while preserving reusable controls such as secure sessions, CSRF, Host/Origin validation, rate limiting, TLS, direct-API denial, abuse controls, auditability and rollback.

No WP23 implementation begins before the corrected WP22A Exit Gate is accepted.

## 14. Cloudflare and edge boundary

Cloudflare may be selected as public DNS/TLS/WAF/DDoS/edge transport. Its engineering account is controlled by the PROJECT OWNER/operations plane.

Cloudflare Access identity must not be the canonical Omni-CIO USER identity for the public product. If retained for staging/engineering, it is a separate pre-auth layer.

Cloudflare Tunnel is not sufficient as final production architecture when its sole origin is the PROJECT OWNER's home Lenovo/network, because that would violate Section 2. A tunnel may be used only when the actual production origin satisfies the hosted/no-home-dependency contract or for non-production engineering surfaces.

## 15. Availability and recovery

The public service must define measured availability and recovery expectations appropriate to the selected provider architecture.

At minimum the owning implementation must prove:

- cloud runtime restart/redeploy without OWNER home access;
- PostgreSQL/private-state backup and restore;
- corrupt-backup rejection/integrity verification;
- secret/key recovery/rotation procedure;
- replacement runtime recovery;
- rollback to last accepted release;
- tenant isolation after restore;
- no dependency on Lenovo being powered on for ordinary user access;
- monitoring that distinguishes provider outage, application outage and broker/provider dependency degradation.

Lenovo remains a protected engineering/recovery asset and V9 rollback source, not the required public serving node.

## 16. One-product rule

This hosted public direction does not authorize a new repository, website-builder project, duplicate Web App, second Core, second broker gateway or second identity product.

The existing `apps/web`, `apps/api`, `omni_cio` Core and accepted migration/reuse contracts remain the implementation basis unless an owning WP proves a concrete change is required.

## 17. Safety invariants retained

Unless an owning later accepted WP explicitly changes them, retain:

- protected V9 `app:app` production/recovery baseline;
- `trading_methods=false`;
- `REAL_TRADING_ENABLED=false`;
- no transfer/withdrawal authority;
- no margin/leverage/uncovered short;
- no broker secret/private portfolio/full account IDs in GitHub/CI/artifacts;
- protected V9 rollback;
- one current WP at a time;
- exact-head applicable all-GREEN merge law;
- post-merge Regression Shield before accepted authority/status progression.

## 18. Precedence

After merge this amendment supersedes conflicting earlier assumptions in amendments #5, #6, #7 and current WP22A planning where they require:

- final Personal-Node/private-home production hosting;
- permanent public multi-user disablement;
- paid trial/subscription entitlement for initial access;
- central infrastructure being forbidden from approved hosted tenant-private state;
- OWNER-only product authentication as the final Web path.

All non-conflicting safety, identity, tenant-isolation, broker-separation, legal, recovery, migration and engineering-quality requirements remain binding.