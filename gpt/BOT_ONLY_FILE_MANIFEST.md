# Bot-only file manifest

Этот список содержит только файлы, относящиеся к Omni-CIO Gateway, Custom GPT и Telegram Companion. Данные старого аккаунта ChatGPT, личные чаты и посторонние проекты сюда не входят.

## 1. Обязательные файлы для нового проекта ChatGPT

| Файл | Назначение |
|---|---|
| `AGENTS.md` | Неприкосновенные правила разработки, read-only и Git workflow |
| `README.md` | Текущая версия, архитектура, запуск и карта репозитория |
| `docs/README.md` | Навигация по документации |
| `knowledge/00_PROJECT_MASTER_CONTEXT.md` | Единая обезличенная память проекта |
| `gpt/PROJECT_INSTRUCTIONS.md` | Готовый текст для Project instructions |
| `gpt/NEW_CHAT_PROMPT.md` | Стартовый запрос для нового чата после подключения GitHub |

## 2. Обязательные файлы для нового Custom GPT

| Файл | Куда использовать |
|---|---|
| `gpt/CONFIGURATION.md` | Имя, описание, starters, capabilities и publishing checklist |
| `gpt/INSTRUCTIONS_COMPACT.md` | Полностью вставить в поле Instructions GPT Editor |
| `gpt/ACTIONS_CATALOG.md` | Проверка списка Actions и operationId |
| `knowledge/13_COMMUNICATION_STYLE_2026.txt` | Загрузить в Knowledge как расширенный профиль общения |

Расширенный `gpt/INSTRUCTIONS.md` нужен для разработки и восстановления контекста, но не вставляется целиком в поле Instructions из-за лимита редактора.

## 3. Профильные knowledge-файлы Gateway

Для разработки и проверок должны оставаться в репозитории все файлы `knowledge/NN_*`, включая правила:

- идентификации инструментов;
- рыночных данных;
- рыночной оценки портфеля;
- аналитики структуры и концентрации;
- денег и ликвидности;
- purchase-capacity preview и integrity;
- операций и cash-flow reconciliation;
- официального брокерского отчёта;
- асинхронного task lifecycle;
- Telegram Companion;
- современного стиля 2026.

В новый ChatGPT Project не обязательно загружать каждый knowledge-файл вручную, если GitHub подключён и чат может прочитать репозиторий. Для Custom GPT Knowledge загружается только необходимый справочный файл стиля или другие явно выбранные документы.

## 4. Runtime и API

В GitHub обязательно сохраняются:

- `app.py` и Gateway runtime modules;
- `telegram_bot/`;
- `broker_report_reconciliation/`;
- `render.yaml`;
- `render.telegram.yaml`;
- `requirements.txt` и dev dependencies;
- `tests/`;
- `scripts/`;
- `.github/`;
- OpenAPI-контракт, формируемый работающим Gateway через `/openapi.json`.

## 5. Документация и эксплуатация

- `docs/architecture/` — архитектура и структура;
- `docs/operations/` — deploy и release runbooks;
- `docs/inventory/` — реестр файлов и внешних компонентов;
- `CHANGELOG.md` — история релизов;
- `SECURITY.md` — правила безопасности;
- `CONTRIBUTING.md` — порядок изменений.

## 6. Что намеренно не переносится и не хранится в GitHub

- экспорт аккаунта ChatGPT;
- старые личные чаты;
- память и настройки другого аккаунта;
- файлы других проектов;
- `TINVEST_TOKEN`;
- `GATEWAY_API_KEY` и `OMNI_GATEWAY_API_KEY`;
- `TELEGRAM_BOT_TOKEN`;
- `TELEGRAM_WEBHOOK_SECRET`;
- реальные Telegram user IDs;
- полный номер брокерского счёта;
- реальные операции, позиции и брокерские отчёты;
- Render secrets;
- секретный Bearer key из GPT Editor.

## 7. Внешние настройки, которые вводятся вручную

GitHub хранит желаемую конфигурацию, но не секретные значения. В новом Custom GPT вручную выполняются только:

1. создание GPT;
2. вставка `INSTRUCTIONS_COMPACT.md`;
3. загрузка выбранных Knowledge-файлов;
4. включение Web Search;
5. импорт production `/openapi.json`;
6. Authentication → API Key → Bearer;
7. ввод существующего `GATEWAY_API_KEY` из Render;
8. тест одного целевого GET Action;
9. проверка `trading_methods=false`.

Render services, T-Invest token и Telegram Companion не создаются заново, если используются существующие production services.
