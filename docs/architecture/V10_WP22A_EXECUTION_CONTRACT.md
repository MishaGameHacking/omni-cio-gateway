# Omni-CIO V10 — WP22A Execution Contract

> **Amendment 18 CURRENT-AUTHORITY OVERRIDE (2026-09-21): HISTORICAL / SUPERSEDED FOR CURRENT PROVIDER AND LOGIN AUTHORITY.** This file preserves accepted WP22A provenance and security evidence. Any “CURRENT”, Cloud.ru, Cloudflare, Render, Neon, Telegram/VK or phase-selection wording below describes the authority state at the time of that historical WP22A work and must not be used as the current V10 provider template. Current authority is ChatGPT + GitHub + Timeweb Cloud + Telegram Login, with VK ID retired and public activation fail-closed until its Timeweb/Telegram gates pass.


Status: **HISTORICAL / SUPERSEDED BY AMENDMENT 18 FOR CURRENT PROVIDER/LOGIN AUTHORITY**  
Historical accepted WP22A status: **CURRENT / CORRECTED PUBLIC-HOSTED TARGET / PHASE 1 ACCEPTED / PHASE 2 ACCEPTED / PHASE 3 AUTHORIZED**  
Owning package: **WP22A — External Web Access / Product Authentication Security Gate**

## 1. Authority and sequencing

- Block: E — Web Platform.
- WP: WP22A.
- Accepted V10 implementation progress: 40%.
- WP16–WP22: COMPLETE.
- WP22A Phase 1: ACCEPTED.
- WP22A Phase 2: ACCEPTED.
- WP22A Phase 3: CURRENT / AUTHORIZED.
- WP22A overall: NOT COMPLETE.
- WP23+: LOCKED.
- Accepted planning authority: Product USER separation + Public Free Multi-User Hosted Runtime.

The earlier accepted Phase-A OWNER/clientless implementation remains historical/dormant engineering evidence. It is **not** final product authority where it assumes Cloudflare OWNER identity, an OWNER-only product session, Lenovo/home origin or permanent public-multi-user disablement.

The corrected planning prerequisite was satisfied by PR #329 merged to exact `main` `5f535c0ced9514866bd3680042f3ba0bb012f866` plus post-merge Regression Shield #1503 / run `32129304332` SUCCESS with both required jobs GREEN.

WP22A Phase 1 service/hosting architecture decision is accepted through PR #333, exact main `51dbe41ad1e63ddb4c0b101f573b70254a5255b8`, plus Regression Shield #1505 SUCCESS. Phase 1 selected **Cloud.ru Evolution** as the managed-cloud production provider/security boundary while preserving current recurring OWNER infrastructure authorization at **0 RUB/month** and keeping provider apply disabled.

WP22A Phase 2 product-auth / tenant-security correction is accepted through PR #336, exact main `00fc692710aa9eaf02ca78ea0535b51600020768`, plus Regression Shield #1508 / run `32277165957` attempt 2 SUCCESS with both required jobs GREEN. The first run attempt was RED because `pip-audit` timed out reading `api.osv.dev`; acceptance remained blocked until the same exact-main security job was re-run without source changes and completed dependency audit, SAST and tracked-content secret scan successfully.

Therefore **Phase 3 — Hosted runtime/data/secret/recovery implementation** is the current authorized source increment after this transition is accepted.

This does not authorize public production activation, privileged provider mutation, a paid-provider purchase, broker-write expansion or WP23 work.

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

Telegram Login integration owned by WP22A product authentication is not WP23 Telegram Bot implementation and must stay limited to the authentication/session boundary required by this gate.

## 4. Reuse baseline

Reuse accepted V10 components rather than rewrite them:

- `apps/web` — accepted WP16–WP22 Web App;
- `apps/api` — accepted Web/API composition;
- `omni_cio` deterministic Core/contracts;
- accepted Phase-2 product identity/session/tenant boundary;
- PostgreSQL server-side session model and accepted tenant RLS direction;
- accepted Web broker-provisioning concept, generalized to hosted tenant-scoped secret custody;
- WP18–WP22 product services and browser contracts;
- existing security/CSRF/Host/session/rate-limit patterns where semantically valid;
- existing WP10/WP13 recovery and PostgreSQL migration/rehearsal patterns where compatible with hosted tenant scope;
- GitHub exact-head/all-GREEN/Regression-Shield governance;
- protected V9 `app:app` baseline and rollback until responsible cutover.

