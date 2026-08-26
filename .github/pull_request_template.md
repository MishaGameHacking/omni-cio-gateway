## Что изменено

Опишите одну логическую цель и выбранный execution unit.

## Причина / source of truth

- Current accepted `main` SHA:
- Execution unit: `FOCUSED_CHANGE` / `INTEGRATED_SYSTEM_UPDATE`
- Current WP / defect / System Update:
- Member milestone(s), если integrated:
- Master Plan / amendment / ADR / contract:
- Почему изменение требуется сейчас:
- OWNER START evidence, если требуется:

## Integrated System Update law

Canonical law: `docs/master-plan/OMNI_CIO_V10_INTEGRATED_SYSTEM_UPDATE_EXECUTION_AMENDMENT.md`.

Для `FOCUSED_CHANGE` отметьте неприменимое как N/A. Для `INTEGRATED_SYSTEM_UPDATE`:

- [ ] Canonical current status явно авторизует exact System Update и его ordered member milestones.
- [ ] Branch Execution Ledger создан по `docs/updates/INTEGRATED_SYSTEM_UPDATE_EXECUTION_LEDGER_TEMPLATE.md`.
- [ ] GitHub System Update dashboard issue создан через repository template.
- [ ] Ledger/dashboard содержат `BRANCH-LOCAL EXECUTION STATE — NOT ACCEPTED MAIN AUTHORITY`.
- [ ] Все required member milestones branch-local PASS в dependency order.
- [ ] Mandatory split triggers проверены: DB/migration ordering, security/authority transition, dependency/toolchain boundary, OWNER/provider action, live/temporal evidence, production cutover, Real-money authority, reviewability limit.
- [ ] `INTEGRATION_READY` установлен только после полного internal preflight и full-diff review.
- [ ] Первый опубликованный implementation head является одним coherent completed head; temporary verifier commits/PRs не использовались.

Execution Ledger / dashboard:

```text
ledger path:
dashboard issue:
INTEGRATION_READY: PASS/FAIL/N/A
```

## Scope

- [ ] Изменение относится к одному текущему authorized execution unit.
- [ ] Не смешан следующий major System Update или несвязанный feature work.
- [ ] Member milestones integrated update не переставлены относительно dependency order.
- [ ] Не создаётся duplicate Gateway/Web/Telegram/AI/scheduler/database/broker/execution stack.
- [ ] Если scope materially изменился, существует OWNER-approved amendment, а не chat-only решение.

## Pre-CI engineering gate

### Root cause / blast radius

Если PR исправляет defect/RED, опишите:

- root cause:
- какие аналогичные места/паттерны найдены поиском по repository:
- blast radius:
- directly coupled producers/consumers/config/workflows:
- adjacent failure modes:
- почему предыдущий preflight не поймал проблему:
- permanent regression/guard:

- [ ] Исправлен класс проблемы, а не только первая упавшая строка, либо доказано, что дефект действительно локальный.
- [ ] Проверены directly coupled producers/consumers/config/workflows.
- [ ] Проверены разумные adjacent failure modes: invalid/missing/stale/duplicate/timeout/restart/auth/recovery по применимости.
- [ ] Для material unexpected RED обновлён `docs/operations/V10_ENGINEERING_FAILURE_LEARNING_LEDGER.md`, если урок переносим на будущие WP.

### Cheap/focused checks before expensive CI

- [ ] Full branch diff против accepted `main` просмотрен **до** запуска финального CI.
- [ ] Format/lint/type/compile preflight пройден по применимому scope.
- [ ] Focused positive + negative tests пройдены.
- [ ] Schema/migration/Terraform/PowerShell/config validation пройдена, если применимо.
- [ ] Dependencies/manifest/lock согласованы; generated locks не правились вручную.
- [ ] Material external dependency/API проверен по актуальной official documentation/support/security информации.
- [ ] External GitHub Actions pinned на full immutable commit SHA.
- [ ] Secret/private-data leakage проверена.
- [ ] Rollback/recovery consequence проверен.
- [ ] Нет известного preflight failure, который намеренно оставлен для обнаружения длинным CI.

