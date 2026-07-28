# Политика безопасности

Omni-CIO работает с финансовыми данными и должен оставаться строго
read-only в Gateway и Custom GPT.

## Сообщение об уязвимости

Не публикуйте токены, ключи, номера счетов, содержимое брокерских
отчётов, Authorization headers или персональные данные в Issues и Pull
Request. Используйте приватный канал владельца репозитория.

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
- Нет создания, отправки, замены, отмены заявок и стоп-заявок.
- Purchase preview получает только сервисы `users`, `instruments` и
  ограниченный `orders` adapter.
- `orders` adapter разрешает только `get_max_lots` и `get_order_price`;
  generic SDK forwarding запрещён.
- Runtime source проверяется AST-сканером на обращения к торговым,
  stop-order, sandbox, withdrawal и transfer методам.
- `app:app` остаётся стабильным Gateway entrypoint.
- Секреты поступают только через переменные окружения.
- Telegram runtime, `/telegram/webhook`, Blueprint и active env
  configuration отсутствуют и блокируются Regression Shield.
- Ответы повторно маскируют номер счёта.
- Ошибки очищаются от секретов перед выводом.

## Запрещённые данные в Git

- `TINVEST_TOKEN`;
- `GATEWAY_API_KEY`;
- любые старые Telegram credentials, IDs и webhook secrets,
  обнаруженные при удалении внешнего service;
- полный ID брокерского счёта;
- реальные HTML/PDF/JSON брокерские отчёты;
- логи с чувствительными значениями;
- приватные ключи и сертификаты пользователя.

## Проверка перед merge

Regression Shield должен подтвердить:

- отсутствие торговых operationId и mutating Gateway routes;
- строгий allowlist SDK-сервисов и методов purchase preview;
- негативные тесты, доказывающие отсутствие доступа к брокерским
  write-методам;
- Bearer-защиту Actions;
- валидность OpenAPI;
- стабильный `app:app`;
- отсутствие `telegram_bot/`, `render.telegram.yaml`, Telegram imports,
  env variables и OpenAPI routes;
- `trading_methods=false` в Gateway health contract.
