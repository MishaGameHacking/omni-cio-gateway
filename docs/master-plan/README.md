# Master plan Omni-CIO

Эта папка хранит **завершённые owner-approved спецификации и audit trail** развития Omni-CIO. Она не является текущей очередью незавершённых задач.

## Omni-CIO v9 Portfolio Autopilot — completed program

Canonical completed program:

`OMNI_CIO_V9_PORTFOLIO_AUTOPILOT_PROGRAM.md`

Status:

- WP0–WP15 полностью реализованы и merged;
- existing Omni-CIO Custom GPT upgraded in place to **v9.0.0**;
- owner external acceptance completed on 2026-08-05;
- tracking epic #176 and WP15 #216 are closed completed;
- repository mode: **controlled maintenance**;
- protected v8.6.1 remains available only as recovery rollback baseline.

Текущий applied/repository status определяется `../../knowledge/16_CURRENT_PROGRAM_STATUS.md`, а не историческим wording внутри программы или старых issues/PR.

## Для чего использовать master plan сейчас

Используйте v9 program для:

- проверки исходно утверждённых требований и Definition of Done;
- архитектурного/audit trace между WP0–WP15;
- recovery-context, если нужно понять происхождение текущего design;
- оценки того, требует ли новая идея новой owner-approved программы.

**Не используйте** completed master plan как список “что делать дальше”. Новая feature work вне maintenance/security/compatibility/recovery требует отдельного явного owner-approved scope/program.

## Исходная пользовательская спецификация

- `OMNI_CIO_MASTER_PROMPT_V9.pdf` — исходный приложенный документ, 39 страниц.
- `OMNI_CIO_MASTER_PROMPT_V9.txt` — машинное извлечение текста для поиска, code review и AI-контекста; при расхождении приоритет у PDF.

Исходное имя вложения: `Мастер-промт Omni-CIO(9).pdf`.

SHA-256 PDF: `1fa50e7ca08f9701879bbc98c77f04e12cd66d52d2802e5f44d360e620f530f8`.

Аудит 2026-07-30 подтвердил, что приложенные версии `(8)` и `(9)` побайтно идентичны, поэтому в репозитории хранится одна каноническая копия v9 без дубля.

## Иерархия источников истины

Для **текущего состояния**:

1. фактический accepted `main`, код, tests и deployed contract определяют реализованное runtime behavior;
2. `AGENTS.md`, `SECURITY.md`, Regression Shield и security policies определяют обязательные engineering/safety boundaries;
3. `knowledge/16_CURRENT_PROGRAM_STATUS.md` определяет текущий applied/repository status;
4. `README.md`, `docs/README.md`, `gpt/SETUP_INDEX.md` и `gpt/CONFIGURATION.md` дают актуальную навигацию/recovery state;
5. effective production `/openapi.json` определяет runtime GPT Action authority.

Для **истории/требований**:

1. `OMNI_CIO_V9_PORTFOLIO_AUTOPILOT_PROGRAM.md` — утверждённая completed v9 program specification;
2. PDF/TXT master prompt — исходные пользовательские требования;
3. closed issues, merged PR, review comments and commits — implementation evidence at the time they were created.

Historical issue/PR text may correctly say that v8.6.1 was applied or a WP was incomplete **at that historical moment**. Such text is not a current-state instruction after v9 acceptance.

## Постоянные safety boundaries после v9

Completion of v9 does not remove the execution boundary:

- production read-only credential remains isolated;
- Sandbox remains virtual and separately credentialed;
- Real execution remains exact-owner-confirmed, immutable, idempotent, fail-closed and broker-reconciled;
- effective OpenAPI is the only GPT Action authority;
- internal engines are not automatically Actions;
- transfer/withdrawal, margin/short, MARKET/BESTPRICE, stop/replace/async and autonomous recurring real-money execution remain outside the reviewed surface;
- stable Gateway entrypoint remains `app:app`.

## Правило дальнейших изменений

- не редактировать исходный PDF;
- не подменять требования предположениями;
- не “переоткрывать” completed WP только из-за старого unchecked checklist в historical issue;
- maintenance/security/dependency/recovery work делать через focused branch + PR;
- новую feature program начинать только после явного owner approval;
- текущий status фиксировать в `knowledge/16_CURRENT_PROGRAM_STATUS.md`;
- applied GPT configuration менять только через reviewed repository change → owner Preview → `Update` на том же GPT;
- не создавать второй GPT/Gateway/frontend/scheduler или competing setup/configuration source;
- protected v8.6.1 rollback assets сохранять до отдельного reviewed решения об их retirement.
