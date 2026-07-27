# Политика безопасности

Omni-CIO работает с финансовыми данными и должен оставаться строго read-only во всех интерфейсах.

## Сообщение об уязвимости

Не публикуйте токены, ключи, номера счетов, Telegram user IDs владельца, содержимое брокерских отчётов, Authorization headers или персональные данные в Issues и Pull Request. Используйте приватный канал владельца репозитория.

В сообщении укажите без секретов:

- затронутый commit или release;
- endpoint или модуль;
- воспроизводимые шаги на фиктивных данных;
- ожидаемое и фактическое поведение;
- возможное влияние;
- безопасный вариант исправления.

## Критические инварианты

- `trading_methods=false`.
- Gateway Actions используют только `GET`.
- Telegram Companion вызывает Gateway только методом `GET`.
- `POST /telegram/webhook` является только транспортом входящих Telegram updates.
- Нет создания, отправки, замены, отмены заявок и стоп-заявок.
- `app:app` остаётся стабильным Gateway entrypoint.
- `telegram_bot.app:app` является отдельным Telegram entrypoint.
- Секреты поступают только через переменные окружения.
- Telegram webhook проверяет `X-Telegram-Bot-Api-Secret-Token`.
- Telegram доступ ограничен allowlist пользователей и private chat.
- Ответы повторно маскируют номер счёта.
- Ошибки очищаются от секретов перед выводом.

## Запрещённые данные в Git

- `TINVEST_TOKEN`;
- `GATEWAY_API_KEY` и `OMNI_GATEWAY_API_KEY`;
- `TELEGRAM_BOT_TOKEN`;
- `TELEGRAM_WEBHOOK_SECRET`;
- реальные `TELEGRAM_ALLOWED_USER_IDS`;
- полный ID брокерского счёта;
- реальные HTML/PDF/JSON брокерские отчёты;
- Telegram update dumps и история сообщений;
- логи с чувствительными значениями;
- приватные ключи и сертификаты пользователя.

## Проверка перед merge

Regression Shield должен подтвердить:

- отсутствие торговых operationId и mutating Gateway routes;
- Bearer-защиту Actions;
- валидность OpenAPI;
- стабильный `app:app`;
- Telegram version и `telegram_bot.app:app`;
- webhook secret validation;
- блокировку unauthorized Telegram user;
- GET-only Gateway client;
- `trading_methods=false` в обоих health contracts.
