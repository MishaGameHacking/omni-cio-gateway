# Подключение Omni-CIO v8.4 в ChatGPT → My GPTs

Дата проверки официальной документации OpenAI: 2026-08-01.

Этот runbook настраивает **существующий** Custom GPT как интерфейс к read-only Omni-CIO Gateway. Он не создаёт новый Gateway, не меняет T-Invest token и не включает торговлю.

Главная точка входа: `gpt/SETUP_INDEX.md`.

## 1. Что хранит GitHub

GitHub является резервной и канонической копией настройки:

- имя/описание/starters/capabilities — `CONFIGURATION.md`;
- Instructions — `INSTRUCTIONS_COMPACT.md`;
- Knowledge для загрузки — папка `gpt/knowledge/`;
- список 14 Actions — `ACTIONS_CATALOG.md`;
- Render/secrets boundary — `SECRETS_AND_RENDER.md`;
- этот пошаговый runbook.

GitHub **не хранит значения секретов**.

## 2. Предварительные условия

- ChatGPT-план и права, позволяющие редактировать GPT;
- редактирование выполняется через web-интерфейс ChatGPT;
- работающий production Gateway;
- доступ владельца к Render Environment;
- значение `GATEWAY_API_KEY` доступно владельцу только для ручного ввода в GPT Editor.

Текущий production Gateway:

`https://omni-cio-gateway.onrender.com`

Сначала проверить:

- `https://omni-cio-gateway.onrender.com/health`
- `https://omni-cio-gateway.onrender.com/openapi.json`

Ожидается:
- `status=ok`;
- `version=3.10.0`;
- `build.entrypoint=app:app`;
- `trading_methods=false`;
- в OpenAPI — ровно 14 GET операций из `ACTIONS_CATALOG.md`.

Предыдущий Blueprint service `omni-cio-gateway-au6d` не использовать для этого GPT.

## 3. Открыть существующий GPT

1. Открыть ChatGPT в браузере.
2. Перейти в GPTs → My GPTs.
3. Найти `Omni-CIO API | Управляющий и аналитик`.
4. Нажать Edit / значок карандаша.
5. Работать во вкладке Configure / Конфигурация.

Не создавать второй дубликат GPT, если существующий бот доступен.

## 4. Имя, описание и starters

Открыть `gpt/CONFIGURATION.md`.

Скопировать из него:
- Name;
- Description;
- четыре Conversation starters.

Рекомендуемое имя текущей конфигурации:

`Omni-CIO API | Управляющий и аналитик v8.4`

## 5. Instructions — что именно копировать

Открыть в GitHub:

`gpt/INSTRUCTIONS_COMPACT.md`

Нажать Raw или открыть содержимое файла и **скопировать весь текст целиком**.

В GPT Editor:
- удалить старый текст поля Instructions;
- вставить новый полностью;
- не смешивать v8.3 и v8.4;
- не вставлять токены или ключи.

`INSTRUCTIONS.md` не требуется копировать в GPT Editor — это расширенная разработческая версия.

## 6. Knowledge — какие файлы скачать

В GitHub открыть папку:

`gpt/knowledge/`

Скачать и загрузить в Knowledge **все 10 файлов**:

1. `02_GATEWAY_DATA_CONTRACT_V2_OPERATIONS.txt`
2. `04_CIO_PORTFOLIO_MANAGER.txt`
3. `05_ANALYST_NEWS_SIMPLE_LANGUAGE.txt`
4. `06_EVIDENCE_CREDIT_BANKRUPTCY.txt`
5. `07_PERSONAL_STRATEGY.txt`
6. `08_DECISION_JOURNAL_AND_QUALITY_CONTROL.txt`
7. `09_AUTONOMOUS_ACTION_ORCHESTRATOR.txt`
8. `10_DECISION_ENGINE_AND_CANDIDATE_COMPARISON.txt`
9. `11_RISK_DECOMPOSITION_AND_SIZING_GATES.txt`
10. `13_COMMUNICATION_STYLE_2026.txt`

Перед загрузкой удалить из GPT Knowledge предыдущие одноимённые версии, чтобы не было конфликтующих дублей.

Не загружать в production GPT Knowledge:
- master-plan PDF;
- исходный код Gateway;
- реальные брокерские отчёты как постоянную knowledge-базу;
- секреты;
- полный accountId.

## 7. Capabilities

Сверить с `CONFIGURATION.md`.

Текущая рабочая конфигурация:
- Web Search — ON;
- Code Interpreter / Data Analysis — ON;
- Image generation — ON в текущем UI, но для Gateway не обязательна;
- Apps — не использовать вместе с Actions;
- Actions — настроены на Omni-CIO Gateway.

## 8. Actions

В существующем Action открыть настройки.

### Authentication

Выбрать:
- Authentication: `API Key`;
- Type: `Bearer`.

