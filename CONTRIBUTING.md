# Вклад в Omni-CIO

Omni-CIO — один продукт. Protected V9 production/recovery baseline остаётся `existing Custom GPT v9.0.0 + production Gateway app:app`; V10 — единственная active feature program в этом же репозитории.

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
8. `docs/master-plan/OMNI_CIO_V10_AMENDMENTS_INDEX.md` и applicable active amendments, включая Amendments 12, 13 и 14;
9. `docs/architecture/V10_INTEGRATED_SYSTEM_UPDATE_EXECUTION_CONTRACT.json`, `docs/architecture/V10_PROGRESSIVE_CAPABILITY_ACTIVATION_CONTRACT.json`, `docs/architecture/V10_CLOUDFLARE_PLATFORM_AUTHORITY_CONTRACT.json` и остальные owning contracts;
10. `docs/master-plan/OMNI_CIO_V10_WP_EXECUTION_TEMPLATE.md`;
11. `knowledge/17_V10_CURRENT_PROGRAM_STATUS.md`;
12. current execution-unit architecture/security/recovery/runbooks/ledgers;
13. actual `main`, recent commits, open PR/issues and GitHub Actions.

Старый chat, screenshots, historical WP contracts, merged/closed PR descriptions и provider dashboard state не заменяют accepted GitHub authority.

## Текущее удобное резюме

Это не второй progress ledger; точное состояние всегда берётся из `knowledge/17_V10_CURRENT_PROGRAM_STATUS.md`.

- WP0–WP22A / Blocks A–E accepted COMPLETE; progress 54%.
- Product implementation PAUSED during the provider/security transition.
- Current next package after Amendment 14 acceptance: `CLOUDFLARE-BUILDS-VERIFIER-INTEGRATION`.
- `WEB-VISUAL-INTEGRATED` remains prepared and requires its separate exact OWNER start/sequence before source work.
- WP23+ locked.
- `PUBLIC_MULTI_USER_ENABLED=false` remains current fail-closed runtime state.
- Telegram Login, VK ID, public multi-user tenant access and public T-Invest READ remain `BLOCKED_EXTERNAL` until their own gates.
- broker write OFF, `trading_methods=false`, `REAL_TRADING_ENABLED=false`.

## GitHub #1 / Cloudflare #2

After Amendment 14 acceptance:

- GitHub is engineering/source/review/provenance authority rank 1;
- Cloudflare Workers Paid is new-V10 application/edge/build platform rank 2 after each owning gate;
- Cloud.ru Evolution is no longer the selected new-V10 target;
- Render is historical new-V10 evidence only and is retired from active new-V10 deployment, zero-charge attestation, hosted-release alignment and recovery authority;
- protected V9 Render `app:app` remains protected;
- Amendment 14 itself does not deploy Cloudflare, mutate DNS/domain/provider state, create secrets or activate public users.

Do not press Cloudflare `Deploy`, create API tokens/secrets, mutate DNS/domain or authorize paid overage merely because the repository is connected to Workers Builds. Those are separate execution-unit/provider-action gates.

Mandatory Cloudflare sequence:

1. `CLOUDFLARE-BUILDS-VERIFIER-INTEGRATION` — portable repository verification; no production deploy;
2. `CLOUDFLARE-RUNTIME-COMPATIBILITY` — React/Vite/backend/native dependency/PostgreSQL/Hyperdrive evidence;
3. `CLOUDFLARE-CANDIDATE-DEPLOYMENT` — immutable candidate provider mutation;
4. `CLOUDFLARE-PUBLIC-CUTOVER` — domain/DNS/TLS/security/promotion/rollback and capability-specific live-user acceptance.

Do not start a later stage before the previous Exit Gate is accepted.

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

Mandatory split triggers include migration/DB ordering, security/authority transition, dependency/toolchain boundary, non-delegable OWNER/provider action, live/temporal evidence, production cutover, Real-money authority and reviewability limit.

Publication of an `INTEGRATED_SYSTEM_UPDATE` requires reaching `INTEGRATION_READY` before external verification is published.

For integrated updates maintain the branch Execution Ledger and GitHub System Update dashboard with `BRANCH-LOCAL EXECUTION STATE — NOT ACCEPTED MAIN AUTHORITY`. Internal milestone PASS never changes accepted progress by itself.

## Pre-CI / HEAD FREEZE

CI is an independent verifier, not the primary interactive debugger.

Before publishing expensive verification:

- establish root cause for material defects;
- determine blast radius;
- inspect analogous locations and directly coupled producers/consumers/config/workflows;
- inspect adjacent failure modes;
- add deterministic regression guards for reusable defect classes;
- run cheap/focused preflight;
- inspect the complete diff.

