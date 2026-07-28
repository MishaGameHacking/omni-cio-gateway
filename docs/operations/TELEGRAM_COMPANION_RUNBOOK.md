# Runbook: Telegram Companion v4.0.1

## Назначение

Telegram Companion — отдельный read-only web service. Он принимает Telegram webhook, проверяет пользователя и вызывает существующий Omni-CIO Gateway только методом GET.

v4.0.1 добавляет короткие русские ответы, `/status`, повтор временно неудачных Gateway-запросов и безопасное разбиение длинных сообщений.

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

## Retry-настройки v4.0.1

Blueprint задаёт безопасные значения:

```text
TELEGRAM_REQUEST_TIMEOUT_SECONDS=20
TELEGRAM_GATEWAY_RETRY_ATTEMPTS=2
TELEGRAM_GATEWAY_RETRY_DELAY_SECONDS=5
```

`TELEGRAM_GATEWAY_RETRY_ATTEMPTS` — количество дополнительных попыток после первого запроса. Повторяются только временные сетевые ошибки и HTTP 408/425/429/5xx. Ошибки авторизации и валидации не повторяются.

При первом повторе бот отправляет:

```text
⏳ Основной сервер просыпается. Повторяю безопасный запрос…
```

Free Render service может просыпаться около минуты, поэтому пользователь может увидеть это сообщение до итогового ответа.

## Проверка health

Откройте URL Telegram service:

```text
https://<telegram-service>.onrender.com/health
```

Ожидается:

```text
status: ok
version: 4.0.1
service: telegram_companion
configured: true
bootstrap.status: ok
bootstrap.webhook_configured: true
bootstrap.commands_configured: true
reliability.gateway_retry_attempts: 2
reliability.friendly_output: true
reliability.safe_message_splitting: true
build.entrypoint: telegram_bot.app:app
read_only: true
trading_methods: false
```

Если `status=degraded`, посмотрите `missing_configuration` и `bootstrap.error`. Ответ не содержит секретных значений.

## Первый тест в Telegram

Отправляйте команды по одной:

```text
/start
/status
/health
/connection
/portfolio
/cash
/analytics
/operations 90
```

### Что проверяет `/status`

- Telegram webhook уже доставил команду;
- Gateway `/health` отвечает;
- T-Invest `/connection` отвечает;
- отображаются версии Telegram и Gateway;
- счёт маскирован;
- торговые методы выключены.

## Официальный брокерский отчёт

Запуск:

```text
/report
```

Если получен `pending`, бот показывает настоящий `task_id` и краткую инструкцию. Затем отправьте:

```text
/report_status
```

Telegram service запоминает последний `task_id` в памяти. После перезапуска используйте явный вариант:

```text
/report_status <task_id>
```

## Friendly output

Telegram показывает краткие поля вместо полного JSON:

- статус и версию;
- маскированный счёт;
- суммы в валюте источника;
- количество операций и ненулевые категории;
- статус сверки и полноту;
- `task_id` для асинхронного отчёта;
- read-only ограничение.

Форматтеры не выполняют новые финансовые расчёты, не складывают валюты и не меняют `partial`, `pending`, `complete=false` на успешный результат.

Telegram Bot API ограничивает текст одного сообщения, поэтому длинный ответ делится на безопасные части с заголовками `Часть N/M`.

## Диагностика

### Бот не отвечает

1. Проверьте Telegram service `/health`.
2. Убедитесь, что `bootstrap.webhook_configured=true`.
3. Проверьте `TELEGRAM_BOT_TOKEN` и `TELEGRAM_ALLOWED_USER_IDS` только в Render Environment.

### `/status` показывает ошибку Gateway

1. Откройте gateway `/health` в браузере.
2. Подождите пробуждения бесплатного Render service.
3. Проверьте `OMNI_GATEWAY_URL` и `OMNI_GATEWAY_API_KEY` Telegram service.
4. Не меняйте ключ, если остальные интерфейсы работают.

### Gateway работает, T-Invest недоступен

Проверьте `TINVEST_TOKEN` только в gateway service. Telegram service не должен содержать T-Invest token.

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

## Ограничения v4.0.1

- Поддерживаются команды, а не свободный AI-диалог.
- История ChatGPT не синхронизируется с Telegram.
- Последний report task хранится только в памяти.
- Free Render service может засыпать; retry снижает вероятность ошибки, но не превращает инфраструктурный сбой в успешный ответ.
- Административных и торговых команд нет.
