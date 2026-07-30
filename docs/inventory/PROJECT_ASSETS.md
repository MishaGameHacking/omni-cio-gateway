# Реестр компонентов и внешних активов

Дата инвентаризации: 2026-07-30.

Этот файл отвечает на вопрос: «Что новый чат получит из GitHub, а что нужно подключить отдельно?»

## 1. Находится в этом репозитории

### Omni-CIO Gateway

- FastAPI gateway и стабильный entrypoint `app:app`;
- T-Invest read-only integration;
- OpenAPI-схема GPT Actions;
- снимки портфеля, рыночные данные и аналитика;
- versioned Pydantic data contracts v1 с `Decimal`, provenance, quality,
  completeness, UTC timestamps и обязательным маскированием счёта;
- fail-closed adapter текущего portfolio market snapshot в
  `PortfolioSnapshotV1` с сохранением blocked cash, НКД и сверкой итогов;
- shadow contract validation для portfolio market payload с состояниями
  `ready`, `partial`, `rejected`, безопасными aggregate logs и отдельным
  fail-closed gate для будущего Decision Engine;
- `OperationsAnalyticsV1` для типизированных операций, денежных потоков,
  оборота, пагинации, сверки и качества данных отдельно по валютам;
- fail-closed adapter существующего `getOperationsAnalytics` payload с
  обязательными `trading_methods=false`, masked account, read-only source и
  double-count protections;
- `AdvancedPortfolioAnalyticsV1` и pure analytics engine для структуры,
  cash/invested weights, asset-class allocation, top-1/top-5 concentration,
  HHI, effective position count и stress sensitivities отдельно по валютам;
- explicit missing-data records для issuer, sector, liquidity, historical
  prices, volatility, drawdown, correlation, tax basis и bond-specific inputs;
- `ConservativeRiskPolicyV1` с отдельными `pass`, `warning`, `breach`,
  `unknown`, `not_applicable`, блокировкой high-risk execution и консервативным
  неперсонализированным baseline;
- `MarketResearchBundleV1` для instrument reference, quotes, liquidity,
  issuer/issue ratings, bond metrics и corporate events;
- offline market readiness assessment по authority, coverage, value timestamp
  и freshness без сетевого fetch, HTML/PDF parsing или нового Action;
- exact Decimal spread arithmetic, identity/currency reconciliation и
  обязательный `trading_methods=false` в market bundle;
- `NewsDocumentInputV1` и `SanitizedNewsDocumentV1` для разделения внешних
  инструкций и данных, явного entity-resolution и безопасного disposition;
- offline news sanitization на стандартной библиотеке: nested hidden HTML,
  NFKC, zero-width/bidi controls, size limits и prompt-injection flags;
- exact content deduplication с article-specific occurrence IDs, source ranking,
  event-time clusters и проверяемым duplicate audit trail;
- news security tests для tool/credential/code/trade/withdrawal instructions,
  hidden scripts, Unicode obfuscation, oversized content и отсутствия network
  client imports;
- cash/liquidity diagnostics;
- purchase capacity preview и integrity;
- operations analytics;
- broker report reconciliation и async integrity;
- Render Blueprint `render.yaml`;
- hash-locked runtime/development dependencies из четырёх прямых runtime constraints (`fastapi`, `httpx`, private-registry `t-tech-investments`, `uvicorn[standard]`);
- unit и Regression Shield tests;
- blocking Ruff, formatting, mypy, coverage, SCA, SAST и secret scan;
- краткоживущие CI diagnostics с mypy, pytest и coverage output;
- machine-checked read-only GPT release manifest для фактической OpenAPI-схемы;
- live read-only acceptance для публичных `/health` и `/openapi.json` с
  ежедневным и ручным GitHub workflow без брокерского или account access;
- weekly Dependabot для pip и GitHub Actions.

### Граница поддерживаемого runtime

- пользовательский интерфейс работает через Custom GPT в ChatGPT;
- Telegram runtime, Blueprint, тесты и активная конфигурация удалены;
- отсутствие Telegram-компонентов контролируют Regression Shield и
  `tests/test_no_telegram_runtime.py`;
- решение и процедура внешней очистки зафиксированы в
  `knowledge/12_TELEGRAM_RETIREMENT.txt` и
  `docs/operations/TELEGRAM_REMOVAL_RUNBOOK.md`;
- PR-11 news pipeline остаётся offline data boundary: live URL fetching и новый
  public Action не подключены.

### Custom GPT Modern Financial Sage — 2026

