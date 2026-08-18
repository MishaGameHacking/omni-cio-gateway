# Omni-CIO V10 — WP22A Execution Contract

Status: **PLANNING HOLD / CORRECTED PUBLIC-HOSTED TARGET / FUNCTIONAL IMPLEMENTATION MUST NOT RESUME UNTIL PLANNING PR ACCEPTED**  
Owning package: **WP22A — External Web Access / Product Authentication Security Gate**

## 1. Authority and sequencing

- Block: E — Web Platform.
- WP: WP22A.
- Accepted V10 implementation progress: 40%.
- WP16–WP22: COMPLETE.
- WP22A: CURRENT / NOT COMPLETE.
- WP23+: LOCKED.
- Current planning correction: Product USER separation + Public Free Multi-User Hosted Runtime.

The earlier accepted Phase-A OWNER/clientless implementation remains historical/dormant engineering evidence. It is **not** final product authority where it assumes Cloudflare OWNER identity, an OWNER-only product session, Lenovo/home origin or permanent public-multi-user disablement.

No functional WP22A code/provider mutation begins while the current planning correction is unaccepted.

## 2. Corrected purpose

WP22A must establish the security and deployment boundary for the eventual **public multi-user hosted Omni-CIO Web product**.

The final normal USER path is:

`ordinary Internet browser -> public HTTPS/edge -> approved managed-cloud Omni-CIO Web/API -> Telegram/VK product auth -> OmniCIOUserAccount -> Tenant -> tenant-scoped state`

The final public path must not depend on PROJECT OWNER home public IP, Wi-Fi/router/LAN, home Internet/power or Lenovo as production origin.

The PROJECT OWNER uses this exact same USER path when acting as a customer. GitHub/cloud-provider/Windows/CI authority is engineering authority, not product authentication.

## 3. Explicit non-goals during WP22A

WP22A must not:

- implement WP23 Telegram Bot Foundation early;
- implement AI/Cortex WPs early;
- enable Real execution;
- add transfer/withdrawal/margin/short authority;
- create a second website, Core, identity system, database source of truth or broker stack;
- treat Cloudflare/GitHub/provider identity as Omni-CIO USER identity;
- make a global/shared USER broker credential;
- claim T-Invest public-service permission that has not been obtained;
- require OWNER home infrastructure for public production;
- silently select/purchase a new paid provider outside the service-selection/budget process.

## 4. Reuse baseline

Reuse accepted V10 components rather than rewrite them:

- `apps/web` — accepted WP16–WP22 Web App;
- `apps/api` — accepted Web/API composition;
- `omni_cio` deterministic Core/contracts;
- PostgreSQL server-side session model;
- accepted tenant/session authorization semantics;
- accepted Web broker-provisioning concept, generalized to hosted tenant-scoped secret custody;
- WP18–WP22 product services and browser contracts;
- existing security/CSRF/Host/session/rate-limit patterns where semantically valid;
- GitHub exact-head/all-GREEN/Regression-Shield governance;
- protected V9 `app:app` baseline and rollback until responsible cutover.

Do not retain an accepted implementation merely because it exists if its OWNER/home-specific assumption conflicts with the newer amendments. Rework the smallest necessary boundary while preserving reusable security controls.

## 5. Production-hosting requirement

Final public production must use an **approved managed-cloud runtime** selected by `V10_WP22A_SERVICE_SELECTION.md` under the Public Free Multi-User Hosted Runtime amendment.

Required properties include:

- ordinary Internet reachability through a public HTTPS hostname;
- no OWNER home/Lenovo availability dependency;
- reviewed region/data-location and legal suitability;
- durable tenant-aware PostgreSQL/private-state storage;
- encrypted secret storage/protection for tenant broker credentials;
- encrypted backup/restore and replacement-runtime recovery;
- least-privilege runtime/service identities;
- source-controlled GitHub deployment/IaC/release provenance;
- monitoring/incident/rollback;
- bounded capacity/load/abuse controls;
- cost and exit/lock-in analysis.

