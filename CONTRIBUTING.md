# Вклад в Omni-CIO

Omni-CIO — один продукт. Текущий production/recovery runtime остаётся **existing Custom GPT v9.0.0 + production Gateway `app:app`**, а owner-approved V10 развивается в этом же репозитории по canonical sequence и active amendments.

V9 WP0–WP15 завершены и owner-accepted; V9 runtime остаётся в режиме **controlled maintenance**. V10 активирована владельцем командой `START V10` 2026-08-05.

## Перед началом

1. Прочитайте `AGENTS.md`.
2. Прочитайте `README.md`, `docs/README.md` и `docs/DOCUMENTATION_AUTHORITY_AND_LIFECYCLE.md`.
3. Прочитайте `knowledge/00_PROJECT_MASTER_CONTEXT.md`.
4. Прочитайте `knowledge/16_CURRENT_PROGRAM_STATUS.md` для текущего V9 runtime baseline.
5. Прочитайте `docs/master-plan/OMNI_CIO_V10_PROGRAM_LOCK.md`, `docs/master-plan/OMNI_CIO_V10_MASTER_PLAN.md`, `docs/master-plan/OMNI_CIO_V10_AMENDMENTS_INDEX.md` и все active amendments, включая `OMNI_CIO_V10_INTEGRATED_SYSTEM_UPDATE_EXECUTION_AMENDMENT.md`.
6. Прочитайте `docs/architecture/V10_INTEGRATED_SYSTEM_UPDATE_EXECUTION_CONTRACT.json` и `docs/master-plan/OMNI_CIO_V10_WP_EXECUTION_TEMPLATE.md`.
7. Прочитайте `knowledge/17_V10_CURRENT_PROGRAM_STATUS.md` — единственный accepted V10 progress/current-next execution ledger.
8. Прочитайте профильные architecture/security/recovery/runbook/ledger current execution unit.
9. Для current GPT/config/recovery задач прочитайте `gpt/SETUP_INDEX.md` и `gpt/CONFIGURATION.md`.
10. Проверьте actual `main`, open PR/issues и latest GitHub Actions.

Закрытые issues, merged PR, package-local execution contracts и старые комментарии — **исторические снимки**. Если они противоречат accepted `main`, Program Lock, accepted amendments или current status files, текущий source of truth имеет приоритет.

## Текущее состояние

- Applied external GPT: **v9.0.0**, owner-accepted in place on 2026-08-05.
- Protected rollback: **v8.6.1**.
- Gateway entrypoint: `app:app`.
- V9 runtime mode: **controlled maintenance**.
- V10 feature program: active; exact accepted progress/current execution authority is only `knowledge/17_V10_CURRENT_PROGRAM_STATUS.md`.
- WP0–WP22A are accepted COMPLETE; accepted progress remains 54%.
- Engineering Quality / Pre-CI / Green-Merge governance: **accepted and active**.
- **Integrated System Update Execution Law** / Amendment 12 governs delivery granularity when accepted on protected `main`.
- Post-Amendment-12 product state: `PRODUCT IMPLEMENTATION PAUSED`; next prepared update `WEB-VISUAL-INTEGRATED`; exact OWNER command required to start product work: `START V10 WEB VISUAL SYSTEM UPDATE`.
- WP23+, public production activation, broker write and Real execution remain locked.

Do not maintain a second `NEXT` or V10 percentage in this contributor guide; the lines above are only a convenience summary and defer to current status.

## Execution-unit model

Every material change is exactly one of:

- `FOCUSED_CHANGE` — isolated defect, governance/documentation correction, maintenance item, independent migration step or mandatory split boundary;
- `INTEGRATED_SYSTEM_UPDATE` — one coherent OWNER-authorized subsystem outcome with ordered member WP/increments.

An integrated update keeps member milestones sequential but uses one integrated branch and one final PR by default. Internal milestone PASS is branch-local only; accepted percentage changes only after full integrated merge plus required exact-main post-merge acceptance.

Every integrated update must keep:

