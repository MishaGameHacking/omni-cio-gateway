# Omni-CIO V10 — Timeweb-Only Platform Consolidation & Telegram-Only Login Authority / Amendment 18

**Status:** OWNER-APPROVED / EFFECTIVE ONLY WHEN ACCEPTED ON PROTECTED `main`  
**OWNER decision:** 2026-09-21  
**Scope:** Russia-only V10 platform consolidation, Timeweb production authority, Telegram-only human login, and legacy-provider retirement  
**Product progress effect:** NONE by itself  
**Runtime mutation effect:** NONE by itself  
**Owning dashboard:** issue #580  
**Database migration dashboard:** issue #559  
**Telegram activation dashboard:** issue #549

## 1. Final service model

The OWNER selects the following target service model for current/future V10:

1. **ChatGPT** — engineering assistant only; never runtime/data authority.
2. **GitHub** — source, review, CI/check provenance and exact-SHA release authority.
3. **Timeweb Cloud** — the single selected production infrastructure provider for V10 Web/API runtime, PostgreSQL, domain/DNS, TLS, network controls, backups and monitoring.
4. **Telegram Login** — the only selected human product login provider.

No other general-purpose hosting, database, edge, identity or CI SaaS belongs in the final V10 operating stack.

## 2. Provider retirement direction

For current/future active V10 authority, this Amendment supersedes conflicting provider-selection language in Amendments 14/15 and the earlier draft of Amendment 18:

- Cloudflare — OWNER reports its external account/resources/domain zone/secrets were manually decommissioned on 2026-09-21; treat Cloudflare as unavailable for rollback and grant no new authority;
- Neon — OWNER reports its project/organization/API keys/account were manually decommissioned on 2026-09-21; treat Neon as unavailable for rollback and grant no new authority;
- Render — RETIRE from active V10; protected legacy runtime retires only after its owning parity/decommission gate;
- Cloud.ru — RETIRED / no return;
- VK ID — RETIRED from product authentication; no public VK login path;
- SonarCloud/Gitar/other external CI-review SaaS — RETIRE from required active verification once equivalent-or-stronger GitHub-executed checks are accepted.

Historical accepted commits, PRs and evidence remain facts of repository history. They do not remain current provider authority.

A retired provider may return only through a fresh explicit OWNER-approved amendment.

## 3. Archive-in-place rule

The OWNER explicitly does **not** authorize mass repository cleanup or deletion of historical provider files.

Cloudflare/Neon/Render/Cloud.ru/VK/external-CI artifacts may remain in their existing repository locations as project memory and compatibility evidence. They are treated as **ARCHIVE-IN-PLACE**:

- no new feature work may depend on them;
- they do not define current/future platform authority;
- they may not be used as templates for new V10 implementation;
- their active workflow triggers, required-check role, provider secrets and external resources may be disabled/revoked only after the owning replacement/cutover gate;
- a historical artifact is modified only when required to keep repository checks consistent with the new current authority, not for cosmetic cleanup;
- current guidance must clearly point engineers to Timeweb/Telegram paths instead.

Protected Git history is never force-rewritten merely to erase provider names. Historical PR/SHA provenance remains intact.

Provider-side physical media erasure cannot be asserted by repository code. The project can prove resource deletion, credential revocation and loss of active authority, not undocumented provider retention.

## 4. One canonical product

Omni-CIO remains one Web/API product with one account/session/tenant model.

- React/Vite Web remains the canonical frontend.
- FastAPI/Python product API remains the canonical backend unless a separately accepted architecture change proves otherwise.
- Product identity, tenant authority, PostgreSQL persistence, financial logic and security controls remain provider-neutral.
- Timeweb-specific behavior stays in thin deployment/infrastructure adapters.
- Browser input can never select tenant or privileged infrastructure identity.
- No second frontend, account system, session authority or temporary product is allowed.

## 5. Timeweb App Platform

Timeweb App Platform is the selected public V10 application platform.

Release flow:

`accepted GitHub main SHA -> GitHub verification -> exact Timeweb candidate -> health/release proof -> production promotion`.

Requirements:

