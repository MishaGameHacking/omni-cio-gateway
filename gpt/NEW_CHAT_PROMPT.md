# Стартовый запрос для нового чата разработки

Скопируйте этот текст в новый чат после подключения GitHub.

```text
Подключись к приватному GitHub-репозиторию Misha2304/omni-cio-gateway.

Цель проекта: довести существующий Custom GPT Omni-CIO до стабильного персонального read-only помощника по моему портфелю T-Invest.

Сначала прочитай:
1. AGENTS.md
2. docs/master-plan/OMNI_CIO_PORTFOLIO_GPT_RESET_V1.md
3. README.md
4. docs/README.md
5. knowledge/00_PROJECT_MASTER_CONTEXT.md
6. knowledge/16_CURRENT_PROGRAM_STATUS.md
7. gpt/README.md
8. gpt/CONFIGURATION.md
9. gpt/INSTRUCTIONS_COMPACT.md
10. gpt/INSTRUCTIONS.md
11. gpt/ACTIONS_CATALOG.md
12. gpt/PORTFOLIO_GPT_ACCEPTANCE_V1.md
13. gpt/PERSONAL_PORTFOLIO_POLICY_TEMPLATE.md

Затем проверь:
- current main и его SHA;
- открытые PR и Issues;
- Regression Shield и artifacts;
- review threads;
- фактические 14 GET Actions;
- stable app:app;
- trading_methods=false;
- текущие Instructions, Knowledge и GPT Editor state, если доступны.

Жёсткий scope:
- только существующий Custom GPT внутри ChatGPT;
- анализ моего реального портфеля;
- новости, рейтинги, риски и диверсификация;
- поиск активов для свободных денег;
- hold/wait/reduce/sell/increase/buy/do-nothing рекомендации;
- read-only расчёты;
- работа только по моим командам.

Не создавать и не развивать:
- сайт, web-кабинет, приложение или frontend;
- Telegram и publishing;
- собственную AI-модель;
- публичный сервис;
- автономную торговлю;
- broker write methods.

Безопасность:
- не хранить и не просить секреты;
- не раскрывать полный account ID;
- не создавать/менять/отменять заявки;
- не выдавать stale/partial данные за надёжную рекомендацию;
- не обещать доходность;
- работать через отдельную ветку и PR;
- не merge без exact-head green CI.

После проверки:
1. покажи фактическое текущее состояние;
2. выбери один следующий логический пакет;
3. создай ветку и draft PR;
4. внеси код/документы/тесты;
5. доведи CI до green;
6. подготовь только одно необходимое owner-only действие для GPT Editor.

Не предлагай новый сайт или новую архитектуру вокруг GPT. Сначала доведи end-to-end работу существующего GPT.
```
