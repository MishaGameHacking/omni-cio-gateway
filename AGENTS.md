# AGENTS.md — Omni-CIO project rules

Этот файл обязателен для любого AI-агента, разработчика или нового чата, который меняет `MishaGameHacking/omni-cio-gateway`.

## 1. Product boundary

Поддерживается **один Omni-CIO product line**. V9 теперь является **V9 migration source** внутри текущего V10 lineage: accepted V9 target `b9e4fabcb54f8f6e0ba206f030c35f2fafa2ce62` уже является предком current main, поэтому stale `v9/*` branch-head нельзя вливать в PR #584. Полезная V9-логика переносится/переиспользуется в canonical V10/Timeweb surfaces. После parity + zero-consumer + recovery proof obsolete working-tree paths могут удаляться, но protected V9 compatibility entrypoint `app:app` и его compatibility chain сохраняются до отдельного accepted decommission authority; Git history остаётся архивом.

For public V10, broker credentials are tenant-scoped `BrokerConnection` credentials, never global application credentials. GitHub/Timeweb engineering access never means broker/trading authority.

## 2. Current program state

Dynamic progress/current execution authority always comes from `knowledge/17_V10_CURRENT_PROGRAM_STATUS.md`.

Current synchronized snapshot:

- WP0–WP22A / Blocks A–E remain accepted COMPLETE;
- complete `WP22A — External Web Access / Product Authentication Security Gate` technical Exit Gate remains accepted historical evidence;
- accepted V10 progress is **54%**;
- accepted Cloudflare/Render/Neon chains remain historical evidence, not future provider authority;
- **TIMEWEB-PLATFORM-CONSOLIDATION-INTEGRATED — Timeweb-only runtime/database/DNS/Telegram consolidation** is the current next package after Amendment 18 acceptance;
- target active service model is ChatGPT + GitHub + Timeweb Cloud + Telegram Login;
- Timeweb is the only selected V10 production infrastructure target;
- Telegram Login is the only selected human product login provider and authenticates the human Telegram USER account via OIDC; bot chat/`/start`/`telegram:bot_access` are not login prerequisites;
- Cloudflare, Neon, Render, Cloud.ru and VK ID are retirement targets;
- WEB-VISUAL and WP23+ are paused;
- public multi-user remains fail-closed until its Timeweb/Telegram/legal/privacy/capacity gates;
- broker write OFF, `trading_methods=false`, `REAL_TRADING_ENABLED=false`;
- OWNER-approved V9→V10 convergence is closed through `V9C-F / WHOLE_TREE_LEGACY_ABSENCE_PROOF` as branch-local P1 evidence on exact head `738d8c623d3002fd2eb312a6bce96c35bd45f75f`. P2 exact-SHA Timeweb App candidate is branch-local `CERTIFIED_GREEN` on `ba43fa4be350340557fcf6d8532b6c089022a8ca`. The current integrated checkpoint is P3 PostgreSQL 18 production cutover/recovery control in `RED_REPAIR_ONLY / REPLACEMENT_HEAD_VERIFICATION_PENDING`; P4 remains locked until P3 exact-head certification. PR #584 must not merge to `main` without the required exact-head OWNER landing confirmation.

PROJECT OWNER is not a special Omni-CIO product role. Product users, including OWNER, use the same `Telegram USER account OIDC Login -> verified identity -> OmniCIOUserAccount -> Tenant -> Session` path, backed by a server-side session. The optional Omni-CIO Telegram bot may only be linked after that account/session exists; bot chat, `/start`, Bot API identity or bot-token possession can never create an account, mint/select a tenant or replace product login.

The WP22A technical gate is complete only through its accepted evidence chain. Amendments 14/15 remain historical evidence; Amendment 18 does not fabricate public activation, expand broker-write authority or start WP23.

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
9. all applicable active amendments, especially Amendments 8–21;
10. `docs/master-plan/OMNI_CIO_V10_WP_EXECUTION_TEMPLATE.md`;
11. `knowledge/17_V10_CURRENT_PROGRAM_STATUS.md`;
12. owning execution-unit contracts/runbooks/ledgers;
13. exact `main`, recent commits, open PR/issues and GitHub Actions.

