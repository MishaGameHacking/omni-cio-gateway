# Вклад в Omni-CIO

Omni-CIO — один продукт. Protected V9 production/recovery baseline остаётся `existing Custom GPT v9.0.0 + production Gateway app:app`; V10 — единственная active feature program в этом же репозитории.

Protected V9 v9.0.0 remains in controlled maintenance; V10 changes must not reinterpret that historical recovery state.

Dynamic V10 progress/current package authority is only `knowledge/17_V10_CURRENT_PROGRAM_STATUS.md`.

## Перед началом

Перед material change восстановите authority из актуального GitHub `main`:

1. `README.md`;
2. `AGENTS.md`;
3. `CONTRIBUTING.md`;
4. `knowledge/00_PROJECT_MASTER_CONTEXT.md`;
5. `knowledge/16_CURRENT_PROGRAM_STATUS.md` для V9;
6. `docs/master-plan/OMNI_CIO_V10_PROGRAM_LOCK.md`;
7. `docs/master-plan/OMNI_CIO_V10_MASTER_PLAN.md`;
8. `docs/master-plan/OMNI_CIO_V10_AMENDMENTS_INDEX.md` и applicable active amendments, включая Amendments 12–18;
9. `docs/architecture/V10_INTEGRATED_SYSTEM_UPDATE_EXECUTION_CONTRACT.json`, `docs/architecture/V10_GREEN_CHECKPOINT_TARGETED_CI_REPAIR_CONTRACT.json`, `docs/architecture/V10_PROGRESSIVE_CAPABILITY_ACTIVATION_CONTRACT.json`, `docs/architecture/V10_CLOUDFLARE_PLATFORM_AUTHORITY_CONTRACT.json`, `docs/architecture/V10_CLOUDFLARE_PUBLIC_PRODUCT_INTEGRATED_CONTRACT.json` и остальные owning contracts;
10. `docs/master-plan/OMNI_CIO_V10_WP_EXECUTION_TEMPLATE.md`;
11. `knowledge/17_V10_CURRENT_PROGRAM_STATUS.md`;
12. current execution-unit architecture/security/recovery/runbooks/ledgers;
13. actual `main`, recent commits, open PR/issues and GitHub Actions.

Старый chat, screenshots, historical WP contracts, merged/closed PR descriptions и provider dashboard state не заменяют accepted GitHub authority.

## Текущее удобное резюме

- accepted progress: **54%**;
- WP0–WP22A remain COMPLETE;
- current next package: **TIMEWEB-PLATFORM-CONSOLIDATION-INTEGRATED**;
- target active services: ChatGPT + GitHub + Timeweb Cloud + Telegram Login;
- Timeweb is the only selected V10 production infrastructure target;
- Telegram is the only selected human login provider;
- Cloudflare/Neon/Render/Cloud.ru/VK ID are retirement targets;
- WEB-VISUAL and WP23+ remain paused during consolidation;
- public multi-user remains fail-closed until Timeweb/Telegram/legal/privacy/capacity gates;
- broker-write and Real-money remain disabled.

Exact dynamic state still comes only from `knowledge/17_V10_CURRENT_PROGRAM_STATUS.md`.

## GitHub #1 / Timeweb production / Telegram identity

GitHub owns code, reviews, CI evidence and exact-SHA provenance. Timeweb owns the target public runtime, PostgreSQL 18, domain/DNS/TLS, backups/monitoring and network controls. Telegram is product identity only.

The old Cloudflare section below is migration history and no longer selects future/current provider work after Amendment 18 acceptance.

## Historical GitHub #1 / Cloudflare #2 — superseded for future provider selection

After Amendment 14 acceptance:

- GitHub is engineering/source/review/provenance authority rank 1;
- Cloudflare Workers Paid is new-V10 application/edge/build platform rank 2 after each owning gate;
- Cloud.ru Evolution is no longer the selected new-V10 target;
- Render is historical new-V10 evidence only and is retired from active new-V10 deployment, zero-charge attestation, hosted-release alignment and recovery authority;
- protected V9 Render `app:app` remains protected;
- Amendment 14 itself does not deploy Cloudflare, mutate DNS/domain/provider state, create secrets or activate public users.

Amendment 15 changes only delivery granularity: the four Amendment-14 Cloudflare stages are ordered internal milestones inside one `CLOUDFLARE-PUBLIC-PRODUCT-INTEGRATED` branch/final PR by default. Their runtime/security/provider/cutover boundaries remain fail-closed.

Do not create Cloudflare tokens/secrets, candidate mutation, DNS/domain changes or paid overage before the exact internal milestone authorizes them.

Integrated Cloudflare sequence:

1. `CF-A / CLOUDFLARE-BUILDS-VERIFIER-INTEGRATION` — portable repository verification, shard/impact/provenance/cost guards;
2. `CF-B / CLOUDFLARE-RUNTIME-COMPATIBILITY` — React/Vite/backend/native dependency/PostgreSQL/Hyperdrive/Containers evidence;
3. `CF-C / CLOUDFLARE-CANDIDATE-DEPLOYMENT` — immutable candidate provider mutation;
4. `CF-D / CLOUDFLARE-PUBLIC-CUTOVER` — domain/DNS/TLS/security/promotion/rollback and capability-specific live-user acceptance.

