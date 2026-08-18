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
8. `docs/master-plan/OMNI_CIO_V10_AMENDMENTS_INDEX.md` и все active amendments, especially Product User / Engineering Authority and Public Free Multi-User Hosted Runtime;
9. `docs/architecture/V10_PUBLIC_FREE_MULTI_USER_HOSTED_RUNTIME_CONTRACT.json`;
10. `knowledge/17_V10_CURRENT_PROGRAM_STATUS.md`;
11. relevant security/threat/recovery/current-WP architecture/runbook;
12. actual `main`, open PR/issues and latest required GitHub Actions.

Current progress/current WP is determined only by `knowledge/17_V10_CURRENT_PROGRAM_STATUS.md` from accepted `main`. Old chat/screenshot/closed-unmerged PR/historical WP wording never overrides accepted authority.

## Current product direction

Final V10 target is a **public modern multi-user Web product** available from ordinary Internet-connected modern phone/desktop browsers after the corrected WP22A and launch gates pass.

Required final topology:

`Internet -> public HTTPS/edge -> approved managed-cloud Omni-CIO Web/API -> Telegram/VK product auth -> OmniCIOUserAccount -> Tenant -> tenant-scoped state`

Binding rules:

- PROJECT OWNER is not a special product role; when using Omni-CIO the OWNER is an ordinary USER;
- GitHub/cloud-provider/Windows/CI authority is engineering authority, not product login;
- final public production must not depend on OWNER home public IP, Wi-Fi/router/LAN, home Internet/power or Lenovo;
- Lenovo remains engineering/self-hosted CI/controlled acceptance/recovery/rollback;
- final public runtime/provider must be selected through the owning managed-cloud service/security/recovery gate; do not silently purchase or select a provider;
- public multi-user is the approved target, but `PUBLIC_MULTI_USER_ENABLED=false` remains implementation default until required gates pass;
- initial registered-user access is free: billing, trial, subscription enforcement and premium gating are disabled; future monetization is `DEFERRED_OPTIONAL`;
- each USER owns only that tenant's broker `BrokerConnection` READ/optional TRADE credentials; no shared/global USER broker secret;
- raw credentials never return to browser storage and never enter GitHub/CI/artifacts;
- T-Invest public connector remains separately fail-closed until broker terms/permission are accepted;
- `trading_methods=false`, `REAL_TRADING_ENABLED=false`, no transfer/withdrawal/margin/short and protected V9 rollback remain active.

Do **not** interpret “public target” as permission to expose an unfinished service. Public deployment is accepted only after the corrected WP22A plus tenant isolation, session/abuse, secrets, backup/recovery, privacy/personal-data, broker/legal/regulatory, capacity and incident/rollback gates.

## V10 sequence rule

Do exactly one current Work Package/defect at a time:

`restore authority -> current WP/defect -> focused branch -> root-cause/blast-radius review -> implementation/tests -> cheap preflight -> full diff -> exact-head applicable gates all SUCCESS -> zero blockers -> squash merge -> exact-main post-merge verification -> OWNER product acceptance only if required -> status -> next WP`.

Do not start later WPs early. Do not start V11. Do not implement Telegram/AI/Real execution/billing early merely because they are mentioned in the target architecture.

The Product USER / Engineering Authority + Public Free Multi-User Hosted Runtime planning correction is **accepted** through PR #329 merged to exact main `5f535c0ced9514866bd3680042f3ba0bb012f866` with post-merge Regression Shield #1503 / run `32129304332` SUCCESS. Corrected WP22A is therefore the current functional package; begin only from the latest accepted main and follow `V10_WP22A_EXECUTION_CONTRACT.md` + `V10_WP22A_SERVICE_SELECTION.md`. This acceptance does not authorize public activation, paid-provider purchase, privileged provider mutation, broker-write expansion or WP23 work.

## Pre-CI Engineering Gate

CI is an independent verifier, not primary debugger.

Before expensive exact-head CI:

1. establish root cause and blast radius;
2. inspect complete diff and coupled surfaces;
3. search analogous repository patterns;
4. inspect adjacent failure modes;
5. add permanent regression guard for reusable failures;
6. run cheap/focused format/lint/type/schema/tests/security/IaC/PowerShell checks;
7. review official current external docs when behavior/support/pricing/terms can change;
8. re-review full diff.

**All applicable exact-head checks must be SUCCESS.** Every applicable check must actually execute and conclude `success`. `failure`, `cancelled`, `queued`, `pending`, `in_progress`, `timed_out`, `action_required`, `stale`, `neutral` and `skipped` are not GREEN evidence for an applicable gate.

Infrastructure/billing/provider failures must be classified truthfully and still block merge when the applicable check is RED. Any new commit invalidates prior final GREEN evidence.

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
- `python scripts/check_v10_documentation_consistency.py`;
- `python scripts/check_v10_public_product_plan.py`.

Do not weaken guards to land a change.

## Broker / money authority

Protected V9 contours remain isolated. For public V10, USER broker credentials are tenant-scoped rather than application-global.

Optional Real execution remains later-gated and requires same-tenant verified READ/TRADE account intersection, durable state, immutable plan, short-lived authenticated USER approval for that USER's own tenant, fresh preflight, own cash/owned quantity, idempotency and reconciliation.

Never grant transfer/withdrawal, margin/short, hidden autonomous recurring Real execution, automatic retry after possible-submit ambiguity or AI direct broker-write authority.

`REAL_TRADING_ENABLED=false` remains the master Real rollback until accepted activation.

## Secrets/private data

Never commit/log/artifact real broker/provider/Telegram/VK secrets, encryption/recovery keys, Authorization headers, full account IDs or private portfolio/database payloads.

Hosted tenant-private state and encrypted broker credentials may exist only inside the approved cloud data/secret boundary after its security/privacy/legal gates. Cross-tenant access is forbidden.

## OWNER handoff

Do everything possible through GitHub/code/CI/provider automation first. Ask OWNER only for genuinely non-delegable account/consent/secret/UAC/admin/physical/legal/budget decisions.

Use `docs/operations/V10_OWNER_ACTION_HANDOFF_STANDARD.md`: verified official target, exact scope, one bounded action, expected result, STOP/do-not-do conditions, cost/authority consequence and minimum non-secret return.