- пошаговая настройка My GPTs и Actions в `gpt/MY_GPT_SETUP_RUNBOOK.md`;
- канонические инструкции в `gpt/INSTRUCTIONS.md`;
- реестр ручной конфигурации в `gpt/CONFIGURATION.md`;
- переносимый профиль `knowledge/13_COMMUNICATION_STYLE_2026.txt`;
- современный разговорный русский язык;
- простые объяснения финансовых терминов;
- разделение фактов, выводов и сценариев;
- умеренный мат без оскорбления пользователя;
- шаблон коротких мобильных публикаций с датой и источниками; это только
  формат ответа внутри ChatGPT, а не Telegram-интеграция;
- сохранение GET-only и `trading_methods=false`.

### Проектная память

- исходный PDF v9, текстовая поисковая копия и иерархия в `docs/master-plan/`;
- `AGENTS.md`;
- `knowledge/00_PROJECT_MASTER_CONTEXT.md`;
- профильные файлы `knowledge/`;
- `docs/` с архитектурой и runbooks;
- `gpt/` с переносимой конфигурацией Custom GPT;
- changelog, contribution и security policies.

## 2. Существует вне GitHub и не должно копироваться как секрет

### Render gateway service

Хранит:

- `TINVEST_TOKEN`;
- `GATEWAY_API_KEY`;
- deploy state и автоматически заданный `RENDER_EXTERNAL_URL`.

Live acceptance проверяет только boolean-статус конфигурации из `/health` и не
получает значения секретов.

### Выведенные из эксплуатации внешние Telegram-активы

Очистка завершена владельцем 2026-07-28: отдельный Telegram Render
service удалён, webhook удалён, token отозван. Значения credentials не
хранятся в GitHub. История процедуры находится в
`docs/operations/TELEGRAM_REMOVAL_RUNBOOK.md`.

### Custom GPT

В GPT Editor хранятся:

- выбранная модель;
- загруженная Action schema;
- Bearer API key;
- опубликованное состояние GPT;
- UI-настройки и доступ пользователей;
- фактически применённый текст Instructions;
- состояние Web Search и других capabilities.

GitHub хранит желаемую каноническую конфигурацию, но не может автоматически изменить GPT Editor.

### T-Invest

Во внешней системе находятся брокерский счёт, токен, позиции, операции и официальные отчёты. GitHub хранит только клиентский код, схемы и фиктивные тестовые данные.

### Dependency audit 2026-07-30

- direct dependency set минимален и не содержит Telegram packages;
- оба lock-файла exact-pinned и SHA-256 hash-locked;
- production/CI используют `--require-hashes`;
- новые upstream версии FastAPI/Uvicorn и переход pytest major проверяются только отдельными dependency PR, а не смешиваются с governance cleanup;
- private `t-tech-investments==1.49.2` нельзя сравнивать или заменять одноимённым публичным PyPI package.

## 3. Ещё не подключено к этому репозиторию

### Frontend Omni-CIO Bot

Существующий сайт:

`https://omni-cio-bot.ervinwilliams97920.chatgpt.site`

Исходный frontend-проект или отдельный репозиторий пока не зафиксирован. До определения источника нельзя создавать копию сайта. Когда источник будет найден, добавить repository/project ID, production URL, framework, build command, hosting configuration, parser path и связь frontend release с backend release.

### HTML-отчёты СберИнвестиций

Реальные отчёты не должны сохраняться в GitHub. Допускаются только специально обезличенные fixtures без счёта, сделок, сумм, персональных данных и иных идентификаторов.

### Live news retrieval

URL fetch, redirect policy, MIME validation, DNS/IP allowlists, SSRF protection,
response-size enforcement и storage policy пока не подключены. PR-11 принимает
только уже предоставленный текст/HTML и не выполняет сетевые запросы.

## 4. Что нужно новому чату

1. GitHub read access.
2. Для изменения кода — GitHub write access через ветку и PR.
3. Для production-проверки — доступ к публичным `/health` и `/openapi.json` Gateway либо результатам live acceptance workflow.
4. Для изменения секретов — доступ к Render Dashboard.
5. Для изменения Custom GPT — доступ к GPT Editor.
6. Для dependency updates — проверка Dependabot PR и Regression Shield.

## 5. Запрещённые способы «сохранить всё»

Нельзя добавлять реальные токены, API keys, отозванные Telegram
credentials, полный номер счёта, export чатов, реальные брокерские
отчёты или screenshots с чувствительными значениями. GitHub хранит
воспроизводимую систему и знания, а не пользовательские секреты.
