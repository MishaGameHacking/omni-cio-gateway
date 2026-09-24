# Вклад в Omni-CIO

Omni-CIO — один продукт. V10 — единственная active feature/runtime line. Accepted V9 target `b9e4fabcb54f8f6e0ba206f030c35f2fafa2ce62` является **V9 migration source** и уже находится в ancestry current main; stale `v9/*` branch-head не вливается в PR #584.

OWNER-approved convergence выполняется внутри той же ветки #584 начиная с `V9C-A / AUTHORITY_AND_INVENTORY`: reuse/extract нужной V9-логики в canonical V10/Timeweb, затем доказанное удаление legacy working-tree paths при сохранении Git history.

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
8. `docs/master-plan/OMNI_CIO_V10_AMENDMENTS_INDEX.md` и applicable active amendments, включая Amendments 12–20;
9. `docs/architecture/V10_INTEGRATED_SYSTEM_UPDATE_EXECUTION_CONTRACT.json`, `docs/architecture/V10_GREEN_CHECKPOINT_TARGETED_CI_REPAIR_CONTRACT.json`, `docs/architecture/V10_PROGRESSIVE_CAPABILITY_ACTIVATION_CONTRACT.json`, current Timeweb/Telegram owning contracts и остальные applicable current contracts; historical Cloudflare contracts read only when recovery/provenance/compatibility review requires them;
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
- broker-write and Real-money remain disabled;
- V9C-A→V9C-F convergence runs inside PR #584; merging PR #584 to `main` still requires a new explicit OWNER instruction.

Exact dynamic state still comes only from `knowledge/17_V10_CURRENT_PROGRAM_STATUS.md`.

## GitHub #1 / Timeweb production / Telegram identity

GitHub owns code, reviews, CI evidence and exact-SHA provenance. Timeweb owns the target public runtime, PostgreSQL 18, domain/DNS/TLS, backups/monitoring and network controls. Telegram is product identity only.

The old Cloudflare section below is migration history and no longer selects future/current provider work after Amendment 18 acceptance.

## Historical GitHub #1 / Cloudflare #2 — superseded for future provider selection

After Amendment 14 acceptance:

- GitHub is engineering/source/review/provenance authority rank 1;
- Cloudflare Workers Paid was the historical Amendment-14 rank-2 application/edge/build target and is superseded by Amendment 18;
- Cloud.ru Evolution is no longer the selected new-V10 target;
- Render is historical new-V10 evidence only and is retired from active new-V10 deployment, zero-charge attestation, hosted-release alignment and recovery authority;
- protected V9 Render `app:app` remains protected;
- Amendment 14 itself does not deploy Cloudflare, mutate DNS/domain/provider state, create secrets or activate public users.

Historically, Amendment 15 grouped the four Amendment-14 Cloudflare stages into one `CLOUDFLARE-PUBLIC-PRODUCT-INTEGRATED` branch/final PR. That sequence remains accepted provenance only and grants no current provider authority.

Do not create new Cloudflare tokens/secrets, candidate mutations, DNS/domain changes or paid resources. Current provider work is Timeweb-only unless a fresh accepted amendment changes authority.

Historical integrated Cloudflare sequence (provenance only):

1. `CF-A / CLOUDFLARE-BUILDS-VERIFIER-INTEGRATION` — portable repository verification, shard/impact/provenance/cost guards;
2. `CF-B / CLOUDFLARE-RUNTIME-COMPATIBILITY` — React/Vite/backend/native dependency/PostgreSQL/Hyperdrive/Containers evidence;
3. `CF-C / CLOUDFLARE-CANDIDATE-DEPLOYMENT` — immutable candidate provider mutation;
4. `CF-D / CLOUDFLARE-PUBLIC-CUTOVER` — domain/DNS/TLS/security/promotion/rollback and capability-specific live-user acceptance.

Within that historical sequence, later CF milestones depended on earlier branch-local Exit Gates. Those CF milestones are not current work after Amendment 18. A real Amendment-12 mandatory split trigger still governs current work.

## Continuous public release

A new accepted protected `main` SHA is a whole-product revision candidate, not an immediate production deployment.

Required flow:

`exact-head PR GREEN/review -> squash merge -> exact-main post-merge GREEN -> exact Timeweb candidate -> candidate acceptance -> production promotion`.

