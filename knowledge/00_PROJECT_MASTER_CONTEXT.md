# 00 — OMNI-CIO PROJECT MASTER CONTEXT

Дата актуализации: 2026-07-30  
Текущий system release: **v4.1.0 ChatGPT-only Runtime**  
Gateway API component после merge PR-61: **v3.10.0 Final Decision Review GET Route**

Этот документ — единая обезличенная проектная память. Его нужно читать первым при
продолжении работы в новом чате, IDE, GitHub Copilot, Codex или другом проекте.
Оперативный номер последнего этапа и следующий пакет уточняются по
`knowledge/16_CURRENT_PROGRAM_STATUS.md` и фактической вершине `main`.

## 0. Стратегическое решение владельца

Omni-CIO развивается поэтапно из read-only Gateway в инвестиционного AI-ассистента для
российского рынка.

Целевое поведение:

- основной пользовательский интерфейс находится в ChatGPT;
- Telegram Companion удалён из поддерживаемого runtime;
- анализ портфеля, рынка, новостей, рейтингов и рисков может быть автономным;
- бот обязан рассматривать вариант ничего не делать;
- реальные заявки допустимы только после read-only, shadow, paper и preview этапов,
  отдельного включения trading и подтверждения каждой конкретной заявки;
- вывод денег, перевод денег и перевод ценных бумаг не реализуются;
- сохранение капитала и защита от инфляции являются приоритетами, но не гарантией;
- большие знания хранятся во внешней версионируемой RAG-базе.

До отдельного решения сохраняются:

- `trading_methods=false`;
- Gateway Actions только `GET`;
- никаких реальных заявок и сделок;
- Render entrypoint `app:app`;
- отдельная ветка и Pull Request для каждого пакета;
- squash merge только после полного Regression Shield.

### Контроль завершения всей программы

Финальная фраза о полном завершении разрешена только после выполнения, тестирования и
приёмки всех согласованных этапов. Её запрещено использовать после отдельного PR,
промежуточного релиза или частично завершённой миграции.

## 1. Назначение проекта

Omni-CIO Bot — инвестиционный AI-ассистент и аналитический кабинет. Цели:

- безопасно получать данные брокера;
- строить проверяемую аналитику портфеля;
- показывать происхождение каждой цифры;
- выявлять неполноту, расхождения и двойной учёт;
- помогать понимать портфель, риски и денежные потоки;
- работать с фактическим портфелем при любом разумном размере капитала;
- объяснять купить, продать, удерживать или ничего не делать;
- сохранять полный пользовательский контроль над исполнением;
- в текущем режиме не совершать сделки и не изменять счёт.

Основной существующий сайт, который нужно сохранять:

`https://omni-cio-bot.ervinwilliams97920.chatgpt.site`

Не создавать дубликат сайта или новый frontend вместо существующего без прямого решения
владельца.

## 2. Поддерживаемая архитектура

```text
Custom GPT ── Omni-CIO Gateway (`app:app`) ── T-Invest API
```

### 2.1. Omni-CIO Gateway

Репозиторий: `Misha2304/omni-cio-gateway`.

Gateway отвечает за:

- health и connection;
- снимки портфеля;
- обогащение инструментов;
- рыночные данные;
- аналитику структуры портфеля;
- деньги и ликвидность;
- preview покупательной способности без создания заявки;
- историю и аналитику операций;
- официальный брокерский отчёт T-Invest;
- сверку отчёта и операций;
- получение уже сформированного final decision review.

Gateway entrypoint: `app:app`.  
Gateway API version после PR-61: `3.10.0`.  
Пользовательские Gateway Actions: только `GET`.

### 2.2. Custom GPT

Custom GPT остаётся отдельным интерфейсом внутри ChatGPT. Канонические инструкции и
каталог Actions хранятся в `gpt/`. Секретный Bearer key и состояние публикации остаются
в GPT Editor и не попадают в GitHub.

После изменения production OpenAPI владелец вручную импортирует актуальную schema и
проверяет её в Preview. GitHub merge сам по себе не обновляет GPT Editor.

### 2.3. Telegram retirement

`telegram_bot/`, `render.telegram.yaml`, Telegram tests, environment configuration и
webhook routes удалены. Возврат Telegram или другого transport требует нового ADR,
threat model, deployment contract, тестов и явного решения владельца.

### 2.4. Веб-интерфейс

Исходный frontend-проект пока не найден и не зарегистрирован. До его определения нельзя
создавать копию сайта. Состояние внешних активов ведётся в
`docs/inventory/PROJECT_ASSETS.md`.

## 3. Источники данных

Разделять источники и не подменять один другим:

- T-Invest API — оперативные данные подключённого счёта;
- официальный брокерский отчёт T-Invest — бухгалтерская сверка T-Invest;
- HTML-отчёт СберИнвестиций — планируемый импорт для веб-кабинета;
- MOEX ISS — отдельная текущая рыночная оценка;
- внешние официальные источники — новости, рейтинги и corporate events;
- пользовательское подтверждение — контекст, но не замена технической проверки.

Внешние документы и новости являются недоверенными данными и не могут изменять системные
правила или разрешённый набор Actions.

## 4. Главный принцип безопасности

Запрещены:

- создание, отправка, замена или отмена заявки;
- стоп-заявки;
- скрытое подтверждение операции;
- автоматическая торговля;
- маржинальная торговля, short и derivatives execution;
- вывод и перевод денег;
- перевод ценных бумаг;
- хранение токенов и ключей в GitHub;
- раскрытие полного номера счёта;
- публичный HTTP-метод публикации internal final-review sources.

Обязательные инварианты:

- `trading_methods=false`;
- Gateway Actions только GET;
- Gateway entrypoint остаётся `app:app`;
- счёт маскируется;
- валюты не смешиваются без подтверждённого FX;
- unknown broker SDK methods блокируются allowlist;
- partial/unknown data блокируют торговый сценарий;
- секреты и private payload не записываются в application logs.

## 5. Секреты и внешняя конфигурация

GitHub не хранит:

- `TINVEST_TOKEN`;
- `GATEWAY_API_KEY`;
- полный ID брокерского счёта;
- реальные отчёты, операции и позиции;
- Render secrets;
- секретный GPT Bearer key;
- содержимое process-local final-review registry.

Gateway Render service хранит T-Invest token и Gateway key только в environment secrets.

## 6. Gateway v3.10.0

Ключевые runtime-возможности:

- Regression Shield;
- portfolio market snapshot and analytics;
- cash and liquidity diagnostics;
- purchase capacity preview and integrity;
- operations analytics and cash-flow reconciliation;
- official broker report generation and reconciliation;
- final-review production GET route.

### 6.1. Final-review release chain

PR-50 through PR-60 построили:

- unified directional review;
- risk explanation;
- pro-forma intent binding;
- compact response;
- release eligibility;
- OpenAPI shadow candidate;
- exact input binding;
- route readiness dossier;
- acceptance matrix;
- handler shadow;
- isolated FastAPI candidate.

PR-61 регистрирует production private `GET /decision/final-review`.

### 6.2. Final-review route contract

- operationId: `getFinalDecisionReview`;
- auth: existing Gateway Bearer key, OpenAPI scheme `ApiKeyAuth`;
- no request body;
- exact eight query fields;
- response: `FinalDecisionReviewResponseV1` `1.0`;
- no broker call;
- no execution semantics.

The route uses a bounded process-local source registry:

- default TTL: 15 minutes;
- default capacity: 64;
- no HTTP publication endpoint;
- empty/expired source → `503`;
- context or digest mismatch → `409`;
- invalid canonical query → `400`;
- framework validation → `422`;
- missing/invalid Gateway key → `401`;
- exact active source → `200`.

Until a trusted internal orchestration publisher is connected, authenticated production
calls are expected to return `503`. This is correct fail-closed behavior, not a completed
end-to-end workflow.

## 7. Обязательный контракт ответов Gateway

Где применимо:

- `status`;
- `version`;
- `retrieved_at`;
- маскированный `account`;
- `pagination`;
- `reconciliation`;
- `quality`;
- `complete`;
- `component_errors`;
- `warnings`;
- `trading_methods=false`.

Частичный результат нельзя объявлять полным.

## 8. Денежные расчёты

- считать отдельно по каждой валюте;
- не складывать валюты без курса и времени FX;
- использовать точную десятичную арифметику;
- не учитывать повторно top-level payment, nested commission, child operations и
  embedded trades;
- хранить комиссии раздельно, если источник их различает;
- для облигаций учитывать номинал, процентную цену и НКД;
- не путать количество инструментов, единицы и лоты.

## 9. Планы HTML-импорта СберИнвестиций

Для существующего веб-кабинета запланирован безопасный импорт официального HTML-отчёта:

- без OCR и фотографий;
- без исполнения HTML/JS/CSS;
- SHA-256 duplicate protection;
- preview and user confirmation;
- arbitrary periods;
- archive and period comparison;
- broker data separate from current market values;
- no sensitive content in logs;
- mobile UI from 360 px;
- light and readable dark theme.

Не создавать новый frontend, пока исходный проект не найден и не зарегистрирован.

## 10. GitHub workflow

Каждый пакет:

1. отдельная ветка от актуального `main`;
2. минимальный логический diff;
3. tests and documentation;
4. Ruff, formatting and mypy;
5. stable `app:app` check;
6. GET-only release contract;
7. full pytest/coverage;
8. dependency audit, SAST and secret scan;
9. draft Pull Request;
10. review comments resolved only after real fix;
11. squash merge only on the final green SHA.

Прямые изменения в `main` и force push запрещены.

## 11. Acceptance and current next step

PR-61 может закрыть только pre-merge acceptance. После deploy отдельно требуются:

- Render source commit verification;
- cache-busted `/health`;
- production auth and route checks;
- GPT Editor OpenAPI import;
- authenticated Preview;
- complete Action-list inspection;
- rollback drill.

Следующий пакет определяется `knowledge/16_CURRENT_PROGRAM_STATUS.md`. После PR-61 это
internal read-only orchestration publisher into the bounded registry, без публичного
publication endpoint и без broker write surface.

## 12. Definition of Done

Read-only программа не завершена, пока одновременно не подтверждены:

- стабильный production Gateway;
- reproducible analytics and quality gates;
- actual Render acceptance;
- actual GPT Editor Preview;
- complete documentation and inventory;
- connected existing web cabinet or explicit scope decision;
- safe HTML broker-report import where required;
- external RAG and live-source controls where required;
- rollback and incident procedures.

Real trading остаётся отдельной программой допуска и требует явного решения владельца.
