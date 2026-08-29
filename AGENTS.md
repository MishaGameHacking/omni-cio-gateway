# AGENTS.md — Omni-CIO project rules

Этот файл обязателен для любого AI-агента, разработчика или нового чата, который меняет `MishaGameHacking/omni-cio-gateway`.

## 1. Product boundary

Поддерживается **один Omni-CIO product line**. Protected owner-accepted V9 production/recovery baseline остаётся `existing Omni-CIO Custom GPT v9.0.0 -> Omni-CIO Gateway (app:app) -> protected broker contours`. V10 productize/migrate этот же продукт; не создавать второй Gateway/Web/product-auth/AI/scheduler/broker/execution stack.

For public V10, broker credentials are tenant-scoped `BrokerConnection` credentials, never global application credentials. GitHub/Cloudflare engineering access never means broker/trading authority.

## 2. Current program state

Dynamic progress/current execution authority всегда берётся из `knowledge/17_V10_CURRENT_PROGRAM_STATUS.md`; этот файл не второй progress ledger.

Current synchronized snapshot:

- WP0–WP22A / Blocks A–E accepted COMPLETE;
- accepted V10 progress is **54%**;
- complete `WP22A — External Web Access / Product Authentication Security Gate` technical Exit Gate is accepted;
- **CLOUDFLARE-BUILDS-VERIFIER-INTEGRATION — Repository-Side Portable Verification Integration** is current next package after Amendment 14 acceptance;
- PRODUCT IMPLEMENTATION PAUSED during provider/security transition;
- `WEB-VISUAL-INTEGRATED` remains prepared and still requires `START V10 WEB VISUAL SYSTEM UPDATE` before its separate source work;
- WP23+ LOCKED;
- `PUBLIC_MULTI_USER_ENABLED=false` current fail-closed state;
- Telegram Login, VK ID, public multi-user tenant access and public T-Invest READ remain `BLOCKED_EXTERNAL` until their own gates;
- broker write OFF, `trading_methods=false`, `REAL_TRADING_ENABLED=false`;
- protected V9 `app:app` rollback intact.

PROJECT OWNER is not a special Omni-CIO product role. When using the product, OWNER is an ordinary USER on the same `OmniCIOUserAccount -> Tenant -> Session` path. Engineering/provider authority cannot mint/select a product tenant.

## 3. Mandatory authority restore

Before material work restore from current GitHub `main`, not chat memory:

1. `README.md`;
2. `AGENTS.md`;
3. `CONTRIBUTING.md`;
4. `knowledge/00_PROJECT_MASTER_CONTEXT.md`;
5. `knowledge/16_CURRENT_PROGRAM_STATUS.md` for protected V9;
6. `docs/master-plan/OMNI_CIO_V10_PROGRAM_LOCK.md`;
7. `docs/master-plan/OMNI_CIO_V10_MASTER_PLAN.md`;
8. `docs/master-plan/OMNI_CIO_V10_AMENDMENTS_INDEX.md`;
9. all applicable active amendments, especially Amendments 8–14;
10. `docs/master-plan/OMNI_CIO_V10_WP_EXECUTION_TEMPLATE.md`;
11. `knowledge/17_V10_CURRENT_PROGRAM_STATUS.md`;
12. owning execution-unit contracts/runbooks/ledgers;
13. exact `main`, recent commits, open PR/issues and GitHub Actions.

Key current authority includes Amendment 14 and `docs/architecture/V10_CLOUDFLARE_PLATFORM_AUTHORITY_CONTRACT.json`. Old chat/screenshots/stale PR text/provider dashboard state never override accepted GitHub authority.

## 4. GitHub #1 / Cloudflare #2

After Amendment 14 acceptance:

- GitHub is engineering/source/review/provenance authority rank 1;
- Cloudflare Workers Paid is platform rank 2 and selected new-V10 managed application/edge/build target after each owning gate;
- Cloud.ru Evolution is no longer selected for new V10 deployment;
- Render is retired from active **new V10** deployment, zero-charge attestation, hosted-release-alignment and recovery authority;
- accepted WP22A Render/Neon evidence remains historical evidence;
- protected V9 Render `app:app` production/recovery remains protected;
- Amendment 14 acceptance itself performs no provider/DNS/domain mutation, secret creation, public-user activation or production cutover.

Final public V10 requires a **managed-cloud production runtime** independent of OWNER home IP/Wi-Fi/router/LAN/Lenovo. Cloudflare services may be adopted when an owning package proves the need: Workers/Static Assets, Workers Builds, Custom Domains/DNS/TLS, WAF/DDoS/rate controls, Turnstile, Access for private/admin/engineering surfaces, Hyperdrive only after PG18 proof, KV/R2/Durable Objects/Queues/Workflows for explicit roles, and Workers AI/Vectorize only inside authorized AI/Cortex scope.