Do not retain an accepted implementation merely because it exists if its OWNER/home-specific assumption conflicts with newer amendments. Rework the smallest necessary boundary while preserving reusable security controls.

## 5. Production-hosting requirement

Final public production must use the **Cloud.ru Evolution managed-cloud boundary selected by accepted Phase 1** under `V10_WP22A_SERVICE_SELECTION.md` and the Public Free Multi-User Hosted Runtime amendment.

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

The accepted cost sequence remains:

`already owned / open source / safe free tier / grant / bonus -> lowest-cost safe paid option -> scale only from measured need`

Current recurring OWNER infrastructure authorization remains **0 RUB/month**. No provider apply is authorized merely because Phase 1 selected the final production boundary or because Phase 3 creates source configuration.

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
- account linking cannot auto-merge by display name/phone/email/avatar;
- external provider subject identity is mapped to an internal Omni-CIO account binding rather than used directly as a tenant identifier;
- PROJECT OWNER engineering/provider identity cannot bypass the ordinary USER product-auth path.

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

Mandatory negative evidence includes IDOR, cross-tenant object references, stale sessions, cache-key collision, job-scope confusion, backup/restore leakage and later AI/RAG cross-scope leakage.

Phase 2 accepted the identity/session/broker persistence isolation correction. Phase 3 must extend that tenant boundary through hosted private state, backup/restore and recovery source contracts without widening authority.

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

Phase 3 may define and test the encrypted secret-custody interface using placeholders/synthetic fixtures only. Real broker/provider secret values are not Phase-3 source inputs.

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

Phase 3 owns source-controlled runtime/edge trust declarations required for later activation. Actual public ingress, real certificate issuance and DNS/provider mutation remain later-phase actions.

## 10. Free initial launch boundary

Initial USER product access is planned as free:

- `BILLING_ENABLED=false`;
- `TRIAL_ENABLED=false`;
- `SUBSCRIPTION_ENFORCEMENT=false`;
- `PREMIUM_FEATURE_GATING=false`.

No payment method is required for initial registration/login and no subscription expiry disables ordinary features.

Future monetization is `DEFERRED_OPTIONAL`. WP22A must not add billing simply because older commercial planning described trial/subscriptions.

Payment/KKT implementation is not an initial-free-launch prerequisite. Privacy/security/broker/regulatory/production legal gates remain applicable.

## 11. T-Invest broker-terms boundary

Public Omni-CIO account/Web activation and public T-Invest-backed production features are separate gates.

Current accepted planning authority records that ordinary client API access does not permit a public service with data retransmission. Therefore:

- user-supplied token is not proof of public-service permission;
- public T-Invest connector remains fail-closed pending explicit contractually valid permission or accepted compliant design;
- no UI/status may represent the broker gate as passed before evidence exists;
- the public account/Web platform can be developed/tested without falsely enabling broker-backed public functionality.

## 12. Provider and secret authority

Source-controlled provider configuration contains only non-secret declarations/placeholders.

Never commit/log/artifact cloud-provider API tokens/keys, tunnel/runtime tokens, Telegram/VK secrets, encryption/recovery keys, broker READ/TRADE credentials, full broker account IDs or private portfolio/database payloads.

Privileged provider mutation can occur only from an explicitly reviewed accepted-main workflow/operations boundary after its own source PR is accepted. Provider engineering identity cannot become a product session.

**Phase 3 is source-only with dormant provider credentials.** It may create reviewed IaC/deployment/configuration and tests but must not apply Cloud.ru resources, create public DNS/ingress, spend money or require real provider secrets.

## 13. Hosted data, recovery and availability

Before public activation, the selected architecture must prove:

- application restart/redeploy without OWNER home access;
- durable tenant-aware PostgreSQL/private-state backup/restore;
- hash/integrity verification and corrupt-backup rejection;
- encrypted off-runtime backup/recovery where required;
- tenant-scoped secret/key rotation/recovery;
- replacement runtime recovery;
- rollback to last accepted release;
- tenant isolation after restore;
- monitoring that distinguishes application, cloud-provider and external broker/provider degradation;
- no ordinary public-user outage solely because Lenovo is powered off or OWNER home Internet is unavailable.

Phase 3 owns the source model and deterministic rehearsals that can be proven without real provider credentials. Phase 4 owns protected provider bootstrap/apply. Phase 5 owns deployed public-hosted acceptance and real recovery/availability evidence that cannot be synthesized offline.

## 14. Accepted prerequisites and evidence

### Corrected planning transition

1. PR #329 final exact-head applicable CI completed `success`;
2. full diff/authority review completed with zero unresolved blockers;
3. PR #329 was squash-merged to exact `main` `5f535c0ced9514866bd3680042f3ba0bb012f866`;
4. post-merge Regression Shield #1503 / run `32129304332` completed `success`;
5. both required post-merge jobs completed `success`.

### WP22A Phase 1 service/hosting decision

1. PR #333 final head `595c7fb2924de71812d8f28b70230fca8089632f` completed the applicable exact-head DRAFT and fresh READY cycles with all applicable checks `success`;
2. full diff/review completed with zero unresolved blocking threads;
3. PR #333 was squash-merged to exact `main` `51dbe41ad1e63ddb4c0b101f573b70254a5255b8`;
4. Regression Shield #1505 on that exact main completed SUCCESS with both required jobs SUCCESS;
5. accepted production provider/security boundary is **Cloud.ru Evolution**;
6. `provider_apply_authorized=false`, current recurring OWNER infrastructure authorization remains `0 RUB/month`, and `PUBLIC_MULTI_USER_ENABLED=false`.

### WP22A Phase 2 product-auth / tenant security

1. PR #336 final exact head `d3bc7b03b0ba589877e771ffe77bdd31e3d2a100` completed required DRAFT and fresh READY cycles with all applicable checks `success`;
2. supplemental Linux governance and PostgreSQL lanes completed `success`;
3. final 20-file Phase-2 diff review completed with zero unresolved blocking threads;
4. PR #336 was squash-merged to exact `main` `00fc692710aa9eaf02ca78ea0535b51600020768`;
5. post-merge Regression Shield #1508 / run `32277165957` attempt 1 was RED because the external OSV API read timed out; acceptance remained blocked;
6. only the failed security job was re-run on the same exact main SHA, consistent with GitHub re-run semantics; no source/check weakening occurred;
7. run attempt 2 completed `success` with both required jobs `success`:
   - `Quality, contracts and coverage`;
   - `Dependency, code and secret security`;
8. Phase-2 implementation retains `PUBLIC_MULTI_USER_ENABLED=false`, V9 `app:app`, `trading_methods=false`, `REAL_TRADING_ENABLED=false`, no provider apply and no WP23 authority.

This evidence accepts Phase 2 and authorizes the Phase-3 source increment. It does not satisfy hosted provider apply or public-production acceptance gates.

## 15. Corrected WP22A implementation phases

Implementation proceeds as focused increments inside the same WP22A sequence, without mixing later WPs:

1. **Service/hosting architecture decision — ACCEPTED**  
   Cloud.ru Evolution selected as managed-cloud production/security boundary under staged free-first cost discipline. No provider apply occurred.
2. **Product-auth / tenant-security correction — ACCEPTED**  
   Verified external identity -> internal account -> tenant -> server-side session semantics and required broker persistence/RLS isolation correction accepted through PR #336 + Regression Shield #1508 attempt 2 SUCCESS.
3. **Hosted runtime/data/secret/recovery implementation — CURRENT / AUTHORIZED**  
   Source-controlled runtime/IaC/deployment/private-state/secret/recovery design and deterministic rehearsals with dormant provider secrets only.