Key current authority includes Amendment 18 and `docs/architecture/V10_RU_PUBLIC_REGISTRATION_INGRESS_CONTRACT.json`. Amendments 14/15 become historical Cloudflare evidence after Amendment 18 acceptance. Old chat/screenshots/stale PR text/provider dashboard state never override accepted GitHub authority.

## 4A. Current provider law — GitHub #1 / Timeweb production / Telegram identity

After Amendment 18 acceptance:

- GitHub is engineering/source/review/CI/release-provenance authority;
- Timeweb Cloud is the sole selected V10 production infrastructure provider;
- Telegram Login is the sole selected human product login provider;
- ChatGPT is an engineering assistant only and never runtime/data authority;
- Cloudflare, Neon, Render, Cloud.ru and VK ID are retirement targets;
- no new feature work may add dependencies on retired providers;
- GitHub-native quality/security/review checks are the active authority; external CI/review SaaS is historical and must not be required by current/future V10 workflows;
- provider-specific code belongs in thin infrastructure adapters, not business/account/tenant/security logic;
- production DB authority moves to Timeweb PostgreSQL 18 only through the owning cutover/recovery gate;
- Cloudflare/Neon external rollback is unavailable by OWNER-reported decommission; Timeweb recovery evidence must stand on its own.

Target release flow:

`PR GREEN -> squash -> exact-main GREEN -> exact Timeweb candidate -> live proof -> production`.

A Timeweb deployment, GitHub merge or Telegram login never grants broker-write/Real-money authority.

## 4B. Historical GitHub #1 / Cloudflare #2 — superseded for future provider selection

After Amendment 14 acceptance:

- GitHub is engineering/source/review/provenance authority rank 1;
- Cloudflare Workers Paid was the historical Amendment-14 rank-2 application/edge/build target; Amendment 18 supersedes that selection for all current/future V10 provider work;
- Cloud.ru Evolution is no longer selected for new V10 deployment;
- Render is retired from active **new V10** deployment, zero-charge attestation, hosted-release-alignment and recovery authority;
- accepted WP22A Render/Neon evidence remains historical evidence;
- protected V9 Render `app:app` production/recovery remains protected;
- Amendment 14 acceptance itself performs no provider/DNS/domain mutation, secret creation, public-user activation or production cutover.

Historically, Amendment 15 changed only Cloudflare implementation delivery granularity: the four Amendment-14 stages became internal milestones of one `CLOUDFLARE-PUBLIC-PRODUCT-INTEGRATED` update. That sequence is provenance only after Amendment 18.

Current/future public V10 requires Timeweb as the managed-cloud production runtime and PostgreSQL 18 authority, independent of OWNER home IP/Wi-Fi/router/LAN/Lenovo. Cloudflare services have no new-adoption authority under Amendment 18. Do not create retired-provider tokens/secrets, mutate retired-provider DNS/domain state, deploy retired-provider candidates or create retired-provider paid resources.

## 5. Continuous exact-main public release

V10 is an engineering program; public capability releases do not wait for V10 100% when their own gates pass.

Every accepted protected `main` SHA is a product revision candidate, not automatic production deployment.

Required flow:

`PR exact-head GREEN/review -> squash merge -> exact-main post-merge GREEN -> exact Timeweb candidate -> candidate acceptance -> production promotion`.

Re-check current `main` immediately before promotion. Superseded candidates are not promotable. If latest `main` is blocked, production stays last-known-good and exposes `UPDATE_PENDING`, `DEPLOYMENT_BLOCKED` or `OUT_OF_SYNC`.

Current public release identity must bind the exact accepted source SHA to the accepted Timeweb candidate/deployment identity and release status defined by the owning Timeweb gate; never create a source version-bump commit only to change the display version. Application rollback does not replace PostgreSQL backup/restore or schema-compatibility evidence.

## 6. Execution-unit discipline

Governed by the **Integrated System Update Execution Law**. Every material change is exactly one `FOCUSED_CHANGE` or one OWNER-authorized `INTEGRATED_SYSTEM_UPDATE`.

