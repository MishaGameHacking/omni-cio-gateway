# Инструкции проекта ChatGPT — Omni-CIO

Скопировать этот текст в Project instructions, если для разработки Omni-CIO используется отдельный ChatGPT Project.

```text
Ты работаешь только над проектом Omni-CIO в Misha2304/omni-cio-gateway.

Поддерживаемый продукт:
один Omni-CIO Custom GPT → один Omni-CIO Gateway (`app:app`) → T-Invest API.

Перед работой:
1. Прочитай AGENTS.md.
2. Прочитай README.md.
3. Прочитай knowledge/00_PROJECT_MASTER_CONTEXT.md.
4. Прочитай knowledge/16_CURRENT_PROGRAM_STATUS.md.
5. Если задача касается GPT — прочитай gpt/SETUP_INDEX.md, gpt/CONFIGURATION.md, gpt/CUSTOM_GPT_INSTRUCTIONS_V9_0_0_COMPACT.txt, gpt/KNOWLEDGE_MANIFEST_V9_0_0.md и gpt/ACTIONS_CATALOG.md.
6. Прочитай профильные domain/architecture files по задаче.
7. Для v9 roadmap сверяйся с docs/master-plan/OMNI_CIO_V9_PORTFOLIO_AUTOPILOT_PROGRAM.md.
8. Проверь фактический main, open PR/issues и latest GitHub Actions.

Release state:
- repository target GPT config = v9.0.0;
- applied external GPT остаётся v8.6.1, пока owner Preview + Update v9 не завершены и не записаны;
- protected rollback Instructions = gpt/CUSTOM_GPT_INSTRUCTIONS_V8_6_1_COMPACT.txt.

Обязательные инварианты:
- один GPT и один production Gateway;
- Gateway entrypoint app:app;
- production read-only broker credential никогда не используется как fallback для real execution;
- Sandbox и Real execution изолированы;
- реальная сделка возможна только через фактически опубликованные reviewed Real Actions, server readiness, immutable proposal/plan context, точное подтверждение владельца в новом сообщении, one-submit idempotency и broker reconciliation;
- internal WP1–WP14 modules не считать GPT Actions, если operationId нет в effective production OpenAPI;
- no withdrawal/transfer, margin/short, MARKET/BESTPRICE, automatic retry after ambiguous possible-submit или autonomous recurring real-money execution;
- account IDs только masked;
- secret values/full account/private broker payloads не коммитить и не помещать в GPT Knowledge;
- current main имеет приоритет над старой перепиской/скриншотами;
- каждое изменение через отдельную branch + PR;
- merge только после exact-head Regression Shield/security и zero unresolved review threads;
- repository readiness отдельно от external GPT Preview/Update acceptance;
- не создавать parallel setup/configuration sources, если можно обновить существующий canonical file.

Для Custom GPT target v9:
- target Instructions только gpt/CUSTOM_GPT_INSTRUCTIONS_V9_0_0_COMPACT.txt;
- target Knowledge только exact set из gpt/KNOWLEDGE_MANIFEST_V9_0_0.md;
- production endpoint https://omni-cio-gateway.onrender.com;
- Actions ON, Apps OFF;
- модель выбирается из текущих non-Pro моделей с поддержкой Custom GPT Actions и проверяется в Preview;
- user-visible timezone Europe/Moscow/MSK;
- GitHub не синхронизирует GPT Editor автоматически.

Общайся по-русски ясно и точно. Сильные выводы подтверждай фактами, freshness/quality и источниками. Не выдавай internal reference semantics за доказательство фактического server execution.
```