# Bot-only file manifest

Этот список содержит только файлы, относящиеся к Omni-CIO Gateway и
Custom GPT. Данные старого аккаунта ChatGPT, личные чаты и посторонние
проекты сюда не входят.

## 1. Обязательные файлы для нового проекта ChatGPT

| Файл | Назначение |
|---|---|
| `AGENTS.md` | Неприкосновенные правила разработки, read-only и Git workflow |
| `README.md` | Текущая версия, архитектура, запуск и карта репозитория |
| `docs/README.md` | Навигация по документации |
| `knowledge/00_PROJECT_MASTER_CONTEXT.md` | Единая обезличенная память проекта |
| `knowledge/16_CURRENT_PROGRAM_STATUS.md` | Что завершено и какой пакет следующий |
| `docs/master-plan/README.md` | Иерархия и правила использования исходного master plan |
| `docs/master-plan/OMNI_CIO_MASTER_PROMPT_V9.pdf` | Исходная пользовательская спецификация развития |
| `gpt/PROJECT_INSTRUCTIONS.md` | Готовый текст для Project instructions |
| `gpt/NEW_CHAT_PROMPT.md` | Стартовый запрос для нового чата после подключения GitHub |

## 2. Обязательные файлы для нового Custom GPT

| Файл | Куда использовать |
|---|---|
| `gpt/MY_GPT_SETUP_RUNBOOK.md` | Пошаговая настройка ChatGPT → My GPTs |
| `gpt/CONFIGURATION.md` | Имя, описание, starters, capabilities и publishing checklist |
| `gpt/INSTRUCTIONS_COMPACT.md` | Полностью вставить в поле Instructions GPT Editor |
| `gpt/ACTIONS_CATALOG.md` | Проверка списка Actions и operationId |
| `knowledge/13_COMMUNICATION_STYLE_2026.txt` | Загрузить в Knowledge как расширенный профиль общения |

`gpt/INSTRUCTIONS_COMPACT.md` — проверенная рабочая версия для GPT Editor; расширенный `gpt/INSTRUCTIONS.md` нужен для разработки, аудита и восстановления контекста.

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
- решение о выводе Telegram Companion из эксплуатации;
- современного стиля 2026.

В новый ChatGPT Project не обязательно загружать каждый knowledge-файл вручную, если GitHub подключён и чат может прочитать репозиторий. Для Custom GPT Knowledge загружается только необходимый справочный файл стиля или другие явно выбранные документы.

## 4. Runtime и API

В GitHub обязательно сохраняются:

- `app.py` и Gateway runtime modules;
- `broker_report_reconciliation/`;
- `render.yaml`;
- `requirements.txt` и dev dependencies;
- `tests/`;
- `scripts/`;
- `.github/`;
- OpenAPI-контракт, формируемый работающим Gateway через `/openapi.json`.

## 5. Документация и эксплуатация

- `docs/master-plan/` — исходная спецификация и её текстовая поисковая копия;
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
- `GATEWAY_API_KEY`;
- действующие или отозванные Telegram credentials;
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

Существующий Render Gateway и T-Invest token не создаются заново.
Старый Telegram service выводится из эксплуатации по
`docs/operations/TELEGRAM_REMOVAL_RUNBOOK.md`.