Do not click dashboard `Deploy`, create provider tokens/secrets, mutate DNS/domain or create paid-overage resources during governance/build-planning unless that exact provider mutation is authorized.

## 5. Continuous exact-main public release

V10 is an engineering program; public capability releases do not wait for V10 100% when their own gates pass.

Every accepted protected `main` SHA is a product revision candidate, not automatic production deployment.

Required flow:

`PR exact-head GREEN/review -> squash merge -> exact-main post-merge GREEN -> immutable Cloudflare candidate -> candidate acceptance -> production promotion`.

Re-check current `main` immediately before promotion. Superseded candidates are not promotable. If latest `main` is blocked, production stays last-known-good and exposes `UPDATE_PENDING`, `DEPLOYMENT_BLOCKED` or `OUT_OF_SYNC`.

Public release ID is event-derived CalVer `YYYY.MM.DD.N` plus exact source SHA, Cloudflare Version ID, UTC release time and status; never create a source version-bump commit only to change the display version. Worker rollback does not rewrite GitHub authority and does not automatically roll back KV/R2/D1/Durable Object state.

## 6. Execution-unit discipline

Governed by the **Integrated System Update Execution Law**. Every material change is exactly one `FOCUSED_CHANGE` or one OWNER-authorized `INTEGRATED_SYSTEM_UPDATE`.

Mandatory split triggers: DB/migration ordering, security/authority transition, dependency/toolchain boundary, genuinely non-delegable OWNER/provider action, live/temporal evidence, production cutover, Real-money authority and reviewability limit.

Amendment 14 therefore requires:

1. `CLOUDFLARE-BUILDS-VERIFIER-INTEGRATION` — repository portable verification only; no production deploy;
2. `CLOUDFLARE-RUNTIME-COMPATIBILITY` — React/Vite/backend/native dependency/PostgreSQL/Hyperdrive evidence;
3. `CLOUDFLARE-CANDIDATE-DEPLOYMENT` — immutable candidate provider mutation after prior gates;
4. `CLOUDFLARE-PUBLIC-CUTOVER` — domain/DNS/TLS/security/promotion/rollback and capability-specific live-user acceptance.

Do not start N+1 before N is accepted.

## 7. Pre-CI / root cause

CI is an independent verifier, not the normal interactive debugger.

Before fixing a material defect: find root cause, determine blast radius, search analogous patterns, inspect coupled producers/consumers/config/workflows, inspect adjacent failure modes, add deterministic regression guards where reusable, run cheap/focused preflight and review the complete diff.

Do not patch systemic defects symptom-by-symptom. After publishing a verification SHA, HEAD FREEZE applies while the safe independent batch reaches terminal state. Consolidate findings by root cause before one coherent correction batch.

Unexpected material RED after declared readiness requires a reusable lesson in `docs/operations/V10_ENGINEERING_FAILURE_LEARNING_LEDGER.md`.

Prefer bounded failure domains rather than one fragile monolith. Consider timeouts/deadlines, bounded retries, idempotency, backpressure/circuit breaker, durable checkpoints, health/readiness/freshness, restart/recovery and least-privilege boundaries. Money/security authority fails closed.

## 8. Git / PR lifecycle

Never develop directly in `main`.

`fresh accepted main -> branch -> authorized implementation -> deterministic guards -> cheap preflight -> complete diff -> DRAFT PR -> applicable exact-head DRAFT SUCCESS -> Files changed + independent review -> zero blockers -> unchanged READY -> fresh applicable READY SUCCESS -> squash merge -> exact-new-main Regression Shield/owning post-merge SUCCESS -> accepted`.

Project law: every **applicable** exact-head V10 check must actually execute and conclude `success`.

`failure`, `cancelled`, `queued`, `pending`, `in_progress`, `timed_out`, `action_required`, `stale`, `neutral` and `skipped` are not GREEN for an applicable gate. New commit invalidates prior final exact-head GREEN/review evidence.

### Changed-files + independent code-review merge gate

Before merge inspect **all** Files changed, inline review threads, annotations and applicable Sonar/Gitar/SAST/security/code-review outputs; classify material findings; unresolved blocking review threads = 0; perform final manual engineering diff review. Bot approval is supporting evidence only. After a correction commit repeat Files changed + review on the new exact head.

## 9. Testing baseline

Do not weaken guards to obtain GREEN. Where applicable run:

