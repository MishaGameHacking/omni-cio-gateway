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
8. docs/master-plan/OMNI_CIO_V10_AMENDMENTS_INDEX.md и все active amendments, especially Product User / Engineering Authority and Public Free Multi-User Hosted Runtime.
9. docs/architecture/V10_PUBLIC_FREE_MULTI_USER_HOSTED_RUNTIME_CONTRACT.json.
10. docs/master-plan/OMNI_CIO_V10_WP_EXECUTION_TEMPLATE.md.
11. knowledge/17_V10_CURRENT_PROGRAM_STATUS.md — единственный current V10 progress/current-next WP ledger.
12. профильные architecture/domain/runbook/contracts по текущей задаче.
13. Если задача касается applied GPT/V9 recovery — gpt/SETUP_INDEX.md и связанные V9 recovery files.

Затем проверь actual main SHA, open PR/issues, required exact-head CI/security, post-merge Regression Shield и authorized current WP.

Current product direction:
- final V10 target is a public modern multi-user Web service reachable from ordinary Internet-connected modern phone/desktop browsers;
- final public production must NOT depend on PROJECT OWNER home IP, Wi-Fi/router/LAN, home Internet/power or Lenovo;
- Lenovo remains engineering/self-hosted CI/controlled acceptance/recovery/rollback;
- final public Web/API/private-state runtime uses an approved managed-cloud production architecture selected by the owning WP22A service/security/recovery gate;
- PROJECT OWNER is not a special product role; when using Omni-CIO the OWNER is an ordinary USER on the same `OmniCIOUserAccount -> Tenant -> Session` path;
- Telegram Login and VK ID are normal product auth providers; GitHub/cloud-provider/Windows identities are engineering authority, not product auth;
- public multi-user is the approved target, but `PUBLIC_MULTI_USER_ENABLED=false` remains safe implementation default until required gates pass;
- initial public USER access is free: `BILLING_ENABLED=false`, `TRIAL_ENABLED=false`, `SUBSCRIPTION_ENFORCEMENT=false`, `PREMIUM_FEATURE_GATING=false`; monetization is `DEFERRED_OPTIONAL`;
- each USER owns only that tenant's BrokerConnection READ/optional TRADE credentials; no shared/global user broker token;
- raw credentials never return to browser storage and never enter GitHub/CI/artifacts;
- T-Invest public connector remains separate/fail-closed until broker terms/permission are accepted;
- `app:app`, `trading_methods=false`, `REAL_TRADING_ENABLED=false`, no transfer/withdrawal/margin/short and protected V9 rollback remain active.

Do not interpret public target as permission to expose unfinished production. Corrected WP22A + tenant isolation + sessions/abuse + secrets/recovery + privacy/personal-data + broker/legal/regulatory + capacity/incident gates must pass first.

Engineering invariants:
- significant changes only through focused branch + PR;
- establish root cause/blast radius for material defects before fixing;
- CI is independent verifier, not primary debugger;
- run cheap/focused preflight before expensive exact-head CI;
- inspect full diff before final CI and before merge;
- every applicable exact-head check must actually run and conclude success; failure/cancelled/queued/pending/neutral/skipped are not GREEN evidence;
- infrastructure/billing/provider failures are classified truthfully but applicable RED blocks merge;
- any new commit invalidates prior final GREEN evidence;
- squash-only merge after exact-head GREEN and zero unresolved blocking review threads;
- post-merge Regression Shield/owning audits must pass before status advancement/OWNER product acceptance where required;
- do not weaken tests/lint/type/security/Regression Shield to make a PR green;
- later WPs do not start early;
- V10 is migration/productization, not greenfield rewrite; prefer REUSE_AS_IS > WRAP_ADAPTER > EXTRACT_TO_CORE > REWRITE_REQUIRED > RETIRE;
- old chats/screenshots/stale PR text lose to accepted main + AGENTS + Current Status.

Current planning/implementation authority:
- Product USER / Engineering Authority + Public Free Multi-User Hosted Runtime planning correction is accepted through PR #329 merged to exact main `5f535c0ced9514866bd3680042f3ba0bb012f866`;
- post-merge Regression Shield #1503 / run `32129304332` completed SUCCESS with both required jobs GREEN;
- corrected WP22A is the only current functional package and must begin from the latest accepted main under `docs/architecture/V10_WP22A_EXECUTION_CONTRACT.md` and `docs/architecture/V10_WP22A_SERVICE_SELECTION.md`;
- current first phase is the service/hosting architecture decision; compare current managed-cloud candidates before selecting a production origin;
- planning acceptance does not authorize public activation, paid-provider purchase, privileged provider mutation, broker-write expansion or WP23 work;
- WP23+ stays locked.

Broker/money safety:
- protected V9 READ/Sandbox/Real contours remain isolated;
- public V10 broker credentials are tenant-scoped BrokerConnection secrets;
- optional Real execution is same-tenant verified READ/TRADE account intersection + durable state + immutable plan + short-lived authenticated USER confirmation + preflight + own cash/owned quantity + idempotency/reconciliation;
- AI never gets raw broker-write secret/tool or Real-money approval authority;
- no withdrawal/transfer, margin/short, automatic retry after ambiguous possible-submit or autonomous recurring Real execution.

Secrets/private data:
- no secret values/full account IDs/private portfolio payloads in GitHub/GPT Knowledge/CI/artifacts;
- hosted tenant-private state and encrypted broker credentials are allowed only in the approved cloud data/secret boundary after security/privacy/legal gates;
- cross-tenant secret/data access is forbidden.

OWNER participation:
- do everything possible through GitHub/code/CI/provider automation first;
- pre-merge OWNER action only for a genuinely non-delegable prerequisite;
- product acceptance only after implementation merge + required post-merge GREEN;
- use docs/operations/V10_OWNER_ACTION_HANDOFF_STANDARD.md for bounded OWNER handoffs.

Общайся по-русски ясно и точно. Сильные выводы подтверждай фактическими evidence/freshness/source данными. Не выдавай documentation/reference semantics за доказательство фактического server execution.
```