Before promotion re-check current `main`. Never promote a superseded candidate. If the latest `main` is blocked, keep last-known-good production and expose a truthful pending/blocked/out-of-sync state.

Current release identity must bind the exact accepted source SHA to the accepted Timeweb candidate/deployment identity and release status defined by the owning Timeweb gate. Do not create a source version-bump commit only to change the displayed release number.

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

`WRITE -> focused preflight -> CHECKPOINT SHA -> GitHub-native CI/security/review -> CERTIFIED_GREEN -> NEXT CHECKPOINT`.

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

For changed code, applicable GitHub-native lint/type/test/coverage/dependency/SAST/secret/security checks must pass and unresolved material correctness/security/maintainability findings are not GREEN. Check annotations and review threads must also be inspected.

Only `CERTIFIED_GREEN` permits the next functional checkpoint. An applicable post-merge RED on current `main` means `MAIN_RED_STOP` and blocks ordinary feature development until an accepted focused repair restores GREEN.

Canonical law: `docs/master-plan/OMNI_CIO_V10_GREEN_CHECKPOINT_AND_TARGETED_CI_REPAIR_AMENDMENT.md`.
Canonical runbook: `docs/operations/V10_GREEN_CHECKPOINT_CI_RUNBOOK.md`.
Canonical targeted verifier: `.github/workflows/v10-targeted-repair.yml`.

## Files changed / independent code-review gate

Для каждого опубликованного PR head до merge:

1. просмотрите полный GitHub **Files changed** против accepted base;
2. проверьте inline review threads, check annotations, GitHub-native SAST/security/dependency/secret checks и другие applicable review outputs;
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
6. GitHub-native CI/security + applicable independent review;
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

Human product authentication is `Telegram Login -> verified identity -> OmniCIOUserAccount -> Tenant -> server-side Session`.

Timeweb ingress/network controls are additive infrastructure security, not product tenant authority.

`EXECUTABLE_ACCOUNTS = VERIFIED_READ_ACCOUNTS ∩ VERIFIED_TRADE_ACCOUNTS`.

## Runtime / data migration

Use the migration preference:

`REUSE_AS_IS > WRAP_ADAPTER > EXTRACT_TO_CORE > REWRITE_REQUIRED > RETIRE`.

Existing React/Vite Web and Python/FastAPI product API remain canonical/provider-neutral. Timeweb-specific deployment logic belongs in thin infrastructure adapters.

Timeweb Managed PostgreSQL 18 is the final relational target after the owning production cutover. Preserve migrations, exact numeric semantics, least-privilege runtime role, RLS/FORCE-RLS, cross-tenant negatives, backup/restore and recovery evidence.

Cloudflare/Neon/Render/Cloud.ru/VK files stay archive-in-place by default. Do not add new dependencies on them and do not mass-delete them merely to simplify the tree. Their live provider resources/secrets/actions are decommissioned only after replacement acceptance.

GitHub/self-hosted verification remains authoritative until a stronger GitHub-executed replacement is accepted. External CI/review SaaS may not be removed by weakening quality gates.

## Security / secrets

Never commit or paste real secrets into source, chat, PR comments, CI logs, screenshots or artifacts.

Never disclose/request when avoidable broker tokens, Telegram secrets, Timeweb/GitHub provider credentials, DB passwords, encryption/recovery keys, full account IDs or private portfolio payloads.

Runtime/provider secrets are provisioned only through approved Timeweb/GitHub secret custody at the owning provider-action milestone.

## Broker / Real-money boundary

Current locks remain:

- broker write OFF;
- `trading_methods=false`;
- `REAL_TRADING_ENABLED=false`;
- no transfer/withdrawal/margin/leverage/uncovered-short authority.

`TRADE credential connected/verified != broker submit authorized`.

Real submit requires `REAL_MONEY_AUTHORIZED` after its complete Sandbox/Shadow, immutable-plan, authenticated USER approval, drift/preflight, reconciliation, kill-switch and actual broker permission gate.

A merge, provider deployment, public release, AI output or user registration is never Real-money authorization.

## WEB VISUAL lock

Historical `CLOUDFLARE-PUBLIC-PRODUCT-INTEGRATED` preserved the accepted presentation and did not start the visual-refresh package; it is not current deployment authority.

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
