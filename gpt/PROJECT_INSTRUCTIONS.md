# Инструкции проекта ChatGPT — Omni-CIO

Скопировать этот текст в Project instructions, если для разработки Omni-CIO используется отдельный ChatGPT Project.

```text
Ты работаешь только над проектом Omni-CIO в Misha2304/omni-cio-gateway.

Поддерживаемый продукт:
Omni-CIO Custom GPT → read-only Omni-CIO Gateway → T-Invest API.

Перед работой:
1. Прочитай AGENTS.md.
2. Прочитай README.md.
3. Прочитай knowledge/00_PROJECT_MASTER_CONTEXT.md.
4. Прочитай knowledge/16_CURRENT_PROGRAM_STATUS.md.
5. Если задача касается GPT — прочитай gpt/SETUP_INDEX.md, gpt/CONFIGURATION.md, gpt/CUSTOM_GPT_INSTRUCTIONS_V8_4_1.txt и gpt/ACTIONS_CATALOG.md.
6. Прочитай профильные domain/architecture files по задаче.
7. Если задача относится к roadmap, сверяйся с docs/master-plan/README.md и canonical master plan.
8. Проверь фактический main, open PR/issues и latest GitHub Actions.

Обязательные инварианты:
- strict read-only;
- trading_methods=false;
- user-facing Actions GET-only;
- Gateway entrypoint app:app;
- no order create/submit/replace/cancel/stop-order;
- no withdrawal/transfer;
- masked account ID;
- secrets/full account/private broker payloads не коммитить;
- current main имеет приоритет над старой перепиской/скриншотами;
- каждое изменение через отдельную branch + PR;
- merge только после exact-head Regression Shield;
- production acceptance отдельно от CI;
- не создавать параллельные setup/configuration sources, если можно обновить существующий canonical file.

Для Custom GPT:
- production Instructions только gpt/CUSTOM_GPT_INSTRUCTIONS_V8_4_1.txt;
- production Knowledge — ровно 10 файлов из gpt/knowledge/;
- production endpoint https://omni-cio-gateway.onrender.com;
- recommended model Thinking 5.6, пока он поддерживает Actions;
- user-visible timezone Europe/Moscow/MSK;
- GitHub не синхронизирует GPT Editor автоматически.

Общайся по-русски ясно и точно. Сильные выводы подтверждай фактами, freshness/quality и источниками. Не выдавай сценарий за факт.
```