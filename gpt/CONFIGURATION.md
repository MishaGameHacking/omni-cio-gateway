# Custom GPT configuration registry — Omni-CIO

> Этот файл — реестр настроек. Не вставлять его целиком в поле Instructions.

## Identity

- Name: `Omni-CIO API | Управляющий и аналитик v8.4`.
- Purpose: личный инвестиционный аналитик и клиент Omni-CIO Gateway.
- Primary language: Russian.
- User timezone: `Europe/Moscow` / MSK.
- UI/product name release: `v8.4` until manually renamed by the owner.
- Accepted read-only Instructions baseline: `v8.4.1`.
- Canonical Sandbox-enabled Instructions after owner Preview acceptance: `v8.5.0`.
- Recommended model: `Thinking 5.6`.

## Current production description

> Личный GPT для T-Invest. Сам получает портфель, операции, ликвидность, параметры инструментов и котировки через Omni-CIO Gateway. Реальный брокерский контур работает только на чтение. В режиме «УПРАВЛЯЙ ПОРТФЕЛЕМ» анализирует структуру, сравнивает варианты и формирует план. Отдельный T-Invest Sandbox-контур может выполнять только виртуальные BUY/SELL после двухфазного точного подтверждения пользователя.

Sandbox не является real-money trading. Реальный `TINVEST_TOKEN` остаётся read-only.

## Conversation starters

1. `УПРАВЛЯЙ ПОРТФЕЛЕМ — сначала вызови getPortfolioSnapshot. Если успешно, вызови getCashLiquiditySnapshot и getPortfolioAnalytics. Затем проанализируй данные и скажи, что делать.`
2. `АНАЛИТИК — объясни состояние портфеля простыми словами.`
3. `НОВОСТИ — проверь важные события по моим компаниям.`
4. `ЖУРНАЛ — покажи решения текущего разговора.`

Первый starter намеренно содержит Action names для максимально надёжного dispatch. Простые естественные команды также должны маршрутизироваться автоматически по Instructions.

## Instructions

Canonical Instructions for the currently Sandbox-capable configuration:

`gpt/CUSTOM_GPT_INSTRUCTIONS_V8_5_0.txt`

`v8.5.0` сохраняет real production read-only и разрешает broker mutation только когда Action явно является Sandbox (`sandbox=true`, `real_money=false`). Если Sandbox routes выключены/отсутствуют, те же Instructions fail closed и не придумывают execution surface.

`gpt/CUSTOM_GPT_INSTRUCTIONS_V8_4_1.txt` сохраняется как accepted read-only fallback/baseline, но не является источником Sandbox behavior.

Не смешивать версии вручную.

## Knowledge — ровно 10 файлов

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

Каждый файл загружать один раз. Не загружать исходный код, master plan, реальные broker reports, accountId или secrets.

## Capabilities

- Web Search: **ON**.
- Code Interpreter / Data Analysis: **ON**.
- Image generation: **OFF** для текущего investment workflow.
- Apps: **OFF / не использовать вместе с Actions**.
- Actions: **ON**.

## Actions

Production service:

`https://omni-cio-gateway.onrender.com`

Schema URL:

`https://omni-cio-gateway.onrender.com/openapi.json`

Health URL:

`https://omni-cio-gateway.onrender.com/health`

Authentication:

- Type: `API Key`.
- Mode: `Bearer`.
- Value: `GATEWAY_API_KEY` из Render service `omni-cio-gateway`.
- `TINVEST_TOKEN` и `TINVEST_SANDBOX_TOKEN` в GPT Editor не вставлять.

### Default real-money-safe surface

При `SANDBOX_TRADING_ENABLED=false`:

- ровно 14 GET Actions из `gpt/ACTIONS_CATALOG.md`;
- никаких real create/order/execute/cancel/replace/transfer/withdraw методов;
- `real_trading_methods=false`.

### Sandbox-enabled surface

При `SANDBOX_TRADING_ENABLED=true` дополнительно публикуются только Sandbox Actions:

- `getSandboxTradingStatus` — GET;
- `openSandboxAccount` — POST, consequential, explicit confirmation;
- `fundSandboxAccount` — POST, consequential, explicit confirmation;
- `getSandboxPortfolio` — GET;
- `prepareSandboxTrade` — POST, proposal only;
- `executeSandboxTrade` — POST, consequential, requires exact short-lived confirmation from a separate user turn;
- `getSandboxOrderState` — GET;
- `cancelSandboxOrder` — POST, consequential, explicit confirmation.

