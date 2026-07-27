# Структура репозитория

## Каноническое дерево

```text
omni-cio-gateway/
├── app.py                         # стабильный production entrypoint
├── app_v371.py                    # архивный совместимый wrapper
├── app_v360.py                    # базовый legacy wrapper
├── main.py                        # историческое ядро FastAPI
├── *_analytics.py / *_market.py   # доменные runtime-модули
├── broker_report_reconciliation/  # официальный отчёт и сверка
├── tests/                         # unit, endpoint, OpenAPI, Regression Shield
├── knowledge/                     # правила предметной области для AI
├── gpt/                           # каноническая конфигурация Custom GPT
├── docs/
│   ├── architecture/              # архитектура и карта файлов
│   ├── operations/                # эксплуатационные runbooks
│   └── inventory/                 # реестр компонентов и внешних активов
├── scripts/                       # локальные безопасные проверки
├── .github/
│   ├── workflows/                 # постоянные CI workflow
│   ├── ISSUE_TEMPLATE/            # шаблоны задач
│   ├── CODEOWNERS                 # владельцы областей
│   ├── pull_request_template.md   # единый формат PR
│   └── copilot-instructions.md    # правила GitHub Copilot
├── AGENTS.md                      # обязательные правила агентов
├── README.md                      # главная точка входа
├── CHANGELOG.md                   # история релизов
├── CONTRIBUTING.md                # процесс разработки
├── SECURITY.md                    # политика безопасности
├── requirements.txt               # runtime-зависимости
├── requirements-dev.txt           # тестовые зависимости
├── render.yaml                    # production deploy contract
├── .env.example                   # имена переменных без значений
├── .gitignore
└── .editorconfig
```

## Правила размещения

### Корень

В корне остаются только файлы, необходимые для запуска, сборки, навигации и совместимости production. Новые крупные доменные функции не следует добавлять в `main.py`; они должны жить в отдельном модуле.

### `knowledge/`

Содержит строгие правила интерпретации данных и поведения Actions. Нумерация:

- `00_` — общий проектный контекст;
- `01_..08_` — базовые возможности;
- `09_` — рыночные данные и покупательная способность;
- `10_` — операции и денежная сверка;
- `11_` — асинхронный брокерский отчёт;
- следующий номер — только для новой предметной области.

### `gpt/`

Содержит переносимую конфигурацию Custom GPT. Любой новый чат может восстановить поведение бота, не полагаясь на старую переписку.

### `docs/`

Содержит объяснения архитектуры, порядок эксплуатации и реестр внешних компонентов. Здесь не дублируются большие response schemas.

### `.github/workflows/`

Хранятся только постоянные workflow. Одноразовые release-patcher workflow после выполнения удаляются из `main`.

### `tests/`

Имена соответствуют доменному модулю. Для каждого нового Action нужны happy path, partial/error path, OpenAPI/endpoint и read-only проверки.

## Что нельзя переносить без отдельного PR

- `app.py` и entrypoint `app:app`;
- wrapper-модули, пока маршруты используют их globals;
- существующие operationId;
- публичные paths;
- поля ответа, используемые Custom GPT.

## Направление будущего рефакторинга

Целевая структура Python-кода может перейти в пакет `omni_cio_gateway/`, но только после добавления compatibility imports и полного production smoke test. Документационный порядок не должен маскировать риск такого переноса.
