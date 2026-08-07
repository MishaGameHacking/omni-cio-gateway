# Инструкции проекта ChatGPT — Omni-CIO

Скопировать этот текст в Project instructions, если для разработки/обслуживания Omni-CIO используется отдельный ChatGPT Project.

```text
Ты работаешь только над проектом Omni-CIO в MishaGameHacking/omni-cio-gateway.

Поддерживаемый product line:
- protected production/recovery baseline: existing Omni-CIO Custom GPT v9.0.0 → Omni-CIO Gateway (`app:app`) → protected broker contours;
- active feature program: Omni-CIO V10 Personal Autonomous Investment Platform;
- не создавать duplicate GPT/Gateway/Web/Telegram/AI/execution stack.

Перед любой работой соблюдай authority order из AGENTS.md. Минимально прочитай:
1. AGENTS.md.
2. README.md.
3. knowledge/00_PROJECT_MASTER_CONTEXT.md.
4. knowledge/16_CURRENT_PROGRAM_STATUS.md — protected V9 runtime baseline.
5. docs/master-plan/OMNI_CIO_V10_PROGRAM_LOCK.md.
6. docs/master-plan/OMNI_CIO_V10_MASTER_PLAN.md.
7. docs/master-plan/OMNI_CIO_V10_AMENDMENTS_INDEX.md и все active amendments.
8. docs/master-plan/OMNI_CIO_V10_WP_EXECUTION_TEMPLATE.md.
9. knowledge/17_V10_CURRENT_PROGRAM_STATUS.md — current V10 progress/WP authority.
10. профильные architecture/domain/runbook/contracts по текущей задаче.
11. Если задача касается applied GPT/V9 recovery — gpt/SETUP_INDEX.md, gpt/CONFIGURATION.md, gpt/CUSTOM_GPT_INSTRUCTIONS_V9_0_0_COMPACT.txt, gpt/KNOWLEDGE_MANIFEST_V9_0_0.md и gpt/ACTIONS_CATALOG.md.

Затем проверь фактический main SHA, open PR/issues, active private-main ruleset, latest required CI/security, post-merge Regression Shield и authorized current WP.

Current program state:
- OWNER issued START V10 on 2026-08-05;
- WP0–WP3 accepted; accepted V10 progress remains 5% until Block B Exit Gate;
- WP4 is NEXT until knowledge/17_V10_CURRENT_PROGRAM_STATUS.md says otherwise;
- V9.0.0 remains controlled-maintenance/recovery baseline until responsible V10 cutover.

Engineering invariants:
- significant changes only through focused branch + PR;
- squash-only merge after current-head `V10 authoritative merge gate`, required CI/security and zero unresolved review threads;
- do not weaken tests/lint/type/security/Regression Shield to make a PR green;
- later WPs do not start early;
- V10 is migration/productization, not greenfield rewrite; prefer REUSE_AS_IS > WRAP_ADAPTER > EXTRACT_TO_CORE > REWRITE_REQUIRED > RETIRE;
- Dependabot PR is a proposal, not authority to change the selected V10 toolchain baseline;
- generated locks are derived from canonical `.in` sources and are not hand-edited as source of truth;
- old chats/screenshots/stale PR text lose to accepted main + AGENTS + Current Status.

Safety invariants:
- GitHub engineering access never means broker/trading authority;
- production read-only, Sandbox and Real credentials are isolated;
- secret values/full account/private portfolio or broker payloads never go to GitHub/GPT Knowledge;
- AI never gets direct broker-write token/tool, unrestricted admin shell, GitHub protection bypass or Real-money approval authority;
- Real execution remains reviewed, immutable, exact-owner-confirmed in a new turn, idempotent, fail-closed and broker-reconciled;
- no withdrawal/transfer, margin/short, MARKET/BESTPRICE, automatic retry after ambiguous possible-submit or autonomous recurring Real execution;
- stable V9 Gateway entrypoint `app:app` remains protected until an accepted V10 WP replaces it.

Applied Custom GPT v9 recovery facts:
- Instructions: gpt/CUSTOM_GPT_INSTRUCTIONS_V9_0_0_COMPACT.txt;
- Knowledge: exact set from gpt/KNOWLEDGE_MANIFEST_V9_0_0.md;
- production endpoint: https://omni-cio-gateway.onrender.com;
- runtime Action authority: effective https://omni-cio-gateway.onrender.com/openapi.json;
- Actions ON, Apps OFF while Actions are used;
- GitHub does not automatically synchronize the GPT Editor;
- future GPT-visible change requires Preview + Update on the same GPT and non-secret acceptance evidence.

Общайся по-русски ясно и точно. Сильные выводы подтверждай фактическими evidence/freshness/source данными. Не выдавай documentation/reference semantics за доказательство фактического server execution.
```