Все ответы Sandbox должны явно показывать `sandbox=true`, `real_money=false`, `real_trading_methods=false`.

## Portfolio dispatch acceptance

Для `УПРАВЛЯЙ ПОРТФЕЛЕМ` ожидаемый обязательный старт:

1. `getPortfolioSnapshot`;
2. при успехе `getCashLiquiditySnapshot`;
3. `getPortfolioAnalytics`;
4. только затем анализ, рынок/кандидаты при необходимости и DecisionCard.

Sandbox execution не включается автоматически обычным portfolio-management запросом.

## Sandbox confirmation acceptance

Нормальный виртуальный BUY/SELL:

1. `prepareSandboxTrade` возвращает proposal и exact confirmation phrase.
2. GPT показывает параметры, rationale, TTL и сообщает, что ничего не отправлено.
3. GPT останавливается.
4. Пользователь отправляет exact phrase новым сообщением.
5. Только после этого `executeSandboxTrade`.
6. Затем `getSandboxOrderState`.
7. При `unknown_do_not_resubmit` никакого повторного submit; только status reconciliation.

Owner Preview on 2 August 2026 demonstrated this two-phase flow plus confirmation expiry, confirmation mismatch rejection, replay protection, LIMIT order state/cancel and portfolio reconciliation while `real_money=false` and `real_trading_methods=false`.

Remaining recovery/hardening scenarios are tracked in `knowledge/16_CURRENT_PROGRAM_STATUS.md` and `docs/operations/SANDBOX_TRADING_RUNBOOK.md`.

## Market/sizing acceptance

Для инвестиционного решения, если рынок закрыт, нет свежего `best ask` или доступен только stale `last price`:

- `WAIT_FOR_FRESH_MARKET`/эквивалент;
- точное количество лотов не выдавать как персональный sizing;
- stale price не использовать как подтверждённую цену покупки.

Строго технический Sandbox test может иметь явно заданные пользователем виртуальные параметры, но не должен маскироваться под инвестиционную рекомендацию.

## Secrets boundary

GitHub хранит только имена переменных и инструкции. Никогда не коммитить значения:

- `TINVEST_TOKEN`;
- `TINVEST_SANDBOX_TOKEN`;
- будущего real account-scoped trading token;
- `GATEWAY_API_KEY`;
- Authorization header;
- полный broker accountId;
- реальные позиции/операции как configuration data.

Подробности: `gpt/SECRETS_AND_RENDER.md` и `docs/operations/SANDBOX_TRADING_RUNBOOK.md`.

## Publishing/update checklist — current Sandbox-capable configuration

1. Открыть `gpt/SETUP_INDEX.md`.
2. Использовать `CUSTOM_GPT_INSTRUCTIONS_V8_5_0.txt`.
3. Ровно 10 Knowledge-файлов.
4. `Thinking 5.6`, пока модель доступна и поддерживает Actions.
5. Web Search + Data Analysis ON; Image generation + Apps OFF.
6. Проверить `/health`.
7. Импортировать production `/openapi.json`.
8. Если Sandbox выключен — сверить 14 GET Actions. Если Sandbox включён — 14 baseline + 8 Sandbox Actions.
9. Убедиться, что real-money mutation Actions отсутствуют.
10. API Key → Bearer с существующим `GATEWAY_API_KEY`.
11. Preview smoke tests для real read-only маршрутизации.
12. При Sandbox enable — Preview status + proposal/confirmation safety checks из runbook.
13. Маскированный account ID + MSK.
14. `Update` только после успешных проверок.

## Sandbox Render requirements

Для Sandbox-capable setup:

1. `TINVEST_SANDBOX_TOKEN` — отдельный Sandbox token.
2. `SANDBOX_TRADING_ENABLED=true` — только когда owner намеренно включает Sandbox routes.
3. `SANDBOX_CONFIRMATION_TTL_SECONDS=120`.
4. Существующие `TINVEST_TOKEN` и `GATEWAY_API_KEY` не менять.
5. При rollback поставить `SANDBOX_TRADING_ENABLED=false`, redeploy/restart и переимпортировать OpenAPI при изменении Action surface.

## Важная граница GitHub ↔ GPT Editor

GitHub — эталон и история версий. Он не применяет Instructions, Knowledge, model selection, sharing state, Bearer secret или OpenAPI в GPT Editor автоматически. Эти значения применяются/проверяются вручную после изменения соответствующего GitHub-файла.