4. **Protected provider bootstrap/apply — LOCKED until Phase 3 acceptance and required OWNER/provider authorization**  
   Apply only from accepted main after reviewed privileged boundary exists.
5. **Public-hosted acceptance — LOCKED**  
   Real HTTPS, normal USER login/logout/session, tenant isolation, availability/recovery, abuse controls and sanitized OWNER acceptance where non-delegable.
6. **Broker/legal activation decisions — LOCKED / separately fail-closed**  
   Public T-Invest-backed features remain fail-closed until permission; personalized investment functionality remains subject to regulatory/legal gate.
7. **WP22A status closeout — LOCKED**  
   Only after all required Exit-Gate evidence and post-merge verification.

No phase grants WP23 authority early.

## 16. Phase-2 accepted boundary

Phase 2 is accepted on exact main `00fc692710aa9eaf02ca78ea0535b51600020768` with the required post-merge Regression Shield GREEN. Its accepted boundary includes:

- no Cloudflare/GitHub/provider engineering identity can mint/select an Omni-CIO USER tenant;
- verified Telegram/VK external identity abstractions bind to an internal Omni-CIO account rather than directly to tenant authority;
- account/tenant scope comes exclusively from server-side session resolution;
- session creation/rotation/expiry/logout/revoke-all remain fail-closed;
- historical OWNER-only session/broker persistence assumptions required for multi-user support are replaced without weakening scope FKs/uniqueness or V9 rollback;
- broker connection CRUD remains tenant-scoped and cross-tenant object IDs fail closed;
- no client-supplied `user_id` / `tenant_id` acts as authorization;
- deterministic IDOR/cross-tenant/session negatives cover the changed boundary;
- no real external-provider or broker secret enters GitHub/CI/artifacts;
- `PUBLIC_MULTI_USER_ENABLED=false`, `app:app`, `trading_methods=false`, `REAL_TRADING_ENABLED=false` and WP23 lock remain intact.

## 17. Phase-3 acceptance boundary

Phase 3 may be accepted only when exact source/tests/CI prove, at minimum:

- one source-controlled hosted runtime/deployment/IaC model for the accepted Cloud.ru Evolution boundary; no parallel website/runtime stack;
- provider apply remains dormant and impossible without an explicit later privileged path/authorization;
- hosted PostgreSQL/private state is tenant-aware and uses a least-privilege runtime role compatible with accepted Phase-2 database isolation;
- real provider/broker/recovery keys are not present in source, CI, artifacts, logs or test fixtures;
- tenant broker-secret custody has an explicit encrypted storage interface, least-privilege runtime access and cross-tenant negative tests using synthetic material only;
- backup/restore rehearsal verifies hashes/integrity, rejects corrupt backups and preserves tenant isolation;
- replacement-runtime recovery and rollback are source-controlled/rehearsable without OWNER home infrastructure;
- public-edge/proxy/Host/TLS trust assumptions are source-controlled and fail closed while actual public ingress remains off;
- observability/incident contracts distinguish application, provider and external broker/auth degradation without leaking private data;
- capacity/cost declarations preserve the accepted free-first sequence and do not authorize paid spend;
- `PUBLIC_MULTI_USER_ENABLED=false`, `app:app`, `trading_methods=false`, `REAL_TRADING_ENABLED=false`, protected V9 rollback and WP23 lock remain intact;
- exact-head applicable CI and required post-merge Regression Shield complete GREEN.

Real Cloud.ru credentials/resources, real Telegram/VK credentials, public DNS/HTTPS activation and OWNER browser acceptance are not Phase-3 source-acceptance prerequisites. They belong to later phases and must not be synthesized.

## 18. WP22A Exit Gate

WP22A is COMPLETE only when the **corrected public-hosted product architecture**, not the historical OWNER-home Phase A, is accepted with code/tests/CI/security/recovery/provider/legal/broker/capacity evidence required by the active amendments.

Until then:

- `PUBLIC_MULTI_USER_ENABLED=false`;
- no accepted public production activation;
- no broker-write/Real expansion;
- WP23+ remains LOCKED;
- protected V9 rollback remains available.