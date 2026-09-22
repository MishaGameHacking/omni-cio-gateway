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
Canonical current verification supersession: `docs/master-plan/OMNI_CIO_V10_GREEN_CHECKPOINT_AND_TARGETED_CI_REPAIR_AMENDMENT.md`.

Для `FOCUSED_CHANGE` отметьте неприменимое как N/A. Для `INTEGRATED_SYSTEM_UPDATE`:

- [ ] Canonical current status явно авторизует exact System Update и его ordered member milestones.
- [ ] Branch Execution Ledger создан по `docs/updates/INTEGRATED_SYSTEM_UPDATE_EXECUTION_LEDGER_TEMPLATE.md`.
- [ ] GitHub System Update dashboard issue создан через repository template.
- [ ] Ledger/dashboard содержат `BRANCH-LOCAL EXECUTION STATE — NOT ACCEPTED MAIN AUTHORITY`.
- [ ] Все required member milestones branch-local PASS в dependency order.
- [ ] Mandatory split triggers проверены: DB/migration ordering, security/authority transition, dependency/toolchain boundary, OWNER/provider action, live/temporal evidence, production cutover, Real-money authority, reviewability limit.
- [ ] `INTEGRATION_READY` используется как final whole-update readiness state перед final landing review.
- [ ] Temporary verifier commits/PRs не использовались.
- [ ] Каждый опубликованный logical checkpoint стал `CERTIFIED_GREEN` до следующего functional checkpoint/dependent milestone.

Execution Ledger / dashboard:

```text
ledger path:
dashboard issue:
current checkpoint SHA:
checkpoint state:
INTEGRATION_READY: PASS/FAIL/N/A
```

## Progressive Capability Activation

Canonical law: `docs/master-plan/OMNI_CIO_V10_LIVE_USER_OPERABILITY_AND_PROGRESSIVE_CAPABILITY_ACTIVATION_AMENDMENT.md`.

Для любого affected user-facing capability:

- Capability ID:
- Accepted current state: `IMPLEMENTED` / `LIVE_OPERABLE` / `BLOCKED_EXTERNAL` / `REAL_MONEY_AUTHORIZED` / N/A-not-implemented
- Proposed state:
- Material activation transition: YES/NO

- [ ] Нереализованная capability не получила fake activation state ради прогресса.
- [ ] `V10 is not finished yet` не используется как external blocker.
- [ ] Перечислены конкретные provider/broker/legal/privacy/secret-custody/runtime/capacity/monitoring blockers, если они есть.
- [ ] Для material transition создан `docs/updates/V10_CAPABILITY_ACTIVATION_LEDGER_TEMPLATE.md` ledger + GitHub Capability Activation dashboard.
- [ ] Ledger/dashboard содержат `WORKING CAPABILITY ACTIVATION STATE — NOT ACCEPTED MAIN AUTHORITY`.
- [ ] Если live proof доступен и безопасен, real supported USER проверяет capability на one canonical Omni-CIO Web через ordinary product path.
- [ ] Multi-user/tenant-isolation negatives доказаны по применимости.
- [ ] Monitoring/revoke/rollback/recovery доказаны по применимости.
- [ ] Accepted capability state отделён от temporary runtime availability/kill-switch suspension.
- [ ] `LIVE_OPERABLE` не трактуется как `REAL_MONEY_AUTHORIZED`.
- [ ] Для broker work READ остаётся независим от unfinished Real execution, TRADE credential не используется как READ fallback.
- [ ] `TRADE credential connected/verified` не трактуется как broker submit authority.
- [ ] Execution eligibility остаётся `VERIFIED_READ_ACCOUNTS ∩ VERIFIED_TRADE_ACCOUNTS`; mismatch fails closed.
- [ ] Real submit остаётся запрещён без owning `REAL_MONEY_AUTHORIZED` gate.
- [ ] Transfer/withdrawal/margin/uncovered-short authority не расширена.
- [ ] В GitHub/CI/chat/evidence нет real provider/broker secret, Authorization header, full broker account ID или private portfolio payload.

Activation evidence:

```text
current state:
proposed state:
external blockers/evidence:
real-user evidence:
multi-user isolation evidence:
kill-switch/runtime availability:
real-money boundary:
```

## Scope

- [ ] Изменение относится к одному текущему authorized execution unit.
- [ ] Не смешан следующий major System Update или несвязанный feature work.
- [ ] Member milestones integrated update не переставлены относительно dependency order.
- [ ] Не создаётся duplicate Gateway/Web/Telegram/AI/scheduler/database/broker/execution stack.
- [ ] Если scope materially изменился, существует OWNER-approved amendment, а не chat-only решение.

## Focused preflight / root-cause engineering gate

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

### Focused checks before checkpoint publication

