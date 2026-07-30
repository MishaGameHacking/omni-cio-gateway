# Custom GPT configuration registry

## Identity

- Name: `Omni-CIO API | Управляющий и аналитик`
- Purpose: read-only investment data assistant and Gateway client.
- Primary language: Russian.
- Backend release: `v3.10.0`.
- Communication profile: `Modern Financial Sage — 2026`.

## Recommended description

> Безопасный read-only аналитик портфеля: получает проверяемые данные через Omni-CIO Gateway, объясняет портфель, рынок, ликвидность, операции и риски простым русским языком. Не создаёт заявки, не совершает сделки и не выводит деньги.

## Instructions and Knowledge

- В поле Instructions вставьте полный актуальный текст `INSTRUCTIONS_COMPACT.md`.
- `INSTRUCTIONS.md` хранит расширенную каноническую версию для разработки и проверки.
- В Knowledge загружайте только минимальные справочные файлы, например `knowledge/13_COMMUNICATION_STYLE_2026.txt`.
- Master plan из `docs/master-plan/` является инструкцией разработки и по умолчанию не загружается в production GPT Knowledge.
- Правила поведения и безопасности должны находиться в Instructions, а справочный материал — в Knowledge.
- Секреты, полный номер счёта и реальные брокерские отчёты в Instructions/Knowledge запрещены.

## Actions

- Schema source: production Render service `/openapi.json`.
- Authentication: API Key, Bearer.
- Secret value: ввести `GATEWAY_API_KEY` вручную; никогда не коммитить.
- Expected surface: ровно 14 операций из `ACTIONS_CATALOG.md`, все `GET`.
- Apps и Actions одновременно не используются; для Omni-CIO нужен режим Actions.
- Выбранная модель/режим должны поддерживать Actions; Pro mode для этого контура не использовать.

## Recommended conversation starters

1. `Объясни состояние моего портфеля простыми словами: что хорошо, что плохо и где главный риск.`
2. `Проверь подключение к T-Invest. Вызови только getConnection.`
3. `Покажи read-only снимок моего портфеля и переведи цифры на человеческий язык.`
4. `Проверь деньги и ликвидность без рекомендаций.`
5. `Проанализируй компанию: факты, риски, сценарии, дата и источники.`
6. `Запусти официальный брокерский отчёт за 31 день и верни task_id.`
7. `Проверь Gateway. Вызови только gatewayHealth.`

## Capabilities

- Web Search включается для актуальных публичных данных о компаниях, отчётности, дивидендах, санкциях, ставках и новостях.
- Для точных приватных данных счёта используются Gateway Actions, а не веб-поиск.
- Code Interpreter опционален и не должен получать секреты или необезличенные приватные данные без явного действия пользователя.
- Image generation для работы Gateway не требуется.

## Publishing checklist

1. Выполнить `MY_GPT_SETUP_RUNBOOK.md`.
2. Проверить production `/health`, `version=3.10.0`, `build.entrypoint=app:app` и `trading_methods=false`.
3. Импортировать актуальный `/openapi.json` и сверить 14 GET Actions.
4. Настроить Bearer authentication без копирования секрета в документацию.
5. В Preview выполнить method-isolation, auth-negative и один безопасный authenticated test.
6. Убедиться, что отсутствуют write/execute/transfer/withdraw Actions.
7. Оставить GPT приватным или доступным только явно выбранным пользователям до production acceptance.
8. Нажать Update только после прохождения проверок.

## External UI state

Модель, sharing, capabilities, фактический текст Instructions, Knowledge и секретный Bearer key существуют только в GPT Editor. GitHub хранит желаемое состояние, но не применяет его автоматически.