Краткое preflight evidence:

```text
commands / focused results / reviewed official dependency state
```

## HEAD FREEZE / verification batch

После публикации verification SHA head заморожен, пока безопасные независимые applicable checks не достигнут terminal state. Первый обычный RED не является поводом немедленно пушить новый symptom-fix commit.

- [ ] Safe batch наблюдался до терминального состояния всех доступных независимых checks.
- [ ] Собран один consolidated finding inventory из Actions/Windows/Sonar/Gitar/SAST/browser/owning gates.
- [ ] Findings сгруппированы по root cause / defect class.
- [ ] `continue-on-error` не использован для fake GREEN.
- [ ] Если продолжение могло раскрыть secret/private data, достичь broker/Real path, сделать destructive migration/provider mutation, uncontrolled spend или cross-tenant exposure — применён safety abort вместо ожидания.

Consolidated finding inventory:

```text
verification SHA:
terminal checks:
findings/root-cause groups:
safety abort: NO / reason
```

Correction batch, если нужен:

```text
all safe findings collected -> systemic hardening -> one coherent correction batch -> full focused preflight -> one new head -> fresh verification
```

Любой новый commit инвалидирует прежнее final exact-head GREEN evidence.

## Fault isolation / degraded behavior

- [ ] Изменение не создаёт ненужный single point of failure для deterministic Core.
- [ ] Для внешних/optional dependencies определены timeout/deadline и bounded retry/idempotency semantics, если применимо.
- [ ] User/system health показывает явный READY/PARTIAL/STALE/DEGRADED/BLOCKED/ERROR/OFFLINE/RECOVERING state вместо ложного успеха.
- [ ] Отказ AI/Research/Telegram/external ingress/другого optional component не валит Core, если безопасная деградация возможна.
- [ ] Money/security/identity/secret/broker authority остаётся fail-closed.
- [ ] Новый язык/runtime/framework добавлен только с concrete component-level justification и reviewed toolchain/recovery/maintenance cost.

## Authority / безопасность

- [ ] Stable protected `app:app` сохранён, если owning accepted migration не заменяет его явно.
- [ ] `PUBLIC_MULTI_USER_ENABLED=false` сохранён, если отдельный activation gate явно не является owning change.
- [ ] `trading_methods=false` сохранён для текущего non-execution surface.
- [ ] `REAL_TRADING_ENABLED=false` сохранён, если текущий later execution WP явно не авторизован Master Plan.
- [ ] Broker write остаётся OFF без owning future gate.
- [ ] Production READ / Sandbox / TRADE credentials не смешаны.
- [ ] Не добавлены transfer/withdrawal, margin/leverage/uncovered-short или новый broker-write bypass.
- [ ] В diff/log/artifact нет real token/key, Authorization header, full account ID, private portfolio payload, recovery/encryption key или raw OWNER identity.
- [ ] Cross-tenant isolation сохраняется fail-closed.
- [ ] Partial/stale/truncated/contradictory data не выдаются за complete/current.
- [ ] Protected V9 rollback сохранён.

## OWNER handoff / external-service action

Canonical standard: `docs/operations/V10_OWNER_ACTION_HANDOFF_STANDARD.md`.

- [ ] OWNER не требуется самостоятельно искать нужную страницу/настройку.
- [ ] Для OWNER browser action дана direct official HTTPS link на exact stable page, если такой URL существует.
- [ ] Если exact deep link нестабилен/непроверяем, дан closest verified official start URL + exact current click path + STOP при отличии UI.
- [ ] Указаны exact account/repository/workspace/service/device scope, expected result, STOP conditions, do-not-do warnings и minimum safe return.
- [ ] Любая стоимость, paid-plan, credential-scope, public-ingress или irreversible authority consequence описана **до** OWNER confirmation.
- [ ] OWNER получает один bounded non-delegable action, а не перенос routine engineering/CI/debugging work.
- [ ] Secret-bearing, shortened, third-party redirect или private-runtime URLs не выдаются как OWNER handoff links.

