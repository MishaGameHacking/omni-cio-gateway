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
3. docs/DOCUMENTATION_AUTHORITY_AND_LIFECYCLE.md.
4. knowledge/00_PROJECT_MASTER_CONTEXT.md.
5. knowledge/16_CURRENT_PROGRAM_STATUS.md — protected V9 runtime baseline.
6. docs/master-plan/OMNI_CIO_V10_PROGRAM_LOCK.md.
7. docs/master-plan/OMNI_CIO_V10_MASTER_PLAN.md.
8. docs/master-plan/OMNI_CIO_V10_AMENDMENTS_INDEX.md и все active amendments.
9. docs/master-plan/OMNI_CIO_V10_WP_EXECUTION_TEMPLATE.md.
10. knowledge/17_V10_CURRENT_PROGRAM_STATUS.md — единственный current V10 progress/current-next WP ledger.
11. профильные architecture/domain/runbook/contracts по текущей задаче.
12. Если задача касается applied GPT/V9 recovery — gpt/SETUP_INDEX.md, gpt/CONFIGURATION.md, gpt/CUSTOM_GPT_INSTRUCTIONS_V9_0_0_COMPACT.txt, gpt/KNOWLEDGE_MANIFEST_V9_0_0.md и gpt/ACTIONS_CATALOG.md.

Затем проверь фактический main SHA, open PR/issues, active private-main ruleset, latest required CI/security, post-merge Regression Shield и authorized current WP.

Current program state:
- OWNER issued START V10 on 2026-08-05;
- exact accepted V10 progress/current-next WP is NOT hard-coded here and must be read only from knowledge/17_V10_CURRENT_PROGRAM_STATUS.md on accepted main;
- package-local historical PENDING/CURRENT/NEXT wording is not current authority;
- Engineering Quality / Pre-CI / Green-Merge governance is accepted and active;
- V9.0.0 remains controlled-maintenance/recovery baseline until responsible V10 cutover.

Engineering invariants:
- significant changes only through focused branch + PR;
- establish root cause and blast radius for material defects before fixing;
- use CI as independent verifier, not primary debugger;
- run applicable cheap/focused preflight before expensive exact-head CI;
- inspect the full diff before final CI and again before merge;
- every applicable exact-head check must actually run and conclude success; failure/cancelled/pending/neutral/skipped are not GREEN evidence for an applicable gate;
- infrastructure/billing/provider failures are classified truthfully but a red applicable gate still blocks merge;
- any new commit invalidates prior final GREEN evidence;
- squash-only merge after exact-head GREEN, required security evidence and zero unresolved blocking review threads;
- post-merge Regression Shield/owning audits must pass before status advancement/OWNER product acceptance where required;
- do not weaken tests/lint/type/security/Regression Shield to make a PR green;
- later WPs do not start early;
- V10 is migration/productization, not greenfield rewrite; prefer REUSE_AS_IS > WRAP_ADAPTER > EXTRACT_TO_CORE > REWRITE_REQUIRED > RETIRE;
- Dependabot PR is a proposal, not authority to change the selected V10 toolchain baseline;
- generated locks are derived from canonical sources and are not hand-edited as source of truth;
- old chats/screenshots/stale PR text lose to accepted main + AGENTS + Current Status;
- current documentation is guarded by scripts/check_v10_documentation_consistency.py; historical evidence is preserved under docs/DOCUMENTATION_AUTHORITY_AND_LIFECYCLE.md.

Safety invariants:
- GitHub engineering access never means broker/trading authority;
- production read-only, Sandbox and Real credentials are isolated;
- secret values/full account/private portfolio or broker payloads never go to GitHub/GPT Knowledge;
- AI never gets direct broker-write token/tool, unrestricted admin shell, GitHub protection bypass or Real-money approval authority;
- Real execution remains reviewed, immutable, exact-owner-confirmed in a new turn, idempotent, fail-closed and broker-reconciled;
- no withdrawal/transfer, margin/short, MARKET/BESTPRICE, automatic retry after ambiguous possible-submit or autonomous recurring Real execution;
- stable V9 Gateway entrypoint `app:app` remains protected until an accepted V10 WP replaces it;
- `trading_methods=false` and `REAL_TRADING_ENABLED=false` remain protected current safety state unless an owning future accepted gate explicitly changes authority.

Repository/runtime ownership:
- one deterministic Core under omni_cio/;
- accepted V10 API/Web roots are apps/api/ and apps/web/;
- accepted Personal-Node infrastructure is under infrastructure/;
- later apps/telegram/ and ai/ remain lifecycle-gated until their owning WPs are authorized;
- V10 Web/API/private state stays on the approved Lenovo/replacement Personal Node unless a later OWNER-approved architecture amendment changes it;
- an external-access provider is access/security transport, not a second private-state app host;
- existing Render app:app remains protected V9 production/recovery only until its owning cutover.

Applied Custom GPT v9 recovery facts:
- Instructions: gpt/CUSTOM_GPT_INSTRUCTIONS_V9_0_0_COMPACT.txt;
- Knowledge: exact set from gpt/KNOWLEDGE_MANIFEST_V9_0_0.md;
- production endpoint: https://omni-cio-gateway.onrender.com;
- runtime Action authority: effective https://omni-cio-gateway.onrender.com/openapi.json;
- Actions ON, Apps OFF while Actions are used;
- GitHub does not automatically synchronize the GPT Editor;
- future GPT-visible change requires Preview + Update on the same GPT and non-secret acceptance evidence.

OWNER participation:
- do everything possible through GitHub/code/CI/provider automation first;
- pre-merge OWNER action only for a genuinely non-delegable prerequisite;
- product acceptance only after implementation merge + required post-merge GREEN;
- OWNER handoff must use docs/operations/V10_OWNER_ACTION_HANDOFF_STANDARD.md and request one bounded action with exact target/result/STOP conditions and no raw secret return.

Общайся по-русски ясно и точно. Сильные выводы подтверждай фактическими evidence/freshness/source данными. Не выдавай documentation/reference semantics за доказательство фактического server execution.
```