Do not start a later internal milestone before the previous milestone's branch-local Exit Gate passes. A separate `main` merge between CF-A…CF-D is not required after Amendment 15 acceptance. A real Amendment-12 mandatory split trigger still forces a stop/split.

## Continuous public release

A new accepted protected `main` SHA is a whole-product revision candidate, not an immediate production deployment.

Required flow:

`exact-head PR GREEN/review -> squash merge -> exact-main post-merge GREEN -> immutable Cloudflare candidate -> candidate acceptance -> production promotion`.

Before promotion re-check current `main`. Never promote a superseded candidate. If the latest `main` is blocked, keep last-known-good production and expose a truthful pending/blocked/out-of-sync state.

Public release identity is event-derived CalVer `YYYY.MM.DD.N` plus exact source SHA, Cloudflare Version ID, UTC release time and status. Do not create a source version-bump commit only to change the displayed release number.

## Execution-unit model

Governed by the **Integrated System Update Execution Law**. Every material change is one of:

- `FOCUSED_CHANGE` — isolated defect, governance/documentation correction, maintenance, independent migration or mandatory split boundary;
- `INTEGRATED_SYSTEM_UPDATE` — one coherent OWNER-authorized subsystem outcome with ordered internal member milestones.

Mandatory split triggers include migration/DB ordering, security/authority transition, dependency/toolchain boundary, non-delegable OWNER/provider action, live/temporal evidence, production cutover, Real-money authority and reviewability limit. Amendment 15 does not remove them.

`INTEGRATION_READY` remains the final whole-update readiness state for an `INTEGRATED_SYSTEM_UPDATE`, but Amendment 16 permits and requires earlier checkpoint certification while work progresses.

For integrated updates maintain the branch Execution Ledger and GitHub System Update dashboard with `BRANCH-LOCAL EXECUTION STATE — NOT ACCEPTED MAIN AUTHORITY`. Internal milestone PASS never changes accepted progress by itself.

## Green Checkpoint & Targeted CI Repair Law

CI is an independent verifier and active checkpoint certifier. Fast CI is used whenever a logical checkpoint needs proof; CI cost/time is not a reason to carry uncertainty forward.

Canonical flow:

`WRITE -> focused preflight -> CHECKPOINT SHA -> CI + Sonar + review -> CERTIFIED_GREEN -> NEXT CHECKPOINT`.

Any material RED immediately changes branch mode to `RED_REPAIR_ONLY`. The next functional checkpoint is forbidden until the current checkpoint is repaired and fully certified.

When RED appears:

1. begin root-cause diagnosis immediately when useful evidence exists; do not wait for every independent job merely to start ordinary repair;
2. determine blast radius, analogous patterns, coupled producers/consumers/config/workflows and adjacent failure modes;
3. fix the defect class and add/strengthen deterministic regression coverage;
4. if source/config is unchanged and the failure is proven transient/infrastructure-only, prefer re-running only the specific failed GitHub Actions job on the same SHA;
5. if source/config/test/governance content changes, the repair necessarily has a replacement SHA; old final evidence is stale;
6. run the smallest canonical targeted recheck proving the reported defect is fixed;
7. fully certify the final replacement exact SHA before beginning the next functional checkpoint.

`git commit --amend` creates a replacement commit/SHA; it does not mutate an existing SHA. Never force-rewrite protected `main` or shared history merely to preserve a one-commit appearance.

Repeated identical “transient” failure becomes an infrastructure/workflow defect and must not be blindly retried until GREEN.

For changed code, applicable Sonar Quality Gate must pass; default new-code requirement is 0 new issues, 0 unresolved new Security Hotspots and 0 unresolved material Reliability/Security/Maintainability findings. Gitar/SAST/check annotations and review threads must also be inspected.

Only `CERTIFIED_GREEN` permits the next functional checkpoint. An applicable post-merge RED on current `main` means `MAIN_RED_STOP` and blocks ordinary feature development until an accepted focused repair restores GREEN.

Canonical law: `docs/master-plan/OMNI_CIO_V10_GREEN_CHECKPOINT_AND_TARGETED_CI_REPAIR_AMENDMENT.md`.
Canonical runbook: `docs/operations/V10_GREEN_CHECKPOINT_CI_RUNBOOK.md`.
Canonical targeted verifier: `.github/workflows/v10-targeted-repair.yml`.

## Files changed / independent code-review gate

Для каждого опубликованного PR head до merge:

1. просмотрите полный GitHub **Files changed** против accepted base;
2. проверьте inline review threads, check annotations, Sonar, Gitar, SAST/security и другие applicable review outputs;
3. классифицируйте material findings по root cause, blast radius, analogous locations, directly coupled surfaces и adjacent failure modes;
4. исправьте реальные correctness/security/maintainability defects и добавьте regression guard для reusable defect class;
5. требуйте `unresolved blocking review threads = 0`;
6. выполните финальный manual engineering diff review.

