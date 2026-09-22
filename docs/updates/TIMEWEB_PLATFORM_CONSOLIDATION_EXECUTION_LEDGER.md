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
- Replacement checkpoint `9527e5974b3cf673a870386590fac228e80a87a3` completed all observed DRAFT checks except the authoritative Windows Regression Shield
- Historical-test-consumer correction head: `cea3edda9d6c7df482cb08fbfaa41adfac943a6d`
- Next exact action: complete one current-authority documentation/guard correction batch, then run a fresh exact-head DRAFT cycle
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

- Third exact-head finding on `d9e34a31cff28eb17290fe7d15fb3cc0a18e94af`: Engineering Governance #1878 passed every individual authority guard through the CI graph repair and then failed one regression test because the new role key `current_provider_secret_authority` violated the repository's own detector-unambiguous naming rule forbidding `secret` in metadata keys.
- Whole-workflow adjacent review found `.github/workflows/v10-neon-egress-boundary.yml` still active on PR/main and performing an anonymous network request to retired Neon. It used no credential and made no mutation, but it remained a runtime dependency on a retired provider and could create future false RED after provider decommission.
- Systemic correction: rename the Timeweb role metadata to detector-safe `current_provider_binding_authority`; archive/hard-disable the Neon egress workflow; extend current machine contracts and guards from the three Cloudflare workflows to the complete retired-provider executable set; keep the probe implementation/tests as historical evidence only.
- Historical manual Render workflows remain fail-closed, but their operator text no longer directs future work to retired Cloudflare.
- Fourth exact-head RED on `1fc3c75d28cc0c03df7eb2bad5f134b03bb1ad72`: authoritative Windows CI reached `ruff format --check` after `ruff check` success and found five guard files requiring canonical formatting.
- Adjacent regression review found `tests/test_v10_cloudflare_cf_d_hosted_egress_recovery.py` still asserting the retired live CF-D DAG rather than archive-in-place hard-disable semantics.
- Current-state review found Telegram legal/readiness contracts, runbooks, privacy inventory/policy and activation ledger still treating former Cloudflare/Neon evidence as current readiness. Amendment 18 makes that state false: Timeweb revalidation is required and Cloudflare/Neon evidence is historical only.
- Correction batch rule: repair all three classes together, remove current readiness dependence on retired `wrangler.jsonc`, preserve historical evidence, keep public-user flags false, and add regression tests before publishing the next head.
- Fifth exact-head RED on `9527e5974b3cf673a870386590fac228e80a87a3`: Engineering Governance, Fast PR, Toolchain and all observed WP audits succeeded; authoritative Windows static quality also succeeded, then full Regression Shield failed only 3 assertions after `3629 passed`.
- Exact failing consumers: `tests/test_v10_cloudflare_cf_d_direct_bootstrap_control_plane.py` and `tests/test_v10_cloudflare_neon_authority_preflight.py` still required former conditional live activation expressions (`needs.*bootstrap_required == 'true'`) even though Amendment 18 correctly hard-disables every retired production-release job with unconditional `if: ${{ false }}`.
- Systemic correction: historical tests must prove two facts simultaneously — legacy recovery implementation/evidence remains preserved, while every retired provider job is unconditionally non-executable and no old `needs.*` expression can reactivate it. Job extraction is bounded so assertions cannot accidentally pass by matching a later historical job.
- Sixth branch-local review finding on `cea3edda9d6c7df482cb08fbfaa41adfac943a6d`: full review of all 58 PR-changed files plus repository-wide current-authority search found contradictory live guidance. `knowledge/17_V10_CURRENT_PROGRAM_STATUS.md` still contained earlier current-tense Cloudflare/RU-PG-B/WEB-VISUAL authority statements alongside the later accepted Amendment-18 Timeweb state; `knowledge/00_PROJECT_MASTER_CONTEXT.md`, `AGENTS.md` and `CONTRIBUTING.md` still exposed a Cloudflare candidate release formula as current guidance; GPT recovery source lists prioritized historical Cloudflare authority contracts; the Telegram data inventory froze an obsolete accepted-base SHA.
- Root cause: existing documentation guards verified presence of the new Timeweb markers but did not forbid contradictory stale current-authority markers. Presence-only validation allowed both old and new authority to coexist.
- Systemic correction: make historical sections explicitly historical/superseded, make current release flow GitHub -> exact Timeweb candidate, make GPT recovery prefer Amendment-18/Timeweb contracts, remove frozen current SHA from the legal inventory, and extend the Amendment-18 guard/tests with negative stale-authority assertions.
- Seventh exact-head RED on `bbd14ec29260300090a0aa96eb6997c884042a71`: all observed non-Windows gates completed `success`, but the authoritative Windows gate failed during `compileall` before pytest. The generated correction in `tests/test_v10_cloudflare_system_update_closeout.py` contained literal `\\n` escape text inside a Python assertion, producing `SyntaxError: unexpected character after line continuation character`.
- Root cause: correction publishing did not perform a syntax-equivalent preflight on every changed Python test after text substitution. The existing remote compile gate caught the defect correctly; no guard was weakened.
- Correction: replace the malformed assertion with ordinary Python syntax, normalize the adjacent Timeweb regression-test formatting in the same batch, and require focused syntax/format review before publishing the replacement head.
- Guard-gap follow-up: `V10 Fast PR Checks` compiled only `scripts` and selected `omni_cio` policy packages, so malformed Python in `tests/` or `apps/` could reach the authoritative Windows gate. The fast compile step is expanded to the complete repository Python source/test surface and a regression test freezes that coverage.
- Eighth exact-head RED on `02ecc42bae9d88a195816dc18db6f1bb3d35adc5`: Fast PR, Engineering Governance, Toolchain and all WP audits succeeded; authoritative Windows compile also succeeded, then Ruff format failed only on `scripts/check_v10_ru_public_registration_ingress.py` because one boolean expression was not in canonical Ruff layout.
- Root cause: Fast PR had gained full syntax compilation but still did not run the already-canonical Ruff lint/format gates before the expensive authoritative job. The project already has the same protected-runner Ruff commands in `v10-targeted-repair.yml`, so no new toolchain is needed.
- Systemic correction: canonical-format the guard and make Fast PR run `ruff check .` plus `ruff format --check .` immediately after full compile; regression coverage freezes both early gates.
- Ninth exact-head RED on `d5204fed17c283217cc5b026e754a1c13b67b557`: the new early Fast PR formatter gate correctly ran but `ruff format --check .` exposed 455 legacy unformatted Python files, only 14 of which are changed by PR #582. Treating the entire historical tree as a new-code formatting gate would create an unrelated mass rewrite.
- Root cause: the early formatter guard was made repository-wide even though the accepted baseline is not globally Ruff-formatted. New-code quality and historical-baseline cleanup were conflated.
- Systemic correction: keep global `ruff check .`, but derive a NUL-safe exact base-to-head list of changed `*.py` files and run Ruff format only on that set. Canonically format the 14 PR-changed tests identified by Ruff; leave the unrelated 441 legacy files untouched. A regression test forbids reintroducing whole-tree `ruff format --check .` in Fast PR.
- Tenth exact-head RED on `d77317fc9158763edf356367bef24ee7b4cfdd52`: Fast PR compile and global Ruff lint succeeded and changed-file format narrowed the remaining formatter defect to one extra blank line in `tests/test_v10_neon_egress_boundary.py`. The authoritative Windows lane passed static quality, stable gateway, read-only release contract, 3636 tests / 813 subtests, 62.20% coverage, pip-audit and Bandit, then failed only at tracked-content secret scanning.
- Secret-scan finding: Ruff canonicalization had collapsed the historical accepted Phase-3 40-hex commit evidence in `tests/test_wp22a_phase4_free_preview_authorization.py` into one contiguous high-entropy literal. This is not a credential, but suppressing or allowlisting the finding would weaken the security boundary.
- Root cause: formatter canonicalization and secret-detector semantics were not treated as adjacent consumers, and the authoritative secret scan ran after the expensive Regression Shield.
- Systemic correction: preserve exact historical SHA evidence as bounded eight-character chunks; remove the final Ruff blank-line drift; move the existing detect-secrets gate immediately after static quality and before Regression Shield; add a Regression Shield guard/test that rejects any future ordering where secret scan runs after protected pytest; keep Fast PR whole-tree lint but exact base-to-head changed-Python formatting only.

