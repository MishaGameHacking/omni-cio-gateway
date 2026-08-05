# Master plan Omni-CIO

Эта папка хранит **owner-approved master programs, program locks и audit trail** развития Omni-CIO. Завершённые программы не являются очередью задач; активная программа определяется её Program Lock и Current Status.

## Omni-CIO V10 Personal Autonomous Investment Platform — active feature program

Owner approved the canonical V10 program and issued explicit **`START V10`** on 2026-08-05.

Canonical artifacts:

- `OMNI_CIO_V10_MASTER_PLAN.md` — searchable canonical program for developers/AI/code review;
- `Omni-CIO_V10_Master_Plan_RU.pdf` — owner-readable synchronized copy;
- `OMNI_CIO_V10_MASTER_PLAN.sha256` — integrity manifest;
- `OMNI_CIO_V10_PROGRAM_LOCK.md` — scope/precedence/exclusivity lock;
- `OMNI_CIO_V10_PLAN_READINESS_AUDIT.md` — pre-development readiness audit;
- `OMNI_CIO_V10_START_RECORD.md` — explicit owner start/WP0 evidence;
- `OMNI_CIO_V10_ACCOUNT_INDEPENDENCE_AMENDMENT.md` — historical owner-approved amendment retained as audit trail after consolidation.

Current V10 progress authority:

`../../knowledge/17_V10_CURRENT_PROGRAM_STATUS.md`

Do **not** hard-code the current WP/progress from historical PR text or this index. The status file on accepted `main` is the authority.

V10 is implemented strictly one Work Package at a time. Starting a development WP does not expand broker authority or retire V9 by itself.

## Omni-CIO v9 Portfolio Autopilot — completed protected runtime program

Canonical completed program:

`OMNI_CIO_V9_PORTFOLIO_AUTOPILOT_PROGRAM.md`

Status:

- WP0–WP15 полностью реализованы и merged;
- existing Omni-CIO Custom GPT upgraded in place to **v9.0.0**;
- owner external acceptance completed on 2026-08-05;
- tracking epic #176 and WP15 #216 are closed completed;
- current V9 runtime mode: **controlled maintenance** while V10 is developed;
- protected v8.6.1 remains available as recovery rollback baseline.

Current V9 applied/runtime status is:

`../../knowledge/16_CURRENT_PROGRAM_STATUS.md`

V9 remains the protected production/recovery baseline until a responsible later V10 Work Package explicitly replaces a boundary and passes its Exit Gate.

## Current V10 delivery chain

Canonical sequence is defined only by `OMNI_CIO_V10_MASTER_PLAN.md` and `../../knowledge/17_V10_CURRENT_PROGRAM_STATUS.md`.

Accepted early-program structure:

- WP0 — Program Lock / Architecture Freeze;
- WP1 — Repository Architecture and boundaries;
- WP2 — Toolchain and Dependency Baseline;
- WP3 — V10 Regression Shield;
- WP4 — Release/build provenance/deployment contract;
- only then Block C Lenovo runtime setup begins.

This list is navigation, not evidence that any listed WP is complete. Completion comes only from accepted `main` + Exit Gate evidence recorded in the current status file.

## Для чего использовать master plans

Используйте V10 Master Plan для:

- текущей утверждённой scope/sequence/Definition of Done;
- проверки Work Package deliverables/Exit Gates;
- архитектурных/security/recovery требований;
- оценки, требует ли новая идея owner-approved program amendment.

Используйте completed V9 program для:

- проверки исходно утверждённых V9 требований и Definition of Done;
- architecture/audit trace между V9 WP0–WP15;
- recovery-context для происхождения текущего design;
- регрессионной проверки защищённого runtime baseline.

**Не используйте** completed V9 plan как список “что делать дальше”. Активная feature queue — только accepted V10 program/status.

## Исходная пользовательская спецификация V9

- `OMNI_CIO_MASTER_PROMPT_V9.pdf` — исходный документ, 39 страниц;
- `OMNI_CIO_MASTER_PROMPT_V9.txt` — машинное извлечение текста для поиска, code review и AI-контекста; при расхождении приоритет у PDF.

Исходное имя вложения: `Мастер-промт Omni-CIO(9).pdf`.

SHA-256 PDF: `1fa50e7ca08f9701879bbc98c77f04e12cd66d52d2802e5f44d360e620f530f8`.

Аудит 2026-07-30 подтвердил, что приложенные версии `(8)` и `(9)` побайтно идентичны, поэтому в репозитории хранится одна каноническая копия V9 без дубля.

## Иерархия источников истины

Для **текущего V10 development state**:

1. accepted `main`;
2. `../../AGENTS.md`;
3. `OMNI_CIO_V10_PROGRAM_LOCK.md`;
4. paired `OMNI_CIO_V10_MASTER_PLAN.md` + PDF + SHA manifest;
5. `../../knowledge/17_V10_CURRENT_PROGRAM_STATUS.md`;
6. accepted V10 architecture/ADR/current-WP files;
7. exact-head PR/CI evidence.

Для **текущего V9 runtime/applied state**:

1. accepted `main`, code/tests and deployed contract;
2. `../../knowledge/16_CURRENT_PROGRAM_STATUS.md`;
3. `../../gpt/SETUP_INDEX.md`, `../../gpt/CONFIGURATION.md` and effective production `/openapi.json`;
4. protected V9 recovery contracts.

Для **истории/требований**:

1. V10 Master Plan — owner-approved active program specification;
2. V9 completed program — completed V9 specification/audit trail;
3. PDF/TXT V9 master prompt — original V9 input requirements;
4. closed issues, merged PRs, review comments and commits — implementation evidence at the time they were created.

Historical issue/PR text may correctly describe an older applied version or unfinished WP **at that historical moment**. It is not a current-state instruction after later acceptance.

## Постоянные safety boundaries

V10 development does not remove existing safety boundaries:

- production read-only credential remains isolated;
- Sandbox remains virtual and separately credentialed;
- Real execution remains exact-owner-confirmed, immutable, idempotent, fail-closed and broker-reconciled;
- effective OpenAPI remains current GPT Action authority while the V9 GPT is applied;
- internal engines are not automatically GPT Actions;
- AI has no direct broker-write authority;
- transfer/withdrawal, margin/short, MARKET/BESTPRICE, stop/replace/async and autonomous recurring real-money execution remain outside the current reviewed surface;
- stable current Gateway entrypoint remains `app:app` until an accepted V10 migration explicitly replaces it.

## Правило дальнейших изменений

- не редактировать исходный V9 PDF;
- не подменять требования предположениями;
- не “переоткрывать” completed V9 WP из-за старого unchecked checklist;
- V10 делать строго current-WP focused branch + PR;
- следующую WP начинать только после acceptance Exit Gate предыдущей;
- новую V11/competing program не начинать до V10 final acceptance;
- текущий V10 status фиксировать только в `../../knowledge/17_V10_CURRENT_PROGRAM_STATUS.md`;
- текущий V9 runtime status фиксировать в `../../knowledge/16_CURRENT_PROGRAM_STATUS.md`;
- applied GPT configuration менять только через reviewed repository change → owner Preview → `Update` на том же GPT;
- не создавать второй GPT/Gateway/frontend/Telegram/AI/execution source of truth;
- protected V9/v8.6.1 rollback assets сохранять до отдельного reviewed retirement decision.
