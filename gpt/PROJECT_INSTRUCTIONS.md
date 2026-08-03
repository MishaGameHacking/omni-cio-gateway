# Инструкции проекта ChatGPT — Omni-CIO

Скопировать этот текст в Project instructions, если для разработки Omni-CIO используется отдельный ChatGPT Project.

```text
Ты работаешь только над проектом Omni-CIO в Misha2304/omni-cio-gateway.

Единственный продукт:
Omni-CIO Custom GPT → Omni-CIO Gateway → T-Invest API.

Перед работой:
1. Прочитай AGENTS.md.
2. Прочитай README.md.
3. Прочитай knowledge/00_PROJECT_MASTER_CONTEXT.md.
4. Прочитай knowledge/16_CURRENT_PROGRAM_STATUS.md.
5. Прочитай docs/master-plan/README.md.
6. Пока v9 не завершён, обязательно прочитай docs/master-plan/OMNI_CIO_V9_PORTFOLIO_AUTOPILOT_PROGRAM.md.
7. Если задача касается GPT — прочитай gpt/SETUP_INDEX.md, gpt/CONFIGURATION.md, gpt/CUSTOM_GPT_INSTRUCTIONS_V8_6_1_COMPACT.txt и gpt/ACTIONS_CATALOG.md.
8. Прочитай профильные architecture/operations/domain files.
9. Проверь фактический main, open PR/issues и latest GitHub Actions.

Protected production baseline:
- applied GPT = Omni-CIO API | Управляющий и аналитик v8.6.1;
- entrypoint app:app;
- production read-only TINVEST_TOKEN остаётся read-only;
- Sandbox и Real execution изолированы;
- real execution использует отдельный TINVEST_TRADING_TOKEN + durable Upstash journal;
- реальные сделки только immutable proposal → exact owner confirmation в новом сообщении → submit once → broker reconciliation;
- no withdrawal/transfer;
- no margin/short в protected v8.6.1 path;
- ambiguous possible-submit никогда не retry;
- account IDs masked;
- secrets/private broker data не коммитить;
- REAL_TRADING_ENABLED=false остаётся master rollback.

Active roadmap:
docs/master-plan/OMNI_CIO_V9_PORTFOLIO_AUTOPILOT_PROGRAM.md

Пока его Definition of Done не закрыт:
- не начинать конкурирующий roadmap;
- не создавать второго бота, второй Gateway, отдельный дублирующий frontend или unrelated execution surface;
- выполнять work packages v9 по порядку, кроме blocking defect/security/dependency maintenance;
- сохранять v8.6.1 через feature flags, shadow mode, regression tests и rollback contracts;
- текущий applied GPT не переводить на v9 до WP15.

Engineering workflow:
- отдельная branch;
- один логический scope на PR;
- architecture/data contract перед сложным runtime change;
- deterministic tests/fake clients;
- exact-head Regression Shield;
- security checks;
- squash merge;
- production/Preview acceptance отдельно от CI.

GitHub является каноническим source/history, но не синхронизирует GPT Editor, Render secrets или Upstash автоматически.

Общайся по-русски ясно и точно. Не выдавай будущий v9 scope за уже реализованный. Не обещай доходность.
```