- branch Execution Ledger from `docs/updates/INTEGRATED_SYSTEM_UPDATE_EXECUTION_LEDGER_TEMPLATE.md`;
- GitHub System Update dashboard issue from `.github/ISSUE_TEMPLATE/v10_integrated_system_update.yml`;
- banner `BRANCH-LOCAL EXECUTION STATE — NOT ACCEPTED MAIN AUTHORITY` in both working records.

Before external publication, complete every required member milestone, focused/local checks, full-diff review, coupled-surface review, analogous-pattern/adjacent-failure review, regression guards and mandatory split-trigger review. Only then mark `INTEGRATION_READY`.

## HEAD FREEZE / correction-batch law

After a verification SHA is published, **HEAD FREEZE** applies while safe independent checks reach terminal state. Do not push one fix per first failing symptom.

Where safe:

1. collect Actions/Windows/Sonar/Gitar/SAST/browser/owning-gate results;
2. build one consolidated finding inventory;
3. group findings by root cause / defect class;
4. determine blast radius, analogous patterns, coupled producers/consumers/config/workflows and adjacent failure modes;
5. add permanent regression guards;
6. produce one coherent **correction batch**;
7. rerun focused/local preflight;
8. publish one new head and collect fresh exact-head evidence.

Safety abort overrides diagnostic completeness if continued execution could expose secrets/private data, reach broker/Real authority, perform destructive migration/provider mutation, create uncontrolled spend or cross-tenant exposure.

Any new commit invalidates previous final exact-head GREEN evidence. `continue-on-error` must never be used to manufacture required GREEN.

## Mandatory split triggers

An `INTEGRATED_SYSTEM_UPDATE` must split when evidence requires a separate accepted state for:

- DB/migration ordering;
- security/authority transition;
- dependency/toolchain boundary;
- genuinely non-delegable OWNER/provider action;
- live/temporal evidence;
- production cutover;
- Real-money authority;
- reviewability limit.

WP numbering alone is not a split trigger.

## Неприкосновенные правила

### Product/runtime

- Не создавать второй Custom GPT, duplicate Gateway, parallel frontend/scheduler/AI stack или competing broker stack.
- Сохранять стабильный V9 Render entrypoint `app:app`, пока отдельный accepted V10 migration package не докажет replacement.
- Internal Python engine не считать GPT Action, если его operationId отсутствует в effective production OpenAPI.
- `docs/architecture/REPOSITORY_STRUCTURE.md` определяет canonical repository ownership.
- `scripts/check_v10_repository_boundaries.py`, `scripts/check_v10_engineering_governance.py`, `scripts/check_v10_integrated_system_update_governance.py` и `scripts/check_v10_documentation_consistency.py` являются обязательными guards и не должны ослабляться ради merge.

### Broker contours

Production intentionally contains isolated READ/Sandbox/Real contours. Do not collapse these boundaries.

Real execution remains later-gated, exact-user-confirmed, immutable, idempotent and broker-reconciled. No transfer/withdrawal, margin/leverage/uncovered-short authority or autonomous recurring real-money execution may be introduced outside its owning future gate.

`trading_methods=false` and `REAL_TRADING_ENABLED=false` remain protected. `START V10`, Amendment 12, an internal milestone, development approval, AI output or alert acknowledgement is not broker-submit authorization.

### Public product

- `PUBLIC_MULTI_USER_ENABLED=false` remains the safe default until its separate activation gate.
- Final public production must not depend on OWNER home IP/Wi-Fi/router/LAN/Lenovo.
- Final public Web/API/private-state hosting uses the accepted managed-cloud boundary selected by owning authority.
- Public T-Invest functionality remains `FAIL_CLOSED_PENDING_BROKER_TERMS_PERMISSION`.
- Initial USER access remains free; billing/trial/subscription/premium gating stay disabled until separately changed by accepted authority.

### Data/security

- Account IDs remain masked in user-facing output.
- Never commit token/key values, Authorization headers, full account IDs, private broker payloads or secret exports.
- Currencies are not aggregated without verified FX + timestamp.
- Do not double-count payments, commissions, child operations or embedded trades.
- Partial/stale/truncated/contradictory data is never presented as complete/current truth.
- Generated lock files are not edited manually; `.in` files are canonical direct constraints.
- External GitHub Actions stay pinned to full commit SHA.
- Cross-tenant secret/data access remains forbidden.

