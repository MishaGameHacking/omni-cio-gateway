# Omni-CIO bot-only manifest

Этот manifest определяет единственный поддерживаемый Omni-CIO Custom GPT и связанные production/recovery assets.

Current applied GPT: `Omni-CIO API | Управляющий и аналитик v8.6.1`.

## Единственный продукт

`Omni-CIO Custom GPT → Omni-CIO Gateway → T-Invest API`

Не создавать второго Custom GPT, отдельный дублирующий frontend, второй Gateway или параллельный execution surface без явного решения владельца.

## Главная точка восстановления

`gpt/SETUP_INDEX.md`

## Активная программа развития

`docs/master-plan/OMNI_CIO_V9_PORTFOLIO_AUTOPILOT_PROGRAM.md`

Программа owner-approved / program-locked. До её Definition of Done разработка следует v9 work packages. Исключения: blocking defects, security/dependency maintenance и сохранение стабильного v8.6.1.

## Production Custom GPT files

| Файл | Назначение |
|---|---|
| `gpt/SETUP_INDEX.md` | Единая карта восстановления |
| `gpt/CONFIGURATION.md` | Name, Description, starters, model, capabilities |
| `gpt/CUSTOM_GPT_INSTRUCTIONS_V8_6_1_COMPACT.txt` | Канонические applied production Instructions |
| `gpt/CUSTOM_GPT_INSTRUCTIONS_V8_6_0.txt` | Полный v8.6 engineering reference |
| `gpt/ACTIONS_CATALOG.md` | Production Actions |
| `gpt/SECRETS_AND_RENDER.md` | Render/secrets boundary |
| `gpt/MY_GPT_SETUP_RUNBOOK.md` | Полное восстановление |
| `gpt/knowledge/` | Ровно 10 production Knowledge-файлов |

Development continuity:

- `AGENTS.md`;
- `gpt/PROJECT_INSTRUCTIONS.md`;
- `gpt/NEW_CHAT_PROMPT.md`;
- `knowledge/16_CURRENT_PROGRAM_STATUS.md`;
- `docs/master-plan/OMNI_CIO_V9_PORTFOLIO_AUTOPILOT_PROGRAM.md`;
- `docs/architecture/V9_BASELINE_FREEZE_AND_MIGRATION.md`.

## Production Knowledge upload set

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

Никаких дубликатов/старых Knowledge-файлов в GPT Editor.

## Runtime assets that must remain

- `app.py`, `app_v371.py`, `app_v360.py`, `main.py` until compatibility refactor;
- current domain runtime modules and `broker_report_reconciliation/`;
- `omni_cio/sandbox/`;
- `omni_cio/real_trading/`;
- `render.yaml`, `.env.example`, dependency files;
- `tests/`, `scripts/`, `.github/`;
- current architecture/operations/master-plan docs.

## Protected baseline

v8.6.1 real BUY/SELL v1 is release-complete and remains protected during v9 development. New v9 engines are additive/feature-flagged/shadow-first until their own acceptance. Existing exact-confirmation, idempotency, broker reconciliation, own-funds/own-position, no-margin/no-transfer and kill-switch boundaries are not bypassed.

## Secrets/private data

GitHub must not contain values of T-Invest/Upstash tokens, `GATEWAY_API_KEY`, Authorization headers, full accountId, private broker positions/operations/reports or private keys/certificates.

## External manual settings

GitHub is canonical source/history but cannot itself fill GPT Editor or Render Environment. Manual recovery may require applying Name/Description/starters, canonical Instructions, 10 Knowledge files, model/capabilities, production OpenAPI, API Key → Bearer and Render secrets, followed by Preview/production acceptance.

Не восстанавливать конфигурацию из старых чатов/скриншотов, если они расходятся с `main`.
