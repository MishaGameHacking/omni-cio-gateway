# Подключение Omni-CIO в ChatGPT → My GPTs

Дата проверки официальной документации: 2026-07-30.

Этот runbook настраивает существующий Custom GPT как интерфейс к read-only Omni-CIO Gateway. Он не деплоит Render, не меняет секреты и не включает торговлю.

## 1. Предварительные условия

- аккаунт ChatGPT с правом создавать/редактировать GPT;
- доступ к веб-версии ChatGPT: создание и редактирование GPT выполняется в web UI;
- работающий production Gateway и его публичный base URL;
- доступ владельца к секрету `GATEWAY_API_KEY` в Render;
- актуальная ветка `main` и зелёный Regression Shield.

Сначала проверьте в браузере:

- `<RENDER_EXTERNAL_URL>/health`;
- `<RENDER_EXTERNAL_URL>/openapi.json`.

Ожидается `version=3.10.0`, `build.entrypoint=app:app`, `trading_methods=false` и ровно 14 GET операций из `ACTIONS_CATALOG.md`.

## 2. Открыть или создать GPT

1. Откройте [Explore GPTs](https://chatgpt.com/gpts).
2. Для нового бота нажмите Create. Для существующего: My GPTs → Omni-CIO → Edit GPT.
3. Работайте в Configure и регулярно проверяйте результат в Preview.

## 3. Основная конфигурация

1. Имя, описание и starters возьмите из `CONFIGURATION.md`.
2. Вставьте полный текст `INSTRUCTIONS_COMPACT.md` в Instructions.
3. Не вставляйте токены, API keys, Authorization headers или полный номер счёта.
4. В Knowledge загрузите только необходимые справочные документы. Рекомендуемый минимум — `knowledge/13_COMMUNICATION_STYLE_2026.txt`.
5. Не загружайте master-plan PDF в production GPT Knowledge: он управляет разработкой и содержит будущие этапы, а не факты текущего runtime.
6. Включите Web Search, если GPT должен проверять текущие публичные сведения.

## 4. Настроить Actions

1. В разделе Actions нажмите Create new action.
2. Выберите Authentication → API Key → Bearer.
3. Вставьте значение `GATEWAY_API_KEY` вручную. Не сохраняйте его в GitHub и не показывайте в Preview-ответах.
4. Импортируйте schema по URL `<RENDER_EXTERNAL_URL>/openapi.json` либо вставьте фактическую schema из production.
5. Сверьте каждую операцию с `ACTIONS_CATALOG.md`: ожидаются 14 `GET`, mutating methods отсутствуют.
6. Не включайте Apps для этого GPT: GPT использует либо Apps, либо Actions.
7. Выберите модель/режим с поддержкой Actions. Не используйте Pro mode для этого контура.

## 5. Проверки в Preview

Выполняйте по одному запросу и проверяйте, что GPT не вызывает лишние методы.

### Health

`Проверь Gateway. Вызови только gatewayHealth.`

Проверьте `status`, `version`, `build.entrypoint=app:app`, `trading_methods=false`.

### Authentication

Сначала убедитесь, что защищённый Action без корректного ключа не возвращает приватные данные. Затем с настроенным Bearer:

`Проверь подключение к T-Invest. Вызови только getConnection.`

Счёт должен быть маскирован.

### Read-only contract

`Покажи read-only снимок портфеля. Вызови только getPortfolioSnapshot.`

Проверьте отсутствие order/execute/cancel/replace/transfer/withdraw Actions.

### Final review

`Не создавай решение. Объясни, что означает безопасный unavailable-ответ getFinalDecisionReview.`

`503` без активного reviewed source допустим и не означает поломку. `409` нельзя автоматически повторять с придуманной identity. При `200` обязательны `trade_authorized=false`, `order_created=false`, `execution_ready=false`, `trading_methods=false`.

## 6. Публикация

1. До production acceptance оставьте GPT приватным или invite-only.
2. Нажмите Update после успешного Preview.
3. Повторно откройте GPT и убедитесь, что настройки сохранились.
4. Зафиксируйте фактические результаты восьми acceptance cases по `knowledge/16_CURRENT_PROGRAM_STATUS.md`; зелёный GitHub CI не заменяет эту проверку.

## 7. Обновление и rollback

- Если меняются только Instructions/Knowledge, замените их, проверьте Preview и нажмите Update.
- Если меняется OpenAPI, сначала задеплойте Gateway, затем импортируйте production schema и снова проверьте все 14 Actions.
- При ошибке верните предыдущий проверенный текст Instructions/schema, нажмите Update и повторите health/auth/read-only checks.
- Никогда не «чините» импорт добавлением write endpoint или отключением Bearer authentication.

## 8. Частые проблемы

- Action отсутствует: проверьте production `/openapi.json`, выбранный режим и повторите импорт.
- GPT не вызывает Action: уберите конфликтующие/дублирующие инструкции, проверьте выбранную модель и сформулируйте один точный запрос.
- Workspace блокирует домен: владелец workspace должен разрешить домен Gateway.
- Knowledge влияет на поведение: перенесите правила поведения в Instructions; Knowledge оставьте справочным.
- Ответ раскрывает лишнее: немедленно верните предыдущую конфигурацию и проверьте маскирование/секреты.

## Официальные источники OpenAI

- [Creating and editing GPTs](https://help.openai.com/en/articles/8554397-creating-and-editing-gpts)
- [Configuring actions in GPTs](https://help.openai.com/en/articles/9442513-configuring-actions-in-gpts)
- [Troubleshooting GPTs](https://help.openai.com/en/articles/11325361-troubleshooting-gpts)
- [Sharing and publishing GPTs](https://help.openai.com/en/articles/8798878-sharing-and-publishing-gpts)
- [GPTs in ChatGPT](https://help.openai.com/en/articles/8554407-gpts-in-chatgpt)