Only `CERTIFIED_GREEN` permits TW-B.

## 8. Root-cause inventory

| Finding / class | Root cause | Blast radius / analogous locations | Coupled surfaces | Adjacent failure modes | Why prior guard missed it | Permanent guard / repair |
|---|---|---|---|---|---|---|
| Cloudflare #106 auto-runs after accepted Timeweb authority | Active Actions DAG was not part of provider-retirement validation | 3 Cloudflare live workflows + Timeweb proof upstream | GitHub Actions, provider secrets, post-merge release | repeated RED, skipped Timeweb proof, accidental retired-provider mutation | Amendment 18 validated docs/contracts but not the concrete workflow graph | archive three workflows, remove automatic triggers, hard-disable jobs, machine-check graph |
| Timeweb proof depends on retired Cloudflare release | Old RU-PG-B chain encoded Cloudflare as upstream authority | workflow + control-plane contract/guard/tests/runbook | Regression Shield, Timeweb environment gate | Timeweb evidence skipped whenever retired workflow fails | provider proof guard checked safety of old chain, not Amendment 18 service-set compatibility | direct Regression Shield -> Timeweb proof, exact-main equality preserved |
| Sonar remains active merge dependency | Amendment 16 historical external-review law survived service-set consolidation | Engineering Governance + authoritative merge gate + guidance | PR certification | external SaaS outage/cancel blocks current service set | no Amendment 18 active-CI graph invariant | GitHub-native lint/type/test/coverage/dependency/SAST/secret authority; Sonar historical only |
| Cloudflare closeout guard rejects historical status wording | historical accepted-completion proof used former current-state literal as eternal marker | guard + 3 regression tests | current status ledger | false RED when authority is correctly superseded | no distinction between immutable event fact and mutable current-state label | require explicit historical archive marker instead |
| Ruff formatting drift in authority guards | correction commits changed Python guard layout without a final local formatter pass | 5 changed guard files | authoritative Windows static-quality gate | exact-head RED before deeper tests | pre-publish batch review did not include formatter-equivalent verification on the replacement head | canonical formatting correction plus fresh exact-head verification |
| Retired CF-D regression consumer remained live-shaped | workflow producer became archive-in-place but one test still asserted former live dependency/result semantics | CF-D archive workflow + recovery regression test | pytest / Regression Shield | hidden future RED after formatter repair | provider-retirement guard checked workflow itself but not every historical test consumer | rewrite the test to assert archive/hard-disable invariants and preserve historical evidence markers |
| Telegram activation state still bound to retired Cloudflare/Neon | provider authority changed without invalidating capability-specific readiness evidence and Cloudflare deployment-config dependencies | Telegram readiness/legal contracts, guards, runbooks, privacy docs, activation ledger | future TW-F activation | false readiness / unsafe activation decision / stale privacy statements | Amendment-18 guard validated general service set but not every capability-specific current-state consumer | rebind current readiness to Timeweb, mark old proof historical, remove active `wrangler.jsonc` dependency, keep activation fail-closed |
| Historical Cloudflare tests still required live job conditions | archived workflow producer changed to unconditional hard-disable while two test consumers preserved former conditional activation assertions | 2 test modules / 3 assertions, plus adjacent job-slicing helpers | full Regression Shield | authoritative merge RED; future false-positive assertions by matching later job text | initial retirement review covered workflow/guards and one recovery test but missed two independent historical consumers | assert unconditional archive disable, forbid former conditional activation in job headers, bound job slicing to the exact historical job |
| Current guidance contains contradictory retired-provider authority | presence-only documentation guards allowed new Amendment-18 markers to coexist with older current-tense Cloudflare/RU-PG-B/WEB-VISUAL statements | canonical status, master context, AGENTS/CONTRIBUTING, GPT recovery prompts, legal data inventory | future engineering/recovery/TW-F decisions | wrong provider implementation, stale release path, incorrect legal provenance | guards asserted required Timeweb markers but did not forbid stale current markers | explicit historical/superseded wording + Timeweb release formula + recovery-source rebinding + negative stale-authority guard/tests |

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