- [ ] Full changed surface против accepted `main` просмотрен до публикации checkpoint.
- [ ] Format/lint/type/compile preflight пройден по применимому scope.
- [ ] Focused positive + negative tests пройдены.
- [ ] Schema/migration/Terraform/PowerShell/config validation пройдена, если применимо.
- [ ] Dependencies/manifest/lock согласованы; generated locks не правились вручную.
- [ ] Material external dependency/API проверен по актуальной official documentation/support/security информации.
- [ ] External GitHub Actions pinned на full immutable commit SHA.
- [ ] Secret/private-data leakage проверена.
- [ ] Rollback/recovery consequence проверен.
- [ ] Нет известного preflight failure, который намеренно оставлен для CI.

Краткое preflight evidence:

```text
commands / focused results / reviewed official dependency state
```

## Green Checkpoint / targeted CI repair

Canonical law: `docs/master-plan/OMNI_CIO_V10_GREEN_CHECKPOINT_AND_TARGETED_CI_REPAIR_AMENDMENT.md`.
Canonical contract: `docs/architecture/V10_GREEN_CHECKPOINT_TARGETED_CI_REPAIR_CONTRACT.json`.

Flow:

`WRITE -> focused preflight -> CHECKPOINT SHA -> GitHub-native CI/security + independent review -> CERTIFIED_GREEN -> NEXT CHECKPOINT`

On RED:

`CHECKPOINT_RED -> RED_REPAIR_ONLY -> root cause/blast radius -> targeted proof -> replacement SHA if content changed -> full exact-SHA certification -> CERTIFIED_GREEN`

- [ ] Current logical checkpoint ID and exact SHA recorded.
- [ ] Any applicable RED/material review finding immediately changed state to `RED_REPAIR_ONLY`; unrelated feature work stopped.
- [ ] Diagnosis began as soon as useful RED evidence existed; no wait-all requirement was used merely to delay ordinary repair.
- [ ] Relevant findings that arrived from other independent checks before repair finalization were inspected.
- [ ] Same-SHA rerun, if used, was only for unchanged source/config plus evidence-based transient/infrastructure-only failure; specific failed job was preferred.
- [ ] Repeated identical transient failure was not blindly rerun until lucky GREEN.
- [ ] Any content-changing repair created a replacement SHA and prior final CI/review evidence was treated as stale.
- [ ] The reported defect was proved with the smallest canonical targeted check before/full alongside recertification.
- [ ] Final replacement exact SHA received full applicable certification before any next functional checkpoint.
- [ ] `continue-on-error` was not used to manufacture required GREEN.
- [ ] Safety abort took priority where continued execution could expose secret/private data, broker/Real reachability, destructive migration/provider mutation, uncontrolled spend or cross-tenant risk.

Checkpoint evidence:

```text
logical checkpoint:
exact SHA:
state: PENDING / RED_REPAIR_ONLY / TARGET_REPAIRED / CERTIFIED_GREEN
material RED/finding:
root cause / blast radius:
same-SHA rerun evidence: N/A / reason
targeted proof:
replacement SHA: N/A / SHA
full recertification:
```

Любой content-changing commit инвалидирует прежнее final exact-head GREEN и review evidence.

### Files changed / independent review evidence

Для **каждого опубликованного exact PR head** GREEN checks необходимы, но недостаточны сами по себе:

- [ ] Полный GitHub **Files changed** просмотрен на текущем exact head против accepted base.
- [ ] Проверены все inline review threads и check annotations.
- [ ] Проверены GitHub-native lint/type/test/coverage/dependency/SAST/secret/security и другие реально применимые code/security review outputs.
- [ ] Каждый material finding сопоставлен с actual code и классифицирован по root cause, blast radius, analogous locations, coupled surfaces и adjacent failure modes по применимости.
- [ ] Реальные correctness/maintainability/diagnostic/security/review-quality defects исправлены; bot approval не использован как замена engineering judgment.
- [ ] Unresolved blocking review threads = 0.
- [ ] Выполнен финальный manual engineering diff review, даже если bots/findings отсутствуют.
- [ ] После любого content-changing repair прежние GREEN и review evidence признаны stale; на новом exact head повторены Files changed + applicable bot/security review.

```text
HEAD SHA:
Files changed reviewed on HEAD: YES/NO
review sources inspected:
material findings / dispositions:
final manual engineering diff review: PASS/FAIL
fresh after content-changing repair: YES/NO/N/A
```

## Fault isolation / degraded behavior

- [ ] Изменение не создаёт ненужный single point of failure для deterministic Core.
- [ ] Для внешних/optional dependencies определены timeout/deadline и bounded retry/idempotency semantics, если применимо.
- [ ] User/system health показывает явный READY/PARTIAL/STALE/DEGRADED/BLOCKED/ERROR/OFFLINE/RECOVERING state вместо ложного успеха.
- [ ] Отказ AI/Research/Telegram/external ingress/другого optional component не валит Core, если безопасная деградация возможна.
- [ ] Money/security/identity/secret/broker authority остаётся fail-closed.
- [ ] Новый язык/runtime/framework добавлен только с concrete component-level justification и reviewed toolchain/recovery/maintenance cost.

## Authority / безопасность

