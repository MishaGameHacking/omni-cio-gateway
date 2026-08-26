# GitHub Copilot Instructions — Omni-CIO

Работай только над существующим продуктом Omni-CIO в `MishaGameHacking/omni-cio-gateway`. Не создавай параллельный проект, второй Web/Core/Gateway/Telegram/AI/execution stack.

Protected effective production/recovery baseline остаётся `existing Omni-CIO Custom GPT v9.0.0 -> Omni-CIO Gateway (app:app) -> T-Invest API` в **controlled maintenance**. V10 — единственная active feature program.

## Перед изменениями

Прочитай в таком порядке:

1. `AGENTS.md`;
2. `README.md`;
3. `docs/DOCUMENTATION_AUTHORITY_AND_LIFECYCLE.md`;
4. `knowledge/00_PROJECT_MASTER_CONTEXT.md`;
5. `knowledge/16_CURRENT_PROGRAM_STATUS.md` — protected V9 runtime baseline;
6. `docs/master-plan/OMNI_CIO_V10_PROGRAM_LOCK.md`;
7. `docs/master-plan/OMNI_CIO_V10_MASTER_PLAN.md`;
8. `docs/master-plan/OMNI_CIO_V10_AMENDMENTS_INDEX.md` и все active amendments, especially Product User / Engineering Authority, Public Free Multi-User Hosted Runtime, WP22A Technical Closeout / Public Activation Separation and **Integrated System Update Execution Law**;
9. `docs/architecture/V10_INTEGRATED_SYSTEM_UPDATE_EXECUTION_CONTRACT.json`;
10. `docs/architecture/V10_PUBLIC_FREE_MULTI_USER_HOSTED_RUNTIME_CONTRACT.json`;
11. `docs/master-plan/OMNI_CIO_V10_WP_EXECUTION_TEMPLATE.md`;
12. `knowledge/17_V10_CURRENT_PROGRAM_STATUS.md`;
13. relevant security/threat/recovery/current execution-unit architecture/runbook/ledger;
14. actual `main`, open PR/issues and latest required GitHub Actions.

Current progress/current execution authority is determined only by `knowledge/17_V10_CURRENT_PROGRAM_STATUS.md` from accepted `main`. Old chat/screenshot/closed-unmerged PR/historical WP wording never overrides accepted authority.

## Current program state

WP0–WP22A are accepted COMPLETE and accepted V10 progress remains 54%.

Amendment 12 prepares `WEB-VISUAL-INTEGRATED` with ordered member milestones `WEB-VISUAL-A -> B -> C -> D -> E -> F -> G`, but **PRODUCT IMPLEMENTATION PAUSED** remains the post-Amendment-12 state until the exact OWNER command:

`START V10 WEB VISUAL SYSTEM UPDATE`

Do not create the integrated visual implementation branch or modify `apps/web` for the refresh before that command is explicitly recorded after Amendment 12 acceptance. WP23+ remains locked.

## Current product direction

Final V10 target is a **public modern multi-user Web product** available from ordinary Internet-connected modern phone/desktop browsers after its launch gates pass.

Required final topology:

`Internet -> public HTTPS/edge -> approved managed-cloud Omni-CIO Web/API -> Telegram/VK product auth -> OmniCIOUserAccount -> Tenant -> tenant-scoped state`

Binding rules:

- PROJECT OWNER is not a special product role; when using Omni-CIO the OWNER is an ordinary USER;
- GitHub/cloud-provider/Windows/CI authority is engineering authority, not product login;
- final public production must not depend on OWNER home public IP, Wi-Fi/router/LAN, home Internet/power or Lenovo;
- Lenovo remains engineering/self-hosted CI/controlled acceptance/recovery/rollback;
- final public runtime/provider remains Cloud.ru Evolution under its separate owning activation gate; do not silently purchase/apply/mutate a provider;
- public multi-user is the approved target, but `PUBLIC_MULTI_USER_ENABLED=false` remains implementation default until required gates pass;
- initial registered-user access is free: billing, trial, subscription enforcement and premium gating are disabled; future monetization is `DEFERRED_OPTIONAL`;
- each USER owns only that tenant's broker `BrokerConnection` READ/optional TRADE credentials; no shared/global USER broker secret;
- raw credentials never return to browser storage and never enter GitHub/CI/artifacts;
- T-Invest public connector remains separately fail-closed until broker terms/permission are accepted;
- `trading_methods=false`, `REAL_TRADING_ENABLED=false`, no transfer/withdrawal/margin/leverage/uncovered-short and protected V9 rollback remain active.

Do **not** interpret public target, an Integrated System Update, a GitHub merge or visual-refresh wording as permission to expose unfinished production.

## V10 execution-unit rule

Every material change uses exactly one execution unit:

- `FOCUSED_CHANGE` for an isolated defect/governance/maintenance/split item;
- `INTEGRATED_SYSTEM_UPDATE` for one coherent OWNER-authorized subsystem outcome with ordered member milestones.

For `INTEGRATED_SYSTEM_UPDATE`:

- one integrated branch + one final PR by default;
- member WP/increments stay sequential and branch-local;
- internal milestone PASS does not advance accepted progress or unlock another major update;
- use `docs/updates/INTEGRATED_SYSTEM_UPDATE_EXECUTION_LEDGER_TEMPLATE.md` and the System Update issue template;
- do not publish for external verification before `INTEGRATION_READY`;
- evaluate mandatory split triggers: migration ordering, security/authority transition, dependency/toolchain boundary, OWNER/provider action, live/temporal evidence, production cutover, Real-money authority, reviewability limit.

## HEAD FREEZE / batch correction

After a verification SHA is published, **HEAD FREEZE** applies while safe independent applicable checks reach terminal state. Do not push one fix per first failing symptom.

Collect all available findings, group them by root cause/defect class, establish blast radius, search analogous patterns, inspect coupled consumers/producers and adjacent failure modes, add permanent regression guards, then publish one coherent correction batch after local/focused preflight.

Safety abort overrides diagnostic completeness if continued execution could expose secrets/private data, reach broker/Real authority, mutate destructive migration/provider state, create uncontrolled spend or cross-tenant exposure.

A new commit invalidates prior final exact-head GREEN evidence. `continue-on-error` must not make a required RED look GREEN.

## Pre-CI Engineering Gate

CI is an independent verifier, not primary debugger.

Before expensive exact-head CI:

1. establish root cause and blast radius where applicable;
2. inspect complete diff and coupled surfaces;
3. search analogous repository patterns;
4. inspect adjacent failure modes;
5. add permanent regression guard for reusable failures;
6. run cheap/focused format/lint/type/schema/tests/security/IaC/PowerShell checks;
7. review official current external docs when behavior/support/pricing/terms can change;
8. re-review full diff;
9. for integrated work require `INTEGRATION_READY` before publication.

**All applicable exact-head checks must be SUCCESS.** Every applicable check must actually execute and conclude `success`. `failure`, `cancelled`, `queued`, `pending`, `in_progress`, `timed_out`, `action_required`, `stale`, `neutral` and `skipped` are not GREEN evidence for an applicable gate.

Infrastructure/billing/provider failures must be classified truthfully and still block merge when the applicable check is RED.

Normal closure: exact-head all-GREEN -> final diff/review -> zero unresolved blockers -> squash merge -> exact new main -> required post-merge Regression Shield.

**OWNER product acceptance only after merge** and required post-merge GREEN, unless a genuinely non-delegable prerequisite is required earlier.

Unexpected material RED after declared preflight readiness requires a confidence postmortem and reusable entry in the **Failure Learning Ledger** at `docs/operations/V10_ENGINEERING_FAILURE_LEARNING_LEDGER.md`.

## Fault isolation

Build bounded failure domains. Optional AI/Research/Telegram/edge failures should not unnecessarily take down deterministic Core where safe degradation is possible. Money/security/identity/secret/broker authority always fails closed.

For public hosting, cloud/edge/provider outage must be distinguishable from application outage and broker/provider degradation. Recovery must not depend on OWNER home access.

## Repository architecture

Canonical structure: `docs/architecture/REPOSITORY_STRUCTURE.md`.

- deterministic Core: `omni_cio/`;
- accepted API/Web: `apps/api/`, `apps/web/`;
- engineering/deployment infrastructure: `infrastructure/`;
- `apps/telegram/` and `ai/` remain lifecycle-gated until owning WPs;
- current GPT recovery source: `gpt/` until parity/decommission gate;
- no competing top-level frontend/backend/server/v10 duplicate stack.

Permanent guards include:

- `python scripts/check_v10_repository_boundaries.py`;
- `python scripts/check_v10_engineering_governance.py`;
- `python scripts/check_v10_integrated_system_update_governance.py`;
- `python scripts/check_v10_documentation_consistency.py`;
- `python scripts/check_v10_public_product_plan.py`.

Do not weaken guards to land a change.

## Broker / money authority

Protected V9 contours remain isolated. For public V10, USER broker credentials are tenant-scoped rather than application-global.

Optional Real execution remains later-gated and requires same-tenant verified READ/TRADE account intersection, durable state, immutable plan, short-lived authenticated USER approval for that USER's own tenant, fresh preflight, own cash/owned quantity, idempotency and reconciliation.

Never grant transfer/withdrawal, margin/leverage/uncovered-short, hidden autonomous recurring Real execution, automatic retry after possible-submit ambiguity or AI direct broker-write authority.

`REAL_TRADING_ENABLED=false` remains the master Real rollback until accepted activation. `trading_methods=false` remains protected. Amendment 12 does not change either value.

## Secrets/private data

Never commit/log/artifact real broker/provider/Telegram/VK secrets, encryption/recovery keys, Authorization headers, full account IDs or private portfolio/database payloads.

Hosted tenant-private state and encrypted broker credentials may exist only inside the approved cloud data/secret boundary after security/privacy/legal gates. Cross-tenant access is forbidden.

## OWNER handoff

Do everything possible through GitHub/code/CI/provider automation first. Ask OWNER only for genuinely non-delegable account/consent/secret/UAC/admin/physical/legal/budget decisions or an exact program START decision.

Use `docs/operations/V10_OWNER_ACTION_HANDOFF_STANDARD.md`: verified official target when applicable, exact scope, one bounded action, expected result, STOP/do-not-do conditions, cost/authority consequence and minimum non-secret return.
