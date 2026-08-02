# Стартовый запрос для нового рабочего чата Omni-CIO

Использовать, когда нужно продолжить разработку/обслуживание проекта в новом чате после подключения GitHub.

```text
Подключись к GitHub-репозиторию Misha2304/omni-cio-gateway.

Сначала прочитай:
1. AGENTS.md
2. README.md
3. knowledge/00_PROJECT_MASTER_CONTEXT.md
4. knowledge/16_CURRENT_PROGRAM_STATUS.md
5. gpt/SETUP_INDEX.md
6. gpt/CONFIGURATION.md
7. gpt/CUSTOM_GPT_INSTRUCTIONS_V8_4_1.txt
8. gpt/ACTIONS_CATALOG.md
9. профильные domain/architecture files по текущей задаче
10. docs/master-plan/README.md только если задача касается roadmap/новой функциональности

Затем проверь:
- фактический main;
- открытые Pull Requests и Issues;
- latest Regression Shield;
- production contract, если задача затрагивает Render/Gateway/GPT.

Обязательные инварианты:
- один пользовательский продукт: Omni-CIO Custom GPT + read-only Gateway;
- trading_methods=false;
- user-facing Actions GET-only;
- Render entrypoint app:app;
- никаких broker write/withdraw/transfer methods;
- account IDs только masked;
- secrets не сохранять в GitHub;
- не считать старые чаты/скриншоты источником истины при расхождении с main;
- изменения делать через отдельную branch + PR;
- merge только после exact-head Regression Shield;
- после backend/GPT change выполнять соответствующую production/Preview acceptance.

Перед изменениями кратко покажи:
- current main SHA;
- текущий product/configuration release;
- open PR/issues, относящиеся к задаче;
- состояние CI;
- какие canonical files прочитаны;
- план изменения.

Не создавай новые параллельные setup/configuration документы, если информация относится к существующему gpt/SETUP_INDEX.md или другому canonical file.
```

Для задачи по настройке самого Custom GPT использовать `gpt/SETUP_INDEX.md` как главный источник.
