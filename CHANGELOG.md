# Changelog

Все заметные изменения Omni-CIO фиксируются здесь. Источник истины по коду — ветка `main`; подробности релизов находятся в соответствующих Pull Request.

## [Unreleased]

### Added
- Hash-locked runtime и development dependency sets, генерируемые из
  `requirements.in` и `requirements-dev.in`.
- Blocking Ruff, formatting, mypy, coverage, pip-audit, Bandit и
  detect-secrets gates в Regression Shield.
- Self-test CI/security policy, weekly Dependabot и профиль
  `knowledge/14_CI_SECURITY_BASELINE.txt`.
- Retirement guard, который запрещает возврат `telegram_bot/`,
  `render.telegram.yaml`, Telegram imports, active env configuration и
  `/telegram/*` routes.
- `knowledge/12_TELEGRAM_RETIREMENT.txt` и post-merge runbook очистки
  внешнего Render service, webhook и token.
- Явный read-only allowlist T-Invest SDK для purchase preview:
  `users`, `instruments`, `orders.get_max_lots` и
  `orders.get_order_price`.
- Негативные тесты и AST-проверка, блокирующие broker order,
  stop-order, sandbox, withdrawal и transfer write-методы.
- Профиль Custom GPT `Modern Financial Sage — 2026`.
- Современный разговорный русский язык без банковского канцелярита.
- Обязательный перевод сложных финансовых терминов на человеческий язык.
- Понятная шкала риска: зелёный, жёлтый, оранжевый, красный.
- Разделение фактов, аналитических выводов и сценариев.
- Правила умеренной нецензурной лексики без оскорбления пользователя и без подмены анализа эмоциями.
- Отдельный стандарт Telegram-постов: короткие мобильные абзацы, главный вывод в начале, дата и источники.
- Профиль знаний `knowledge/13_COMMUNICATION_STYLE_2026.txt`.
- Компактный рабочий файл `gpt/INSTRUCTIONS_COMPACT.md`, рассчитанный на лимит 8000 символов GPT Editor.

### Removed
- Telegram Companion runtime package и его unit-тесты.
- Telegram Render Blueprint и active environment template.
- Telegram entrypoint, webhook, startup configuration и проверки из
  Regression Shield.

### Changed
- Render и GitHub Actions устанавливают зависимости только с
  `--require-hashes`.
- Все внешние GitHub Actions закреплены полными commit SHA.
- Начальный branch-inclusive coverage floor установлен на 60% после
  фактического измерения 60,8%.
- Поддерживаемый пользовательский интерфейс теперь находится только в
  Custom GPT внутри ChatGPT; Gateway остаётся `app:app`.
- System release подготовлен как `v4.1.0 ChatGPT-only Runtime`, Gateway
  API component остаётся `v3.9.1`.
- Канонический `gpt/INSTRUCTIONS.md` теперь ориентирован на простые объяснения состояния портфеля, компаний, рисков и денежных потоков.
- GPT Editor использует компактные Instructions, а расширенный документ остаётся проектным источником истины.
- Рекомендуемые conversation starters обновлены для понятного анализа и подготовки Telegram-публикаций.
- Web Search рекомендуется включать для актуального анализа компаний, отчётности, дивидендов, новостей и рыночного контекста.

### Safety
- Security/quality gates являются блокирующими и не используют
  `continue-on-error`.
- Зафиксирован узкий Bandit B102 exception только для checked-in
  broker-report fragments из фиксированного package path.
- Удалён generic SDK forwarding из `OrdersServiceRequestAdapter` и
  `ClientView`.
- Публичные Action-контракты, Gateway version и Render entrypoint не
  изменены.
- `trading_methods=false` и GET-only контракт сохранены.
- Сильные выводы должны подтверждаться цифрами, датой и источниками.

## [4.0.1] — 2026-07-28

### Added
- Команда `/status` для проверки Telegram Companion, Omni-CIO Gateway и подключения к T-Invest.
- Краткие русские сводки для всех Telegram-команд вместо больших JSON-блоков.
- Безопасное разбиение длинных сообщений с маркировкой частей.
- Необязательный Telegram typing indicator.
- Безопасный reliability profile в `/health` Telegram service.

### Changed
- Временные ошибки Gateway автоматически повторяются по настраиваемой политике.
- Перед первым повтором пользователь получает сообщение о пробуждении основного сервера.
- Ошибки Gateway показываются понятным сообщением без утечки технических секретов.

### Safety
- Повторяются только GET-запросы и только для временных сетевых/HTTP ошибок.
- HTTP 401/403 и другие постоянные ошибки не повторяются.
- `trading_methods=false` сохранён.
- Gateway API v3.9.1 и entrypoint `app:app` не изменены.

## [4.0.0] — 2026-07-28

### Added
- Отдельный FastAPI service `telegram_bot.app:app`.
- Команды `/health`, `/connection`, `/portfolio`, `/cash`, `/analytics`, `/operations`, `/report`, `/report_status`.
- Автоматическая установка Telegram webhook и списка команд при старте.
- Изолированный Render Blueprint `render.telegram.yaml`.
- Ограничение доступа по `TELEGRAM_ALLOWED_USER_IDS` и только личным чатам.
- Webhook secret validation, update deduplication, rate limit и повторное маскирование account ID.
- In-memory удобство для повторного использования `task_id` официального брокерского отчёта.
- Полный runbook и профильный knowledge-файл Telegram Companion.

### Safety
- Telegram вызывает Omni-CIO Gateway только методом GET.
- Торговые команды отсутствуют.
- `trading_methods=false`.
- Gateway component и его entrypoint `app:app` не изменены.
- Telegram и gateway deploy разделены, поэтому сбой Telegram не ломает основной API.

## [3.9.1] — 2026-07-27

### Added
- Асинхронная целостность официального брокерского отчёта.
- Возврат настоящего `task_id` при первом вызове без преждевременного опроса.
- Обработка T-Invest `30058` как штатного состояния `pending`.
- Ограничение периода официального отчёта до `1..31` дня.

### Safety
- `trading_methods=false`.
- Стабильный Render entrypoint `app:app`.

## [3.9.0] — 2026-07-27

- Official Broker Report & Operations Reconciliation.