Cloudflare may remain DNS/TLS/WAF/DDoS/edge/origin-protection infrastructure. A Tunnel from cloud edge to a managed-cloud origin may be valid if selected; a Tunnel whose sole production origin is OWNER home Lenovo is not.

## 6. Product authentication and session boundary

Ordinary product identity:

`Telegram Login or VK ID -> verified external identity binding -> OmniCIOUserAccount -> Tenant -> server-side Session`

Rules:

- Cloudflare Access/GitHub/provider account membership never mints/selects a product tenant;
- USER/tenant scope is derived only from authenticated server-side session context;
- session identifiers are opaque/high entropy;
- production cookies are Secure, HttpOnly, appropriately SameSite/host/path scoped;
- session fixation protection and rotation are mandatory;
- bounded idle/absolute lifetime is mandatory;
- logout and revoke-all-sessions are mandatory;
- credentials/session tokens are not stored in browser Web Storage;
- account linking cannot auto-merge by display name/phone/email/avatar.

PROJECT OWNER acceptance must exercise the same USER product-auth/session code path as a normal user.

## 7. Tenant isolation

Public activation requires structural tenant isolation, not UI convention.

Mandatory controls:

- every private durable object carries/is strongly related to tenant scope;
- API ignores client-supplied user/tenant selectors as authority;
- object ID alone never grants access;
- PostgreSQL row-level isolation or equivalent reviewed database-enforced policy supplements application authorization;
- cross-tenant foreign-key/uniqueness rules prevent rebinding;
- jobs/queues/checkpoints carry immutable tenant scope;
- caches/RAG/AI memory/audit/notifications/exports/backups preserve tenant scope;
- restore/recovery cannot collapse tenant boundaries.

Mandatory negative evidence includes IDOR, cross-tenant object references, stale sessions, cache-key collision, job-scope confusion, backup/restore leakage and AI/RAG cross-scope leakage.

## 8. Tenant broker-secret boundary

Canonical ownership:

`USER -> Tenant -> BrokerConnection -> READ / TRADE_OPTIONAL -> verified broker accounts`

Normal Web provisioning rules:

- USER enters/replaces/revokes only that tenant's credential;
- submit only over reviewed HTTPS;
- raw secret never returned after submission;
- no browser Web Storage;
- no GitHub/CI/log/artifact secret material;
- approved encryption-at-rest / cloud secret boundary;
- least-privilege runtime decryption;
- Cortex, frontend, ordinary CI and unrelated tenant cannot access raw secret;
- no shared/global user READ/TRADE credential.

Optional TRADE credential remains separately gated. Same-tenant exact account intersection remains:

`EXECUTABLE_ACCOUNTS = VERIFIED_READ_ACCOUNTS ∩ VERIFIED_TRADE_ACCOUNTS`

This contract does not enable broker write or Real execution.

## 9. Public Web request security

The selected public architecture must prove at minimum:

- public TLS with exact certificate/hostname lifecycle;
- trusted reverse-proxy chain and explicit forwarded-protocol trust boundary;
- Host allowlist / anti-host-header abuse;
- HSTS;
- CSRF protection and exact Origin/Referer validation on unsafe requests;
- CORS deny-by-default;
- login/session/API abuse and rate limits;
- no cache of private responses where unsafe;
- strict security headers/CSP appropriate to accepted frontend;
- direct API calls without valid USER session/tenant authorization fail closed;
- stolen/expired/revoked session behavior;
- no hidden edge-identity bypass;
- provider/origin secrets unavailable to arbitrary PR code.

OWASP ASVS-relevant controls remain part of the review/evidence basis where applicable.

## 10. Free initial launch boundary

Initial USER product access is planned as free:

- `BILLING_ENABLED=false`;
- `TRIAL_ENABLED=false`;
- `SUBSCRIPTION_ENFORCEMENT=false`;
- `PREMIUM_FEATURE_GATING=false`.