```text
python scripts/check_ci_security_baseline.py
python scripts/check_repository_layout.py
python scripts/check_v10_repository_boundaries.py
python scripts/check_v10_engineering_governance.py
python scripts/check_v10_cloudflare_platform_authority.py
python scripts/check_v10_documentation_consistency.py
python scripts/check_gpt_recovery_consistency.py
python -m ruff check .
python -m ruff format --check .
python -m mypy
python -m pytest -q --cov --cov-branch --cov-fail-under=60
```

Also run owning focused checks, dependency/security scans, frontend typecheck/lint/test/build/audit and browser/recovery checks when applicable.

Current GitHub/Lenovo routing remains authoritative until `CLOUDFLARE-BUILDS-VERIFIER-INTEGRATION` is accepted. Do not fake Windows/PowerShell/ACL/PostgreSQL-18 semantics in a portable lane. Quota/provider outage is never `success`.

## 10. Dependencies / runtime compatibility

Do not upgrade to `latest` by initiative. Use accepted versions/locks: `requirements.in`, `requirements-dev.in`, generated `requirements.txt`, `requirements-dev.txt`, and `docs/architecture/V10_TOOLCHAIN_BASELINE.*`.

Cloudflare migration preference remains `REUSE_AS_IS > WRAP_ADAPTER > EXTRACT_TO_CORE > REWRITE_REQUIRED > RETIRE`.

Existing React/Vite Web remains canonical source. FastAPI availability in Python Workers does not prove all CPython/native dependencies compatible; test them. Neon/PostgreSQL 18 tenant/RLS authority remains; D1 is not an automatic replacement; Hyperdrive + PostgreSQL 18 compatibility must be proved.

## 11. Product / tenant / activation

One canonical Omni-CIO Web is the ordinary user-facing product. Human product auth remains Telegram Login and VK ID unless later authority changes it:

`Telegram Login | VK ID -> verified identity -> OmniCIOUserAccount -> Tenant -> server-side Session`.

Tenant scope is server-derived; PostgreSQL RLS/FORCE-RLS and cross-tenant negatives remain mandatory. Cloudflare WAF/Access/Turnstile is additive outer security, not tenant authorization.

Capability states are exactly `IMPLEMENTED | LIVE_OPERABLE | BLOCKED_EXTERNAL | REAL_MONEY_AUTHORIZED`. “V10 unfinished” is not itself an external blocker, but every owning technical/security/external gate must be real and accepted.

## 12. Security / secrets

Never place real secrets in GitHub, chat, commits, PR comments, CI logs, screenshots or artifacts. Never request real credentials when the task can be completed without receiving them.

Do not disclose broker tokens, Telegram/VK secrets, provider API secrets, DB passwords, encryption/recovery keys, full account IDs or private portfolio payloads. `.env` is local-only from `.env.example`. Cloudflare tokens/secrets belong only in approved secret custody at the owning provider-action gate.

## 13. Broker / Real-money boundary

Current protected locks: broker write OFF, `trading_methods=false`, `REAL_TRADING_ENABLED=false`, no transfer/withdrawal/margin/leverage/uncovered-short authority.

READ/optional TRADE credentials are tenant-scoped and role-separated. `TRADE credential connected/verified != broker submit authorized`.

Real submit requires `REAL_MONEY_AUTHORIZED` after representative Sandbox/Shadow, immutable plan, authenticated USER approval, drift/preflight, ambiguous-submit reconciliation, kill switches and actual broker permission. GitHub merge, Cloudflare deploy/release, AI output, START command or user registration is never broker-submit authorization.

## 14. V9 / V10 boundary

Protected V9 remains production/recovery until an explicit parity/decommission gate. Stable entrypoint remains `app:app`. Do not mutate/delete protected V9 Render merely because Render is retired from **new V10** authority. V10 is controlled migration/productization, not greenfield rewrite.

## 15. OWNER participation / handoff law

Do safe repository/GitHub/tool work autonomously. OWNER participation is only for genuinely non-delegable external consent/account/provider UI, physical/UAC, secret custody, domain/payment or Master Plan authority.

When OWNER action is required: provide a direct official HTTPS link when stable, otherwise verified official start URL + exact click path; state exact scope/expected result, stop conditions, do-not-do warnings, minimum safe return and cost/authority consequences. Never ask OWNER to send real secret values. OWNER product acceptance is post-merge/post-Regression-Shield unless a genuinely non-delegable prerequisite must occur earlier.

## 16. Continuity

After a substantial stage leave GitHub-visible handoff with exact base/main/head SHA, execution unit, completed work, checks/conclusions, review/blockers, remaining work and next authorized step. Do not create a competing current-status document.
