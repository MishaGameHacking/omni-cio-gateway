# Timeweb Platform Consolidation Execution Ledger

Status: **BRANCH-LOCAL EXECUTION STATE — NOT ACCEPTED MAIN AUTHORITY**

## 1. Identity

- Update ID: `TIMEWEB-PLATFORM-CONSOLIDATION-INTEGRATED`
- Title: Timeweb-only runtime/database/DNS/Telegram consolidation
- Execution unit: `INTEGRATED_SYSTEM_UPDATE`
- Initial TW-A branch: `system/timeweb-platform-consolidation` (squash-merged via PR #583)
- Current TW-B continuation branch: `system/timeweb-platform-consolidation-tw-b`
- TW-A accepted base SHA: `82e3a45c7016f2956c9b3761d10d15e433375f3c`
- Current accepted-main SHA after PR #583: `c7ea5ba549e1bf8e627d61117a15ace8da6387a4`
- OWNER authority: Amendment 18 accepted through PR #581
- GitHub dashboard issue: #580
- Accepted split-boundary PR: #582
- Accepted TW-A certification PR: #583
- Governing authority:
  - `docs/master-plan/OMNI_CIO_V10_RU_PUBLIC_REGISTRATION_AND_RUSSIAN_INGRESS_AMENDMENT.md`
  - `docs/architecture/V10_RU_PUBLIC_REGISTRATION_INGRESS_CONTRACT.json`
  - `docs/architecture/V10_RU_POSTGRES_TIMEWEB_CONTROL_PLANE_CONTRACT.json`
  - Amendment 16 Green Checkpoint law

## 2. Member milestones — ordered

| Order | Member milestone | State | Branch-local evidence | Notes |
|---:|---|---|---|---|
| 1 | TW-A / INVENTORY_AND_AUTHORITY | CERTIFIED_GREEN / ACCEPTED | PR #583; post-merge Regression Shield #1647 + Governance #1909 + Timeweb Proof #14 | Inventory/authority cleanup accepted on exact main `c7ea5ba549e1bf8e627d61117a15ace8da6387a4` |
| 2 | TW-B / SOURCE_AND_RUNTIME_CONSOLIDATION | IN_PROGRESS | continuation branch `system/timeweb-platform-consolidation-tw-b` | Provider-neutral source/runtime only; no production cutover |
| 3 | TW-C / TIMEWEB_APP_CANDIDATE | TODO |  | Technical Timeweb candidate only after TW-B |
| 4 | TW-D / TIMEWEB_POSTGRES_PRODUCTION_CUTOVER | TODO |  | Mandatory production DB split gate |
| 5 | TW-E / TIMEWEB_PUBLIC_INGRESS_DNS | TODO |  | Mandatory DNS/public cutover split gate |
| 6 | TW-F / TELEGRAM_PUBLIC_ACTIVATION | TODO |  | Auth/privacy/legal/capacity gate |
| 7 | TW-G / LEGACY_PROVIDER_DECOMMISSION | TODO |  | External proof + active-authority cleanup; repository history stays archive-in-place |

Milestone state is branch-local only and does not change accepted V10 implementation progress.

## 3. Current execution state

- Current exact work item: TW-B provider-neutral source/runtime consolidation
- Current logical checkpoint ID: `TW-B-SOURCE-AND-RUNTIME-CONSOLIDATION`
- Accepted base: `c7ea5ba549e1bf8e627d61117a15ace8da6387a4`
- Current branch: `system/timeweb-platform-consolidation-tw-b`
- TW-A exact reviewed head: `2c4cf7915c02d05e42b269544bc0336c31fa9a87`
- TW-A accepted PR: #583
- Post-merge evidence on current accepted main:
  - Regression Shield #1647: success
  - Engineering Governance #1909: success
  - WP16/WP17/WP18/WP19/WP20/WP21/WP22/WP22A owning audits: success
  - Timeweb Read-Only Proof #14: success
  - `TIMEWEB_GITHUB_ENVIRONMENT_GATE=READY`
  - `TIMEWEB_RU_PG_CONTROL_PLANE=READ_ONLY_READY`
- Timeweb IPv4 recovery remains fail-closed: `TIMEWEB_IPV4_ORPHAN_PROVENANCE_REQUIRED`
- Inventory artifact: `docs/architecture/V10_TIMEWEB_PLATFORM_PROVIDER_INVENTORY.json`
- TW-B source scope started from the 33 accepted `TIMEWEB_REPLACE` consumers/producers identified by TW-A; branch-local closure now classifies all completed current source consumers as `KEEP` and detached provider wrappers as `HISTORY`, with no explicit `TIMEWEB_REPLACE` source consumer remaining.
- TW-B does not authorize provider mutation, Timeweb App Platform deployment, production DB cutover, DNS cutover, public-user activation or Real-money authority.
- TW-B runtime root-cause review found that the first provider-neutral entrypoint still called `_probe_hosted_preview_database()`, which requires the historical synthetic preview USER/TENANT fixture. A clean Timeweb production database must not depend on that Phase-4 fixture.
- Correction head `7306c2ae0dfa806c49774d2ccfa629da5e1f85e7` replaces the Timeweb runtime probe with the production runtime-only PostgreSQL 18 / least-privilege / schema / FORCE-RLS probe, gives the Timeweb entrypoint its own hosted session policy, and keeps historical synthetic verification inside the historical preview path.
- The same correction adds a process-only `/livez` Docker health check and explicitly permits `localhost` for the container-local Timeweb health probe; `/healthz` remains database readiness and is intentionally not used as the process liveness gate.
- Non-synthetic hosted status no longer identifies the database as Neon or emits synthetic-preview broker/decision reason codes. Historical synthetic behavior remains unchanged when `synthetic_preview=true`.
- Second-pass review also found stale handoff text later in this ledger that still described TW-A as RED and TW-B as locked after PR #583 acceptance. That stale handoff is corrected as part of the same TW-B documentation convergence.
- No TW-C provider mutation or App Platform candidate deployment is authorized by these source changes.
- Protected flags remain false: `PUBLIC_MULTI_USER_ENABLED`, `OMNI_V10_TELEGRAM_LOGIN_ENABLED`, broker write, `trading_methods`, `REAL_TRADING_ENABLED`.


## 4. Accepted MAIN_RED_STOP repair provenance

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
- Eleventh exact-head RED on `f150519cc9ca7578f809c1cb571c2d70d3c0ddc1`: every observed DRAFT gate except authoritative Windows completed `success`; the authoritative lane reached the newly earlier tracked-content scan and failed on `scripts/check_v10_regression_shield.py:372` because the new local variable name itself contained the detector-sensitive word used for credential classification. Sonar Quality Gate stayed `success` but reported four maintainability findings: three duplicated retired-workflow path literals in `check_v10_ru_public_registration_ingress.py` and one duplicated Ruff command literal in `check_v10_regression_shield.py`.
- Adjacent active-workflow audit found a more important hidden retirement defect: `.github/workflows/v10-wp22a-clientless-access-audit.yml` still executed `scripts/validate_wp22a_terraform.ps1`, which transitively downloaded the retired Cloudflare provider package from GitHub Releases on active PR/push CI. The known retired-provider workflow list therefore did not cover transitive retired-provider tooling invoked by a differently named active workflow.
- Systemic correction batch: use detector-safe tracked-content terminology and fragmented step-marker construction; deduplicate workflow/quality literals into constants; remove executable Cloudflare/OpenTofu validation from the active WP22A audit while retaining static syntax/provenance checks; mark legacy WP22A provider-selection/IaC documents explicitly historical under Amendment 18; extend the Timeweb authority contract/guard/tests so automatically triggered non-retired workflows cannot execute retired-provider tooling or consume retired-provider credentials.
- Twelfth exact-head RED on `40d9845f1d15431eab03c846387ca4854c65bf0c`: Sonar Quality Gate completed `success` with zero annotations and all observed governance/toolchain/product audits except Fast PR, authoritative Windows and WP22A clientless completed `success`. All three REDs reduce to the same formatter class: Ruff 0.16.1 requires canonical layout in four changed Python files (`check_v10_ru_public_registration_ingress.py`, `test_v10_regression_shield.py`, `test_v10_ru_public_registration_ingress.py`, `test_v10_wp22a_provisioning_contract.py`). No provider execution occurred; WP22A failed before the static-only historical source contract step.
- Root cause: the transitive-retirement/Sonar correction batch was logically coherent but was published after textual edits without applying the exact pinned formatter to every newly changed Python consumer. The changed-file Fast PR gate correctly detected the drift early, while authoritative Windows and the focused WP22A audit independently confirmed the same class.
- Systemic correction: apply the exact Ruff-produced layout for all four files; strengthen the retirement scanner to cover both `.yml` and `.yaml` plus pull/push/workflow-run/manual/scheduled/reusable workflow entry forms; forbid retired Render/Cloud.ru/VK secret consumption in addition to Cloudflare/Neon; keep the V9 manual Render read-only recovery probe outside current V10 provider authority; add regression assertions that freeze these future workflow forms and prove the dormant WP22A validator is referenced only for non-executing syntax/provenance inspection.
- Pre-certification canonical-guidance audit on `b3da1b53a1d9a1ec44e2ad99ac8806f913963ded` found no new executable provider re-entry, but found authority ambiguity in live guidance: `README.md`, `AGENTS.md`, `CONTRIBUTING.md` and `knowledge/00_PROJECT_MASTER_CONTEXT.md` still contained present/future-tense Cloudflare instructions inside historical sections, and `knowledge/17_V10_CURRENT_PROGRAM_STATUS.md` preserved the old Cloudflare release formula without an immediately adjacent current-Timeweb disclaimer.
- Root cause: earlier documentation repair made sections historical at the heading level but did not prohibit actionable retired-provider language inside the section body. Presence-only Timeweb guards therefore allowed semantically contradictory historical instructions to coexist with correct current authority.
- Systemic correction: convert live front-door historical text to past-tense/provenance-only wording, remove the exact retired Cloudflare release formula from `README.md`, mark inherited WP22A provider documents `HISTORICAL / SUPERSEDED` at their status lines, add an explicit historical-only disclaimer beside the preserved formula in `knowledge/17`, and extend the Timeweb authority guard/tests with negative stale-provider guidance markers across README/master context/AGENTS/CONTRIBUTING.
- Thirteenth exact-head RED on `d8898c8aaa18ae8182dd35b762e66a260e7017a8`: Sonar remained `success` with zero annotations, but Fast PR stopped at `check_v10_engineering_governance.py` before compile/format because the guidance rewrite replaced the required provider-neutral marker `managed-cloud production runtime` in `AGENTS.md` with the shorter `managed-cloud runtime` phrase.
- Root cause: the documentation rewrite preserved semantics but did not preserve an immutable machine-consumed governance token. This is producer/consumer drift between live guidance and `SURFACE_MARKERS`.
- Correction: restore the exact marker only in the current Timeweb statement (`Timeweb as the managed-cloud production runtime`), keeping all Cloudflare future authority removed. No provider/runtime/dependency authority changes.

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
| Active CI transitively executed retired Cloudflare tooling | retirement guard enumerated provider-named workflows but did not inspect commands inside other automatically triggered workflows | WP22A clientless audit -> `validate_wp22a_terraform.ps1` -> Cloudflare provider bootstrap | PR/push CI, external GitHub release dependency, historical IaC evidence | future provider download outage, retired-provider supply-chain dependency, false GREEN authority graph | workflow retirement validation was filename/DAG-centric rather than executable-consumer-centric | static-only historical validation + active-workflow transitive-execution prohibition in Amendment-18 guard/tests |
| Detector-sensitive guard terminology self-triggered tracked-content scan | security-ordering fix introduced a local identifier containing the detector keyword | regression-shield guard + authoritative tracked-content scan | Windows merge gate before pytest | deterministic RED despite no real credential | security consumer was not run mentally against the new guard source itself | detector-safe identifiers/messages + fragmented exact workflow marker + regression coverage |
| Authority-hardening batch introduced formatter-only drift | post-fix textual edits were not normalized by pinned Ruff before publish | 4 changed Python guard/test consumers | Fast PR + authoritative Windows + WP22A focused audit | repeated REDs with identical semantics despite correct logic | early formatter gate existed remotely but no exact formatter pass was applied to the final local batch | apply CI-emitted Ruff layout before replacement head; keep changed-file formatter gate and focused lane redundancy |
| Historical headings still contained actionable retired-provider instructions | sections were labeled historical but body text retained present/future imperative Cloudflare wording | README, AGENTS, CONTRIBUTING, master/current status and inherited WP22A docs | new-chat recovery and future engineering decisions | accidental retired-provider re-entry despite correct top-level Timeweb authority | guard checked Timeweb presence and a few exact stale markers, not actionability inside historical sections | past-tense/provenance-only rewrite + explicit superseded status + negative stale-provider guidance markers |

| TW-B document guard required mutable checkpoint wording | Durable authority evidence was coupled to transient execution-state text | Timeweb authority guard + branch ledger | Engineering Governance | false RED whenever checkpoint state legitimately changes | document guard mixed immutable provenance and mutable current status | require accepted milestone identity/PR evidence only; regression forbids transient-state literal in durable document guard |
| GitHub blob rewrite lost canonical final LF | connector-fetched text was republished without restoring the repository text-file EOF invariant | 15 changed Python files + execution ledger | Fast PR Ruff changed-file format gate | formatter-only repeated RED and noisy source diffs | pre-publish path trusted fetched text representation instead of reviewing resulting Git diff | explicitly preserve final LF on rewritten text and inspect full PR diff for no-newline markers before publish |
| RU-PG-B neutral error code matched retired Render detector | provider scan used broad lexical `RENDER_` matching instead of executable/provider-specific identifiers | neutral PostgreSQL runtime primitives + parity guard | Engineering Governance | false provider-dependency classification for ordinary render/format terminology | detector semantics conflated a common verb with provider authority | use bounded provider-specific markers and regression-test neutral `POSTGRES_RUNTIME_ROLE_RENDER_FAILED` |
| Provider verifier detection data self-triggered Timeweb inventory | raw source scanner interpreted verifier-owned retired-provider marker literals as executable dependencies | parity verifier + Timeweb inventory scanner | Engineering Governance | KEEP verifier repeatedly classified as retired-provider consumer | producer/detector strings and consumer execution were not separated | fragment scanner-only literals while keeping executable-source scan fail-closed; regression forbids raw self-trigger markers |
| Global T-Bank extra index requires unavailable Russian CA trust | canonical Python locks expose the T-Bank repository to every package resolution while self-hosted Windows trust does not contain the required Russian Trusted CA chain | root runtime/dev locks + Python audit workflows + future Docker build | WP13/WP15/WP17/WP18/WP19/WP20/WP21/WP22/WP22A/authoritative Windows | mass TLS RED, misleading no-matching-distribution tail error, Timeweb image-build failure | dependency topology and machine trust were treated as independent even though pip contacts every configured index | keep TLS/hash checks fail-closed; repair trusted CA out-of-band and split broker-index/dependency topology under its dedicated toolchain boundary before TW-C |
| WP17 READ-vault exact-head evidence drift | sanitized OWNER evidence remained bound to an older implementation SHA | protected READ-vault + sanitized evidence root on Windows runner | WP17 OWNER Read Vault audit | stale binding blocks exact-head acceptance and intentionally prevents direct permission probes | source CI cannot synthesize or rewrite an OWNER/Admin host-security proof | preserve the fail-closed ACL boundary; distinguish skipped probes from fresh permission observations; after final code SHA freeze run OWNER/Admin provision+finalizer and require non-admin negative probes on exact head |

| RU-PG-B direct-entry regression asserted removed import scaffolding | test encoded the historical `v10_jsonc` dual import implementation instead of the executable behavior it intended to protect | parity guard unit contract | Engineering Governance | deterministic false RED after provider-neutral guard stopped importing JSONC | regression protected an implementation detail rather than direct-script operability | execute the guard as a real child Python process from repository root and assert successful contract output; keep source free of unnecessary package/import compatibility code |
| Current security/runbook guidance still described Telegram+VK as ordinary login | Amendment 18 updated canonical authority and deployed composition but several still-applicable security/OWNER runbooks retained pre-Amendment multi-provider present tense | WP17 application-shell runbook, identity security notes, WP15 live-read runbook, active security-boundaries architecture | future OWNER/security/TW-C/TW-F operations | operator could reintroduce VK or mistake historical local acceptance identity for Timeweb product authority | archive-in-place policy distinguished historical files but current-guidance guard did not cover these security consumers | add explicit Amendment-18 override, Telegram-only current wording and negative stale-guidance regression while preserving historical procedures as evidence |
| Full-repository audit depended on selected provider/code surfaces | TW-A inventory proved provider consumers but did not structurally parse/read every checked-out repository file on every governance run | entire repository tree | Engineering Governance / future TW-B+ corrections | an unrelated syntax/config/conflict defect could survive if its owning lane was not selected | provider inventory and repository integrity were separate concerns | extend the existing Timeweb inventory verifier to read every discovered file, parse Python/JSON/TOML/XML, reject executable/config conflict markers and preserve bounded file/byte limits |
| Final TW-B source correction had two Ruff format drifts | last source edits were semantically correct but were not normalized to the pinned formatter output | two changed regression tests | Fast PR source gate | deterministic RED before focused unit tests | final edit batch was published before formatter-equivalent review | apply the exact Ruff-emitted layout and keep changed-file formatting fail-closed |
| Synthetic-create runbook guard used an exact whitespace-sensitive marker | the required no-production-cutover sentence was wrapped across Markdown lines | Timeweb RU-PG-B create runbook + source guard | authoritative pytest | one deterministic contract RED despite correct policy meaning | guard marker and prose layout were coupled | keep the explicit no-cutover sentence contiguous while preserving TW-D ownership of production DB cutover |
| Timeweb inventory transitive-consumer validator exceeded Sonar complexity threshold | classification, historical-detachment, V9, VK and database-authority checks accumulated in one function | Timeweb provider inventory guard | Sonar maintainability | quality finding on the source/runtime checkpoint | responsibilities were not split after successive TW-A/TW-B hardening | extract bounded classification and authority helpers without weakening any check |
| Timeweb Docker build inherited the T-Bank package-index CA prerequisite without a build-scoped trust bundle | canonical `requirements.txt` contains the official T-Bank extra index while the stock Linux image has no reviewed Russian Trusted Root CA augmentation | `Dockerfile`, T-Bank CA contract/preparer, Docker build context and runtime SDK TLS mode | Timeweb App Platform image build | dependency install can fail before application startup; TLS bypass would create a supply-chain regression | prior CA closure enumerated Windows job-local consumers but not the future Linux/Timeweb image-build consumer | reuse the pinned certifi+Russian-root `PIP_CERT` bundle only for Docker dependency install, delete it after use, enable locked SDK `SSL_TBANK_VERIFY=True`, and regression-test no TLS bypass/secret baking |
| Whole-repository XML syntax validation used unsafe stdlib ElementTree on potentially hostile repository content | repository-integrity guard expanded from named provider files to every discovered file but reused a trusted-input parser primitive | `scripts/check_v10_timeweb_platform_inventory.py`, repository-wide governance/SAST | authoritative Windows Bandit B314 / CWE-20 | SAST correctly blocks merge even though functional governance passes | security parser threat model was not extended when audit scope expanded to arbitrary repository XML | reuse the repository's accepted stdlib Expat hardening pattern, reject DTD/entity/external-entity payloads before tree construction, add malicious-XML regression, no Bandit suppression |
### TW-B Timeweb App Platform source constraints — verified 2026-09-23

Applicable official Timeweb documentation was rechecked before this source correction.
The repository source is aligned as follows, without granting TW-C provider-mutation authority:

- Dockerfile deployment is the selected App Platform source mode. Timeweb requires an
  `EXPOSE` declaration so the platform can identify the application port; the current
  source explicitly exposes `8080`.
- Timeweb allows an App Platform health-check path and documents that the panel setting
  takes precedence over Dockerfile `HEALTHCHECK`. The current runtime therefore keeps
  `/livez` process-only and `/healthz` database-aware; TW-C must configure the platform
  health path to `/livez` rather than making platform liveness depend on PostgreSQL.
- App Platform starts a fresh container environment on each deploy, so durable product
  state must stay outside the application container. PostgreSQL remains the relational
  state boundary; no local-container persistence is accepted as product storage.
- Timeweb App Platform variables are the intended runtime configuration/secret injection
  surface. The current Docker image does not bake `OMNI_V10_RELEASE_SHA`, PostgreSQL
  credentials or Telegram credentials into build arguments or image metadata.
- Timeweb private-network selection for App Platform is a creation-time choice and cannot
  be changed in place later. TW-C must resolve that network choice explicitly before
  candidate creation; TW-B does not guess it and performs no provider mutation.
- Timeweb Managed PostgreSQL supports PostgreSQL 18 and private/public/domain connection
  modes. The production DB/network choice remains the later TW-D split gate and must keep
  TLS/least-privilege/RLS/recovery evidence intact.

Official references rechecked:
- https://timeweb.cloud/docs/apps/deploying-with-dockerfile
- https://timeweb.cloud/docs/apps/healthcheck-path
- https://timeweb.cloud/docs/apps/how-it-works
- https://timeweb.cloud/docs/apps/variables
- https://timeweb.cloud/docs/apps/trusted-certificates
- https://developer.tbank.ru/docs/tls-settings
- https://timeweb.cloud/docs/apps/upravlenie-apps-v-paneli
- https://timeweb.cloud/docs/dbaas/postgresql
- https://timeweb.cloud/docs/dbaas/postgresql/connect-to-database


### Exact-head RED repair — c74e0ad8394076b866119c642e63bbe81b1bc680

Fast PR and authoritative Windows independently exposed one formatting-only defect in the two new Docker trust tests. Authoritative Windows then reached SAST and found Bandit B314/CWE-20 in the new whole-repository XML parser. Root cause is verifier threat-model expansion without parser hardening: repository XML is verifier input and must be treated as hostile. The first correction incorrectly imported `defusedxml` into a governance guard that runs before dependency installation and therefore failed with `ModuleNotFoundError`. The systemic correction instead reuses the repository's accepted dependency-free Expat hardening pattern with parameter entities disabled and DTD/entity/external-entity rejection, while retaining the malicious-DTD/entity regression and exact Ruff formatting; no scanner suppression or assertion weakening is allowed. WP17 OWNER evidence remains a separate exact-head binding blocker.

### OWNER-laptop manual dependency removal — Amendment 19

The repeated WP17 RED was not a runtime defect: the old required check demanded exact-head Windows ACL evidence stored on the OWNER laptop. OWNER explicitly removed that manual-machine dependency from the Timeweb PR path on 2026-09-23. The systemic replacement does not suppress the control: current Timeweb composition is forbidden from importing the Windows vault, hosted broker mutation remains fail-closed, a GitHub-hosted source-security guard becomes the required WP17 check, and the original local ACL audit is retained as manual historical evidence. This change intentionally creates a new exact head and invalidates the earlier 23/24 evidence set; full certification must rerun.

### Amendment 19 inventory-cardinality repair

The Amendment 19 correction intentionally added four new Timeweb-named current surfaces (amendment, machine contract, guard and regression test). The TW-A provider inventory's exact provider-named cardinality therefore moved from 216 to 220. Engineering Governance correctly rejected the stale count with `TIMEWEB_INVENTORY_PROVIDER_SURFACE_COUNT_DRIFT`. The repair updates the exact count and explicitly classifies all four additions as `KEEP`; no minimum-count weakening or unclassified-provider bypass is introduced.

### Amendment 19 producer/consumer closure repair

Exact head `01cb544e87e71827aec6b22e0ada3292d96233e1` proved that the new GitHub-hosted
Timeweb WP17 source-security gate itself was sound: it completed `success`, Engineering
Governance completed `success`, and the whole-repository integrity pass read all 1,728
discovered files. The replacement was still incomplete because two consumers continued
to encode the superseded local-laptop topology: `tests/test_v10_wp17_read_connection_vault.py`
expected the active required workflow to execute the Windows ACL auditor, and
`scripts/check_v10_wp17_web_security.py` plus the WP17 machine contract still described
OWNER exact-head ACL evidence as a current acceptance requirement. Fast/authoritative
gates independently also caught Ruff formatting drift in the two newly added Amendment-19
Python files.

Root cause: the authority producer was changed before the complete producer/consumer
closure was rewritten. The first closure repair then exposed one additional consumer:
the Timeweb current-guidance guard/test were coupled to the literal Amendment-18 heading
instead of the durable current-authority semantics, so an Amendment-19 wording update
created a deterministic false RED. The systemic correction separates **current Timeweb hosted
custody** from **historical local DPAPI custody** in the WP17 contract, moves local ACL
workflow assertions to the manual historical workflow, makes current Timeweb broker
mutation remain fail-closed, and extends the no-OWNER-laptop guard so this split cannot
silently regress. This is a contract/topology repair, not test weakening: historical
DPAPI/ACL tests remain required and the active Timeweb gate gains stronger negative
proof that it cannot depend on the local vault.

## 9. Integration-ready preflight

- [ ] Current replacement checkpoint is `CERTIFIED_GREEN`.
- [x] Complete changed surface reviewed.
- [x] Directly coupled workflow/contract/guard/test/runbook surfaces reviewed.
- [x] Analogous live Cloudflare workflows searched.
- [x] Retired provider secret consumers searched.
- [x] Deterministic graph regression guards added.
- [x] Security/authority/secret/recovery consequences reviewed.
- [x] Full final diff reviewed on replacement exact head.
- [ ] DRAFT exact-head applicable checks all success.
- [ ] READY exact-head applicable checks all success.
- [ ] Zero unresolved blocking review threads.

## 10. Handoff

- Accepted main: `26bdc17c4e5d68c262f47b999e975b1eb8651858` (TW-A accepted via PR #583; focused CA-trust repairs #585 and #586 accepted afterward)
- Accepted TW-A: PR #583 / exact reviewed head `2c4cf7915c02d05e42b269544bc0336c31fa9a87`
- Post-merge TW-A evidence: Regression Shield #1647, Engineering Governance #1909, owning WP audits and Timeweb Read-Only Proof #14 = `success`
- Current update: `TIMEWEB-PLATFORM-CONSOLIDATION-INTEGRATED`
- Current member milestone: TW-B / source and runtime consolidation
- Current checkpoint: `TW-B-SOURCE-AND-RUNTIME-CONSOLIDATION`
- Current branch: `system/timeweb-platform-consolidation-tw-b`
- Exact branch head is resolved from GitHub/PR evidence rather than frozen self-referentially inside this ledger.
- State: `RED_REPAIR_ONLY / AMENDMENT_19_PRODUCER_CONSUMER_CLOSURE`; DRAFT PR #584 is open and TW-C remains blocked
- Proven defect classes closed branch-locally before current RED repair: synthetic-preview startup dependency, provider-specific runtime/transport coupling, current dual-provider auth defaults/import graph, stale provider-specific PostgreSQL/recovery/readiness paths, and untrusted build-time release-SHA display
- Latest pre-correction exact-head evidence: the complete repository-integrity gate passed over 1,723 discovered files (1,693 text, 30 binary; 919 Python and 80 JSON structurally parsed), Engineering Governance and all observed functional WP lanes passed, while Fast PR and authoritative Windows stopped on one Ruff-format drift in the repository-integrity verifier. Sonar Quality Gate passed with zero Security Hotspots and one remaining non-security issue on the new audit code. WP17 remains separately fail-closed on exact-head OWNER evidence binding. T-Bank CA trust failures remain accepted-repaired on main through PR #585/#586; prior direct-entry, stale guidance and hosted/provider-duplication source defects remain closed.
- Remaining TW-B work: complete the coherent correction set, publish a replacement exact head, require all applicable exact-head checks to complete `success`, then READY-verify the unchanged head; only after accepted squash merge and required post-merge GREEN may TW-C begin
- TW-C remains forbidden until TW-B is certified and accepted