OWNER handoff evidence, если применимо:

```text
NONE / verified official starting URL + exact bounded action + expected non-secret result
```

## V10 runtime / hosting boundary

- [ ] Final public V10 Web/API/private-state runtime не зависит от OWNER home IP/Wi-Fi/router/LAN/Lenovo.
- [ ] Production-provider apply/public cutover остаётся отдельным fail-closed gate и не выводится из planning/merge/System Update автоматически.
- [ ] Existing Render.com `app:app` сохранён как protected V9 production/recovery baseline до owning parity/decommission gate.
- [ ] Новый provider/runtime не создаёт competing second Web/API/private-state stack.
- [ ] Paid/provider mutation имеет exact OWNER authority и cost revalidation, если применимо.

## Exact-head GREEN merge gate

**All applicable exact-head checks = SUCCESS.**

Project policy is stricter than generic GitHub semantics: applicable `skipped`, `neutral`, `cancelled`, `pending`, `queued`, `in_progress` or infrastructure/billing `failure` are **not GREEN**.

- [ ] Проверен exact current PR head SHA.
- [ ] Все применимые V10 workflows реально запустились.
- [ ] Все применимые checks завершились `success`.
- [ ] Неприменимые workflows не висят misleading skipped/cancelled checks; routing/trigger исправлен по необходимости.
- [ ] Старые GREEN runs предыдущего SHA не используются как final evidence.
- [ ] Full diff reviewed after final code change.
- [ ] Unresolved blocking review threads = 0.
- [ ] P0/P1 blockers = 0.

Final exact-head evidence:

```text
HEAD SHA:
workflow/run IDs:
all applicable conclusions: success
review threads: 0
```

## OWNER participation

- [ ] OWNER product acceptance is post-merge: телефон/browser/UX/login/logout/portfolio comparison не запрашивались для незамерженного implementation PR.
- [ ] Если OWNER участвовал до merge, это был только genuinely non-delegable prerequisite (account/consent/domain/payment/narrow credential/UAC-admin/physical/Master-Plan decision), и scope действия описан ниже.
- [ ] OWNER не использовался как transport layer для обычного CI/debugging/log inspection.

Pre-merge OWNER prerequisite, если был:

```text
NONE / exact prerequisite only; no secrets
```

## Контракты / документация / learning

- [ ] Обновлены canonical docs/contracts; competing source of truth не создан.
- [ ] WP/execution-unit contract отражает pre-CI, negative tests, rollback, internal milestone gates и final acceptance boundary.
- [ ] Failure Learning Ledger обновлён, если неожиданный RED выявил reusable process/technical lesson.
- [ ] Current status изменяется только из accepted evidence; integrated member checkboxes не повышают accepted percentage.
- [ ] Исторические PR/issues не выдаются за current authority.

## Merge / после merge

- [ ] Normal closure: PR будет закрыт squash merge только после полного GREEN exact-head gate.
- [ ] Exact new `main` SHA будет проверен после merge.
- [ ] Required post-merge Regression Shield должен быть GREEN до OWNER product acceptance/следующего major System Update.
- [ ] OWNER product acceptance, если нужен, выполняется только после merge + post-merge GREEN.
- [ ] Если OWNER acceptance найдёт defect: новый authorized `FOCUSED_CHANGE` или correction path; direct patch в `main` запрещён.
- [ ] Известен rollback/recovery path.

## Следующий milestone / System Update

- [ ] Следующий member milestone внутри того же authorized integrated update начинается только после branch-local predecessor Exit evidence.
- [ ] Следующий **major System Update** остаётся LOCKED до полного integrated Exit Gate, merge, exact-main post-merge acceptance и canonical status transition.
