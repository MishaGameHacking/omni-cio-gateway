# Portfolio GPT file manifest

Этот список содержит только файлы, необходимые для существующего Omni-CIO Custom GPT и его защищённого Gateway.

## 1. Канонические файлы продукта

| Файл | Назначение |
|---|---|
| `AGENTS.md` | Обязательные правила разработки и read-only границы |
| `docs/master-plan/OMNI_CIO_PORTFOLIO_GPT_RESET_V1.md` | Текущий portfolio-only scope |
| `knowledge/16_CURRENT_PROGRAM_STATUS.md` | Фактический текущий этап |
| `gpt/INSTRUCTIONS_COMPACT.md` | Текст для поля Instructions GPT Editor |
| `gpt/INSTRUCTIONS.md` | Расширенная версия для разработки и аудита |
| `gpt/CONFIGURATION.md` | Имя, описание, capabilities, starters и publishing checklist |
| `gpt/ACTIONS_CATALOG.md` | Фактические 14 read-only Actions |
| `gpt/PERSONAL_PORTFOLIO_POLICY_TEMPLATE.md` | Шаблон личной инвестиционной политики |
| `gpt/PORTFOLIO_GPT_ACCEPTANCE_V1.md` | Preview end-to-end acceptance |
| `gpt/MY_GPT_SETUP_RUNBOOK.md` | UI-настройка существующего GPT |

## 2. Что вставляется и загружается в GPT Editor

### Instructions

Полностью вставить:

- `gpt/INSTRUCTIONS_COMPACT.md`.

### Knowledge

Загрузить минимальный набор:

1. Заполненную личную политику на основе `gpt/PERSONAL_PORTFOLIO_POLICY_TEMPLATE.md`.
2. Один компактный документ с методикой анализа портфеля/инструментов, если нужные правила не помещаются в Instructions.
3. Один нейтральный style/reference файл при необходимости.

Не загружать автоматически весь каталог `knowledge/`.

## 3. Что не загружается в production GPT Knowledge

- master plans и roadmap;
- CI/security baseline;
- GitHub issue/PR history;
- architecture/release evidence;
- Telegram history и removal runbook;
- deployment diagnostics;
- реальные операции, позиции и отчёты;
- секреты;
- полный account ID.

## 4. Capabilities

Включить:

- Web Search;
- Data Analysis / Code Interpreter;
- Actions.

Выключить:

- Image generation;
- Apps;
- любые Telegram-интеграции.

## 5. Runtime и API в GitHub

Сохраняются:

- `app.py` и Gateway runtime;
- `omni_cio/`;
- `broker_report_reconciliation/`;
- `render.yaml`;
- hash-locked dependencies;
- `tests/`;
- `scripts/`;
- `.github/`;
- production OpenAPI через `/openapi.json`.

Gateway остаётся минимальным data/validation layer. Backend-файл сохраняется только при наличии consumer/test или явного compatibility status.

## 6. Полностью исключено из продукта

- сайт и web-кабинет;
- мобильное приложение;
- отдельный frontend;
- Telegram-бот;
- Telegram drafts и publishing;
- Telegram API и credentials;
- собственная AI-модель;
- autonomous execution;
- broker write methods.

Исторические Telegram retirement files могут оставаться в репозитории как audit evidence, но не входят в продукт, GPT Knowledge, Actions или roadmap.

## 7. Секреты

Не хранить в GitHub:

- `TINVEST_TOKEN`;
- `GATEWAY_API_KEY`;
- Authorization headers;
- полный номер счёта;
- Render secrets;
- реальные брокерские payload.

## 8. Owner-only действия

Владелец вручную выполняет только:

1. вставку `INSTRUCTIONS_COMPACT.md` в существующий GPT;
2. заполнение и загрузку personal policy;
3. удаление конфликтующих Knowledge-файлов;
4. включение Web Search и Data Analysis;
5. выключение Image generation;
6. импорт `/openapi.json`, когда schema changed/stale;
7. ввод Bearer key;
8. Preview acceptance;
9. Update.

ChatGPT/agent выполняет GitHub, код, тесты, OpenAPI review, документацию и подготовку точных UI-инструкций.
