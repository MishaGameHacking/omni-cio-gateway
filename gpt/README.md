# Omni-CIO Custom GPT

> **PROTECTED V9 RECOVERY ONLY — NOT CURRENT V10 AUTHORITY.** This file preserves the accepted Custom GPT v9.0.0 / `app:app` recovery surface. Current V10 implementation authority is the Timeweb + Telegram path defined by Amendments 18–21 and `knowledge/17_V10_CURRENT_PROGRAM_STATUS.md`.

`gpt/` — каноническая папка applied/recovery configuration единственного пользовательского интерфейса проекта: existing Custom GPT `Omni-CIO API | Управляющий и аналитик v9.0.0`.

Applied v9.0.0 was owner-accepted in place on 2026-08-05. Protected rollback remains v8.6.1.

## Быстрый вход

Начинать всегда с:

`SETUP_INDEX.md`

Там находится единая инструкция по настройке, восстановлению, тестированию и обновлению **того же** GPT.

## Как устроена связь

```text
GitHub main ──> Render: Omni-CIO Gateway (`app:app`) ──> T-Invest API
     │
     └────────> canonical applied/recovery Instructions + Knowledge

Existing Custom GPT v9.0.0 Actions ──HTTPS/Bearer──> https://omni-cio-gateway.onrender.com
```

GitHub не является живой памятью GPT и не синхронизирует GPT Editor автоматически. Он хранит проверенный code/config/recovery source. Владелец применяет future configuration changes к существующему GPT только после repository review/Preview.

## Канонические файлы

- `SETUP_INDEX.md` — главная карта настройки, восстановления и обновления.
- `CONFIGURATION.md` — applied Name, Description, conversation starters, capabilities and recovery policy.
- `CUSTOM_GPT_INSTRUCTIONS_V9_0_0_COMPACT.txt` — **applied production Instructions**.
- `KNOWLEDGE_MANIFEST_V9_0_0.md` — exact applied Knowledge registry.
- `knowledge/` — ровно 10 applied Knowledge-файлов.
- `ACTIONS_CATALOG.md` — reviewed baseline/Sandbox/Real Action policy.
- `SECRETS_AND_RENDER.md` — external Render/secrets boundary.
- `MY_GPT_SETUP_RUNBOOK.md` — Preview, Update, recovery and rollback.
- `BOT_ONLY_FILE_MANIFEST.md` — bot/recovery asset manifest.
- `CUSTOM_GPT_INSTRUCTIONS_V8_6_1_COMPACT.txt` — protected rollback Instructions.
- `PROJECT_INSTRUCTIONS.md` / `NEW_CHAT_PROMPT.md` — восстановление контекста разработки в новом рабочем чате.

## Applied Knowledge

Single source: `KNOWLEDGE_MANIFEST_V9_0_0.md`.

Applied set contains exactly one copy of each:

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

Knowledge is reference material. Behavior/execution safety lives in Instructions and server enforcement.

## Production Gateway

- Base: `https://omni-cio-gateway.onrender.com`
- Health: `https://omni-cio-gateway.onrender.com/health`
- OpenAPI: `https://omni-cio-gateway.onrender.com/openapi.json`
- Entrypoint: `app:app`
- API: v3.10.0
- Legacy marker: `trading_methods=false`

The effective `/openapi.json` is runtime Action authority. Baseline read-only flow is preserved, while reviewed Sandbox/Real contours may be conditionally published by server feature/readiness gates.

Reviewed Real operationIds:

- `getRealTradingStatus`
- `prepareRealTrade`
- `executeRealTrade`
- `getRealOrderState`

Internal v9 engines are not automatically Actions.

## Как пользоваться ботом

Обычные фразы работают без знания operationId:

- `Сколько у меня сейчас денег?`
- `Что у меня сейчас в портфеле?`
- `Проверь подключение к брокеру.`
- `Какие операции были за последние 90 дней?`
- `АНАЛИТИК — объясни состояние портфеля простыми словами.`
- `НОВОСТИ — проверь важные события по моим компаниям.`
- `УПРАВЛЯЙ ПОРТФЕЛЕМ — обнови данные и скажи, что делать.`

Если нужен строгий технический тест, можно назвать конкретный Action и добавить `вызови только ...`.

A portfolio-management/advisory request is not real-execution authorization.

## Что умеет

Omni-CIO reads and analyzes T-Invest portfolio/account facts, liquidity, operations, structure, concentration, market data and purchase capacity; reconciles official broker reports; applies v9 routing/policy/research/risk/strategy discipline; supports read-only Watchtower and decision-journal semantics; and can use reviewed protected execution Actions only through the server-controlled confirmation lifecycle.

Real execution remains exact-owner-confirmed, immutable, idempotent and broker-reconciled. It does not enable withdrawal/transfer, margin/short, MARKET/BESTPRICE, stop/replace/async, token management or autonomous recurring real-money execution.

## Как обновлять

1. changes first land in GitHub via branch/PR;
2. merge only after exact-head Regression Shield/security and zero unresolved review threads;
3. Render consumes accepted `main` according to deployment settings;
4. if applied GPT config changes, edit the **existing** GPT, never Create a duplicate;
5. apply reviewed Instructions/Knowledge/OpenAPI/authentication changes;
6. run `MY_GPT_SETUP_RUNBOOK.md` Preview cases;
7. press `Update` only after Preview passes;
8. record non-secret acceptance/restoration evidence.

Current v9 acceptance has already completed this procedure.

## Секреты

В GitHub никогда не хранить значения:

- `TINVEST_TOKEN`;
- `TINVEST_SANDBOX_TOKEN`;
- `TINVEST_TRADING_TOKEN`;
- `GATEWAY_API_KEY`;
- Upstash/QStash keys/tokens;
- Authorization headers;
- полный accountId;
- реальные приватные broker payloads как configuration data.

Secret roles/env names are documented in `SECRETS_AND_RENDER.md`; values remain external.