After a verification SHA is published, **HEAD FREEZE** applies while safe independent checks reach terminal state. Consolidate findings by root cause and publish one coherent correction batch only after focused/local preflight.

Any new commit invalidates prior final exact-head GREEN and review evidence. `continue-on-error` must never manufacture required GREEN.

## Files changed / independent code-review gate

Для каждого опубликованного PR head до merge:

1. просмотрите полный GitHub **Files changed** против accepted base;
2. проверьте inline review threads, check annotations, Sonar, Gitar, SAST/security и другие applicable review outputs;
3. классифицируйте material findings по root cause, blast radius, analogous locations, directly coupled surfaces и adjacent failure modes;
4. исправьте реальные correctness/security/maintainability defects и добавьте regression guard для reusable defect class;
5. требуйте `unresolved blocking review threads = 0`;
6. выполните финальный manual engineering diff review.

**Bot approval is supporting evidence**, not a replacement for engineering judgment. Manual review also does not replace applicable CI/security gates.

После любого correction commit обязательны **fresh Files changed + review evidence** на новом exact head.

## PR lifecycle

Никогда не разрабатывайте напрямую в `main`.

1. fresh accepted `main`;
2. focused/integrated branch;
3. exact authorized scope;
4. deterministic tests/guards;
5. cheap/focused preflight;
6. complete diff/coupled-surface review;
7. DRAFT PR;
8. all applicable exact-head DRAFT checks actually `success`;
9. independent review + Files changed;
10. zero blocking threads;
11. unchanged head -> READY;
12. fresh applicable READY checks actually `success`;
13. squash merge;
14. exact-new-main Regression Shield + owning post-merge gates;
15. accepted status transition only after post-merge success.

`failure`, `cancelled`, `queued`, `pending`, `in_progress`, `timed_out`, `action_required`, `stale`, `neutral` and `skipped` are not GREEN for an applicable gate.

## Progressive Capability Activation

Implemented capability states are exactly:

`IMPLEMENTED | LIVE_OPERABLE | BLOCKED_EXTERNAL | REAL_MONEY_AUTHORIZED`.

One canonical Omni-CIO Web remains the user-facing product. A completed capability may become `LIVE_OPERABLE` when all its own technical/security/external gates pass; unfinished unrelated V10 work is not itself a blocker.

Human product authentication remains Telegram Login / VK ID -> verified identity -> `OmniCIOUserAccount -> Tenant -> server-side Session`.

Cloudflare Access/WAF/Turnstile are additive infrastructure security, not product tenant authority.

## Runtime / data migration

Use the migration preference:

`REUSE_AS_IS > WRAP_ADAPTER > EXTRACT_TO_CORE > REWRITE_REQUIRED > RETIRE`.

Existing React/Vite Web remains canonical source. Python Workers/FastAPI availability does not prove current native/CPython dependencies compatible; test them.

Neon/PostgreSQL 18 tenant/RLS authority remains intact unless an explicit migration changes it. Do not assume Hyperdrive supports PostgreSQL 18. D1 does not silently replace financial/tenant truth.

Current GitHub/Lenovo CI routing stays authoritative until Cloudflare build lanes are accepted. Do not fake Windows/PowerShell/ACL/PostgreSQL-native semantics as portable GREEN.

## Security / secrets

Never commit or paste real secrets into source, chat, PR comments, CI logs, screenshots or artifacts.

Never disclose/request when avoidable broker tokens, Telegram/VK secrets, provider API tokens, DB passwords, encryption/recovery keys, full account IDs or private portfolio payloads.

Cloudflare API tokens/secrets are provisioned only through approved secret custody at the owning provider-action gate.

## Broker / Real-money boundary

Current locks remain:

- broker write OFF;
- `trading_methods=false`;
- `REAL_TRADING_ENABLED=false`;
- no transfer/withdrawal/margin/leverage/uncovered-short authority.

`TRADE credential connected/verified != broker submit authorized`.

Real submit requires `REAL_MONEY_AUTHORIZED` after its complete Sandbox/Shadow, immutable-plan, authenticated USER approval, drift/preflight, reconciliation, kill-switch and actual broker permission gate.

A merge, Cloudflare deployment, public release, AI output or user registration is never Real-money authorization.

## Минимальные проверки

Where applicable:

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

Also run current-package focused checks, dependency/security scans, frontend typecheck/lint/test/build/audit and recovery/browser evidence when applicable.

## OWNER handoff

Do safe repository/GitHub/tool work autonomously. Ask OWNER only for genuinely non-delegable physical/provider/consent/secret/domain/payment actions.

When OWNER action is required, provide a direct official HTTPS link when stable, exact click path, scope, expected result, stop conditions, do-not-do warnings and minimum safe return evidence. Never ask OWNER to paste real secret values into chat.
