# Timeweb Platform Consolidation Execution Ledger

Status: **BRANCH-LOCAL EXECUTION STATE — NOT ACCEPTED MAIN AUTHORITY**

## 1. Identity

- Update ID: `TIMEWEB-PLATFORM-CONSOLIDATION-INTEGRATED`
- Title: Timeweb-only runtime/database/DNS/Telegram consolidation
- Execution unit: `INTEGRATED_SYSTEM_UPDATE`
- Branch: `system/timeweb-platform-consolidation`
- Accepted base SHA: `e8e583f366bb314ef6d37e8057b90cde9a42d4f4`
- Current accepted-main SHA rechecked at branch creation: `e8e583f366bb314ef6d37e8057b90cde9a42d4f4`
- OWNER authority: Amendment 18 accepted through PR #581
- GitHub dashboard issue: #580
- Current split-boundary PR: #582
- Governing authority:
  - `docs/master-plan/OMNI_CIO_V10_RU_PUBLIC_REGISTRATION_AND_RUSSIAN_INGRESS_AMENDMENT.md`
  - `docs/architecture/V10_RU_PUBLIC_REGISTRATION_INGRESS_CONTRACT.json`
  - `docs/architecture/V10_RU_POSTGRES_TIMEWEB_CONTROL_PLANE_CONTRACT.json`
  - Amendment 16 Green Checkpoint law

## 2. Member milestones — ordered

| Order | Member milestone | State | Branch-local evidence | Notes |
|---:|---|---|---|---|
| 1 | TW-A / INVENTORY_AND_AUTHORITY | IN_PROGRESS | PR #582 | MAIN_RED_STOP active-workflow graph correction is the first accepted-boundary requirement |
| 2 | TW-B / SOURCE_AND_RUNTIME_CONSOLIDATION | TODO |  | Must not begin until TW-A checkpoint is CERTIFIED_GREEN and accepted |
| 3 | TW-C / TIMEWEB_APP_CANDIDATE | TODO |  | Technical Timeweb candidate only after TW-B |
| 4 | TW-D / TIMEWEB_POSTGRES_PRODUCTION_CUTOVER | TODO |  | Mandatory production DB split gate |
| 5 | TW-E / TIMEWEB_PUBLIC_INGRESS_DNS | TODO |  | Mandatory DNS/public cutover split gate |
| 6 | TW-F / TELEGRAM_PUBLIC_ACTIVATION | TODO |  | Auth/privacy/legal/capacity gate |
| 7 | TW-G / LEGACY_PROVIDER_DECOMMISSION | TODO |  | External proof + active-authority cleanup; repository history stays archive-in-place |

Milestone state is branch-local only and does not change accepted V10 implementation progress.

## 3. Current execution state

- Current exact work item: retire the stale Cloudflare/Neon/Sonar active execution graph and establish direct GitHub -> Timeweb post-merge proof
- Current logical checkpoint ID: `TW-A-CI-AUTHORITY-GRAPH-REPAIR`
- First published checkpoint SHA: `f888dc7b0dc0b3eb0816b27b41eeac7fbe7992e9`
- First checkpoint state: `RED_REPAIR_ONLY`
- First material RED: Engineering Governance on PR #582
- Root cause of that RED: historical Cloudflare closeout guard still required a former current-state status marker after Amendment 18 reclassified the accepted Cloudflare update as historical archive evidence
- Replacement checkpoint: pending exact-head recertification after systemic marker/test repair
- Next exact action: finish DRAFT exact-head checks and inspect every material RED before READY
- Scope/non-goals still intact: YES
- Main drift since accepted base: NONE observed at branch creation

## 4. MAIN_RED_STOP source defect being repaired

Accepted `main` `e8e583f...` had a post-merge workflow graph inconsistent with Amendment 18:

`Regression Shield -> V10 Cloudflare Production Release -> Timeweb Read-Only Proof`

Observed evidence:

- Regression Shield #1645: success;
- Engineering Governance #1862: success;
- Cloudflare Production Release #106: failure before provider mutation because retired Cloudflare credentials were absent;
- Timeweb Read-Only Proof #12: skipped because its upstream Cloudflare workflow did not succeed.

Target graph for this repair:

`protected-main push -> Regression Shield -> Timeweb Read-Only Proof`

Retired Cloudflare provider workflows remain archive-in-place but have no automatic trigger and no executable provider-mutation job.

## 5. Mandatory split-trigger review

| Trigger | State | Evidence / consequence |
|---|---|---|
| DB/migration ordering | CLEAR | No production DB mutation in PR #582 |
| Security/authority transition | TRIGGERED | PR #582 is the independent CI/provider-authority transition boundary |
| Dependency/toolchain boundary | CLEAR | No dependency/toolchain version change |
| OWNER/provider action | CLEAR | No new provider purchase/mutation; prior external decommission is OWNER-reported evidence |
| Live/temporal evidence | TRIGGERED | Post-merge workflow behavior must be proved on exact new main |
| Production cutover | CLEAR | No App Platform/DNS/DB production cutover in this repair |
| Real-money authority | CLEAR | No broker-write/Real authority change |
| Reviewability limit | CLEAR | Focused active-workflow graph correction |

Split decision: **PR #582 is the mandatory security/authority + live-evidence acceptance split.**

## 6. Protected authority checklist

