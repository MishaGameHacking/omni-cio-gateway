# Runbook: Telegram Companion v4.0.0

## Назначение

Telegram Companion — отдельный read-only web service. Он принимает Telegram webhook, проверяет пользователя и вызывает существующий Omni-CIO Gateway только методом GET.

## Что понадобится вручную

1. Telegram bot token от `@BotFather`.
2. Ваш числовой Telegram user ID.
3. Текущее значение `GATEWAY_API_KEY` из Render gateway service.

Не вставляйте эти значения в GitHub, Issue, Pull Request или чат.

## Создание бота в Telegram

1. Откройте официальный `@BotFather`.
2. Отправьте `/newbot`.
3. Задайте имя и username.
4. Сохраните полученный token в менеджере секретов.
5. Получите собственный числовой Telegram ID через доверенный инструмент или Telegram API.

## Развёртывание на Render

Telegram service вынесен в отдельный Blueprint `render.telegram.yaml`, чтобы не менять существующий gateway.

1. Render Dashboard → New → Blueprint.
2. Подключите `Misha2304/omni-cio-gateway`.
3. В поле Blueprint Path укажите `render.telegram.yaml`.
4. Выберите ветку `main`.
5. Заполните secret variables:
   - `TELEGRAM_BOT_TOKEN`;
   - `TELEGRAM_ALLOWED_USER_IDS`;
   - `OMNI_GATEWAY_API_KEY` — то же значение, что `GATEWAY_API_KEY` gateway.
6. `TELEGRAM_WEBHOOK_SECRET` генерируется Render автоматически.
7. `OMNI_GATEWAY_URL` уже указывает на production gateway.
8. Нажмите Deploy Blueprint.

Render автоматически предоставляет `RENDER_EXTERNAL_URL`. После старта Telegram Companion формирует `<RENDER_EXTERNAL_URL>/telegram/webhook`, вызывает `setMyCommands` и устанавливает webhook с secret token.

## Проверка health

Откройте URL нового сервиса:

```text
https://<telegram-service>.onrender.com/health
```

Ожидается:

```text
status: ok
version: 4.0.0
service: telegram_companion
configured: true
bootstrap.status: ok
bootstrap.webhook_configured: true
bootstrap.commands_configured: true
build.entrypoint: telegram_bot.app:app
read_only: true
trading_methods: false
```

Если `status=degraded`, посмотрите `missing_configuration` и `bootstrap.error`. Ответ не содержит секретных значений.

## Первый тест в Telegram

Отправьте боту:

```text
/start
/health
/connection
/portfolio
/cash
/operations 90
```

Для официального отчёта:

```text
/report
```

Если получен `pending`, затем отправьте:

```text
/report_status
```

Telegram service запоминает последний `task_id` в памяти. После перезапуска используйте явный вариант:

```text
/report_status <task_id>
```

## Команды безопасности

Telegram Companion не имеет команд для:

- изменения ключей;
- управления Render;
- merge Pull Request;
- запуска произвольного кода;
- создания, отправки, замены или отмены заявок;
- совершения сделок.

## Ротация ключей

### Telegram token

При компрометации отзовите token через BotFather, создайте новый и замените только `TELEGRAM_BOT_TOKEN` в Telegram service.

### Gateway key

При ротации `GATEWAY_API_KEY` замените одно и то же новое значение:

- в gateway service как `GATEWAY_API_KEY`;
- в Telegram service как `OMNI_GATEWAY_API_KEY`;
- в GPT Editor Actions authentication.

### Webhook secret

Можно заменить `TELEGRAM_WEBHOOK_SECRET` в Telegram service. После redeploy startup автоматически повторно установит webhook.

## Ограничения v4.0.0

- Поддерживаются команды, а не свободный AI-диалог.
- История ChatGPT не синхронизируется с Telegram.
- Последний report task хранится только в памяти.
- Ответы gateway могут сокращаться по лимиту символов.
- Free Render service может засыпать и отвечать с задержкой после простоя.