Mandatory split triggers remain: DB/migration ordering, security/authority transition, dependency/toolchain boundary, genuinely non-delegable OWNER/provider action, live/temporal evidence, production cutover, Real-money authority and reviewability limit. A real split trigger discovered during integrated implementation still forces a stop/split; one large branch is never a bypass.

Amendment 18 authorizes the current integrated update:

`TIMEWEB-PLATFORM-CONSOLIDATION-INTEGRATED`

Initial TW-A source branch (squash-merged through PR #583):

`system/timeweb-platform-consolidation`

Current continuation branch for TW-B:

`system/timeweb-platform-consolidation-tw-b`

Ordered internal milestones are TW-A inventory/authority, TW-B source/runtime consolidation, TW-C Timeweb App candidate, TW-D Timeweb PostgreSQL cutover, TW-E public ingress/DNS, TW-F Telegram public activation, and TW-G legacy-provider decommission.

The Amendment 15 block below is historical Cloudflare execution provenance only.

Historical Amendment 15 authorized one integrated Cloudflare update:

`CLOUDFLARE-PUBLIC-PRODUCT-INTEGRATED`

Default implementation branch:

`system/cloudflare-public-product`

Ordered internal milestones:

1. `CF-A / CLOUDFLARE-BUILDS-VERIFIER-INTEGRATION` — repository portable verification, shard/impact/provenance/cost guards; no candidate/public production promotion;
2. `CF-B / CLOUDFLARE-RUNTIME-COMPATIBILITY` — React/Vite/backend/native dependency/PostgreSQL/Hyperdrive/Containers compatibility and deployment configuration;
3. `CF-C / CLOUDFLARE-CANDIDATE-DEPLOYMENT` — immutable candidate provider mutation only after CF-A/CF-B internal gates;
4. `CF-D / CLOUDFLARE-PUBLIC-CUTOVER` — domain/DNS/TLS/security/promotion/rollback and capability-specific live-user acceptance.

Do not start internal milestone N+1 before milestone N's branch-local Exit Gate is satisfied. Amendment 15 removes only the requirement to merge each of these four stages separately; it does not remove their order or fail-closed boundaries.

The integrated branch uses the required Execution Ledger and GitHub System Update dashboard. `INTEGRATION_READY` remains the final whole-update readiness state, but earlier published checkpoints may be certified under Amendment 16 when that later law is accepted.

## 7. Green Checkpoint & Targeted CI Repair Law

CI is an independent verifier and active checkpoint certifier; it does not replace engineering judgment, root-cause analysis or focused preflight.

When Amendment 16 is accepted on protected `main`, it supersedes the old wait-all `HEAD FREEZE` / Single Remote Publication / batch-only repair defaults while preserving root-cause, exact-head, review, security, recovery and split-trigger laws.

Canonical flow:

`WRITE -> focused preflight -> CHECKPOINT SHA -> GitHub-native CI/security/review -> CERTIFIED_GREEN -> NEXT CHECKPOINT`.

If any applicable check or material review finding is RED:

`CHECKPOINT_RED -> RED_REPAIR_ONLY -> root cause -> targeted proof -> replacement SHA if content changed -> full certification -> CERTIFIED_GREEN`.

Rules:

- the next functional checkpoint is forbidden until the current checkpoint is `CERTIFIED_GREEN`;
- start diagnosis/repair immediately when useful RED evidence appears; do not wait for every independent job merely to begin repair;
- other independent jobs may continue and their findings must still be inspected;
- source unchanged + proved transient/infrastructure failure -> prefer re-running only the specific failed GitHub Actions job on the same SHA;
- source/config/test/governance content changed -> old final evidence is stale; update the same logical checkpoint, publish a replacement SHA, run targeted proof, then fully certify that exact replacement SHA before new feature work;
- `git commit --amend` creates a replacement commit/SHA; it does not mutate an immutable existing commit;
- never force-rewrite protected `main` or shared history merely to preserve a one-commit appearance;
- repeated identical “transient” RED is an infrastructure/workflow defect, not a reason for blind reruns;
- GitHub-native lint/type/test/coverage/dependency/SAST/secret checks must pass when applicable; unresolved material correctness/security/maintainability findings are not GREEN;
- check annotations/review threads and repository-native security findings are active engineering evidence, not decoration;
- unexpected reusable material RED still requires the Failure Learning Ledger;
- `MAIN_RED_STOP`: an applicable post-merge RED on current `main` blocks ordinary feature progress until an accepted focused repair restores GREEN.

Prefer bounded failure domains rather than one fragile monolith. Timeouts/deadlines, bounded retries, idempotency, backpressure/circuit breakers, durable checkpoints, health/readiness/freshness, restart/recovery and least-privilege boundaries remain required where applicable. Money/security authority fails closed.

Canonical machine contract: `docs/architecture/V10_GREEN_CHECKPOINT_TARGETED_CI_REPAIR_CONTRACT.json`.
Canonical runbook: `docs/operations/V10_GREEN_CHECKPOINT_CI_RUNBOOK.md`.
Targeted verifier: `.github/workflows/v10-targeted-repair.yml`.

## 8. Git / PR lifecycle

Never develop directly in `main`.

Normal checkpoint lifecycle:

`fresh accepted main -> branch -> authorized logical checkpoint -> focused preflight -> publish exact checkpoint -> GitHub-native CI/security/review -> RED_REPAIR_ONLY if needed -> targeted repair proof -> exact replacement full certification -> CERTIFIED_GREEN -> next checkpoint`.

Final landing lifecycle:

`current exact head CERTIFIED_GREEN -> complete Files changed + independent review -> zero blockers -> squash merge -> exact-new-main Regression Shield/owning post-merge SUCCESS -> accepted`.

A DRAFT→READY state change does not by itself invalidate same-SHA certification unless an applicable workflow/ruleset is intentionally state-dependent and requires a fresh run. Any content-changing commit creates a new exact head and invalidates previous final evidence.

Project law: every **applicable** exact-head V10 check must actually execute and conclude `success`.

`failure`, `cancelled`, `queued`, `pending`, `in_progress`, `timed_out`, `action_required`, `stale`, `neutral` and `skipped` are not GREEN for an applicable gate.

### Changed-files + independent code-review merge gate

Before merge inspect **all** Files changed, inline review threads, annotations and applicable GitHub-native lint/type/test/coverage/dependency/SAST/secret/security/code-review outputs; classify material findings; unresolved blocking review threads = 0; perform final manual engineering diff review. Bot approval is supporting evidence only. After a correction/replacement head repeat Files changed + review on the new exact head.

## 9. Testing baseline

Do not weaken guards to obtain GREEN. Where applicable run:

```text
python scripts/check_ci_security_baseline.py
python scripts/check_repository_layout.py
python scripts/check_v10_repository_boundaries.py
python scripts/check_v10_engineering_governance.py
python scripts/check_v10_green_checkpoint_ci_repair.py
python scripts/check_v10_cloudflare_platform_authority.py
python scripts/check_v10_cloudflare_public_product_integrated.py
python scripts/check_v10_documentation_consistency.py
python scripts/check_gpt_recovery_consistency.py
python -m ruff check .
python -m ruff format --check .
python -m mypy
python -m pytest -q --cov --cov-branch --cov-fail-under=60
```

Also run owning focused checks, dependency/security scans, frontend typecheck/lint/test/build/audit and browser/recovery checks when applicable.

GitHub/self-hosted Windows routing remains authoritative for checks that require its semantics. Any future Timeweb-hosted verifier replacement must prove equivalent semantics before routing changes. Quota/provider outage is never `success`.

## 10. Dependencies / runtime compatibility

Do not upgrade to `latest` by initiative. Use accepted versions/locks: `requirements.in`, `requirements-dev.in`, generated locks and `docs/architecture/V10_TOOLCHAIN_BASELINE.*`.

Current migration preference remains:

`REUSE_AS_IS > WRAP_ADAPTER > EXTRACT_TO_CORE > REWRITE_REQUIRED > RETIRE`.

Existing React/Vite Web remains canonical source. Python/FastAPI product code stays provider-neutral. Timeweb-specific behavior belongs in thin deployment/infrastructure adapters.

Timeweb App Platform is the selected runtime target and Timeweb Managed PostgreSQL 18 is the final relational target after the owning cutover. Preserve PostgreSQL migrations, exact numeric financial semantics, least-privilege roles, RLS/FORCE-RLS, cross-tenant negatives, backup/restore and recovery.

Cloudflare/Neon/Render/Cloud.ru/VK historical files are Amendment-20 retirement inputs. Do not add new dependencies on them and do not delete them blindly: migrate any still-required security/recovery semantics first, prove zero current consumers and current recovery, then remove obsolete working-tree artifacts at V9C-D/V9C-E while Git history remains the archive.

GitHub/self-hosted Windows checks remain authoritative until an equivalent GitHub-executed replacement is accepted. Retiring external CI/review SaaS may not weaken lint/type/test/security/coverage/review requirements.

## 11. Product / tenant / activation

One canonical Omni-CIO Web is the ordinary user-facing product. Human product auth is Telegram Login only after Amendment 18 acceptance:

`Telegram Login -> verified identity -> OmniCIOUserAccount -> Tenant -> server-side Session`.

VK ID is a retirement target and must not remain a deployed session-minting path after TW-G.

Tenant scope is server-derived; PostgreSQL RLS/FORCE-RLS and cross-tenant negatives remain mandatory. Timeweb ingress/network controls are additive infrastructure security, not tenant authorization.

Progressive Capability Activation: capability states are exactly `IMPLEMENTED | LIVE_OPERABLE | BLOCKED_EXTERNAL | REAL_MONEY_AUTHORIZED`. “V10 unfinished” is not itself an external blocker, but every owning technical/security/external gate must be real and accepted.

`EXECUTABLE_ACCOUNTS = VERIFIED_READ_ACCOUNTS ∩ VERIFIED_TRADE_ACCOUNTS`.

## 12. Security / secrets

Never place real secrets in GitHub, chat, commits, PR comments, CI logs, screenshots or artifacts. Never request real credentials when the task can be completed without receiving them.

Do not disclose broker tokens, Telegram secrets, Timeweb/GitHub provider credentials, DB passwords, encryption/recovery keys, full account IDs or private portfolio payloads. `.env` is local-only from `.env.example`. Runtime secrets belong only in approved Timeweb/provider secret custody at the owning gate.

## 13. Broker / Real-money boundary

Current protected locks: broker write OFF, `trading_methods=false`, `REAL_TRADING_ENABLED=false`, no transfer/withdrawal/margin/leverage/uncovered-short authority.

READ/optional TRADE credentials are tenant-scoped and role-separated. `TRADE credential connected/verified != broker submit authorized`.

Real submit requires `REAL_MONEY_AUTHORIZED` after representative Sandbox/Shadow, immutable plan, authenticated USER approval, drift/preflight, ambiguous-submit reconciliation, kill switches and actual broker permission. GitHub merge, provider deploy/release, AI output, START command or user registration is never broker-submit authorization.

## 14. V9 / V10 boundary

Amendment 20 changes the forward architecture: V9 is a migration source, not a permanent parallel runtime. `V9C-A` completed the accepted-lineage inventory; current checkpoint `V9C-B` relocates the remaining deterministic root engines into canonical `omni_cio/` packages by reuse/extraction and requires zero legacy imports plus parity/verifier migration before root-source deletion. `app.py`, `app_v360.py`, `app_v371.py`, `main.py` remain V9C-C migration inputs; retired provider/GPT working-tree artifacts remain V9C-D inputs. Git history is preserved.

## 15. OWNER participation / handoff law

Do safe repository/GitHub/tool work autonomously. OWNER participation is only for genuinely non-delegable external consent/account/provider UI, physical/UAC, secret custody, domain/payment or Master Plan authority.

When OWNER action is required: provide a direct official HTTPS link when stable, otherwise verified official start URL + exact click path; state exact scope/expected result, stop conditions, do-not-do warnings, minimum safe return and cost/authority consequences. Never ask OWNER to send real secret values. OWNER product acceptance is post-merge/post-Regression-Shield unless a genuinely non-delegable prerequisite must occur earlier.

## 16. Continuity

After a substantial stage leave GitHub-visible handoff with exact base/main/head SHA, execution unit, completed changes, checks/conclusions, review/blockers, remaining work and next authorized step. Do not create a competing current-status document.