- repository `MishaGameHacking/omni-cio-gateway`;
- explicit accepted `main` commit;
- Dockerfile/Compose or supported backend mode only after repository tests prove the exact runtime;
- production autodeploy must never bypass GitHub acceptance;
- runtime secrets stay in Timeweb environment/secret custody, never Git;
- `/healthz` exposes sanitized exact release identity;
- rollback remains last-known-good until the owning legacy decommission gate.

Official Timeweb docs support Git repository integration, explicit branch/commit selection, Dockerfile/Compose deployment, environment variables and custom domains/TLS.

## 6. Timeweb PostgreSQL 18

Timeweb Managed PostgreSQL 18 is the final V10 relational authority.

Migration must preserve:

- PostgreSQL 18 semantics;
- all migrations;
- exact numeric financial storage;
- account/tenant/session persistence;
- RLS/FORCE RLS and cross-tenant negatives;
- least-privilege runtime role;
- backup/restore;
- restart/redeploy recovery;
- deterministic migrated-data verification.

No new Neon feature work is authorized. The OWNER-reported external Neon decommission means Neon is no longer an available rollback target. Timeweb PostgreSQL migration/recovery evidence must therefore stand on its own; provider-side physical erasure is not independently provable from GitHub.

## 7. Network / DNS / Russia reachability

Final ordinary-user path:

`Russian user -> OWNER-confirmed canonical domain -> Timeweb public ingress -> Omni-CIO -> Timeweb PostgreSQL`.

Cloudflare is no longer an available final hop or rollback provider.

A domain-authority mismatch is currently fail-closed: accepted repository/Telegram evidence uses `omnicio.ru`, while OWNER-supplied Cloudflare screenshots show deletion of the zone `omni-cio.ru`. These are distinct domain names. No Timeweb canonical DNS cutover or Telegram production-origin mutation may occur until the OWNER confirms which registered domain is the canonical V10 domain and ownership/control is re-verified.

A technical Timeweb candidate is proven before canonical DNS cutover.

Prefer private Timeweb app-to-database networking only when the exact provider configuration is proven. If unavailable, use explicit TLS/firewall/least-privilege evidence. Never guess a trusted proxy/client-IP contract.

Representative Russian no-VPN acceptance is required before public activation.

## 8. Telegram-only human authentication

Final human auth path:

`Unauthenticated browser -> Telegram Login -> verified OIDC identity -> OmniCIOUserAccount -> Tenant -> server-side Session`.

VK ID is not a fallback and must not remain a hidden disabled session path after cleanup.

Telegram uses registered Allowed URLs/redirect URIs, Authorization Code Flow + PKCE, backend-generated state, nonce where applicable, server-side token verification and minimal scopes.

No OWNER/admin/demo/preview/developer path may mint a product session.

## 9. GitHub-only CI/review service

GitHub becomes the only active CI/review service.

Quality may not weaken while external review SaaS is retired. GitHub-executed verification must cover where applicable:

- Ruff format/lint;
- mypy;
- pytest + branch coverage;
- frontend lint/type/test/build;
- Playwright/browser checks;
- dependency and secret scans;
- repository-run SAST;
- PostgreSQL 18 integration/recovery rehearsals;
- governance/security contracts;
- full Files changed review and zero unresolved blocking threads.

External Sonar/Gitar/CircleCI/etc may be removed only after equivalent-or-stronger GitHub verification is accepted. Disabling a gate without replacement is forbidden.

## 10. Integrated System Update

The OWNER authorizes one umbrella System Update:

`TIMEWEB-PLATFORM-CONSOLIDATION-INTEGRATED`

Default implementation branch after this governance PR is accepted:

`system/timeweb-platform-consolidation`.

Ordered internal milestones:

1. **TW-A / INVENTORY_AND_AUTHORITY** — complete provider/dependency inventory and KEEP/REPLACE/RETIRE/HISTORY classification.
2. **TW-B / SOURCE_AND_RUNTIME_CONSOLIDATION** — provider-neutral runtime, Timeweb deployment source, Telegram-only auth composition, GitHub-native verification replacement; no production cutover.
3. **TW-C / TIMEWEB_APP_CANDIDATE** — exact-SHA Timeweb candidate and runtime/security acceptance.
4. **TW-D / TIMEWEB_POSTGRES_PRODUCTION_CUTOVER** — migrate and verify production PostgreSQL authority.
5. **TW-E / TIMEWEB_PUBLIC_INGRESS_DNS** — canonical domain/DNS/TLS cutover and Russia no-VPN acceptance.
6. **TW-F / TELEGRAM_PUBLIC_ACTIVATION** — real Telegram registration/public multi-user after legal/privacy/capacity gates.
7. **TW-G / LEGACY_PROVIDER_DECOMMISSION** — revoke/delete retired external provider resources/secrets and disable their active execution/required-check role while leaving historical repository artifacts archive-in-place.

