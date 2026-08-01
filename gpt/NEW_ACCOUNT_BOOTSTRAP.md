# Восстановление Omni-CIO Portfolio GPT из GitHub

Этот документ нужен только для восстановления проекта в новом аккаунте ChatGPT или после потери настроек. В обычной работе обновляется уже существующий GPT; дубликат создавать не нужно.

## Целевой результат

Восстанавливается один продукт:

`Omni-CIO | Портфельный управляющий`

Он работает внутри ChatGPT, подключается к существующему read-only Gateway и помогает только с личным портфелем владельца.

Не восстанавливаются:

- старые чаты и память аккаунта;
- сайт, web-кабинет или приложение;
- Telegram;
- отдельный frontend;
- собственная AI-модель;
- write/trading methods.

## 1. Подключить GitHub для разработки

Разрешить доступ только к:

```text
Misha2304/omni-cio-gateway
```

Не создавать копию репозитория. Актуальный `main` остаётся источником истины.

## 2. Проект ChatGPT для разработки

Создание отдельного ChatGPT Project необязательно для работы самого Custom GPT, но удобно для разработки.

При создании проекта:

- рекомендуемое имя: `Omni-CIO Portfolio Development`;
- Project instructions: полный текст `gpt/PROJECT_INSTRUCTIONS.md`;
- первый запрос: полный текст `gpt/NEW_CHAT_PROMPT.md`.

## 3. Существующий или восстановленный Custom GPT

Если GPT уже существует:

1. Открыть My GPTs.
2. Выбрать Omni-CIO.
3. Нажать Edit GPT.
4. Обновить его по `gpt/MY_GPT_SETUP_RUNBOOK.md`.

Создавать новый GPT разрешается только если старый действительно недоступен.

## 4. Канонические настройки

Использовать:

- `gpt/CONFIGURATION.md` — identity, capabilities и starters;
- `gpt/INSTRUCTIONS_COMPACT.md` — поле Instructions;
- `gpt/PERSONAL_PORTFOLIO_POLICY_TEMPLATE.md` — личная политика;
- `gpt/ACTIONS_CATALOG.md` — сверка Actions;
- `gpt/PORTFOLIO_GPT_ACCEPTANCE_V1.md` — Preview acceptance.

## 5. Knowledge

Загрузить только:

1. Заполненную личную политику владельца.
2. Минимальные справочные правила анализа портфеля и инструментов, если они нужны сверх Instructions.
3. Нейтральный style/reference файл при необходимости.

Не загружать:

- master plans;
- CI/security runbooks;
- GitHub history;
- Telegram history;
- release/evidence документы;
- реальные brokerage payload;
- секреты.

## 6. Capabilities

Включить:

- Web Search;
- Code Interpreter / Data Analysis;
- Actions.

Выключить:

- Image generation;
- Apps.

Выбрать модель, поддерживающую Custom Actions.

## 7. Actions и секреты

1. Импортировать production Gateway `/openapi.json`.
2. Authentication → API Key → Bearer.
3. Ввести `GATEWAY_API_KEY` вручную.
4. Проверить ровно 14 GET Actions.
5. Проверить отсутствие order/cancel/transfer/withdraw methods.
6. Проверить `trading_methods=false`.

Значения `TINVEST_TOKEN` и `GATEWAY_API_KEY` не передаются в чат и не сохраняются в GitHub.

## 8. Минимальная проверка

В Preview выполнить:

```text
Проверь только состояние Gateway. Вызови только gatewayHealth.
```

```text
Проверь подключение. Вызови только getConnection.
```

```text
Проанализируй мой портфель: структура, риски, диверсификация и варианты действий.
```

Проверить:

- маскированный account ID;
- timestamp и quality;
- отсутствие write methods;
- наличие варианта «ничего не делать»;
- отсутствие Telegram/site/autonomous-trading поведения.

Затем пройти полную матрицу `gpt/PORTFOLIO_GPT_ACCEPTANCE_V1.md`.

## 9. Готовность

GPT готов, когда:

- используется канонический Instructions;
- personal policy заполнена либо явно включён limited diagnostic mode;
- Web Search, Data Analysis и Actions работают;
- Image generation и Apps выключены;
- Bearer auth работает;
- Actions совпадают с каталогом;
- Preview acceptance пройдена;
- GPT остаётся private;
- владелец нажал Update.

## 10. Главное правило

GitHub хранит конфигурацию и историю разработки, но не изменяет GPT Editor автоматически. Владелец вручную выполняет только защищённые и UI-действия; код, тесты, документацию и GitHub-проверки выполняет ChatGPT/агент.
