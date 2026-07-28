# Runbook: окончательное отключение Telegram Companion

## Назначение

Этот runbook завершает переход Omni-CIO на единственный пользовательский
интерфейс — Custom GPT внутри ChatGPT.

GitHub-изменение удаляет код и конфигурацию Telegram, но само по себе не
останавливает уже созданный Render service и не удаляет webhook из Telegram.
Внешнюю очистку выполняйте только после merge PR и успешного Regression
Shield.

## Что будет удалено из GitHub

- package `telegram_bot/`;
- `render.telegram.yaml`;
- Telegram unit-тесты;
- активный Telegram knowledge contract и deployment runbook;
- Telegram-переменные из `.env.example`;
- Telegram-проверки из CI.

История остаётся доступна в Git, changelog и ADR.

## Шаг 1. Проверить основной Gateway

Откройте Gateway `/health` и убедитесь:

- `status=ok`;
- `build.entrypoint=app:app`;
- `regression_shield.read_only=true`;
- `trading_methods=false`.

Не удаляйте service `omni-cio-gateway` и не меняйте его `TINVEST_TOKEN` или
`GATEWAY_API_KEY`.

## Шаг 2. Остановить Telegram service в Render

В Render Dashboard найдите только service:

```text
omni-cio-telegram-bot
```

Проверьте имя дважды. Не выбирайте `omni-cio-gateway`.

Сначала отключите автоматические деплои или приостановите Telegram service.
После проверки цели удалите этот отдельный service через его Settings.

Если Telegram-переменные находятся в общем Environment Group, удалите только:

```text
TELEGRAM_BOT_TOKEN
TELEGRAM_WEBHOOK_SECRET
TELEGRAM_ALLOWED_USER_IDS
OMNI_GATEWAY_URL
OMNI_GATEWAY_API_KEY
TELEGRAM_AUTO_CONFIGURE
TELEGRAM_PUBLIC_BASE_URL
TELEGRAM_REQUEST_TIMEOUT_SECONDS
TELEGRAM_GATEWAY_RETRY_ATTEMPTS
TELEGRAM_GATEWAY_RETRY_DELAY_SECONDS
TELEGRAM_MAX_RESPONSE_CHARS
TELEGRAM_MIN_REQUEST_INTERVAL_SECONDS
```

Не удаляйте Gateway-переменные `TINVEST_TOKEN` и `GATEWAY_API_KEY`.

## Шаг 3. Удалить webhook

Telegram Bot API предоставляет официальный метод `deleteWebhook`:

<https://core.telegram.org/bots/api#deletewebhook>

Выполните его в доверенной локальной среде или через собственный защищённый
инструмент. Не вставляйте token в чат, GitHub, Issue, PR, документацию или
скриншот.

После успешного ответа удалите локальную команду из истории shell, если она
содержала token.

## Шаг 4. Отозвать Telegram token

Откройте официальный BotFather и отзовите token удалённого Companion. Если bot
account больше никогда не нужен, отдельно подтвердите его удаление в
BotFather.

Не создавайте новый Telegram token для Omni-CIO: поддерживаемый интерфейс
теперь находится в ChatGPT.

## Шаг 5. Финальная проверка

1. URL бывшего Telegram service больше не обслуживает webhook.
2. Telegram bot не отвечает на старые команды.
3. В Render нет Telegram service и Telegram-specific secrets.
4. Gateway `/health` остаётся `ok`.
5. Custom GPT вызывает только существующие GET Actions.
6. `trading_methods=false`.

## Откат

Восстановление Telegram не выполняется возвратом секретов в GitHub.
Потребуется отдельный PR, новый security review, новый token, изолированный
Render service и повторная регистрация webhook.
