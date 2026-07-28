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
- Runtime и CI устанавливают только полностью pinned зависимости с
  проверенными SHA-256 hashes.
- Внешние GitHub Actions закреплены полным commit SHA.

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
- совпадение `.in` constraints и hash-locked dependency files;
- Ruff, formatting baseline и mypy;
- branch-inclusive покрытие не ниже 60%;
- pip-audit для runtime dependencies;
- Bandit для medium/high SAST findings;
- detect-secrets без необработанных находок;
- full-SHA pinning всех внешних GitHub Actions.

Гейты блокируют merge. Для них запрещён `continue-on-error`. Узкое
исключение Bandit B102 для фиксированного loader checked-in `.pyfrag`
описано в `knowledge/14_CI_SECURITY_BASELINE.txt`; оно не разрешает
загрузку или исполнение внешнего кода.
