# 00 — OMNI-CIO PROJECT MASTER CONTEXT

Дата актуализации: 2026-08-29

Этот файл хранит долгоживущий контекст проекта. Динамический прогресс/current package всегда берётся только из `knowledge/17_V10_CURRENT_PROGRAM_STATUS.md`.

## 1. Project identity

Canonical repository: `MishaGameHacking/omni-cio-gateway`.

Omni-CIO — один investment platform/product line. Защищённый V9 остаётся production/recovery baseline, V10 — единственная активная feature-development программа.

Нельзя создавать competing Gateway, competing Web product, parallel product-auth stack, competing AI/scheduler/broker/execution stack или второй пользовательский staging-продукт без отдельного OWNER-approved amendment/execution unit.

Temporary V9 compatibility/recovery entrypoint during Amendment-20 convergence: `app:app`; forward V10 source entrypoint: `apps.api.hosted_runtime:create_app`.

Protected V9 WP0–WP15 delivery is complete and remains in controlled maintenance.

## 2. Source of truth

Порядок authority для разработки:

1. актуальный protected GitHub `main`;
2. `AGENTS.md`;
3. `README.md` / `CONTRIBUTING.md`;
4. этот Master Context;
5. `knowledge/16_CURRENT_PROGRAM_STATUS.md` для V9 runtime;
6. `docs/master-plan/OMNI_CIO_V10_PROGRAM_LOCK.md`;
7. `docs/master-plan/OMNI_CIO_V10_MASTER_PLAN.md`;
8. `docs/master-plan/OMNI_CIO_V10_AMENDMENTS_INDEX.md` + все applicable active amendments;
9. machine-readable architecture/security/release contracts;
10. `docs/master-plan/OMNI_CIO_V10_WP_EXECUTION_TEMPLATE.md`;
11. `knowledge/17_V10_CURRENT_PROGRAM_STATUS.md` для dynamic progress/current execution authority;
12. current execution-unit contracts/runbooks/ledgers;
13. actual recent commits, PR/issues and GitHub Actions.

Chat memory, screenshots, old PR descriptions, Cloudflare dashboard state and historical WP evidence never override accepted `main`.

## 3. Current convenience snapshot

Omni-CIO V10 remains at **54% accepted implementation** with WP0–WP22A COMPLETE.

Amendment 18 is accepted on protected `main` through PR #581 and selects **TIMEWEB-PLATFORM-CONSOLIDATION-INTEGRATED** as the current next package.

Target operating model:

- ChatGPT — engineering assistant;
- GitHub — source/review/CI/release provenance;
- Timeweb Cloud — sole selected production infrastructure platform;
- Telegram Login — sole selected human product authentication provider.

Cloudflare, Neon, Render, Cloud.ru and VK ID are migration/decommission targets. WEB-VISUAL and WP23+ remain paused while platform consolidation/public activation is completed.

This is a convenience snapshot only; exact state remains `knowledge/17_V10_CURRENT_PROGRAM_STATUS.md`.

## 4. Current GitHub / Timeweb authority model

GitHub remains the engineering source of truth. Timeweb is the target runtime/database/domain platform. Telegram is identity only. Provider-specific infrastructure must stay outside the product core.

The accepted historical Cloudflare section below remains provenance only and is superseded for future provider selection by Amendment 18.

## 4B. Historical GitHub / Cloudflare authority model — superseded for future provider selection

GitHub is authority rank 1 for engineering:

- source code;
- protected `main`;
- Pull Requests;
- exact commit SHA;
- review/check evidence;
- accepted status/provenance;
- release source identity.

At Amendment 14 acceptance, Cloudflare Workers Paid was the historical platform rank 2 for new V10 work:

- application/edge hosting target;
- Workers/Static Assets;
- Workers Builds portable compute/verification target after CF-A proof;
- Containers for proven full-Linux/native runtime needs after CF-B evidence;
- Custom Domains/DNS/TLS;
- WAF/DDoS/rate/Turnstile security where applicable to the actual plan;
- Access for private/admin/engineering surfaces only by default;
- Hyperdrive only after database compatibility evidence;
- KV/R2/Durable Objects/Queues/Workflows when a concrete owning milestone justifies them;
- Workers AI/Vectorize only when AI/Cortex scope is authorized.

Cloudflare dashboard/provider state never overrides accepted GitHub authority.

Cloudflare infrastructure identity is not Omni-CIO product identity.

## 5. Historical provider transition boundary — superseded by Amendment 18

At Amendment 14 acceptance, the historical new-V10 deployment/release selection was:

- historical managed target at that time: `CLOUDFLARE_WORKERS_PAID`;
- Cloud.ru Evolution was no longer the selected new-V10 provider target;
- Render was no longer the active new-V10 deployment, zero-charge-attestation, hosted-release-alignment or recovery target;
- no new Render attestation refresh/provider mutation was required;
- accepted WP22A Render + Neon evidence remains historical evidence and must not be rewritten;
- V9 Render/app:app remains a temporary recovery/migration boundary only until its V9C-C/V9C-D replacement, zero-consumer and recovery gates.

