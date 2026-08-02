# Omni-CIO bot-only manifest

Этот manifest определяет, что относится к рабочему Omni-CIO Custom GPT и его read-only Gateway. Всё, что не требуется для настройки, работы, безопасности, тестирования или дальнейшего развития этого бота, не должно становиться отдельным активным контуром проекта.

## 1. Главная точка восстановления

`gpt/SETUP_INDEX.md`

Она содержит единый сценарий настройки, восстановления и обновления.

## 2. Production Custom GPT files

| Файл | Назначение |
|---|---|
| `gpt/SETUP_INDEX.md` | Единая карта настройки/обновления |
| `gpt/CONFIGURATION.md` | Name, Description, starters, model, capabilities |
| `gpt/CUSTOM_GPT_INSTRUCTIONS_V8_4_1.txt` | Единственные production Instructions |
| `gpt/ACTIONS_CATALOG.md` | 14 GET Actions |
| `gpt/SECRETS_AND_RENDER.md` | Render/secrets boundary |
| `gpt/MY_GPT_SETUP_RUNBOOK.md` | Полное восстановление |
| `gpt/knowledge/` | Ровно 10 production Knowledge-файлов |

Development continuity:

- `gpt/PROJECT_INSTRUCTIONS.md`
- `gpt/NEW_CHAT_PROMPT.md`

## 3. Production Knowledge upload set

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

Никаких дубликатов и старых версий Knowledge в GPT Editor.

## 4. Gateway/runtime files that must remain

`app.py` — production wrapper и OpenAPI surface.

`app_v371.py`, `app_v360.py` и `main.py` выглядят историческими, но **сейчас являются runtime-зависимостями `app.py`**. Их нельзя удалять как мусор без отдельного compatibility refactor.

Также обязательны:

- domain runtime modules (`portfolio_market.py`, `portfolio_analytics.py`, `cash_liquidity.py`, `purchase_capacity*.py`, `operations_analytics.py`);
- `broker_report_reconciliation/`;
- `omni_cio/` contracts, quality, analytics, risk, market and release modules, которые импортируются/тестируются текущим Gateway;
- `render.yaml`;
- `.env.example` без значений secrets;
- runtime/dev dependency files;
- `tests/` и `scripts/` для Regression Shield;
- `.github/` для CI/security/dependency maintenance.

## 5. Documentation that remains relevant

- `README.md` — текущее устройство проекта и быстрый вход;
- `AGENTS.md` — правила для AI/development;
- `SECURITY.md` — финансовая и secret boundary;
- `knowledge/00_PROJECT_MASTER_CONTEXT.md` — краткая долговременная память;
- `knowledge/16_CURRENT_PROGRAM_STATUS.md` — текущий статус;
- профильные `knowledge/` — domain rules, которые поддерживают runtime;
- `docs/master-plan/` — исходная спецификация развития именно Omni-CIO;
- `docs/architecture/` — действующие contracts/architecture;
- `docs/operations/` — deploy/release/acceptance procedures.

## 6. Намеренно удалённый/неподдерживаемый scope

Не поддерживать отдельный внешний publishing/transport контур, отдельное приложение/сайт, дублирующий Custom GPT, либо broker write execution без нового явного решения владельца.

Удалённые исторические setup-дубли не должны восстанавливаться как параллельные источники истины. Для production Instructions есть один файл — `CUSTOM_GPT_INSTRUCTIONS_V8_4_1.txt`.

## 7. Секреты и приватные данные

В GitHub не хранятся:

- `TINVEST_TOKEN`;
- значение `GATEWAY_API_KEY`;
- Bearer/Authorization headers;
- полный accountId;
- реальные приватные операции/позиции/отчёты как configuration files;
- Render secret exports.

## 8. Внешние ручные настройки

GitHub хранит эталон, но не может сам заполнить GPT Editor.

Вручную в GPT Editor остаются:

1. применение Name/Description/starters;
2. вставка production Instructions;
3. загрузка 10 Knowledge-файлов;
4. выбор supported recommended model;
5. capabilities;
6. импорт production OpenAPI URL;
7. API Key → Bearer;
8. `GATEWAY_API_KEY`;
9. Preview acceptance;
10. `Update`.

`TINVEST_TOKEN` остаётся только в Render.
