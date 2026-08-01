# Bot-only file manifest

Этот список содержит только файлы, относящиеся к Omni-CIO Gateway и Custom GPT. Данные старого аккаунта ChatGPT, личные чаты и посторонние проекты сюда не входят.

## 1. Главная точка восстановления Custom GPT

Начинать с:

`gpt/SETUP_INDEX.md`

Этот файл показывает:
- что копировать в GPT Editor;
- какие файлы скачать из GitHub;
- что импортировать по URL;
- где находятся секреты и почему они не хранятся в GitHub.

## 2. Обязательные файлы для Custom GPT

| Файл | Куда использовать |
|---|---|
| `gpt/SETUP_INDEX.md` | Главная карта восстановления |
| `gpt/MY_GPT_SETUP_RUNBOOK.md` | Пошаговая настройка ChatGPT → My GPTs |
| `gpt/CONFIGURATION.md` | Имя, описание, starters, capabilities и publishing checklist |
| `gpt/INSTRUCTIONS_COMPACT.md` | Полностью вставить в поле Instructions GPT Editor |
| `gpt/ACTIONS_CATALOG.md` | Проверка списка Actions и operationId |
| `gpt/SECRETS_AND_RENDER.md` | Render/secrets boundary без секретных значений |
| `gpt/knowledge/` | Скачать 10 `.txt` и загрузить в GPT Knowledge |

`gpt/INSTRUCTIONS.md` — расширенная версия для разработки, аудита и восстановления логики; в GPT Editor по умолчанию вставляется `INSTRUCTIONS_COMPACT.md`.

## 3. Production Knowledge upload set

В `gpt/knowledge/` должны оставаться:

1. `02_GATEWAY_DATA_CONTRACT_V2_OPERATIONS.txt`
2. `04_CIO_PORTFOLIO_MANAGER.txt`
3. `05_ANALYST_NEWS_SIMPLE_LANGUAGE.txt`
4. `06_EVIDENCE_CREDIT_BANKRUPTCY.txt`
5. `07_PERSONAL_STRATEGY.txt`
6. `08_DECISION_JOURNAL_AND_QUALITY_CONTROL.txt`
7. `09_AUTONOMOUS_ACTION_ORCHESTRATOR.txt`
8. `10_DECISION_ENGINE_AND_CANDIDATE_COMPARISON.txt`
9. `11_RISK_DECOMPOSITION_AND_SIZING_GATES.txt`
10. `13_COMMUNICATION_STYLE_2026.txt`

Этот каталог — канонический набор именно для загрузки в production Custom GPT Knowledge.

## 4. Обязательные файлы для нового ChatGPT Project / разработки

| Файл | Назначение |
|---|---|
| `AGENTS.md` | Неприкосновенные правила разработки, read-only и Git workflow |
| `README.md` | Текущая версия, архитектура, запуск и карта репозитория |
| `docs/README.md` | Навигация по документации |
| `knowledge/00_PROJECT_MASTER_CONTEXT.md` | Единая обезличенная память проекта |
| `knowledge/16_CURRENT_PROGRAM_STATUS.md` | Что завершено и какой пакет следующий |
| `docs/master-plan/README.md` | Иерархия и правила использования исходного master plan |
| `docs/master-plan/OMNI_CIO_MASTER_PROMPT_V9.pdf` | Исходная пользовательская спецификация развития |
| `gpt/PROJECT_INSTRUCTIONS.md` | Готовый текст для Project instructions |
| `gpt/NEW_CHAT_PROMPT.md` | Стартовый запрос для нового чата после подключения GitHub |

## 5. Runtime и API

В GitHub обязательно сохраняются:

- `app.py` и Gateway runtime modules;
- `broker_report_reconciliation/`;
- `render.yaml`;
- `requirements.txt` и dev dependencies;
- `tests/`;
- `scripts/`;
- `.github/`;
- OpenAPI-контракт, формируемый работающим Gateway через `/openapi.json`.

## 6. Что намеренно не переносится и не хранится в GitHub

- экспорт аккаунта ChatGPT;
- старые личные чаты;
- память и настройки другого аккаунта;
- файлы других проектов;
- значение `TINVEST_TOKEN`;
- значение `GATEWAY_API_KEY`;
- Authorization headers;
- действующие или отозванные сторонние credentials;
- полный номер брокерского счёта;
- реальные операции, позиции и брокерские отчёты как постоянная конфигурация;
- Render secret exports;
- секретный Bearer key из GPT Editor.

## 7. Внешние настройки, которые вводятся вручную

GitHub хранит желаемую конфигурацию, но не секретные значения. В Custom GPT вручную выполняются только:

1. открыть существующий GPT или создать его при полном восстановлении;
2. имя/описание/starters из `CONFIGURATION.md`;
3. вставка `INSTRUCTIONS_COMPACT.md`;
4. загрузка 10 файлов `gpt/knowledge/`;
5. настройка capabilities;
6. импорт production `/openapi.json`;
7. Authentication → API Key → Bearer;
8. ввод существующего `GATEWAY_API_KEY` из Render;
9. Preview tests;
10. Update.

Существующий Render Gateway и T-Invest token не создаются заново без отдельной причины.
