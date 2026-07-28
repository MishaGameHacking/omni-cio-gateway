# Реестр компонентов и внешних активов

Дата инвентаризации: 2026-07-28.

Этот файл отвечает на вопрос: «Что новый чат получит из GitHub, а что нужно подключить отдельно?»

## 1. Находится в этом репозитории

### Omni-CIO Gateway

- FastAPI gateway и стабильный entrypoint `app:app`;
- T-Invest read-only integration;
- OpenAPI-схема GPT Actions;
- снимки портфеля, рыночные данные и аналитика;
- cash/liquidity diagnostics;
- purchase capacity preview и integrity;
- operations analytics;
- broker report reconciliation и async integrity;
- Render Blueprint `render.yaml`;
- unit и Regression Shield тесты.

### Telegram Companion v4.0.1

- отдельный FastAPI service `telegram_bot.app:app`;
- webhook validation;
- allowlist пользователей;
- read-only команды gateway;
- `/status` для проверки всей цепочки;
- автоматические повторы временных Gateway-ошибок;
- короткие русские форматтеры финансовых ответов;
- безопасное разбиение длинных сообщений;
- автоматические `setMyCommands` и `setWebhook`;
- отдельный Blueprint `render.telegram.yaml`;
- Telegram unit/security/reliability tests;
- runbook и профильный knowledge-файл.

### Custom GPT Modern Financial Sage — 2026

- канонические инструкции в `gpt/INSTRUCTIONS.md`;
- реестр ручной конфигурации в `gpt/CONFIGURATION.md`;
- переносимый профиль `knowledge/13_COMMUNICATION_STYLE_2026.txt`;
- современный разговорный русский язык;
- простые объяснения финансовых терминов;
- разделение фактов, выводов и сценариев;
- умеренный мат без оскорбления пользователя;
- шаблон мобильных Telegram-постов с датой и источниками;
- сохранение GET-only и `trading_methods=false`.

### Проектная память

- `AGENTS.md`;
- `knowledge/00_PROJECT_MASTER_CONTEXT.md`;
- профильные файлы `knowledge/`;
- `docs/` с архитектурой и runbooks;
- `gpt/` с переносимой конфигурацией Custom GPT;
- changelog, contribution и security policies.

## 2. Существует вне GitHub и не должно копироваться как секрет

### Render gateway service

Хранит:

- `TINVEST_TOKEN`;
- `GATEWAY_API_KEY`;
- deploy state и автоматически заданный `RENDER_EXTERNAL_URL`.

### Render Telegram service

Хранит:

- `TELEGRAM_BOT_TOKEN`;
- `TELEGRAM_WEBHOOK_SECRET`;
- `TELEGRAM_ALLOWED_USER_IDS`;
- `OMNI_GATEWAY_API_KEY`;
- production URL и deploy state.

В GitHub находятся только имена переменных, placeholders, retry defaults и deploy contract.

### Telegram / BotFather

Во внешней системе находятся:

- Telegram bot account и username;
- bot token;
- установленный webhook;
- список команд;
- Telegram user IDs и сообщения.

GitHub содержит код настройки, но не токен, реальные IDs и историю сообщений.

### Custom GPT

В GPT Editor хранятся:

- выбранная модель;
- загруженная Action schema;
- Bearer API key;
- опубликованное состояние GPT;
- UI-настройки и доступ пользователей;
- фактически применённый текст Instructions;
- состояние Web Search и других capabilities.

GitHub хранит желаемую каноническую конфигурацию, но не может автоматически изменить GPT Editor.

### T-Invest

Во внешней системе находятся брокерский счёт, токен, позиции, операции и официальные отчёты. GitHub хранит только клиентский код, схемы и фиктивные тестовые данные.

## 3. Ещё не подключено к этому репозиторию

### Frontend Omni-CIO Bot

Существующий сайт:

`https://omni-cio-bot.ervinwilliams97920.chatgpt.site`

Исходный frontend-проект или отдельный репозиторий пока не зафиксирован. До определения источника нельзя создавать копию сайта. Когда источник будет найден, добавить repository/project ID, production URL, framework, build command, hosting configuration, parser path и связь frontend release с backend release.

### HTML-отчёты СберИнвестиций

Реальные отчёты не должны сохраняться в GitHub. Допускаются только специально обезличенные fixtures без счёта, сделок, сумм, персональных данных и иных идентификаторов.

## 4. Что нужно новому чату

1. GitHub read access.
2. Для изменения кода — GitHub write access через ветку и PR.
3. Для production-проверки — доступ к публичным `/health` обоих сервисов.
4. Для изменения секретов — доступ к Render Dashboard.
5. Для изменения Custom GPT — доступ к GPT Editor.
6. Для создания или ротации Telegram token — доступ к BotFather владельца.

## 5. Запрещённые способы «сохранить всё»

Нельзя добавлять реальные токены, API keys, webhook secret, Telegram user IDs владельца, полный номер счёта, export чатов, реальные брокерские отчёты или screenshots с чувствительными значениями. GitHub хранит воспроизводимую систему и знания, а не пользовательские секреты.
