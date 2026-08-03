# Omni-CIO bot-only manifest

Этот manifest определяет единственный поддерживаемый Omni-CIO Custom GPT и связанные с ним production/recovery assets.

## 1. Единственный продукт

`Omni-CIO Custom GPT → Omni-CIO Gateway → T-Invest API`

Current production UI:

`Omni-CIO API | Управляющий и аналитик v8.6.1`

Не создавать второго Custom GPT, отдельный дублирующий frontend, второй Gateway или параллельный execution surface без явного решения владельца.

## 2. Главная точка восстановления

`gpt/SETUP_INDEX.md`

Она содержит единый сценарий настройки, восстановления и обновления.

Canonical production registry:

- Gateway: `https://omni-cio-gateway.onrender.com`;
- OpenAPI: `https://omni-cio-gateway.onrender.com/openapi.json`;
- Health: `https://omni-cio-gateway.onrender.com/health`;
- Entrypoint: `app:app`;
- Instructions: `gpt/CUSTOM_GPT_INSTRUCTIONS_V8_6_1_COMPACT.txt`;
- full engineering reference: `gpt/CUSTOM_GPT_INSTRUCTIONS_V8_6_0.txt`.

## 3. Активная программа развития

`docs/master-plan/OMNI_CIO_V9_PORTFOLIO_AUTOPILOT_PROGRAM.md`

Программа owner-approved и program-locked. Пока её Definition of Done не завершён, разработка должна следовать WP0–WP15. Допустимы также только блокирующие исправления, security/dependency maintenance и сохранение стабильного v8.6.1.

Protected baseline/migration contract:

`docs/architecture/V9_BASELINE_AND_RECOVERY_CONTRACT.md`

## 4. Production Custom GPT files

| Файл | Назначение |
|---|---|
| `gpt/SETUP_INDEX.md` | Единая карта настройки/обновления |
| `gpt/CONFIGURATION.md` | Name, Description, starters, model, capabilities |
| `gpt/CUSTOM_GPT_INSTRUCTIONS_V8_6_1_COMPACT.txt` | Канонические production Instructions |
| `gpt/CUSTOM_GPT_INSTRUCTIONS_V8_6_0.txt` | Полный engineering reference |
| `gpt/ACTIONS_CATALOG.md` | Production Actions |
| `gpt/SECRETS_AND_RENDER.md` | Render/secrets boundary |
| `gpt/MY_GPT_SETUP_RUNBOOK.md` | Полное восстановление |
| `gpt/knowledge/` | Ровно 10 production Knowledge-файлов |

Development continuity:

- `gpt/PROJECT_INSTRUCTIONS.md`;
- `gpt/NEW_CHAT_PROMPT.md`;
- `AGENTS.md`;
- `knowledge/00_PROJECT_MASTER_CONTEXT.md`;
- `knowledge/16_CURRENT_PROGRAM_STATUS.md`;
- `docs/master-plan/OMNI_CIO_V9_PORTFOLIO_AUTOPILOT_PROGRAM.md`.

## 5. Production Knowledge upload set

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

## 6. Gateway/runtime files that must remain

- `app.py` — production wrapper и OpenAPI surface;
- `app_v371.py`, `app_v360.py`, `main.py` — current runtime dependencies до отдельного compatibility refactor;
- domain runtime modules;
- `broker_report_reconciliation/`;
- `omni_cio/` contracts, quality, analytics, risk, market, Sandbox and real-trading modules;
- `render.yaml`;
- `.env.example` без secrets;
- dependency files;
- `tests/`, `scripts/`, `.github/` для Regression Shield.

## 7. Required documentation

- `README.md`;
- `AGENTS.md`;
- `SECURITY.md`;
- `knowledge/00_PROJECT_MASTER_CONTEXT.md`;
- `knowledge/16_CURRENT_PROGRAM_STATUS.md`;
- `docs/master-plan/OMNI_CIO_V9_PORTFOLIO_AUTOPILOT_PROGRAM.md`;
- `docs/architecture/V9_BASELINE_AND_RECOVERY_CONTRACT.md`;
- `docs/architecture/`;
- `docs/operations/`;
- `gpt/` recovery/configuration sources.

Не создавать duplicate setup/audit docs вместо обновления существующего source of truth.

## 8. Production release state

Omni-CIO v8.6.1 real BUY/SELL v1 is **100% complete** and owner-accepted. The first controlled real SBER order was broker-filled, reconciled to portfolio/operations and replayed without a second submit.

This accepted baseline remains protected while v9 is developed.

## 9. Secrets и приватные данные

В GitHub не хранятся:

- T-Invest/Upstash tokens;
- `GATEWAY_API_KEY` value;
- Bearer/Authorization headers;
- полный accountId;
- реальные приватные позиции/операции/отчёты;
- private keys/certificates.

## 10. Внешние ручные настройки

GitHub хранит эталон, но не может сам заполнить GPT Editor или Render Environment.

Вручную остаются:

1. применение Name/Description/starters;
2. вставка canonical Instructions;
3. загрузка 10 Knowledge-файлов;
4. выбор supported model/capabilities;
5. импорт production OpenAPI;
6. API Key → Bearer с `GATEWAY_API_KEY`;
7. Render secrets;
8. Preview/production acceptance;
9. `Update` в GPT Editor.

Не восстанавливать конфигурацию из старых чатов/скриншотов, если они расходятся с `main`.
