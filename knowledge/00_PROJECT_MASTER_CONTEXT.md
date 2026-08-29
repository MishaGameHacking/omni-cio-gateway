# 00 — OMNI-CIO PROJECT MASTER CONTEXT

Дата актуализации: 2026-08-29

Этот файл хранит долгоживущий контекст проекта. Динамический прогресс/current package всегда берётся только из `knowledge/17_V10_CURRENT_PROGRAM_STATUS.md`.

## 1. Project identity

Canonical repository: `MishaGameHacking/omni-cio-gateway`.

Omni-CIO — один investment platform/product line. Защищённый V9 остаётся production/recovery baseline, V10 — единственная активная feature-development программа.

Нельзя создавать competing Gateway, competing Web product, parallel product-auth stack, competing AI/scheduler/broker/execution stack или второй пользовательский staging-продукт без отдельного OWNER-approved amendment/execution unit.

Stable protected V9 Gateway entrypoint: `app:app`.

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

This is a convenience snapshot only; exact details remain in `knowledge/17_V10_CURRENT_PROGRAM_STATUS.md`.

Current V10 snapshot after the Amendment-14 authority transition is accepted:

- **54% accepted implementation**;
- WP0–WP22A / Blocks A–E COMPLETE;
- **CLOUDFLARE-BUILDS-VERIFIER-INTEGRATION** as the current authorized functional package;
- `WEB-VISUAL-INTEGRATED` remains the prepared product System Update, **PRODUCT IMPLEMENTATION PAUSED**, with `START V10 WEB VISUAL SYSTEM UPDATE` still required before its separate source work;
- WP23+ LOCKED;
- current `PUBLIC_MULTI_USER_ENABLED=false`;
- Telegram Login / VK ID / public multi-user tenant access / public T-Invest READ remain `BLOCKED_EXTERNAL` until their own live gates;
- broker write OFF, `trading_methods=false`, `REAL_TRADING_ENABLED=false`;
- protected V9 `app:app` rollback remains intact.

## 4. GitHub / Cloudflare authority model

GitHub is authority rank 1 for engineering:

- source code;
- protected `main`;
- Pull Requests;
- exact commit SHA;
- review/check evidence;
- accepted status/provenance;
- release source identity.

Cloudflare Workers Paid is platform rank 2 for **new V10** work after Amendment 14 acceptance:

- application/edge hosting target;
- Workers/Static Assets;
- Workers Builds portable compute/verification target after repository integration;
- Custom Domains/DNS/TLS;
- WAF/DDoS/rate/Turnstile security where applicable;
- Access for private/admin/engineering surfaces only by default;
- Hyperdrive only after database compatibility evidence;
- KV/R2/Durable Objects/Queues/Workflows when a concrete owning package justifies them;
- Workers AI/Vectorize only when AI/Cortex scope is authorized.

Cloudflare dashboard/provider state never overrides accepted GitHub authority.

Cloudflare infrastructure identity is not Omni-CIO product identity.

## 5. Provider transition boundary

For new V10 deployment/release work after Amendment 14 acceptance:

- selected managed target: `CLOUDFLARE_WORKERS_PAID`;
- Cloud.ru Evolution is no longer the selected new-V10 provider target;
- Render is no longer active new-V10 deployment, zero-charge-attestation, hosted-release-alignment or recovery target;
- no new Render attestation refresh/provider mutation is required;
- accepted WP22A Render + Neon evidence remains historical evidence and must not be rewritten;
- protected V9 Render production/recovery remains protected.

Amendment 14 is governance only. It does not itself:

- click/deploy Cloudflare;
- mutate DNS/domain;
- create API tokens/secrets;
- activate public users;
- migrate Neon/PostgreSQL;
- provision Telegram/VK provider secrets;
- authorize Real money.

Provider/security authority, build integration, runtime compatibility, candidate provider mutation and production cutover are mandatory split boundaries.

## 6. Mandatory Cloudflare implementation sequence

After Amendment 14 acceptance, execute exactly:

1. `CLOUDFLARE-BUILDS-VERIFIER-INTEGRATION` — repository-side portable build/check integration; no production deploy;
2. `CLOUDFLARE-RUNTIME-COMPATIBILITY` — React/Vite/backend/native dependency/PostgreSQL/Hyperdrive compatibility evidence/config;
3. `CLOUDFLARE-CANDIDATE-DEPLOYMENT` — immutable candidate provider mutation only after prior gates;
4. `CLOUDFLARE-PUBLIC-CUTOVER` — canonical domain/DNS/TLS/security/promotion/rollback and capability-specific live-user acceptance.

Do not start stage N+1 before stage N is accepted through exact-main post-merge verification.

## 7. Continuous public release model

V10 is not a monolithic “finish 100%, then show users” program.

Every accepted protected `main` SHA is a new whole-product revision **candidate**. It is not an automatic production deployment.

Required release path:

`exact-head PR GREEN/review -> squash merge -> exact-main post-merge GREEN -> immutable Cloudflare candidate -> candidate acceptance -> production promotion`.

Before promotion, current `main` is rechecked. A superseded candidate is not promotable.

