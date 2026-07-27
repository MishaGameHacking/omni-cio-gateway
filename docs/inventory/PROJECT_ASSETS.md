# Реестр компонентов и внешних активов

Дата инвентаризации: 2026-07-27.

Этот файл отвечает на вопрос: «Что новый чат получит из GitHub, а что нужно подключить отдельно?»

## 1. Находится в этом репозитории

### Backend и API

- FastAPI gateway и стабильный entrypoint `app:app`;
- T-Invest read-only integration;
- OpenAPI-схема GPT Actions;
- снимки портфеля, рыночные данные и аналитика;
- cash/liquidity diagnostics;
- purchase capacity preview и integrity;
- operations analytics;
- broker report reconciliation и async integrity;
- Render blueprint `render.yaml`;
- unit и Regression Shield тесты.

### Проектная память

- `AGENTS.md`;
- `knowledge/00_PROJECT_MASTER_CONTEXT.md`;
- профильные файлы `knowledge/`;
- `docs/` с архитектурой и runbooks;
- `gpt/` с переносимой конфигурацией помощника;
- changelog, contribution и security policies.

## 2. Существует вне GitHub и не должно копироваться как секрет

### Render

Хранит production-переменные окружения:

- `TINVEST_TOKEN`;
- `GATEWAY_API_KEY`;
- автоматически задаваемый `RENDER_EXTERNAL_URL`.

В GitHub находятся только имена переменных и deploy contract. Значения нужно проверять в Render Dashboard.

### Custom GPT

В интерфейсе ChatGPT хранятся:

- выбранная модель;
- загруженная Action schema;
- Bearer API key;
- опубликованное состояние GPT;
- UI-настройки и доступ пользователей.

Канонический текст инструкций и список Actions сохраняются в `gpt/`, но секретный API key не сохраняется.

### T-Invest

Во внешней системе находятся брокерский счёт, токен, позиции, операции и официальные отчёты. GitHub хранит только клиентский код, схемы и фиктивные тестовые данные.

## 3. Ещё не подключено к этому репозиторию

### Frontend Omni-CIO Bot

Существующий сайт:

`https://omni-cio-bot.ervinwilliams97920.chatgpt.site`

Исходный frontend-проект или отдельный репозиторий пока не зафиксирован. До определения источника нельзя создавать копию сайта. Когда источник будет найден, в этот файл нужно добавить:

- repository/project ID;
- production URL;
- framework и build command;
- hosting configuration;
- путь к parser-модулю HTML-отчётов;
- связь frontend release с backend release.

### HTML-отчёты СберИнвестиций

Реальные отчёты не должны сохраняться в GitHub. Допускаются только специально обезличенные fixtures, если из них удалены счёт, сделки, суммы, персональные данные и иные идентификаторы.

## 4. Что нужно новому чату

Минимальный доступ:

1. GitHub repository read access.
2. Для изменения кода — GitHub write access через ветку и PR.
3. Для production-проверки — доступ к публичному `/health`.
4. Для изменения Render secrets — отдельный доступ к Render, не GitHub.
5. Для изменения Custom GPT — доступ к GPT Editor, не GitHub.

## 5. Запрещённые способы «сохранить всё»

Нельзя добавлять в репозиторий реальные токены, Action API key, полный номер счёта, export чатов с финансовыми данными, реальные брокерские отчёты или screenshots с чувствительными значениями. GitHub должен хранить воспроизводимую систему и знания, а не пользовательские секреты.