Historically, Amendment 14 selected the Cloudflare platform and Amendment 15 grouped its four stages into one `INTEGRATED_SYSTEM_UPDATE`. Amendment 18 supersedes that provider model for all current/future V10 work.

Neither governance amendment by itself:

- clicks/deploys Cloudflare;
- mutates DNS/domain;
- creates API tokens/secrets;
- activates public users;
- migrates Neon/PostgreSQL;
- provisions Telegram/VK provider secrets;
- authorizes Real money.

## 6. Historical Cloudflare integrated implementation sequence — superseded by Amendment 18

After Amendment 15 acceptance, the historical delivery model executed one integrated update:

`CLOUDFLARE-PUBLIC-PRODUCT-INTEGRATED`

Default branch:

`system/cloudflare-public-product`

Ordered internal milestones:

1. `CF-A / CLOUDFLARE-BUILDS-VERIFIER-INTEGRATION` — repository-side portable build/check integration, shard/impact/provenance/cost guards; no candidate/public promotion;
2. `CF-B / CLOUDFLARE-RUNTIME-COMPATIBILITY` — React/Vite/backend/native dependency/PostgreSQL/Hyperdrive/Containers compatibility evidence/config;
3. `CF-C / CLOUDFLARE-CANDIDATE-DEPLOYMENT` — immutable candidate provider mutation only after prior internal gates;
4. `CF-D / CLOUDFLARE-PUBLIC-CUTOVER` — canonical domain/DNS/TLS/security/promotion/rollback and capability-specific live-user acceptance.

Do not start milestone N+1 before milestone N's branch-local Exit Gate passes. A separate `main` merge between these four milestones is no longer required by Amendment 15. A real DB/security/OWNER/live/cutover/Real-money/reviewability split trigger discovered during implementation still forces a stop/split; the integrated branch is never a bypass.

## 7. Current continuous public release model — GitHub to Timeweb

V10 is not a monolithic “finish 100%, then show users” program.

Every accepted protected `main` SHA is a new whole-product revision **candidate**. It is not an automatic production deployment.

Required release path:

`exact-head PR GREEN/review -> squash merge -> exact-main post-merge GREEN -> exact Timeweb candidate -> candidate acceptance -> production promotion`.

Before promotion, current `main` is rechecked. A superseded candidate is not promotable.

If a newer `main` is blocked, production remains last-known-good and reports `UPDATE_PENDING`, `DEPLOYMENT_BLOCKED` or `OUT_OF_SYNC` instead of silently drifting.

Current release identity must bind the exact accepted source SHA to the accepted Timeweb candidate/deployment identity and release status defined by the owning Timeweb gate. No source-code version-bump commit is made only to change the displayed public version.

Timeweb rollback/recovery must preserve last-known-good application and PostgreSQL compatibility; deployment rollback never substitutes for database backup/restore evidence.

## 8. Public product / identity model

One canonical public Omni-CIO Web is the target.

PROJECT OWNER is an ordinary product USER, not a product superuser.

Canonical human product identity remains:

`Telegram Login -> verified identity -> OmniCIOUserAccount -> Tenant -> server-side Session`.

`WP22A — External Web Access / Product Authentication Security Gate` is technically COMPLETE, but real provider/public runtime activation remains capability-specific.

Tenant scope must be server-derived. PostgreSQL RLS/FORCE-RLS and cross-tenant negatives remain mandatory regardless of the outer infrastructure provider.

Historical Cloudflare Access/WAF/Turnstile could protect infrastructure/browser surfaces but never minted or selected an Omni-CIO tenant; current Timeweb ingress must preserve the same product-authority boundary.

## 9. Progressive capability activation

Amendment 13 activation states are exactly:

`IMPLEMENTED | LIVE_OPERABLE | BLOCKED_EXTERNAL | REAL_MONEY_AUTHORIZED`.

A completed capability may become `LIVE_OPERABLE` when all its own technical/security/external gates pass; unrelated later V10 blocks are not a valid artificial blocker.

Current public-facing activation remains fail-closed where evidence is missing:

- Telegram Login — `BLOCKED_EXTERNAL`;
- public multi-user tenant access — `BLOCKED_EXTERNAL`;
- VK ID — retired from current/future deployed product composition under Amendment 18;
- T-Invest READ — `BLOCKED_EXTERNAL` / `FAIL_CLOSED_PENDING_BROKER_TERMS_PERMISSION`.

`PUBLIC_MULTI_USER_ENABLED=false` is current runtime state, not a permanent V10-wide release lock. It may change only at the owning Timeweb/Telegram public-activation gate after all required live security/privacy/legal/capacity evidence is accepted.

## 10. Web/runtime migration discipline