If a newer `main` is blocked, production remains last-known-good and reports `UPDATE_PENDING`, `DEPLOYMENT_BLOCKED` or `OUT_OF_SYNC` instead of silently drifting.

Public release identity is event-derived CalVer `YYYY.MM.DD.N` plus exact source SHA, Cloudflare Version ID, UTC release time and release status. No source-code version-bump commit is made only to change the displayed public version.

Rollback of Worker code does not imply rollback of KV/R2/D1/Durable Object state; schema/storage compatibility and recovery are separate evidence.

## 8. Public product / identity model

One canonical public Omni-CIO Web is the target.

PROJECT OWNER is an ordinary product USER, not a product superuser.

Canonical human product identity remains:

`Telegram Login | VK ID -> verified identity -> OmniCIOUserAccount -> Tenant -> server-side Session`.

`WP22A — External Web Access / Product Authentication Security Gate` is technically COMPLETE, but real provider/public runtime activation remains capability-specific.

Tenant scope must be server-derived. PostgreSQL RLS/FORCE-RLS and cross-tenant negatives remain mandatory even when Cloudflare protects the outer edge.

Cloudflare Access/WAF/Turnstile can protect infrastructure/browser surfaces but cannot mint/select an Omni-CIO tenant.

## 9. Progressive capability activation

Amendment 13 activation states are exactly:

`IMPLEMENTED | LIVE_OPERABLE | BLOCKED_EXTERNAL | REAL_MONEY_AUTHORIZED`.

A completed capability may become `LIVE_OPERABLE` when all its own technical/security/external gates pass; unrelated later V10 blocks are not a valid artificial blocker.

Current public-facing activation remains fail-closed where evidence is missing:

- Telegram Login — `BLOCKED_EXTERNAL`;
- VK ID — `BLOCKED_EXTERNAL`;
- public multi-user tenant access — `BLOCKED_EXTERNAL`;
- T-Invest READ — `BLOCKED_EXTERNAL` / `FAIL_CLOSED_PENDING_BROKER_TERMS_PERMISSION`.

`PUBLIC_MULTI_USER_ENABLED=false` is current runtime state, not a permanent V10-wide release lock.

## 10. Web/runtime migration discipline

V10 is controlled migration/productization, not a greenfield rewrite.

Default decision preference:

`REUSE_AS_IS > WRAP_ADAPTER > EXTRACT_TO_CORE > REWRITE_REQUIRED > RETIRE`.

Existing React/Vite `apps/web` remains canonical Web source.

FastAPI support in Cloudflare Python Workers does not prove current CPython/native dependencies are compatible. Exact compatibility evidence is required before migration.

Accepted Neon/PostgreSQL 18 tenant/RLS authority remains intact. D1 does not replace financial/tenant truth by default. Hyperdrive + PostgreSQL 18 compatibility is not assumed and requires focused evidence.

Do not create a second Gateway, second Web product, competing DB authority or competing scheduler simply to use more Cloudflare features.

## 11. Cloudflare capacity / cost boundary

The OWNER has an active Workers Paid baseline. The Amendment-14 contract records the 2026-08-29 official-reference values as mutable facts that must be revalidated before material configuration:

- 6000 included build minutes/month;
- up to 6 concurrent builds/account;
- 20-minute build timeout;
- 4 vCPU/build;
- 8 GB memory/build;
- 20 GB disk/build.

The existing subscription authorizes use of included capacity after the owning repository integration is accepted. It does not authorize uncontrolled paid overage or a higher paid plan.

Current GitHub/Lenovo CI routing does not change merely because Cloudflare Builds capacity exists.

Portable verification should migrate only when semantics are equivalent. Windows/PowerShell/ACL/PostgreSQL-18-native contracts remain on trusted Lenovo self-hosted runners until an accepted equivalence proof exists.

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
- Telegram/VK secrets;
- provider API secrets;
- DB passwords;
- encryption/recovery keys;
- full account IDs;
- private portfolio payloads.

Cloudflare API tokens/secrets belong in approved secret custody at the owning provider-action gate, never repository source.

## 14. Broker / Real-money boundary

Current protected locks:

- broker write OFF;
- `trading_methods=false`;
- `REAL_TRADING_ENABLED=false`;
- transfer/withdrawal authority false;
- margin/leverage/uncovered-short authority false.

READ and optional TRADE credentials are tenant-scoped. `TRADE credential connected/verified != broker submit authorized`.

Real broker submit requires `REAL_MONEY_AUTHORIZED` through the owning later execution gate after representative Sandbox/Shadow, immutable plan, authenticated USER approval, drift/preflight, reconciliation, kill switches and actual broker permission.

A GitHub merge, Cloudflare deployment, public release, AI output, START command or user registration is never broker-submit authorization.

## 15. V9 protection / recovery

Protected V9 production/recovery remains available until an explicit accepted decommission/parity gate.

Stable entrypoint remains `app:app`.

Render retirement in **new V10** authority does not authorize mutation/deletion of the protected V9 Render baseline.

## 16. Continuity

After substantial work leave a GitHub-visible handoff with exact main/head SHA, execution unit, completed changes, checks/conclusions, review/blockers, remaining work and next authorized step.

Do not create a competing current-status document.