В Secret/API key вставить **значение `GATEWAY_API_KEY` из Render service `omni-cio-gateway`**.

Не вставлять туда `TINVEST_TOKEN`.

### Schema

Импортировать из URL:

`https://omni-cio-gateway.onrender.com/openapi.json`

После импорта проверить:
- OpenAPI version читается без ошибок;
- backend info version = `3.10.0`;
- список Actions совпадает с `ACTIONS_CATALOG.md`;
- ровно 14 GET операций;
- write/execute/transfer/withdraw Actions отсутствуют.

OpenAI GPT Actions используют OpenAPI-схему и отдельно настроенную authentication; для server-to-server API key поддерживается Bearer.

## 9. Render и токены

Открыть Render → service `omni-cio-gateway` → Environment.

Должны существовать переменные:
- `GATEWAY_API_KEY`;
- `TINVEST_TOKEN`;
- `SSL_TBANK_VERIFY`.

Значения не копировать в GitHub.

Правильная цепочка:

Custom GPT
→ Bearer `GATEWAY_API_KEY`
→ `https://omni-cio-gateway.onrender.com`
→ `TINVEST_TOKEN`
→ T-Invest API

Подробнее: `SECRETS_AND_RENDER.md`.

## 10. Preview — обязательные проверки

Проверять по одному запросу.

### Test A — Gateway

`Проверь Gateway. Вызови только gatewayHealth. Другие методы не вызывай.`

Ожидание:
- status ok;
- version 3.10.0;
- app:app;
- trading_methods=false.

### Test B — Authentication

`Проверь подключение к T-Invest. Вызови только getConnection. Полный анализ не запускай.`

Ожидание:
- успешный ответ;
- счёт маскирован;
- никаких других Actions.

### Test C — Method isolation

`Вызови только getPortfolioSnapshot. Операции не вызывай. Рекомендаций не давай.`

Ожидание:
- вызван только snapshot;
- нет лишних рекомендаций.

### Test D — автономное управление

`УПРАВЛЯЙ ПОРТФЕЛЕМ — обнови данные и скажи, что делать.`

Ожидание:
- бот сам обращается к Gateway;
- не просит вручную «обновить доступ», пока Action не вернул реальную ошибку;
- сначала анализирует портфель и структурный пробел;
- сравнивает действие с бездействием;
- не выдаёт technical max lots за персонально рекомендуемое количество;
- при существенном решении формирует DecisionCard.

### Test E — закрытый рынок / нет ask

Если best ask отсутствует или рынок закрыт:
- last price не выдаётся за текущую цену покупки;
- точный план маркируется `WAIT_FOR_FRESH_MARKET` или как условный сценарий.

### Test F — final review

`503` без активного reviewed source допустим и не означает поломку.
`409` нельзя автоматически повторять с придуманной identity.
При `200` обязательны read-only признаки и `trading_methods=false`.

## 11. Сохранение

После успешного Preview:
1. Нажать Update.
2. Закрыть редактор.
3. Повторно открыть GPT.
4. Проверить, что Instructions, Knowledge и Action сохранились.
5. Выполнить `gatewayHealth` и `getConnection` ещё раз.

## 12. Обновление через GitHub в будущем

Если меняется только логика GPT:
1. изменения сначала в GitHub;
2. обновить `INSTRUCTIONS_COMPACT.md` и/или файлы `gpt/knowledge/`;
3. пройти PR/CI;
4. после merge скачать/скопировать изменённые файлы в GPT Editor;
5. пройти Preview;
6. нажать Update.

Если меняется Gateway/OpenAPI:
1. код → PR → CI → main;
2. Render deploy service `omni-cio-gateway`;
3. проверить `/health`;
4. заново импортировать `https://omni-cio-gateway.onrender.com/openapi.json`;
5. сверить `ACTIONS_CATALOG.md`;
6. Preview → Update.

## 13. Rollback

Если новая версия GPT ведёт себя хуже:
- в GitHub открыть предыдущий проверенный commit/tag;
- восстановить прошлый `INSTRUCTIONS_COMPACT.md`;
- скачать прошлые файлы из `gpt/knowledge/`;
- загрузить их в GPT;
- повторить health/auth/method-isolation tests.

Секреты при rollback не меняются без отдельной причины.

## 14. Официальные источники OpenAI

- Creating and editing GPTs: https://help.openai.com/en/articles/8554397
- Configuring actions in GPTs: https://help.openai.com/en/articles/9442513-gpt-actions-domain-settings-chatgpt-enterprise
- GPTs in ChatGPT: https://help.openai.com/en/articles/8554407-creating-a-gpt

Эти источники подтверждают разделение Instructions/Knowledge/Capabilities/Actions, необходимость OpenAPI schema для Actions, настройку authentication и тестирование GPT через Preview перед Update.
