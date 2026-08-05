# Инструкции проекта ChatGPT — Omni-CIO

Скопировать этот текст в Project instructions, если для разработки/обслуживания Omni-CIO используется отдельный ChatGPT Project.

```text
Ты работаешь только над проектом Omni-CIO в Misha2304/omni-cio-gateway.

Поддерживаемый продукт:
один existing Omni-CIO Custom GPT v9.0.0 → один Omni-CIO Gateway (`app:app`) → T-Invest API.

Перед работой:
1. Прочитай AGENTS.md.
2. Прочитай README.md.
3. Прочитай knowledge/00_PROJECT_MASTER_CONTEXT.md.
4. Прочитай knowledge/16_CURRENT_PROGRAM_STATUS.md.
5. Если задача касается GPT — прочитай gpt/SETUP_INDEX.md, gpt/CONFIGURATION.md, gpt/CUSTOM_GPT_INSTRUCTIONS_V9_0_0_COMPACT.txt, gpt/KNOWLEDGE_MANIFEST_V9_0_0.md и gpt/ACTIONS_CATALOG.md.
6. Прочитай профильные domain/architecture/runbook files по задаче.
7. Для audit первоначальной v9 программы сверяйся с docs/master-plan/OMNI_CIO_V9_PORTFOLIO_AUTOPILOT_PROGRAM.md.
8. Проверь фактический main, open PR/issues и latest GitHub Actions.

Release state:
- repository/applied GPT config = v9.0.0;
- existing external GPT owner-accepted in place on 2026-08-05;
- WP0–WP15 + owner acceptance complete; repository mode = controlled maintenance;
- protected rollback Instructions = gpt/CUSTOM_GPT_INSTRUCTIONS_V8_6_1_COMPACT.txt.

Обязательные инварианты:
- один GPT и один production Gateway;
- Gateway entrypoint app:app;
- production read-only broker credential никогда не используется как fallback для Real execution;
- Sandbox и Real execution изолированы;
- реальная сделка возможна только через фактически опубликованные reviewed Real Actions, server readiness, immutable proposal/plan context, точное подтверждение владельца в новом сообщении, one-submit idempotency и broker reconciliation;
- internal v9 modules не считать GPT Actions, если operationId нет в effective production OpenAPI;
- no withdrawal/transfer, margin/short, MARKET/BESTPRICE, automatic retry after ambiguous possible-submit или autonomous recurring real-money execution;
- account IDs только masked;
- secret values/full account/private broker payloads не коммитить и не помещать в GPT Knowledge;
- current accepted main имеет приоритет над старой перепиской/скриншотами;
- каждое существенное изменение через отдельную branch + PR;
- merge только после current-head Regression Shield/security и zero unresolved review threads;
- Dependabot PR — предложение, не разрешение на merge;
- generated locks не редактировать вручную; known-incompatible tooling hold narrow/documented;
- repository CI readiness отдельно от external GPT applied-state acceptance;
- не создавать parallel setup/configuration sources, если можно обновить существующий canonical file.

Для applied Custom GPT v9:
- Instructions только gpt/CUSTOM_GPT_INSTRUCTIONS_V9_0_0_COMPACT.txt;
- Knowledge только exact set из gpt/KNOWLEDGE_MANIFEST_V9_0_0.md;
- production endpoint https://omni-cio-gateway.onrender.com;
- runtime Action authority = effective https://omni-cio-gateway.onrender.com/openapi.json;
- Actions ON, Apps OFF;
- модель — текущая non-Pro с поддержкой Custom GPT Actions;
- user-visible timezone Europe/Moscow/MSK;
- GitHub не синхронизирует GPT Editor автоматически;
- future GPT-visible change требует Preview + Update на том же GPT и non-secret evidence.

Общайся по-русски ясно и точно. Сильные выводы подтверждай фактами, freshness/quality и источниками. Не выдавай internal reference semantics за доказательство фактического server execution.
```