## Development/test bootstrap baseline

WP1 established repository ownership and WP2 already selected and accepted the reproducible V10 toolchain/dependency baseline.

Canonical V10 toolchain sources:

- `docs/architecture/V10_TOOLCHAIN_BASELINE.md`;
- `docs/architecture/V10_TOOLCHAIN_BASELINE.json`.

Do not infer versions from memory or blindly upgrade to `latest`. Material dependency/runtime changes follow accepted support/security/license/platform/reproducibility/rollback review and may trigger Amendment-12 dependency/toolchain split requirements.

Safe local configuration starts from `.env.example`. Real secret values stay outside GitHub.

Canonical Python dependency sources/locks remain `requirements.in`, `requirements.txt`, `requirements-dev.in`, `requirements-dev.txt`.

## Рабочий процесс

Для `FOCUSED_CHANGE`:

1. Создайте focused branch от актуального accepted `main`.
2. Зафиксируйте exact defect/governance unit и source of truth.
3. Установите root cause, blast radius и analogous locations для material defect.
4. Сделайте минимальное coherent изменение.
5. Добавьте deterministic regression guard для reusable defect class.
6. Выполните cheap/focused preflight и full diff.
7. Опубликуйте PR и требуйте all applicable exact-head `success`.
8. Resolve blockers, squash merge, verify exact new main and required post-merge gates.

Для `INTEGRATED_SYSTEM_UPDATE`:

1. Требуется exact accepted current-status authorization и, когда предусмотрено, exact OWNER START.
2. Создайте one integrated branch from current accepted main.
3. Ведите Ledger + dashboard.
4. Выполняйте ordered member milestones branch-locally.
5. Re-check accepted-main drift during long-lived work.
6. До публикации достигните `INTEGRATION_READY`.
7. Publish one coherent head / DRAFT PR.
8. Apply HEAD FREEZE and collect full safe verification batch.
9. If findings exist, diagnose systemically and publish one correction batch after local preflight.
10. Require fresh final DRAFT GREEN, independent review, READY fresh GREEN, zero blockers.
11. Squash merge, exact-main Regression Shield/owning post-merge gates, then status transition.

Repository merge сам по себе не меняет GPT Editor и не расширяет Real-money/public-production authority.

## Минимальные проверки

Точный набор команд и routing определяет current repository governance. Среди постоянных проверок:

```bash
python scripts/check_ci_security_baseline.py
python scripts/check_repository_layout.py
python scripts/check_v10_repository_boundaries.py
python scripts/check_v10_engineering_governance.py
python scripts/check_v10_integrated_system_update_governance.py
python scripts/check_v10_documentation_consistency.py
python scripts/check_gpt_recovery_consistency.py
python -m ruff check .
python -m ruff format --check .
python -m mypy
python -m pytest -q --cov --cov-branch --cov-fail-under=60
```

Dependency audit, SAST, secret scan, frontend type/lint/test/build/audit and owning focused checks run where applicable. Do not weaken a gate to make a PR green.

## Требования к Pull Request

PR должен объяснять:

- execution unit и exact current authority;
- current WP/member milestones/defect/System Update;
- accepted base SHA;
- root cause/blast radius для material defect;
- полный changed surface и coupled producers/consumers;
- mandatory split-trigger review для integrated work;
- `INTEGRATION_READY` evidence для integrated work;
- verification SHA + HEAD FREEZE consolidated finding inventory;
- correction batch/root-cause groups, если применимо;
- runtime/data/GPT/public/broker contours;
- credentials/tenant/authority boundaries;
- cheap/focused preflight и exact-head gates;
- deterministic regression guards;
- canonical docs;
- dependencies/locks/Action SHAs;
- rollback path;
- post-merge OWNER acceptance, если required.

## Исторические записи GitHub

Не переписывайте исторический смысл merged PR/closed issue/WP record так, будто он всегда описывал текущее состояние. Если старый файл может ввести в заблуждение, добавьте lifecycle/supersession note и ссылку на current status.

Current status должен жить в canonical status file, а не в случайном старом комментарии, dashboard checkbox или branch Execution Ledger.
