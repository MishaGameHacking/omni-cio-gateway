# Omni-CIO Custom GPT

`gpt/` — каноническая папка настройки единственного пользовательского интерфейса проекта: Custom GPT `Omni-CIO API | Управляющий и аналитик v8.4`.

## Быстрый вход

Начинать всегда с:

`SETUP_INDEX.md`

Там находится единая инструкция по настройке, восстановлению, тестированию и обновлению.

## Как устроена связь

```text
GitHub main ──> Render: Omni-CIO Gateway (`app:app`) ──> T-Invest API
     │
     └────────> эталон Instructions/Knowledge для ручного применения в GPT Editor

Custom GPT Actions ──HTTPS/Bearer──> https://omni-cio-gateway.onrender.com
```

GitHub не является живой памятью GPT и не синхронизирует поле Instructions автоматически. Он хранит проверенный код и эталон конфигурации. После изменения Instructions/Knowledge владелец применяет соответствующие файлы в GPT Editor вручную.

## Канонические файлы

- `SETUP_INDEX.md` — главная карта настройки, восстановления и обновления.
- `CONFIGURATION.md` — Name, Description, conversation starters, capabilities, model and publishing checklist.
- `CUSTOM_GPT_INSTRUCTIONS_V8_4_1.txt` — **единственный production-файл**, который целиком вставляется в Instructions.
- `knowledge/` — ровно 10 production Knowledge-файлов.
- `ACTIONS_CATALOG.md` — контрольный список 14 GET Actions.
- `SECRETS_AND_RENDER.md` — границы Render и секретов.
- `MY_GPT_SETUP_RUNBOOK.md` — подробное восстановление после полного сбоя.
- `BOT_ONLY_FILE_MANIFEST.md` — что относится к боту и должно сохраняться.
- `PROJECT_INSTRUCTIONS.md` / `NEW_CHAT_PROMPT.md` — восстановление контекста разработки в новом рабочем чате.

## Production Knowledge

Загружается ровно один экземпляр каждого файла:

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

## Production Gateway

- Base: `https://omni-cio-gateway.onrender.com`
- Health: `https://omni-cio-gateway.onrender.com/health`
- OpenAPI: `https://omni-cio-gateway.onrender.com/openapi.json`
- Entrypoint: `app:app`
- API: v3.10.0
- Surface: 14 GET Actions
- Safety: `trading_methods=false`

## Как пользоваться ботом

Обычные фразы должны работать без знания operationId:

- `Сколько у меня сейчас денег?`
- `Что у меня сейчас в портфеле?`
- `Проверь подключение к брокеру.`
- `Какие операции были за последние 90 дней?`
- `АНАЛИТИК — объясни состояние портфеля простыми словами.`
- `НОВОСТИ — проверь важные события по моим компаниям.`
- `УПРАВЛЯЙ ПОРТФЕЛЕМ — обнови данные и скажи, что делать.`

Если нужен строгий технический тест, можно назвать конкретный Action и добавить `вызови только ...`.

## Что умеет

Omni-CIO читает и анализирует портфель T-Invest, позиции, ликвидность, операции, структуру, концентрацию, рыночные данные и technical purchase capacity; умеет сверять официальный broker report, делать read-only decision review и при необходимости дополнять анализ свежими публичными источниками.

Бот остаётся аналитиком. Он не создаёт, не отправляет, не заменяет и не отменяет заявки, не выводит деньги и не меняет брокерский счёт.

## Как обновлять

Правило простое:

1. изменения сначала фиксируются в GitHub через branch/PR;
2. backend merge проходит только после Regression Shield;
3. Render получает production-код из `main` согласно своей deploy-настройке;
4. если менялись Instructions/Knowledge — соответствующие файлы вручную применяются в GPT Editor;
5. если менялся OpenAPI — schema повторно импортируется по production URL;
6. Preview tests;
7. `Update`.

Точная процедура: `SETUP_INDEX.md`.

## Секреты

В GitHub никогда не хранить:

- `TINVEST_TOKEN`;
- значение `GATEWAY_API_KEY`;
- Authorization headers;
- полный accountId;
- реальные приватные broker payloads как конфигурацию.

`TINVEST_TOKEN` остаётся в Render. `GATEWAY_API_KEY` хранится в Render и как Bearer secret в GPT Action.