**Bot approval is supporting evidence**, not a replacement for engineering judgment. Manual review also does not replace applicable CI/security gates.

После любого replacement/correction head обязательны **fresh Files changed + review evidence** на новом exact head.

## PR lifecycle

Никогда не разрабатывайте напрямую в `main`.

Checkpoint lifecycle:

1. fresh accepted `main`;
2. focused/integrated branch;
3. one authorized logical checkpoint;
4. deterministic tests/guards + focused preflight;
5. publish exact checkpoint SHA;
6. CI + Sonar + applicable independent review;
7. any RED -> `RED_REPAIR_ONLY` and immediate targeted repair;
8. source change -> replacement SHA + targeted proof + full exact-SHA certification;
9. only `CERTIFIED_GREEN` -> next functional checkpoint allowed.

Final landing lifecycle:

1. final exact head `CERTIFIED_GREEN`;
2. complete Files changed + independent review;
3. zero blocking threads/findings;
4. squash merge;
5. exact-new-main Regression Shield + owning post-merge gates;
6. accepted status transition only after post-merge success.

DRAFT→READY by itself does not invalidate same-SHA certification unless an applicable workflow/ruleset is intentionally state-dependent. Any content-changing head requires fresh evidence.

`failure`, `cancelled`, `queued`, `pending`, `in_progress`, `timed_out`, `action_required`, `stale`, `neutral` and `skipped` are not GREEN for an applicable gate.

## Progressive Capability Activation

Implemented capability states are exactly:

`IMPLEMENTED | LIVE_OPERABLE | BLOCKED_EXTERNAL | REAL_MONEY_AUTHORIZED`.

One canonical Omni-CIO Web remains the user-facing product. Telegram is the only selected human login provider after Amendment 18 acceptance. A completed capability may become `LIVE_OPERABLE` when all its own technical/security/external gates pass.

Human product authentication remains Telegram Login / VK ID -> verified identity -> `OmniCIOUserAccount -> Tenant -> server-side Session`.

Cloudflare Access/WAF/Turnstile are additive infrastructure security, not product tenant authority.

`EXECUTABLE_ACCOUNTS = VERIFIED_READ_ACCOUNTS ∩ VERIFIED_TRADE_ACCOUNTS`.

## Runtime / data migration

Use the migration preference:

`REUSE_AS_IS > WRAP_ADAPTER > EXTRACT_TO_CORE > REWRITE_REQUIRED > RETIRE`.

Existing React/Vite Web remains canonical source. Python Workers/FastAPI availability does not prove current native/CPython dependencies compatible; test them. Cloudflare Containers may be used only when CF-B proves a concrete full-Linux/native runtime need and cost/recovery semantics are acceptable.

Neon/PostgreSQL 18 tenant/RLS authority remains intact unless an explicit equivalent migration changes it. Do not assume Hyperdrive supports PostgreSQL 18. D1 does not silently replace financial/tenant truth.

Prefer Cloudflare services over replaceable external infrastructure only when semantics are equivalent. Do not remove GitHub or a PostgreSQL/Neon authority boundary simply to claim “Cloudflare-only”.

Current GitHub/Lenovo CI routing stays authoritative until CF-A proves Cloudflare build lanes. Do not fake Windows/PowerShell/ACL/PostgreSQL-native semantics as portable GREEN.

## Security / secrets

Never commit or paste real secrets into source, chat, PR comments, CI logs, screenshots or artifacts.

Never disclose/request when avoidable broker tokens, Telegram/VK secrets, provider API tokens, DB passwords, encryption/recovery keys, full account IDs or private portfolio payloads.

Cloudflare API tokens/secrets are provisioned only through approved secret custody at the owning provider-action milestone.

## Broker / Real-money boundary

Current locks remain:

- broker write OFF;
- `trading_methods=false`;
- `REAL_TRADING_ENABLED=false`;
- no transfer/withdrawal/margin/leverage/uncovered-short authority.

`TRADE credential connected/verified != broker submit authorized`.

Real submit requires `REAL_MONEY_AUTHORIZED` after its complete Sandbox/Shadow, immutable-plan, authenticated USER approval, drift/preflight, reconciliation, kill-switch and actual broker permission gate.

A merge, Cloudflare deployment, public release, AI output or user registration is never Real-money authorization.

## WEB VISUAL lock

`CLOUDFLARE-PUBLIC-PRODUCT-INTEGRATED` deploys the existing accepted presentation. It does not start the visual-refresh package.

Do not start `WEB-VISUAL-INTEGRATED` until the exact OWNER command exists:

`START V10 WEB VISUAL SYSTEM UPDATE`

## Минимальные проверки

Where applicable:

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

Also run current-package focused checks, dependency/security scans, frontend typecheck/lint/test/build/audit and recovery/browser evidence when applicable.

## OWNER handoff

Do safe repository/GitHub/tool work autonomously. Ask OWNER only for genuinely non-delegable physical/provider/consent/secret/domain/payment actions.

When OWNER action is required, provide a direct official HTTPS link when stable, exact click path, scope, expected result, stop conditions, do-not-do warnings and minimum safe return evidence. Never ask OWNER to paste real secret values into chat.