- [x] Protected V9 entrypoint remains `app:app`.
- [x] `PUBLIC_MULTI_USER_ENABLED=false` remains unchanged.
- [x] `trading_methods=false` remains unchanged.
- [x] `REAL_TRADING_ENABLED=false` remains unchanged.
- [x] Broker write remains OFF.
- [x] No transfer/withdrawal/margin/leverage/uncovered-short authority is introduced.
- [x] Tenant isolation remains fail-closed.
- [x] No real secret/private payload/full account ID is stored in GitHub/CI/artifacts.
- [x] No paid/provider/public mutation occurs in PR #582.
- [x] Deterministic Core remains financial truth authority.

## 7. Current checkpoint evidence

### Checkpoint 1 — TW-A-CI-AUTHORITY-GRAPH-REPAIR

- DRAFT PR: #582
- Initial exact head: `f888dc7b0dc0b3eb0816b27b41eeac7fbe7992e9`
- Initial state: `RED_REPAIR_ONLY`
- Fast policy/source contracts on initial head: success
- Sonar on initial head: incidental external historical check, success; not active acceptance authority
- Engineering Governance on initial head: failure
- Failure location: `scripts/check_v10_cloudflare_public_product_integrated.py`
- Failure class: historical-current marker drift after Amendment 18 supersession
- Repair: guard and all known regression consumers now require the historical archive marker rather than reinstating old current Cloudflare authority
- Replacement exact-head full certification: PENDING

- Second replacement head `72967eb53db2fcb43eded016299371d756c7c43f`: DRAFT checks completed with two material RED results:
  - Self-Hosted Windows CI #3086 failed only at protected static quality because four changed Python guards were not Ruff-formatted;
  - V10 Engineering Governance #1877 passed every preceding authority guard and failed at `TIMEWEB_CONSOLIDATION_RETIRED_WORKFLOW_MUTATION_ENABLED`.
- Second-RED root cause: the Timeweb consolidation guard still had one production-only assertion for the removed legacy `false && ...` disable representation, while the repaired archived workflow correctly used unconditional `if: ${{ false }}`.
- Correction rule: all three retired Cloudflare workflows use one exact hard-disable representation, with expected disabled-job counts `1 / 1 / 6`, no automatic trigger and no legacy `false &&` fallback.

Only `CERTIFIED_GREEN` permits TW-B.

## 8. Root-cause inventory

| Finding / class | Root cause | Blast radius / analogous locations | Coupled surfaces | Adjacent failure modes | Why prior guard missed it | Permanent guard / repair |
|---|---|---|---|---|---|---|
| Cloudflare #106 auto-runs after accepted Timeweb authority | Active Actions DAG was not part of provider-retirement validation | 3 Cloudflare live workflows + Timeweb proof upstream | GitHub Actions, provider secrets, post-merge release | repeated RED, skipped Timeweb proof, accidental retired-provider mutation | Amendment 18 validated docs/contracts but not the concrete workflow graph | archive three workflows, remove automatic triggers, hard-disable jobs, machine-check graph |
| Timeweb proof depends on retired Cloudflare release | Old RU-PG-B chain encoded Cloudflare as upstream authority | workflow + control-plane contract/guard/tests/runbook | Regression Shield, Timeweb environment gate | Timeweb evidence skipped whenever retired workflow fails | provider proof guard checked safety of old chain, not Amendment 18 service-set compatibility | direct Regression Shield -> Timeweb proof, exact-main equality preserved |
| Sonar remains active merge dependency | Amendment 16 historical external-review law survived service-set consolidation | Engineering Governance + authoritative merge gate + guidance | PR certification | external SaaS outage/cancel blocks current service set | no Amendment 18 active-CI graph invariant | GitHub-native lint/type/test/coverage/dependency/SAST/secret authority; Sonar historical only |
| Cloudflare closeout guard rejects historical status wording | historical accepted-completion proof used former current-state literal as eternal marker | guard + 3 regression tests | current status ledger | false RED when authority is correctly superseded | no distinction between immutable event fact and mutable current-state label | require explicit historical archive marker instead |

## 9. Integration-ready preflight

- [ ] Current replacement checkpoint is `CERTIFIED_GREEN`.
- [ ] Complete changed surface reviewed.
- [x] Directly coupled workflow/contract/guard/test/runbook surfaces reviewed.
- [x] Analogous live Cloudflare workflows searched.
- [x] Retired provider secret consumers searched.
- [x] Deterministic graph regression guards added.
- [x] Security/authority/secret/recovery consequences reviewed.
- [ ] Full final diff reviewed on replacement exact head.
- [ ] DRAFT exact-head applicable checks all success.
- [ ] READY exact-head applicable checks all success.
- [ ] Zero unresolved blocking review threads.

## 10. Handoff

- Accepted main: `e8e583f366bb314ef6d37e8057b90cde9a42d4f4`
- Current update: `TIMEWEB-PLATFORM-CONSOLIDATION-INTEGRATED`
- Current member milestone: TW-A / inventory and authority cleanup
- Current checkpoint: `TW-A-CI-AUTHORITY-GRAPH-REPAIR`
- State: `RED_REPAIR_ONLY` until the replacement exact head is fully certified
- Current PR: #582 (DRAFT)
- Next lawful action: finish replacement exact-head DRAFT verification; no TW-B runtime work before certification and acceptance