V10 is controlled migration/productization, not a greenfield rewrite.

Default preference:

`REUSE_AS_IS > WRAP_ADAPTER > EXTRACT_TO_CORE > REWRITE_REQUIRED > RETIRE`.

Existing React/Vite `apps/web` remains canonical Web source. Python/FastAPI product logic stays provider-neutral.

Timeweb App Platform is the selected runtime target. Timeweb Managed PostgreSQL 18 is the final relational target after the owning production cutover. Preserve migrations, exact numeric semantics, least-privilege roles, RLS/FORCE-RLS, cross-tenant negatives, backup/restore and recovery evidence.

Do not create a second Gateway, second Web product, competing DB authority or competing scheduler merely to fit provider products.

Cloudflare/Neon/Render/Cloud.ru/VK files are retirement inputs under Amendment 20. They are historical evidence, not implementation templates. Remove working-tree artifacts only at their owning V9C-D/V9C-E gate after useful invariants are migrated and zero-current-consumer/recovery proof exists; Git history remains the archive.

## 11. Timeweb-first dependency / capacity / cost boundary

Prefer Timeweb services for active infrastructure when the current accepted milestone requires them and semantics/security/recovery are adequate.

Do not buy or enable spare capacity merely because it is available. Revalidate exact current price before creating a paid resource. Use existing prepaid Timeweb funds first; a new top-up or materially higher recurring commitment requires fresh OWNER approval.

Production Timeweb autodeploy must not bypass accepted GitHub exact-SHA verification.

Retiring external CI/review SaaS may not weaken lint/type/test/security/coverage/review requirements; equivalent-or-stronger GitHub-executed verification is required first.

## 12. Engineering / CI law

Never develop directly in `main`.

Required lifecycle:

`fresh accepted main -> focused/integrated branch -> root-cause/blast-radius/coupled-surface preflight -> deterministic guards -> complete diff review -> DRAFT PR -> exact-head SUCCESS-only checks -> independent review/Files changed -> READY fresh SUCCESS-only checks -> zero blockers -> squash merge -> exact-new-main Regression Shield + owning post-merge -> accepted`.

`failure`, `cancelled`, `queued`, `pending`, `in_progress`, `timed_out`, `action_required`, `stale`, `neutral` and `skipped` are not GREEN for an applicable gate.

A new commit invalidates prior final exact-head GREEN/review evidence.

CI is an independent verifier; do not use it as the primary interactive debugger.

Material defects require root cause, blast radius, analogous-pattern search, coupled producer/consumer inspection, adjacent failure analysis and a deterministic regression guard when reusable.

Do not weaken lint/type/security/test/coverage/CI guards.

## 13. Security / secrets

Never place real secrets/private payloads in GitHub, chat, commits, PR comments, CI logs, screenshots or artifacts.

Never disclose/request when avoidable:

- broker tokens;
- Telegram secrets and any historical VK secrets;
- provider API secrets;
- DB passwords;
- encryption/recovery keys;
- full account IDs;
- private portfolio payloads.

Historical Cloudflare API tokens/secrets are not current credential targets under Amendment 18; do not create or request new ones. Any retained historical secret reference remains outside repository source.

## 14. Broker / Real-money boundary

Current protected locks:

- broker write OFF;
- `trading_methods=false`;
- `REAL_TRADING_ENABLED=false`;
- transfer/withdrawal authority false;
- margin/leverage/uncovered-short authority false.

READ and optional TRADE credentials are tenant-scoped. `TRADE credential connected/verified != broker submit authorized`.

Real broker submit requires `REAL_MONEY_AUTHORIZED` through the owning later execution gate after representative Sandbox/Shadow, immutable plan, authenticated USER approval, drift/preflight, reconciliation, kill switches and actual broker permission.

A GitHub merge, Timeweb deployment, public release, AI output, START command or user registration is never broker-submit authorization.

## 15. WEB VISUAL lock

`WEB-VISUAL-INTEGRATED` remains prepared but paused behind the current `TIMEWEB-PLATFORM-CONSOLIDATION-INTEGRATED` path.

Do not create its implementation branch or perform visual-refresh source changes until the Timeweb consolidation/public-activation path reaches its owning gate and current accepted authority explicitly starts WEB-VISUAL.

## 16. V9 protection / recovery

Protected V9 production/recovery remains available until an explicit accepted decommission/parity gate.

`app:app` remains only the temporary V9C-C compatibility/recovery entrypoint; the forward Timeweb source entrypoint is `apps.api.hosted_runtime:create_app`.

Render retirement in forward V10 authority is implemented through Amendment-20 gates: V9 runtime/recovery dependencies are removed only after V9C-C/V9C-D parity, zero-consumer and recovery proof.

## 17. Continuity

After substantial work leave a GitHub-visible handoff with exact main/head SHA, execution unit, completed changes, checks/conclusions, review/blockers, remaining work and next authorized step.

Do not create a competing current-status document.