- [ ] Stable protected `app:app` сохранён, если owning accepted migration не заменяет его явно.
- [ ] Current `PUBLIC_MULTI_USER_ENABLED=false` сохранён, если этот PR не является exact capability-specific activation change с полным accepted external evidence.
- [ ] `trading_methods=false` сохранён для текущего non-execution surface.
- [ ] `REAL_TRADING_ENABLED=false` сохранён, если exact owning Real-money gate не авторизован и не доказан.
- [ ] Broker write остаётся OFF без owning `REAL_MONEY_AUTHORIZED` future gate.
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
- [ ] Capability activation не выводится автоматически из planning/merge/System Update; реальные provider/runtime/privacy/legal/capacity/monitoring gates доказаны для exact proposed transition.
- [ ] Existing Render.com `app:app` сохранён как protected V9 production/recovery baseline до owning parity/decommission gate.
- [ ] Новый provider/runtime не создаёт competing second Web/API/private-state stack.
- [ ] Paid/provider mutation имеет exact OWNER authority и cost revalidation, если применимо.

## Exact-head CERTIFIED_GREEN merge gate

**All applicable exact-head project checks = SUCCESS.**

Project policy is stricter than generic GitHub semantics: applicable `skipped`, `neutral`, `cancelled`, `pending`, `queued`, `in_progress`, `timed_out`, `action_required`, `stale` or infrastructure/billing `failure` are **not GREEN**.

- [ ] Проверен exact current PR head SHA.
- [ ] Current checkpoint state = `CERTIFIED_GREEN`.
- [ ] Все применимые V10 workflows реально запустились.
- [ ] Все применимые checks завершились `success`.
- [ ] GitHub-native quality/security checks PASS when applicable; unresolved material correctness/security/maintainability findings = 0.
- [ ] Неприменимые workflows имеют truthful applicability routing и не используются как fake GREEN.
- [ ] Старые GREEN runs предыдущего SHA не используются как final evidence.
- [ ] Full diff reviewed after final code change.
- [ ] Files changed / independent review evidence выше относится к этому же exact HEAD.
- [ ] Unresolved blocking review threads = 0.
- [ ] P0/P1 blockers = 0.

Final exact-head evidence:

```text
HEAD SHA:
checkpoint state: CERTIFIED_GREEN
workflow/run IDs:
all applicable conclusions: success
GitHub-native quality/security evidence:
review threads: 0
```

DRAFT→READY при неизменном SHA сам по себе не инвалидирует сертификацию, если ни один applicable workflow/ruleset не зависит от этого transition. Любой новый content-changing commit требует fresh evidence.

## OWNER participation / real-user operability

- [ ] OWNER product acceptance is post-merge for ordinary implementation; phone/browser/UX/login/logout/portfolio comparison was not used as a substitute for pre-merge engineering verification.
- [ ] Если OWNER участвовал до merge, это был only genuinely non-delegable prerequisite (account/consent/domain/payment/narrow credential/UAC-admin/physical/Master-Plan decision).
- [ ] OWNER не использовался как transport layer для обычного CI/debugging/log inspection.
- [ ] For an Amendment-13 live capability transition, sanitized real-user operability evidence is collected through the ordinary USER path after engineering/post-merge readiness where required.
- [ ] Real-user evidence contains no secret/private payload and is not confused with broker/Real-money authorization.

Pre-merge OWNER prerequisite, если был:

```text
NONE / exact prerequisite only; no secrets
```

## Контракты / документация / learning

- [ ] Обновлены canonical docs/contracts; competing source of truth не создан.
- [ ] WP/execution-unit contract отражает focused preflight, negative tests, Green Checkpoint/targeted repair, rollback, internal milestone gates, progressive capability-state decision where applicable and final acceptance boundary.
- [ ] Failure Learning Ledger обновлён, если неожиданный RED выявил reusable process/technical lesson.
- [ ] Current status изменяется только из accepted evidence; integrated member/capability working checkboxes не повышают accepted percentage.
- [ ] Исторические PR/issues не выдаются за current authority.

## Merge / после merge

- [ ] Normal closure: PR будет закрыт squash merge только после полного exact-head `CERTIFIED_GREEN` gate.
- [ ] Exact new `main` SHA будет проверен после merge.
- [ ] Required post-merge Regression Shield и owning gates должны быть GREEN до принятия изменения.
- [ ] Applicable post-merge RED на current main означает `MAIN_RED_STOP`; ordinary feature progress запрещён до accepted focused repair.
- [ ] Capability state becomes accepted only from exact-main evidence; merge alone does not imply `LIVE_OPERABLE` or `REAL_MONEY_AUTHORIZED`.
- [ ] Если OWNER/live-user acceptance найдёт defect: новый authorized `FOCUSED_CHANGE` или correction path; direct patch в `main` запрещён.
- [ ] Известен rollback/recovery path.

## Следующий milestone / System Update

- [ ] Следующий functional checkpoint/member milestone внутри того же authorized integrated update начинается только после `CERTIFIED_GREEN` текущего published checkpoint и branch-local predecessor Exit evidence.
- [ ] Следующий **major System Update** остаётся LOCKED до полного integrated Exit Gate, merge, exact-main post-merge acceptance и canonical status transition.
- [ ] Capability activation не используется для ложного unlock следующего implementation WP/System Update.