One integrated source branch is the default. Amendment-12 split triggers remain stronger: DB cutover, DNS/public cutover, destructive provider deletion, security/authority transition, OWNER-only/legal/payment action and recovery boundaries require independent acceptance.

## 11. Repository archive-in-place end-state

At TW-G acceptance:

- Timeweb/Telegram/GitHub documentation is the only current/future implementation authority;
- retired provider files may remain in the current tree unchanged as historical project memory;
- retired provider workflows must not perform live deploy/provisioning/provider actions;
- retired provider checks must not remain required merge gates unless they validate provider-neutral invariants;
- retired provider secrets/tokens are revoked from active provider/GitHub environments after replacement acceptance;
- no new code imports or composes retired provider adapters into the production runtime;
- VK ID is absent from deployed product composition even if historical source/tests remain;
- external CI/review SaaS is not required after equivalent GitHub-native verification is accepted;
- historical documents may retain exact old provider terminology and PR/SHA evidence;
- no mass rename/delete is required merely to make keyword searches “clean”.

A future cleanup may remove historical files only under separate OWNER authority if there is a demonstrated maintenance/security benefit.
## 12. Cost discipline

Use Timeweb services only when required by the current accepted milestone.

- existing prepaid Timeweb funds first;
- no speculative replicas/load balancers/extra compute;
- backups/monitoring when the production/recovery gate requires them;
- exact recurring price checked before creating a paid resource;
- new top-up or materially higher commitment requires fresh OWNER approval.

## 13. Public-user legal/privacy gate

Russia-hosted infrastructure alone does not activate users.

Before the first public user, the owning legal/privacy gate must have applicable personal-data processing/notification evidence, real cross-border-flow assessment, published Privacy Policy, request channel, incident/capacity readiness and Telegram callback/provider evidence.

No passport/tax/private address/payment-card/filing credentials belong in GitHub or chat.

## 14. External financial/data providers

This Amendment governs platform/hosting/database/CI/human-login services. It does not silently activate or delete separately governed broker/market/data capabilities such as T-Invest.

Those remain capability-specific external boundaries and stay fail-closed until their own authority.

## 15. Protected invariants

Until owning gates accept transitions:

- `PUBLIC_MULTI_USER_ENABLED=false`;
- `OMNI_V10_TELEGRAM_LOGIN_ENABLED=false`;
- VK login disabled and scheduled for removal;
- broker write OFF;
- `trading_methods=false`;
- `REAL_TRADING_ENABLED=false`;
- tenant isolation/RLS/FORCE-RLS mandatory;
- no secret/private payload disclosure;
- no direct development in `main`;
- external Cloudflare/Neon rollback is unavailable by OWNER-reported decommission;
- Timeweb candidate/backup/restore evidence must be established before public activation;
- canonical DNS/Telegram origin remains blocked until the exact domain is OWNER-confirmed.

## 16. Immediate effect after acceptance

After acceptance on protected `main`:

- Amendments 14/15 remain historical Cloudflare evidence but no longer select future/current platform work;
- Amendment 17 remains the PostgreSQL migration/security foundation;
- `TIMEWEB-PLATFORM-CONSOLIDATION-INTEGRATED` becomes current authorized System Update;
- WEB-VISUAL and WP23+ remain paused;
- no new Cloudflare/Neon/Render/Cloud.ru/VK feature work is authorized except bounded compatibility/decommission/recovery work;
- historical repository files remain archive-in-place by default;
- destructive external provider deletion still requires its own gate;
- governance merge alone performs no provider mutation, data move, DNS change, activation or Real-money action.

Acceptance requires exact-head SUCCESS, zero blocking threads, squash merge and exact-new-main post-merge SUCCESS.
