# Custom GPT Omni-CIO

Эта папка хранит воспроизводимую конфигурацию пользовательского интерфейса Omni-CIO внутри ChatGPT. История чатов, память аккаунта и секреты для восстановления не нужны.

## Начинать отсюда

**`SETUP_INDEX.md` — главная страница настройки и восстановления Custom GPT.**

Она отвечает на три практических вопроса:
- что копировать как текст;
- какие файлы скачать и загрузить в Knowledge;
- что импортировать по URL и какие секреты вводятся только вручную.

## Канонические точки входа

- `SETUP_INDEX.md` — единая карта установки/восстановления.
- `MY_GPT_SETUP_RUNBOOK.md` — точная пошаговая настройка ChatGPT → My GPTs.
- `CONFIGURATION.md` — желаемое состояние GPT Editor v8.4.
- `INSTRUCTIONS_COMPACT.md` — рабочий текст, который целиком копируется в поле Instructions.
- `INSTRUCTIONS.md` — расширенная каноническая версия поведения для разработки и аудита.
- `knowledge/` — готовый production-набор `.txt`, который скачивается из GitHub и загружается в GPT Knowledge.
- `ACTIONS_CATALOG.md` — ровно 14 production GET Actions.
- `SECRETS_AND_RENDER.md` — Render, переменные окружения и границы секретов без самих секретов.
- `NEW_ACCOUNT_BOOTSTRAP.md` — запуск в новом аккаунте.
- `BOT_ONLY_FILE_MANIFEST.md` — что относится к боту и что не переносится.
- `PROJECT_INSTRUCTIONS.md` и `NEW_CHAT_PROMPT.md` — восстановление контекста разработки.

Стратегическая спецификация разработки находится в `docs/master-plan/`; фактический выполненный этап и следующий пакет — в `knowledge/16_CURRENT_PROGRAM_STATUS.md`.

## Production Knowledge upload set

В Custom GPT Knowledge загружается набор из `gpt/knowledge/`:

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

Этот каталог является каноническим набором именно для Custom GPT. Не собирать Knowledge из старых локальных копий и случайных чатов.

## Что вводится вручную

- имя, описание, starters, capabilities и sharing;
- полный текст из `INSTRUCTIONS_COMPACT.md`;
- 10 файлов из `gpt/knowledge/`;
- production `/openapi.json` в разделе Actions;
- Authentication → API Key → Bearer;
- секретное значение `GATEWAY_API_KEY` из Render.

`TINVEST_TOKEN` остаётся только на Render и в GPT Editor не вводится.

## Что никогда не хранится в GitHub

- `TINVEST_TOKEN`;
- значение `GATEWAY_API_KEY`;
- Authorization headers;
- полный номер счёта;
- реальные приватные операции/позиции как конфигурационные данные;
- секретные Render exports.

## Синхронизация

Если меняется только поведение ответа:
1. изменить GitHub-файлы через branch/PR;
2. после merge скопировать новый `INSTRUCTIONS_COMPACT.md` и/или скачать изменённые файлы `gpt/knowledge/`;
3. обновить GPT Editor;
4. проверить Preview;
5. нажать Update.

Если меняется OpenAPI:
1. deploy Gateway;
2. проверить production `/health`;
3. повторно импортировать production `/openapi.json`;
4. сверить `ACTIONS_CATALOG.md`;
5. Preview → Update.

Внутри GPT нельзя считать Render/Gateway/GPT acceptance выполненной по одному зелёному CI. Нужны реальные проверки Gateway и Preview.
