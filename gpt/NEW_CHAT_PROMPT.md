# Стартовый запрос для нового рабочего чата Omni-CIO

Использовать, когда нужно продолжить разработку/обслуживание проекта после подключения GitHub.

```text
Подключись к GitHub-репозиторию Misha2304/omni-cio-gateway.

Сначала прочитай:
1. AGENTS.md
2. README.md
3. knowledge/00_PROJECT_MASTER_CONTEXT.md
4. knowledge/16_CURRENT_PROGRAM_STATUS.md
5. docs/master-plan/README.md
6. docs/master-plan/OMNI_CIO_V9_PORTFOLIO_AUTOPILOT_PROGRAM.md
7. gpt/SETUP_INDEX.md
8. gpt/CONFIGURATION.md
9. gpt/CUSTOM_GPT_INSTRUCTIONS_V8_6_1_COMPACT.txt
10. gpt/ACTIONS_CATALOG.md
11. профильные architecture/operations/domain files текущего work package

Затем проверь:
- фактический main SHA;
- EPIC v9 и текущий work package;
- открытые Pull Requests и Issues;
- latest exact-head Regression Shield;
- production contract, если задача затрагивает Render/Gateway/GPT.

Current protected baseline:
- Omni-CIO API | Управляющий и аналитик v8.6.1;
- real BUY/SELL v1 owner-accepted and release-complete;
- single Custom GPT + single Gateway;
- read-only, Sandbox и Real execution изолированы;
- real writes используют только отдельный TINVEST_TRADING_TOKEN + durable journal;
- proposal и real submit разделены новым exact owner confirmation;
- ambiguous submit никогда не retry;
- no withdrawal/transfer, no margin/short в protected v8.6.1 path;
- account IDs masked;
- secrets не сохранять в GitHub;
- REAL_TRADING_ENABLED=false = master rollback.

Active program lock:
docs/master-plan/OMNI_CIO_V9_PORTFOLIO_AUTOPILOT_PROGRAM.md

До закрытия v9 Definition of Done не начинай другой roadmap, второй бот, второй Gateway, дублирующий frontend или unrelated execution surface. Работай по v9 work packages; исключения — blocking defect, security/dependency maintenance и сохранение стабильного v8.6.1.

Development discipline:
- отдельная branch + PR;
- один логический scope;
- feature-flag/shadow-first для новых v9 engines;
- deterministic tests и fake clients;
- не ослаблять существующие safety gates;
- merge только после exact-head Regression Shield;
- production/Preview acceptance отдельно от CI;
- applied GPT остаётся v8.6.1 до WP15.

Перед изменениями кратко зафиксируй current main, текущий work package, CI и canonical files. Затем работай автономно и не проси владельца о действиях, которые можно выполнить через GitHub/код самостоятельно.
```

Для настройки самого Custom GPT главным recovery source остаётся `gpt/SETUP_INDEX.md`.