No payment method is required for initial registration/login and no subscription expiry disables ordinary features.

Future monetization is `DEFERRED_OPTIONAL`. WP22A must not add billing simply because the older commercial amendment described trial/subscriptions.

Payment/KKT implementation is not an initial-free-launch prerequisite. Privacy/security/broker/regulatory/production legal gates remain applicable.

## 11. T-Invest broker-terms boundary

Public Omni-CIO account/Web activation and public T-Invest-backed production features are separate gates.

Current official T-Invest documentation says ordinary client API access does not permit a public service with data retransmission. Therefore:

- user-supplied token is not proof of public-service permission;
- public T-Invest connector remains fail-closed pending explicit contractually valid permission or accepted compliant design;
- no UI/status may represent the broker gate as passed before evidence exists;
- the public account/Web platform can be developed/tested without falsely enabling broker-backed public functionality.

## 12. Provider and secret authority

Source-controlled provider configuration contains only non-secret declarations/placeholders.

Never commit/log/artifact cloud-provider API tokens/keys, tunnel/runtime tokens, Telegram/VK secrets, encryption/recovery keys, broker READ/TRADE credentials, full broker account IDs or private portfolio/database payloads.

Privileged provider mutation can occur only from an explicitly reviewed accepted-main workflow/operations boundary after its own source PR is accepted. Provider engineering identity cannot become a product session.

## 13. Recovery and availability

Before public activation, the selected architecture must prove:

- application restart/redeploy without OWNER home access;
- database/private-state backup/restore;
- hash/integrity verification and corrupt-backup rejection;
- encrypted off-runtime backup/recovery where required;
- secret/key rotation/recovery;
- replacement runtime recovery;
- rollback to last accepted release;
- tenant isolation after restore;
- monitoring that distinguishes application, cloud-provider and external broker/provider degradation;
- no ordinary public-user outage solely because Lenovo is powered off or OWNER home Internet is unavailable.

## 14. Planning-to-implementation transition

The current planning PR must first complete:

1. exact-head applicable CI all `success`;
2. full diff and authority review;
3. zero unresolved blockers;
4. squash merge with exact-head guard;
5. exact new `main` verification;
6. required post-merge Regression Shield `success`.

Only after that acceptance may a fresh WP22A implementation branch be created from the exact accepted main.

## 15. Corrected WP22A implementation phases

After planning acceptance, implementation should proceed as focused increments inside the same WP22A sequence, without mixing later WPs:

1. **Service/hosting architecture decision** — select managed-cloud origin and edge/data/secret boundaries; no real secrets in PR.
2. **Product-auth / tenant-security correction** — remove OWNER edge-identity product-session assumptions and prove USER session/tenant isolation.
3. **Hosted runtime/data/secret/recovery implementation** — source-controlled runtime/IaC/deployment/backup design with dormant secrets.
4. **Protected provider bootstrap/apply** — only from accepted main after reviewed privileged boundary exists.
5. **Public-hosted acceptance** — real HTTPS, normal USER login/logout/session, tenant isolation, availability/recovery, abuse controls and sanitized OWNER acceptance where non-delegable.
6. **Broker/legal activation decisions** — public T-Invest-backed features remain separately fail-closed until permission; personalized investment functionality remains subject to regulatory/legal gate.
7. **WP22A status closeout** — only after all required Exit-Gate evidence and post-merge verification.

No phase grants WP23 authority early.

## 16. Exit Gate

WP22A is COMPLETE only when the **corrected public-hosted product architecture**, not the historical OWNER-home Phase A, is accepted with code/tests/CI/security/recovery/provider/legal/broker/capacity evidence required by the active amendments.

Until then:

- `PUBLIC_MULTI_USER_ENABLED=false`;
- no accepted public production activation;
- no broker-write/Real expansion;
- WP23+ remains LOCKED;
- protected V9 rollback remains available.
