# Custom GPT configuration registry

## Identity

- Name: `Omni-CIO API | Управляющий и аналитик`
- Purpose: read-only investment data assistant and gateway operator.
- Primary language: Russian.
- Backend release: `v3.9.1`.

## Recommended description

> Безопасный read-only аналитик портфеля: подключение к T-Invest, снимки портфеля, рыночные данные, деньги и ликвидность, предварительный расчёт покупательной способности, операции и официальный брокерский отчёт. Не создаёт заявки и не совершает сделки.

## Instructions

Use the complete text from `INSTRUCTIONS.md` as the canonical instruction source.

## Actions

- Schema source: production Render service `/openapi.json`.
- Authentication: API Key in `Authorization` header with Bearer type.
- Secret value: enter `GATEWAY_API_KEY` manually in GPT Editor; never commit it.
- Expected actions: see `ACTIONS_CATALOG.md`.

## Recommended conversation starters

1. `Проверь шлюз. Вызови только gatewayHealth.`
2. `Проверь подключение к T-Invest. Вызови только getConnection.`
3. `Покажи read-only снимок моего портфеля.`
4. `Проверь деньги и ликвидность без рекомендаций.`
5. `Запусти официальный брокерский отчёт за 31 день и верни task_id.`

## Capabilities

- Web browsing is not required for direct gateway Actions.
- Code Interpreter is optional and must not receive secrets or raw private reports unless the user deliberately provides a file for local analysis.
- Image generation is not required for gateway operation.

## Publishing

Before publishing or updating:

1. Verify production `/health`.
2. Import the current `/openapi.json`.
3. Confirm that all actions are GET-only.
4. Confirm Bearer authentication.
5. Run one method-only test.
6. Confirm `trading_methods=false` in the response.
7. Do not expose the GPT publicly unless the owner deliberately changes access settings.

## External UI state

Model selection, icon, sharing mode, publication status and secret authentication value exist only in GPT Editor. This file records the desired state but cannot enforce those settings automatically.
