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
7. gpt/CUSTOM_GPT_INSTRUCTIONS_V9_0_0_COMPACT.txt
8. gpt/KNOWLEDGE_MANIFEST_V9_0_0.md
9. gpt/ACTIONS_CATALOG.md
10. docs/architecture/SYSTEM_OVERVIEW.md
11. docs/architecture/REPOSITORY_STRUCTURE.md
12. профильные domain/architecture/runbook files по текущей задаче
13. docs/master-plan/OMNI_CIO_V9_PORTFOLIO_AUTOPILOT_PROGRAM.md, если нужен audit исходных v9 requirements или планируется новая owner-approved программа

Затем проверь:
- фактический main SHA;
- открытые Pull Requests и Issues;
- latest exact-head Regression Shield/security;
- knowledge/16_CURRENT_PROGRAM_STATUS.md;
- production contract, если задача затрагивает Render/Gateway/GPT.

Release state различай строго:
- repository/applied GPT config = v9.0.0;
- existing external GPT owner-accepted in place on 2026-08-05;
- WP0–WP15 and owner acceptance complete; current mode = controlled maintenance;
- protected rollback Instructions = gpt/CUSTOM_GPT_INSTRUCTIONS_V8_6_1_COMPACT.txt.

Обязательные инварианты:
- один пользовательский продукт: один existing Omni-CIO Custom GPT + один Gateway `app:app`;
- read-only broker credential, Sandbox и Real execution изолированы;
- internal v9 engine не является GPT Action без operationId в effective production OpenAPI;
- Real execution только через reviewed server lifecycle: readiness → immutable proposal/plan context → exact owner confirmation новым сообщением → one idempotent submit → broker reconciliation;
- no withdrawal/transfer, margin/short, MARKET/BESTPRICE, automatic retry after ambiguous possible-submit или autonomous recurring real-money execution;
- account IDs только masked;
- secret values/private broker payloads не сохранять в GitHub или GPT Knowledge;
- не считать старые чаты/скриншоты источником истины при расхождении с accepted main + explicit owner evidence;
- изменения делать через отдельную branch + PR;
- merge только после current-head Regression Shield/security и zero unresolved review threads;
- dependency/Dependabot PR не сливать только потому, что версия новее;
- locks generated from `.in` sources; known-incompatible tooling held narrowly rather than weakening CI;
- repository merge и applied external GPT acceptance — разные состояния;
- после future GPT config/Action change выполнять owner Preview/Update acceptance на существующем GPT, не создавать новый;
- не создавать parallel setup/configuration документы вместо обновления canonical sources.

Перед изменениями кратко зафиксируй:
- current main SHA;
- applied/rollback GPT state;
- open PR/issues по задаче;
- состояние CI;
- какие canonical files прочитаны;
- точный maintenance/dependency/security defect или owner-approved scope.
```

Для настройки самого Custom GPT использовать `gpt/SETUP_INDEX.md` как главный источник.
