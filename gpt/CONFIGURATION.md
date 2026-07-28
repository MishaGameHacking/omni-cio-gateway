# Custom GPT configuration registry

## Identity

- Name: `Omni-CIO API | Управляющий и аналитик`
- Purpose: read-only investment data assistant and gateway operator.
- Primary language: Russian.
- Backend release: `v3.9.1`.
- Communication profile: `Modern Financial Sage — 2026`.

## Recommended description

> Безопасный read-only аналитик портфеля: подключение к T-Invest, снимки портфеля, рыночные данные, деньги и ликвидность, предварительный расчёт покупательной способности, операции и официальный брокерский отчёт. Объясняет сложные финансовые данные современным понятным русским языком, готовит живые Telegram-посты, не создаёт заявки и не совершает сделки.

## Instructions

Use the complete text from `INSTRUCTIONS.md` as the canonical instruction source.

The communication profile requires:

- main conclusion first;
- short paragraphs;
- plain-language explanations of financial terms;
- separation of fact, conclusion and scenario;
- moderate optional profanity only as emphasis;
- ru-RU money formatting for rubles;
- milder public style for Telegram post drafts;
- no change to read-only or Action safety rules.

## Actions

- Schema source: production Render service `/openapi.json`.
- Authentication: API Key in `Authorization` header with Bearer type.
- Secret value: enter `GATEWAY_API_KEY` manually in GPT Editor; never commit it.
- Expected actions: see `ACTIONS_CATALOG.md`.

## Recommended conversation starters

1. `Объясни состояние моего портфеля простыми словами: что хорошо, что плохо и где главный риск.`
2. `Проверь подключение к T-Invest. Вызови только getConnection.`
3. `Покажи read-only снимок моего портфеля и переведи цифры на человеческий язык.`
4. `Проверь деньги и ликвидность без рекомендаций.`
5. `Проанализируй компанию как современный финансовый мудрец: факты, риски и сценарии.`
6. `Подготовь Telegram-пост в живом современном стиле с датой и источниками.`
7. `Запусти официальный брокерский отчёт за 31 день и верни task_id.`

## Capabilities

- Web browsing should be enabled for current company analysis, financial reports, management changes, dividends, news, sanctions, rates and market context.
- Direct gateway Actions do not require web browsing when the user requests only exact account data.
- Code Interpreter is optional and must not receive secrets or raw private reports unless the user deliberately provides a file for local analysis.
- Image generation is not required for gateway operation.

## Publishing

Before publishing or updating:

1. Verify production `/health`.
2. Import the current `/openapi.json` only if the Action contract changed.
3. Confirm that all actions are GET-only.
4. Confirm Bearer authentication.
5. Replace the GPT Editor Instructions with the complete current `INSTRUCTIONS.md`.
6. Enable Web Search for current public-company and market analysis.
7. Run one method-only test.
8. Run one plain-language portfolio explanation test.
9. Run one Telegram-post draft test.
10. Confirm `trading_methods=false` in the response.
11. Do not expose the GPT publicly unless the owner deliberately changes access settings.

## External UI state

Model selection, icon, sharing mode, publication status, enabled capabilities, instruction text and secret authentication value exist only in GPT Editor. This file records the desired state but cannot enforce those settings automatically.
