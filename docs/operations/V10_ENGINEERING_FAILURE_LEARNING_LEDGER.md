# Omni-CIO V10 — Engineering Failure Learning Ledger

Status: **ACTIVE ENGINEERING MEMORY AFTER GOVERNANCE AMENDMENT ACCEPTANCE**  
Purpose: retain reusable non-secret lessons from failed or misleading engineering cycles so future chats, agents and developers do not repeat the same failure classes.

This is not a blame log and it is not a replacement for current status, issue tracking, tests or CI evidence.

## Rules

Create/update an entry when a material failure occurs **after** the branch was considered ready for an expensive validation cycle, or when a check was misleading enough to expose a process weakness.

Every reusable entry should contain:

- Date / WP / PR or accepted change reference;
- Symptom / failing gate;
- Root cause;
- Blast radius searched;
- Why preflight missed it;
- Corrective change;
- Permanent regression/guard;
- Future prevention rule;
- Dependency/tooling knowledge change, if any.

Never record:

- broker/Telegram/provider tokens;
- Authorization headers;
- private portfolio/account payloads;
- raw OWNER identities;
- BitLocker/recovery keys;
- sensitive machine identifiers.

A short SHA may be used for navigation when useful. Full random-looking secret material must not be copied here.

---

## FL-001 — Infrastructure RED must not be merged around

**Date:** 2026-08-16  
**Scope:** V10-wide policy correction  
**Symptom:** GitHub-hosted Fast/Toolchain checks could fail before substantive job execution because of account billing/spending-limit state while authoritative Lenovo checks were GREEN. Earlier engineering treatment correctly classified those checks as infrastructure failures rather than code failures, but that classification was allowed to coexist with merge acceptance.

**Root cause:** the merge policy distinguished code failure from infrastructure failure for diagnosis, but did not separately enforce the OWNER requirement that the PR status surface itself be completely GREEN before merge.

**Blast radius searched:** all future V10 PR/maintenance/status/dependency merges and workflow routing semantics.

**Why preflight missed it:** this was a governance gap rather than an application-code defect.

**Corrective change:** the Engineering Quality / Green-Merge Amendment now states that any applicable RED check blocks merge regardless of whether the cause is code, billing, provider startup or infrastructure.

**Permanent guard:** machine-readable quality contract + PR template + agent instructions + governance CI check. Irrelevant workflows must be routed so they do not trigger; `skipped`/`neutral` are not GREEN evidence for applicable V10 gates.

**Future prevention rule:** classification explains the failure; it never grants a bypass.

---

## FL-002 — PowerShell native stderr is not equivalent to process failure

**Date:** 2026-08-12  
**Reference:** accepted WP15 correction PR #287  
**Symptom:** a Windows PowerShell 5.1 path treated native `npm` stderr as fatal despite the command's exit status being authoritative.

**Root cause:** PowerShell error-stream behavior and native process exit semantics were conflated.

**Blast radius searched:** the reviewed Web build commands that invoke npm under Windows PowerShell 5.1.

**Why preflight missed it:** the failure depended on the exact shell/runtime behavior rather than only application logic.

**Corrective change:** preserve global fail-closed behavior while handling non-fatal native stderr only inside the reviewed npm commands; keep npm exit codes authoritative.

**Permanent guard:** Windows PowerShell 5.1 regression probe in the accepted correction.

**Future prevention rule:** when wrapping native tools, test both exit-code and stderr behavior under the exact production/CI shell before declaring the wrapper portable.

**Dependency/tooling knowledge change:** shell semantics are part of the toolchain contract, not incidental implementation detail.

---

## FL-003 — Runtime probes must bind their source root explicitly

**Date:** 2026-08-12  
**Reference:** accepted WP15 correction PR #295  
**Symptom:** an archived runtime session probe could resolve/import the wrong application source when started from an arbitrary current working directory.

**Root cause:** implicit CWD/module-resolution assumptions leaked into a recovery/acceptance probe.

**Blast radius searched:** archived application source binding, bootstrap exit behavior and arbitrary-CWD execution.

**Why preflight missed it:** the happy path used the expected repository working directory and did not initially exercise an arbitrary CWD.

**Corrective change:** bind the probe to the archived application source root before importing Omni-CIO modules and use a bounded bootstrap exit code.

**Permanent guard:** arbitrary-CWD regression test added by the accepted correction.

**Future prevention rule:** recovery/deployment/evidence scripts must never rely on caller CWD for authoritative source selection; source identity/path must be explicit and testable.

---

## FL-004 — OWNER instructions must not require page discovery

**Date:** 2026-08-16  
**Scope:** V10-wide OWNER handoff policy  
**Symptom:** an OWNER prerequisite was described as a navigation path such as opening GitHub settings/billing without first giving a direct official page link and without making the exact target/result sufficiently explicit.

**Root cause:** the engineering handoff format optimized for the engineer's mental model of the provider UI instead of the OWNER's need for a deterministic, non-ambiguous action path.

**Blast radius searched:** all future GitHub, Cloudflare, broker, domain, billing, consent, account, provider and browser-only OWNER handoffs.

**Why preflight missed it:** OWNER instruction quality was documented informally but was not yet a machine-checked engineering-governance contract.

**Corrective change:** add `V10_OWNER_ACTION_HANDOFF_STANDARD.md` and require direct official links when stable, exact scope, expected result, STOP conditions, do-not-do warnings and minimum safe return.

**Permanent regression/guard:** engineering quality contract v2 + governance validator + tests reject removal of the direct-link requirement or acceptance of generic navigation as sufficient.

**Future prevention rule:** the OWNER must never be asked to discover the destination page; engineering verifies the current official UI/docs first and supplies the safest exact starting link.

**Dependency/tooling knowledge change:** provider UI/navigation is temporally unstable and is treated as a current-source dependency before click instructions are issued.

---

## FL-005 — Local V10 rendering is not Render.com hosting

**Date:** 2026-08-16  
**Scope:** V10 runtime/hosting boundary  
**Symptom:** discussion of an empty/new Render.com workspace risked implying that V10 should be hosted or configured there, while the OWNER's intended V10 model is the free self-hosted Lenovo/replacement Personal Node.

**Root cause:** the word `Render` was allowed to blur two distinct concepts: rendering/building/serving the V10 Web locally versus the commercial Render.com hosting service retained for the protected V9 baseline.

**Blast radius searched:** V10 Web deployment, WP22A access transport, service-selection recommendations, recurring-cost decisions, private-state custody and V9 rollback.

**Why preflight missed it:** the accepted browser-only amendment preserved the V9 Render.com boundary but did not state strongly enough that a new Render.com workspace is not a V10 hosting target.

**Corrective change:** formally bind V10 Web/API runtime to the approved Personal Node and classify external-access providers as access/security transport rather than application/private-state hosting.

**Permanent regression/guard:** engineering quality contract v2 rejects Render.com as the V10 runtime target and requires the protected V9 `app:app` Render baseline to remain intact until its owning parity/decommission gate.

**Future prevention rule:** do not create, pay for, configure or recommend a new Render.com V10 service without a later OWNER-approved amendment proving that the Personal-Node model cannot satisfy the owning requirement.

**Dependency/tooling knowledge change:** hosted deployment convenience is not sufficient justification to move V10 runtime or private state off the Personal Node.

---

## FL-006 — Zero-budget hard stop is a CI-routing constraint, not a merge bypass

**Date:** 2026-08-16  
**Scope:** V10 GitHub Actions cost control / hosted CI routing  
**Symptom:** GitHub-hosted Fast/Toolchain jobs repeatedly failed before any substantive step, while GitHub reported a payment/spending-limit blocker. The OWNER then supplied a direct browser screenshot of `Billing & licensing → Budgets and alerts` showing the personal GitHub Actions product budget at **USD 0** and **Stop usage = Yes**.

**Root cause:** the current external GitHub account state contains a hard zero-dollar Actions budget. GitHub's budget semantics can block metered hosted usage when the configured hard budget is exhausted/reached. The earlier CI process knew the annotation was infrastructure/billing-related but had not yet bound the concrete account budget state into the engineering cost-control model.

**Blast radius searched:** all future GitHub-hosted Ubuntu/Windows V10 jobs, fast feedback, disposable clean-room checks, dependency/maintenance PRs, governance PRs and any workflow whose applicability would create a guaranteed hosted RED while the hard-stop state remains.

**Why preflight missed it:** CI logic treated hosted capacity availability as an environmental assumption and only observed the generic GitHub startup annotation. The exact OWNER-controlled budget state had not yet been verified directly.

**Corrective change:** create `docs/operations/V10_CI_COST_CONTROL_STANDARD.md`; record the zero-budget state as a mutable external observation; require engineering to prefer already-paid/zero-cost/self-hosted equivalent validation before requesting paid capacity; forbid silently increasing budget or disabling the hard stop; keep RED applicable checks merge-blocking.

**Permanent regression/guard:** engineering quality contract now contains an explicit `ci_cost_control` boundary; repository agent instructions prohibit implicit spend/budget mutation; deterministic tests verify the cost-control contract and standard.

**Future prevention rule:** before a final PR cycle, detect whether a known budget-blocked hosted workflow will be applicable. Do not intentionally generate predictable RED. Either preserve the required verification semantics through an accepted zero-cost/self-hosted route, correct genuinely non-applicable workflow routing, or stop at an explicit OWNER cost decision if paid hosted clean-room execution is truly indispensable.

**Dependency/tooling knowledge change:** GitHub billing/budget state is a mutable external dependency. It must be reverified when relevant; it is neither code evidence nor permanent architecture authority.

---

## FL-007 — Formatting preflight must cover the exact authoritative scope

**Date:** 2026-08-16  
**Reference:** governance PR #322  
**Symptom / failing gate:** the first authoritative Lenovo cycle reached `Run protected runtime static quality`; Ruff lint passed, but `ruff format --check` rejected three newly changed governance guard files before mypy/tests/security stages could execute.

**Root cause:** the branch was treated as ready for expensive exact-head validation after source/logic review without first reproducing the authoritative formatter scope over every changed Python guard file.

**Blast radius searched:** all Python files introduced or modified by the governance PR, plus the authoritative formatter command and focused governance workflow. The failure was formatting-only; no lint defect or protected-runtime semantic failure was reported by the failed cycle.

**Why preflight missed it:** pre-CI review checked logic, action pins, workflow routing and syntax but did not execute the exact `ruff format --check` surface used by the authoritative gate. That violated the preflight discipline the amendment itself is intended to enforce.

**Corrective change:** apply Ruff-compatible formatting to all three files identified by the authoritative log; do not weaken, narrow or skip the formatter gate. Any new commit invalidates the old failed/green evidence and requires a fresh exact-head cycle.

**Permanent regression/guard:** the authoritative static-quality stage already fail-closes on repository formatter drift, while the new PR/WP governance templates require format/lint preflight before expensive CI. This ledger entry makes the failure mode explicit for future agents.

**Future prevention rule:** before opening or refreshing a final CI cycle, run the exact authoritative formatter scope (or a provably equivalent superset) over all changed Python sources. A known formatter mismatch blocks the expensive cycle until fixed.

**Dependency/tooling knowledge change:** Ruff formatting is part of the deterministic CI contract, not cosmetic post-processing; formatter version/scope must match the repository lock and authoritative workflow.

---

## FL-008 — Windows CI must use the canonical Windows dependency projection

**Date:** 2026-08-16  
**Reference:** governance PR #322  
**Symptom / failing gate:** during an intermediate attempt to evaluate Lenovo as the live V9 authority route, the Windows dependency-install step failed before the read-only live probe could run. The canonical POSIX runtime lock attempted to build `uvloop`, which is unsupported on Windows. The later FL-012 finding supersedes the assumption that this Lenovo route was evidence-equivalent for deployed-live acceptance.

**Root cause:** the runner OS was changed from GitHub-hosted Linux to self-hosted Windows without changing the dependency-install projection at the same time.

**Blast radius searched:** every workflow moved between runner operating systems, especially self-hosted Windows jobs that install runtime or development locks; the canonical `windows_ci_lock.py` projection and existing accepted Windows workflows were reviewed as the established solution.

**Why preflight missed it:** the zero-budget routing review focused on applicability, runner choice, secrets and merge semantics but did not include an OS-transition audit of every platform-sensitive dependency/toolchain command.

**Corrective change:** use `scripts/windows_ci_lock.py` whenever an accepted Windows workflow legitimately projects the canonical POSIX runtime lock to Windows. For the live V9 deployed-authority probe specifically, this intermediate Windows route was later removed after FL-012 proved the network vantage point non-equivalent.

**Permanent regression/guard:** preserve the general platform-transition rule: a Windows runner must use the reviewed Windows dependency projection where required. FL-012 is authoritative for the separate live-evidence routing decision and forbids treating the Personal Node as equivalent deployed-live evidence.

**Future prevention rule:** any runner-OS change requires an explicit audit of dependency locks, shell syntax, tool bootstrap, path semantics and platform-only packages before the expensive exact-head cycle.

**Dependency/tooling knowledge change:** the repository already owns the platform compatibility boundary: `windows_ci_lock.py` excludes non-Windows runtime packages such as `uvloop` while preserving the canonical lock as source authority.

---

## FL-009 — Self-hosted PowerShell steps must respect the node execution policy

**Date:** 2026-08-16  
**Reference:** governance PR #322  
**Symptom / failing gate:** while diagnosing repeated `LIVE_HTTP_RETRY_EXHAUSTED` results from the newly self-hosted live V9 authority lane, a bounded provider wake-up step failed before making any HTTP request. GitHub generated a temporary `.ps1` for `shell: powershell`, and the Lenovo node rejected that temporary script because script execution is disabled by its Windows PowerShell execution policy.

**Root cause:** the workflow used GitHub's implicit PowerShell script-file shell on a protected self-hosted node whose established repository convention is to invoke reviewed `.ps1` files explicitly with `powershell.exe -NoProfile -ExecutionPolicy Bypass -File ...`. The new diagnostic/warm-up path did not reuse that established execution boundary.

**Blast radius searched:** all self-hosted Windows workflow steps that select `shell: powershell`, all reviewed infrastructure/operations PowerShell entrypoints, and the live-authority workflow's newly added provider-readiness stage. Existing accepted Windows automation predominantly uses explicit reviewed script entrypoints where policy bypass is deliberate and bounded.

**Why preflight missed it:** the first warm-up change was reviewed for network scope, endpoint allowlisting, time bounds and secret safety, but it was not tested against the exact execution-policy posture of the Lenovo runner before the workflow cycle.

**Corrective change:** move the warm-up logic into a source-controlled reviewed PowerShell entrypoint and invoke it through the repository's established explicit execution-policy boundary while diagnosing the route. This made the diagnostic trustworthy enough to classify the deeper network-path failure; the temporary warm-up implementation was subsequently removed once the route proved non-equivalent.

**Permanent regression/guard:** the failure class remains recorded here and self-hosted workflow review must treat PowerShell execution policy as part of the runner contract.

**Future prevention rule:** on protected self-hosted Windows nodes, do not assume GitHub's temporary PowerShell shell scripts are executable. Prefer a source-controlled reviewed `.ps1` entrypoint invoked through the repository's established explicit-bypass boundary, and test that shell path before the expensive exact-head cycle.

**Dependency/tooling knowledge change:** Windows PowerShell execution policy is part of the self-hosted runner contract. A change from hosted runners or `cmd` to implicit `shell: powershell` is a platform-boundary change that requires explicit preflight.

---

## FL-010 — Windows cleanup must not depend on implicit Bash PATH

**Date:** 2026-08-16  
**Reference:** governance PR #322  
**Symptom / failing gate:** the Fast frontend applicability job completed its Node/npm version checks, fixture typecheck/lint/tests/build and product Web typecheck/lint/tests/build and dependency audit successfully, then failed only in its always-run cleanup because `shell: bash` could not resolve `bash` on that self-hosted Windows job.

**Root cause:** the route and policy jobs explicitly bootstrap Git for Windows into `GITHUB_PATH`, but the frontend job does not run that bootstrap. The cleanup step therefore depended on PATH state established in other jobs, even though GitHub Actions jobs do not share job-local environment mutations.

**Blast radius searched:** all cleanup-only Bash uses in the self-hosted Fast PR workflow and other newly re-routed Windows jobs. Cleanup commands here are plain Git commands and require no Bash semantics.

**Why preflight missed it:** substantive frontend commands were validated, while the `if: always()` epilogue was treated as incidental boilerplate instead of part of the job-local toolchain contract.

**Corrective change:** run the routing, policy and frontend workspace cleanup steps under native `cmd` on Windows. Keep Bash only where the same job has explicitly bootstrapped it and Bash semantics are required.

**Permanent regression/guard:** `check_v10_ci_cost_control.py` and its deterministic governance tests require the three Fast PR cleanup steps to use `shell: cmd`.

**Future prevention rule:** every Actions job must be self-sufficient. Never rely on PATH/tool initialization from another job; validate `always()` cleanup and failure epilogues under the exact shell/tool state of the job that owns them.

**Dependency/tooling knowledge change:** Git for Windows may be installed while `bash.exe` is not yet addressable through a given job's PATH. Job-local `GITHUB_PATH` mutations do not cross job boundaries.

---

## FL-011 — PowerShell failure reporting must preserve intended exit codes

**Date:** 2026-08-16  
**Reference:** governance PR #322  
**Symptom / failing gate:** the bounded live V9 wake-up stage correctly failed after the protected endpoint did not become healthy inside the reviewed window, but the job reported process exit code `1` instead of the intended classified exit code `41`.

**Root cause:** the script set `$ErrorActionPreference = "Stop"` and then called `Write-Error` immediately before `exit 41`. Under that policy `Write-Error` is terminating, so control never reached the explicit `exit` statement.

**Blast radius searched:** all newly added PowerShell fail paths in the live-authority warm-up and the repository pattern for scripts that intentionally return bounded numeric status codes. No secret-bearing diagnostic output is required for this failure class.

**Why preflight missed it:** the script was reviewed for fail-closed behavior but the exact error-stream interaction with `$ErrorActionPreference = "Stop"` was not exercised before the live run.

**Corrective change:** centralize failure termination in a helper that writes only a sanitized classification through the process error stream and then executes the intended numeric `exit`. This allowed the next diagnostic cycle to report the real network-path state without leaking provider/private details.

**Permanent regression/guard:** preserve the lesson here for any PowerShell script that owns an explicit process-code contract; the temporary live warm-up script was removed after the non-equivalent route was classified.

**Future prevention rule:** when a PowerShell script owns an explicit process exit-code contract, do not place a potentially terminating PowerShell error cmdlet before the `exit`; test the actual process code under the same error-action policy used in CI.

**Dependency/tooling knowledge change:** PowerShell error-stream semantics can preempt explicit exit-code semantics. Process-status contracts must be tested as process behavior, not inferred from source order.

---

## FL-012 — External live evidence cannot be moved to a non-equivalent network path

**Date:** 2026-08-16  
**Reference:** governance PR #322  
**Symptom / failing gate:** after the live V9 authority probe was made executable on Lenovo and its Windows/platform defects were corrected, a bounded exact-head diagnostic still failed. The sanitized result was `dns=OK`, `tcp443=TIMEOUT`, `http=WEB_ConnectFailure`: the Personal Node could resolve the protected Render host but could not establish the public HTTPS path required by the live probe.

**Root cause:** the zero-budget routing change assumed that a self-hosted Personal Node was semantically equivalent to the former independent GitHub-hosted network observer. It is not. Deterministic source checks can move to Lenovo, but deployed external-authority evidence depends on an independent reachable network path.

**Blast radius searched:** scheduled/public runtime probes, provider health/availability checks, future external-access acceptance, all CI routing changes that replace a hosted observer with the Personal Node, and V9 production acceptance requirements.

**Why preflight missed it:** the initial cost-control review classified runner cost and operating-system/tooling differences but did not make external network-observer independence an explicit routing dimension.

**Corrective change:** remove the non-equivalent Lenovo live probe. Preserve real `Live Gateway Authority Acceptance` as a manual GitHub-hosted workflow, suspend automatic live execution while the trusted hosted route is budget-blocked, and add a separate self-hosted `V10 Live Gateway Authority Contract` that validates routing/non-fabrication without claiming deployed live PASS. Record current evidence as `DEFERRED_NO_TRUSTED_ZERO_COST_ROUTE_NOT_PASS`.

**Permanent regression/guard:** the machine quality contract, CI cost-control guard, live acceptance runbook and focused tests now require the actual live probe to remain hosted/manual while deferred, forbid the Personal Node from masquerading as equivalent live evidence, and require missing live evidence to block any V9 runtime/deployment/Action-authority release that owns production acceptance.

**Future prevention rule:** before moving any external acceptance job between runners, identify whether the runner's network location/identity is part of the evidence semantics. If it is, a cheaper runner is acceptable only after equivalence is proven; otherwise classify the evidence as unavailable/deferred rather than fabricate success.

**Dependency/tooling knowledge change:** network vantage point is part of some acceptance contracts. DNS success does not imply HTTPS reachability, and increasing cold-start retries cannot repair a TCP path that is not available from the chosen observer.

---

## FL-013 — Test runner must match the test discovery model

**Date:** 2026-08-16  
**Reference:** governance PR #322  
**Symptom / failing gate:** `V10 Live Gateway Authority Contract` passed its routing/cost guard and then failed in `Verify tracked live-authority assets` because `python -m unittest tests.test_live_acceptance_repository_assets` discovered **zero tests** and exited non-zero. The module contains pytest-style top-level `test_*` functions, not `unittest.TestCase` methods.

**Root cause:** the workflow command and the test module's discovery model were inconsistent. Static review verified that the expected command string existed, but did not prove that the exact command could discover and execute a positive number of checks.

**Blast radius searched:** focused governance workflows, lightweight source-contract checks, and other places where `unittest` may be invoked against pytest-style function modules or where a CI step asserts a test command without executing the same discovery path during preflight.

**Why preflight missed it:** the test assertions were reviewed and run under broader pytest surfaces, while the exact lightweight workflow command was not reproduced independently before the final exact-head cycle.

**Corrective change:** make the repository-asset module executable with a dependency-free `main()` that explicitly invokes all three contract checks, and run that file directly from the lightweight workflow. Pytest can still collect the same `test_*` functions in broader suites.

**Permanent regression/guard:** `check_v10_ci_cost_control.py` requires the exact standalone command, and the module's direct execution reports the number of checks actually run. The self-test also asserts that the workflow uses this executable contract path.

**Future prevention rule:** whenever a focused CI lane uses a lightweight test runner, preflight the exact command and require positive discovery/execution evidence; do not infer runner compatibility from file names or function names alone.

**Dependency/tooling knowledge change:** pytest function discovery and `unittest` class discovery are different execution contracts. Test-runner selection is part of CI harness semantics, not interchangeable syntax.

---

## FL-014 — Workflow policy tests must distinguish references from execution

**Date:** 2026-08-16  
**Reference:** governance PR #322  
**Symptom / failing gate:** the authoritative protected Regression Shield reached the full pytest suite and reported one failure after 2,099 passing tests. The failing governance assertion rejected the string `check_live_gateway_authority.py` anywhere in the self-hosted routing workflow, even though the only occurrence was a legitimate `pull_request.paths` source reference used to retrigger the routing contract when the real hosted probe changes.

**Root cause:** a negative whole-file substring assertion conflated workflow metadata/source references with executable commands. The safety requirement is that Lenovo must not execute the deployed-live probe, not that the filename can never appear in the workflow document.

**Blast radius searched:** governance and workflow-policy tests that use broad negative substring assertions over complete YAML/text files, especially where the same file/function name can legitimately appear in `paths`, comments, documentation or test metadata without being executed.

**Why preflight missed it:** the dedicated live-routing workflow had already validated the intended non-fabrication contract, but the exact full-suite assertion semantics were not independently challenged with the legitimate path-filter case before the expensive authoritative cycle.

**Corrective change:** preserve the `pull_request.paths` dependency and narrow the negative test to executable command forms (`python scripts/check_live_gateway_authority.py` and the Windows path equivalent). No workflow safety boundary or routing behavior was weakened.

**Permanent regression/guard:** the focused test now documents the distinction explicitly and fails only if the real hosted probe is actually invoked from the Lenovo routing workflow. Future policy tests should prefer parsed/anchored execution semantics over naive whole-document token absence when metadata can contain the same identifier.

**Future prevention rule:** when a safety contract says “must not execute X,” test execution syntax/AST/YAML structure rather than banning every textual reference to X. Broad substring bans are acceptable only when the contract truly forbids the identifier everywhere.

**Dependency/tooling knowledge change:** GitHub Actions `pull_request.paths` entries are trigger metadata, not job execution. Source-coupling in a path filter may be required precisely so policy contracts rerun when the guarded implementation changes.

---

## FL-015 — Provider ZIP lock and installed-content lock are different checksums

**Date:** 2026-08-16  
**WP / PR / reference:** WP22A / PR #321 / focused Clientless Access Audit #67  
**Symptom / failing gate:** the exact Cloudflare provider 5.22.0 Windows ZIP was found in the reviewed filesystem mirror and OpenTofu installed it, but `init -lockfile=readonly` warned that the dependency lock wanted augmentation and the subsequent `validate` rejected the unpacked cached provider as not matching the lock.

**Root cause:** the committed provider lock contained the reviewed `zh:` checksum of the original publisher ZIP but no matching `h1:` content checksum for the installed/unpacked package representation used by OpenTofu 1.12. The provider version, Windows ZIP SHA-256 and mirror layout were correct; the lock representation was incomplete for readonly offline validation.

**Blast radius searched:** the shared WP22A OpenTofu bootstrap/validation boundary, Phase-A schema validation, later Phase-B provider execution using the same pinned provider identity, registry fallback behavior, source-lock mutation risk and Windows package/platform selection.

**Why preflight missed it:** source review and tests proved the exact release asset hash, mirror layout and provider address, but did not reproduce OpenTofu 1.12's installed-package checksum semantics on the protected Windows runner before the expensive exact-head cycle.

**Corrective change:** keep the committed `zh:` value as the reviewed publisher-ZIP trust anchor. In an isolated temporary copy only, derive the matching `h1:` with `tofu providers lock -fs-mirror=... -platform=windows_amd64`, then run `init -lockfile=readonly` and `validate`. Verify the source lock SHA before/after and fail if it changes.

**Permanent regression/guard:** focused WP22A tests require the exact filesystem-mirror lock derivation, Windows platform binding, derived `h1:` presence, source-lock immutability check, readonly init, exact trusted `zh:` anchor and explicit direct-registry exclusion. The IaC toolchain decision records the failure class and remedy.

**Future prevention rule:** when validating a provider from an offline/explicit mirror, test both the publisher archive trust anchor and the installed-content checksum model under the exact IaC CLI version/platform. Do not fix checksum-model mismatches by disabling readonly locks, deleting checksums or allowing registry fallback.

**Dependency/tooling knowledge change:** `zh:` authenticates an original provider ZIP while `h1:` authenticates package contents and is the portable form used for installed/unpacked provider verification. OpenTofu 1.12 may need the corresponding `h1:` even when the exact trusted ZIP is already pinned.

---

## FL-016 — Public provider checksums must not be duplicated as secret-shaped literals

**Date:** 2026-08-17  
**WP / PR / reference:** WP22A / PR #321 / authoritative Self-Hosted Windows CI #1425  
**Symptom / failing gate:** all authoritative compile/static/type/tests/dependency/SAST stages passed, but the final tracked-content secret scan rejected `scripts/validate_wp22a_terraform.ps1` because a duplicated 64-hex provider checksum was classified as `Hex High Entropy String`.

**Root cause:** the validator copied the same public provider ZIP SHA-256 already owned and verified by the provider bootstrap into a second standalone literal. The literal was not a secret, but its representation was intentionally indistinguishable from secret-shaped high-entropy material to the repository scanner.

**Blast radius searched:** WP22A provider bootstrap, Terraform/OpenTofu validator, committed provider lock, focused provider-lock regression tests, detect-secrets policy and unrelated workflow routing that appeared as skipped on the same PR.

**Why preflight missed it:** provider integrity review concentrated on cryptographic trust continuity and offline lock semantics. The changed PowerShell surface was not independently run through the exact tracked-content secret scan before the expensive authoritative cycle.

**Corrective change:** retain the reviewed provider SHA-256 only in the bootstrap trust boundary, where the downloaded archive is authenticated. The validator now hashes that already-authenticated archive and compares the committed `zh:` lock against the derived value, removing the duplicate standalone high-entropy literal without adding a scanner exception or weakening integrity. The unrelated WP5 evidence workflow is also narrowed to WP5-owned Windows paths so WP22A changes no longer create a misleading skipped check.

**Permanent regression/guard:** focused WP22A regression coverage rejects any standalone quoted 64-hex checksum in the validator, requires the archive-derived lock comparison and verifies that the WP5 evidence workflow no longer routes the entire Windows infrastructure tree.

**Future prevention rule:** before final authoritative CI, run the exact secret-scan policy over all changed tracked text. Public checksums may remain as reviewed trust anchors, but do not duplicate them into additional secret-shaped literals when a verified artifact can carry the trust value forward.

**Dependency/tooling knowledge change:** secret scanners classify representation, not business meaning. A public checksum can be a legitimate false positive; the preferred repair is to remove redundant secret-shaped representation rather than broadly allowlist or disable the detector when trust semantics can stay equally strong.

---

## FL-017 — Self-hosted authority bootstrap must not depend on codeload Action preparation

**Date:** 2026-08-17  
**WP / PR / reference:** V10 CI maintenance / PR #328 / blocker discovered while validating PR #327  
**Symptom / failing gate:** multiple exact-head self-hosted workflows failed before repository tests executed. GitHub annotations reported HTTP 429 and 503 while preparing pinned `actions/checkout` and `actions/upload-artifact` content from the GitHub Actions download path.

**Root cause:** the mandatory Lenovo authority plane had a shared external Action-preparation dependency before project-owned validation could begin. A pinned SHA protects action identity, but it does not make the action archive transport available or reliable.

**Blast radius searched:** Engineering Governance, Fast PR, Toolchain Compatibility, Self-Hosted Windows authority, active Live Gateway Authority routing contract, path-triggered WP6 identity audit, WP15 deterministic Web support, WP16-WP22A Web gates and post-merge Regression Shield. Historical OWNER physical-evidence workflows and GitHub-hosted release provenance were classified separately rather than bulk-rewritten.

**Why preflight missed it:** external Action preparation had been treated as trusted CI plumbing rather than an availability dependency of the mandatory self-hosted authority plane. Initial correction also focused too narrowly on `actions/checkout` until a separate failure showed `actions/upload-artifact` used the same failure domain.

**Corrective change:** replace external checkout preparation in the current generic self-hosted authority plane with source-controlled exact-SHA Git bootstrap using `contents: read`; remove external artifact transport from that mandatory plane and keep authoritative diagnostics/results in project tests, GitHub logs and job summaries.

**Permanent regression/guard:** `tests/test_v10_ci_action_download_resilience.py` enumerates the active self-hosted authority workflows and rejects reintroduction of `actions/checkout` or `actions/upload-artifact`; Engineering Governance runs that guard on PRs and the full authoritative/post-merge test suite collects it again.

**Future prevention rule:** before adding an external Action to a mandatory self-hosted authority job, classify whether its download/initialization occurs before project checks and whether failure would create a shared pre-test single point of failure. Identity pinning and transport resilience are separate requirements.

**Dependency/tooling knowledge change:** self-hosted Actions still depend on GitHub-hosted Action distribution. A full-SHA pin constrains code identity but does not eliminate codeload/network rate-limit or availability failure modes.

---

## FL-018 — Headless Windows Git bootstrap must fail closed without inherited credential interactivity

**Date:** 2026-08-17  
**WP / PR / reference:** V10 CI maintenance / PR #328  
**Symptom / failing gate:** after external Action checkout was removed and the Lenovo service was confirmed online/assigned, a manual `git fetch` remained in progress at repository bootstrap instead of reaching project checks. After the headless credential correction, Engineering Governance then exposed a second contract-drift symptom because its validator still required the old `actions/checkout`-specific `persist-credentials: false` marker.

**Root cause:** a persistent Windows service account may inherit Git/Git Credential Manager helper configuration capable of interactive prompting. The first manual bootstrap appended a job-token helper but did not reset inherited helpers or disable terminal/GCM interactivity. Separately, one governance validator expressed the security intent through an implementation-specific checkout marker rather than through the actual credential properties.

**Blast radius searched:** every active generic self-hosted authority bootstrap, current credential-helper usage, Git Bash first-step availability, exact-SHA verification, cleanup shells, Engineering Governance and CI cost-control validators. Pre-CI diff review also caught and restored the accepted FL-010 native-`cmd` cleanup contract before final acceptance.

**Why preflight missed it:** manual Git fetch was initially reasoned about as a repository/network operation, not as a composition of system/global/local credential-helper layers under a headless service identity. The stale validator was not exercised until the replacement bootstrap had already passed its first real runner execution.

**Corrective change:** set `GIT_TERMINAL_PROMPT=0` and `GCM_INTERACTIVE=0`; reset inherited helper resolution with an empty local `credential.helper`; append only the temporary job-scoped GitHub-token helper; remove all local helper entries immediately after fetch; verify exact reviewed/event SHA; update governance validators to require these semantic properties rather than `persist-credentials: false`.

**Permanent regression/guard:** the repository-wide resilience test requires the non-interactive environment, helper reset/add/unset sequence, `contents: read`, clean workspace, and exact-SHA verification across the active self-hosted authority set. Engineering Governance and cost-control guards additionally preserve the accepted native Windows cleanup semantics and the separation between the self-hosted live routing contract and the actual hosted V9 live probe.

**Future prevention rule:** headless CI must never rely on an inherited interactive credential chain. Express security guards in terms of the property being protected—least privilege, no persistent credentials, no prompt, exact source identity—not in terms of one helper Action's configuration syntax.

**Dependency/tooling knowledge change:** Git can compose credential helpers across configuration scopes; Git Credential Manager interaction is enabled unless explicitly disabled. Headless build/service environments should fail when interaction is required rather than wait for an invisible prompt.

---

## FL-019 — Deployment retries must distinguish repeatable reads from ambiguous mutations

**Date:** 2026-08-25

**WP / reference:** WP22A Phase 4 deployment run `32828381444`, job `97741349681`, exact accepted main `ef8db1e`

**Symptom / failing gate:** exact-main Regression Shield, the zero-charge provider boundary, the Neon Free/Frankfurt checks, migrations, runtime-role convergence and grants all passed. The job then paused for roughly one socket-timeout interval during `DATABASE_BOOTSTRAP_STAGE=SYNTHETIC_SEED`, stopped as `DATABASE_BOOTSTRAP_FAILED`, and an immediately following read-only Render diagnostic stopped as `RENDER_API_NETWORK_ERROR`. The already deployed preview remained available.

**Root cause:** a transient outbound network interruption on the self-hosted deployment node crossed two independent provider connections. The provisioner used a single long-lived bootstrap database connection and converted every database exception into one generic code. Provider API reads also made only one attempt, so the follow-up diagnostic could not recover or preserve the useful failure class.

**Blast radius searched:** Neon bootstrap connection establishment, migrations, runtime-role/grant mutation, synthetic preview seeding and verification, pooled runtime read-only verification, all Render/Neon API methods, the fallback Render diagnostic, secret-safe logging, provider billing boundaries and the existing live service. No evidence implicated repository tests, authentication/tenant code, provider credentials, paid-resource state or the previous accepted deployment.

**Why preflight missed it:** deterministic tests covered fail-closed provider status handling, idempotent runtime-role convergence and fixed stage evidence, but did not inject socket disconnects between database stages or into provider GET requests. The failure required the real self-hosted outbound network path.

**Corrective change:** isolate the synthetic seed onto a fresh PostgreSQL connection with a finite connection timeout; retry that stage only because both inserts use `ON CONFLICT DO NOTHING` and the stored canonical hashes are reverified after every attempt. Retry pooled runtime verification because it is read-only. Add bounded backoff to provider GET transport failures and the explicit transient HTTP allowlist `408/429/502/503/504`. Keep migrations, role/grant mutation, non-transient HTTP errors and all provider POST/PUT operations fail-closed without blind replay after an ambiguous response.

**Permanent regression/guard:** deterministic fault-injection tests now prove a three-attempt bound, fresh database connections, exact backoff, convergence after an ambiguous seed disconnect, no retry on seed drift, read-only runtime reconnection, GET-only transport and allowlisted transient HTTP retry, no retry for HTTP 500, no provider mutation replay and absence of URI/token/exception detail in emitted diagnostics. The Phase 4 workflow executes this suite before any provider mutation.

**Future prevention rule:** classify every retry boundary by idempotency and ambiguity before adding resilience. A network error is retryable only when the operation is a read or its convergence proof is explicit and tested; mutating provider calls remain stopped unless they carry a provider-supported idempotency key or are reconciled by an independent read.

**Dependency/tooling knowledge change:** PostgreSQL `INSERT ... ON CONFLICT DO NOTHING` plus post-write digest verification provides a safe convergence primitive for the fixed synthetic records. Psycopg connection failures are handled as `OperationalError` without logging raw exception text. Render documents transient outbound resets as an expected condition that clients should handle with bounded reconnect logic for safe repeatable operations.

---

## FL-020 — Authority replacement must close every producer and consumer contract

**Date:** 2026-09-24  
**WP / PR / reference:** TIMEWEB-PLATFORM-CONSOLIDATION TW-B / PR #584 / Amendment 19

**Symptom / failing gate:** the new GitHub-hosted Timeweb WP17 source-security check
passed, but WP17 Application Shell and WP15 Live Web Support both failed the same
historical READ-vault test. Fast and authoritative gates also found formatter drift in
the newly added Amendment-19 guard/test. WP17 later confirmed a third formatting drift
in `scripts/check_v10_wp17_web_security.py` after all preceding Web, browser and npm-audit
steps had passed.

**Root cause:** the active workflow producer was correctly replaced, but directly coupled
consumers were not closed in the same coherent batch. The WP17 contract, Web-security
guard and local-vault regression still encoded OWNER/Admin exact-head Windows ACL proof
as a current Timeweb acceptance dependency. A second-order false RED also showed that
the Timeweb current-guidance validator had coupled the required meaning to the literal
`Amendment 18 CURRENT-AUTHORITY OVERRIDE` heading instead of the durable authority
semantics.

**Blast radius searched:** active/historical WP17 workflows, local DPAPI provisioner/
finalizer/auditor, WP17 machine contract and security guard, WP15 live-support consumer,
Timeweb hosted runtime, no-OWNER-laptop guard, broker credential mutation endpoints,
Timeweb provider inventory and current operator runbooks.

**Why preflight missed it:** the first Amendment-19 correction proved the new workflow
and runtime negative dependency but did not enumerate every test/contract/runbook that
consumed the old workflow semantics. CI therefore became the first place the stale
consumer assertion was executed.

**Corrective change:** explicitly separate current Timeweb hosted custody from historical
local DPAPI custody in the WP17 contract; keep hosted broker mutation disabled; move
Windows ACL workflow assertions to the manual historical workflow; update the WP17
security guard and runbooks; strengthen the no-OWNER-laptop regression; normalize the
new Python files and the WP17 security guard to the pinned Ruff format.

**Permanent regression/guard:** the Timeweb no-OWNER-laptop guard now verifies the active
WP17 contract, active WP17 security guard, hosted runtime, GitHub-hosted required workflow
and manual historical workflow as one graph. Historical DPAPI/ACL unit/security coverage
remains intact rather than being deleted or suppressed.

**Future prevention rule:** when replacing an authority producer, enumerate and update
all consumers, validators, tests, runbooks and status contracts before publishing the
replacement checkpoint. Document guards must validate durable semantic markers rather
than amendment-number-specific prose when later accepted amendments may extend the same
authority. A passing new producer does not prove the old authority has
ceased to be a hidden prerequisite.

**Dependency/tooling knowledge change:** a required-check name may be preserved for
branch-protection continuity while its implementation authority changes, but every
consumer must bind to the new semantics rather than infer them from the legacy check
name.

---

## FL-021 — Metadata references must not impersonate credential values

**Date:** 2026-09-24  
**WP / PR / reference:** TIMEWEB-PLATFORM-CONSOLIDATION TW-B / PR #584 / authoritative Windows gate #3188

**Symptom / failing gate:** compile, Ruff, formatting and mypy passed on the exact PR head, but the tracked-content secret scan rejected two new Timeweb no-OWNER-laptop metadata lines as `Secret Keyword` findings.

**Root cause:** a machine contract field that stores only the repository path of the hosted custody contract used a credential-shaped field name. The deterministic verifier duplicated the same field name. The secret scanner correctly classifies representation rather than business meaning, so both non-secret path references looked like credential assignments.

**Blast radius searched:** the Timeweb no-OWNER-laptop contract, its deterministic verifier and regression tests, the fail-closed secret-scan validator, all current PR patches for suppression/bypass patterns, current Timeweb runtime/auth/PostgreSQL authority and retired-provider archive references.

**Why preflight missed it:** the new contract/verifier pair was semantically reviewed and passed focused logic checks, but the exact tracked-content secret-scan policy was not applied to the final metadata vocabulary before publication.

**Corrective change:** rename the path-reference field to custody-oriented vocabulary in both producer and consumer, keep the referenced custody source unchanged, and add a regression test that freezes the exact runtime metadata key set. Do not add a scanner allowlist, exclusion or threshold change.

**Permanent regression/guard:** the existing fail-closed tracked-content secret scan remains unchanged. The Timeweb regression now requires the custody-reference metadata shape, so a future credential-shaped alias becomes an unexpected contract key and fails focused validation before merge.

**Future prevention rule:** use credential-sensitive words for actual secret values, secret bindings or deliberately protected boundaries; use `*_custody_*`, `*_reference` or `*_path` vocabulary for non-secret source/document references. Run the exact tracked-content secret scan on every final changed-text batch before external certification.

**Dependency/tooling knowledge change:** secret scanners intentionally reason from lexical representation and entropy rather than project semantics. The preferred repair for a legitimate non-secret finding is to make the representation unambiguous when possible, not to weaken the detector.

---

## FL-022 — Auth cookie policy changes must close every session-minting producer

**Date:** 2026-09-24  
**WP / PR / reference:** TIMEWEB-PLATFORM-CONSOLIDATION TW-B / PR #584 / exact-head RED repair

**Symptom / failing gate:** the Telegram-only Timeweb route emitted authenticated session and CSRF cookies with the accepted `SameSite=Strict` policy, but the shared provider-auth compatibility route still emitted those authenticated cookies as `SameSite=Lax`. The authoritative Regression Shield failed the provider-auth regression while the focused Telegram path looked correct. Fast PR also exposed formatter drift in the same regression file.

**Root cause:** the previous repair reviewed the current Timeweb Telegram composition but did not close every session-minting producer that remained executable/tested in the repository. The browser-proof cookie and authenticated product cookies have intentionally different cross-site requirements, so treating all OAuth-related cookies as one policy class allowed the weaker `Lax` value to survive in the generic producer.

**Blast radius searched:** current Telegram-only auth routes, the generic Telegram/VK compatibility route, browser cookie/CSRF policy, provider callback identity binding, hosted session bootstrap, frontend CSRF transport, WP17 application-shell contract and all changed tests that create or inspect authenticated cookies.

**Corrective change:** keep the short-lived OIDC browser-proof cookie `SameSite=Lax` for the provider redirect/callback flow; require `SameSite=Strict` for post-authenticated session and CSRF cookies in every product-session producer; reject a provider runtime that returns a verified identity for a provider different from the fixed callback route; normalize the regression file to pinned Ruff formatting.

**Permanent regression/guard:** provider-auth tests distinguish proof-cookie `Lax` from authenticated-cookie `Strict`, verify cryptographic CSRF binding and reject provider-identity mix-up before account/session binding. The accepted WP17 machine contract remains `browser_cookie_same_site=strict`.

**Future prevention rule:** any authentication/session policy change must search by authority operation, not only by current deployment imports: enumerate every `bind_session`, session-cookie emission, CSRF-cookie emission, provider callback and logout/revoke producer/consumer before publishing the checkpoint.

---

## FL-023 — Provider TLS termination is deployment evidence, not a source default

**Date:** 2026-09-24  
**WP / PR / reference:** TIMEWEB-PLATFORM-CONSOLIDATION TW-B / PR #584 pre-merge security audit

**Symptom / failing gate:** the new Timeweb source runtime unconditionally passed `trusted_edge_tls_terminated=True` before TW-C had selected and proven the network/private-ingress topology. That source assertion would make every internal HTTP request trusted as an HTTPS-terminated request once deployed.

**Root cause:** a provider-specific trust assertion from the historical hosted topology survived conceptually during provider-neutral extraction. Timeweb provides a managed application edge, but the accepted TW-B source stage does not yet prove that the application port has no alternate public ingress.

**Corrective change:** edge-TLS trust is now an explicit fail-closed runtime flag, false by default and invalid on unknown values. Plain HTTP is permitted only for `/livez` from a loopback peer so process liveness does not require weakening browser/API transport. TW-C may supply the trust flag only after provider-network evidence establishes the proxy boundary.

**Permanent regression/guard:** Timeweb tests prove default edge trust is false, malformed values fail closed, non-loopback HTTP `/livez` is rejected and current source no longer contains an unconditional trusted-edge assertion.

**Future prevention rule:** never infer trusted proxy/edge authority from a provider name. Bind it to explicit provider/network evidence and keep client-controlled forwarded headers outside the trust decision.

---

## FL-024 — Current hosted runtime must not import legacy broker stacks transitively

**Date:** 2026-09-24  
**WP / PR / reference:** TIMEWEB-PLATFORM-CONSOLIDATION TW-B / PR #584 pre-merge dependency audit

**Symptom / failing gate:** `apps/api/hosted_runtime.py` imported two generic PostgreSQL connection helpers from `apps/api/app.py`. Importing that module also imports gRPC, the T-Invest SDK and broker/live-acceptance modules even though the current Timeweb runtime exposes no broker authority.

**Root cause:** implementation reuse crossed an authority/dependency boundary. The reused behavior was provider-neutral PostgreSQL serialization, but its definition lived inside the legacy local/broker application composition.

**Corrective change:** extract the PostgreSQL serialization/autocommit adapter into `apps/api/postgres_web_connection.py`; re-export it from the legacy app for compatibility; make the Timeweb runtime import the neutral module directly.

**Permanent regression/guard:** Timeweb source tests forbid importing `apps.api.app` from the current runtime and verify the neutral adapter contains neither `grpc` nor `t_tech`. The platform inventory classifies the new adapter as current `KEEP`.

**Future prevention rule:** reuse behavior from the lowest authority-neutral layer. A current runtime must not import a higher-authority composition module merely to obtain a utility.

---

## FL-025 — Runtime readiness must detect privilege and RLS-policy drift

**Date:** 2026-09-24  
**WP / PR / reference:** TIMEWEB-PLATFORM-CONSOLIDATION TW-B / PR #584 pre-merge PostgreSQL security audit

**Symptom / failing gate:** the provider-neutral runtime probe verified PostgreSQL 18, role attributes, zero memberships, relation presence and FORCE RLS flags, but it did not prove the exact runtime grants, ownership boundary, PUBLIC grants, tenant-scope function or RLS policy expressions required by the hosted runtime contract.

**Root cause:** bootstrap-time least-privilege validation was stronger than runtime-start readiness. A later ACL or policy drift could therefore leave the process reporting READY with authority wider than the accepted contract.

**Corrective change:** startup readiness now compares exact table/routine grants including grantability, rejects PUBLIC table/routine/schema grants, verifies effective database/schema privileges, rejects database/schema/object ownership, verifies the tenant-scope function semantics and verifies the exact forced RLS policy set and expressions. SQL canonicalization preserves function-call and Boolean-grouping parentheses; only whitespace and one deparser-added outer policy wrapper are normalized. Sequence objects may exist in later migrations, but the runtime must have no effective USAGE/SELECT/UPDATE privilege on them.

**Permanent regression/guard:** focused runtime tests reject an extra table privilege and a modified tenant policy in addition to existing role/schema/FORCE-RLS negatives.

**Future prevention rule:** when a contract states `runtime_acl_match_required` or `tenant_boundary_match_required`, the live probe must verify the authority itself, not only the existence of objects that are supposed to enforce it.

---

## FL-026 — SQL test doubles must dispatch on the most specific query signature

**Date:** 2026-09-24  
**WP / PR / reference:** TIMEWEB-PLATFORM-CONSOLIDATION TW-B / PR #584 / exact head `f5a69c0fd34fc58ed9b79c0d13840a25c17a5c66`

**Symptom / failing gate:** the authoritative Regression Shield reported four failures in the new hosted PostgreSQL readiness tests. The production probe called the ownership query, but the fake connection returned the runtime-role tuple instead; converting the role name to `int` then raised `ValueError`. WP17/Fast PR also rejected two newly edited files on Ruff formatting.

**Root cause:** the fake SQL dispatcher matched the broad substring `FROM pg_catalog.pg_roles` before the ownership query's more specific `AS database_owned` signature. The ownership query legitimately contains nested `pg_roles` subqueries, so the broad branch shadowed the intended fake response. The same correction batch had also been published without reproducing the exact formatter scope.

**Blast radius searched:** every branch in `_RuntimeProbeConnection.execute`, every SQL statement emitted by `probe_hosted_runtime_database`, the authoritative PostgreSQL readiness tests, WP17 static-quality scope and Fast PR changed-file formatter scope.

**Why preflight missed it:** source review treated SQL substring dispatch branches as independent predicates and did not test overlap/precedence among them. Formatting was checked conceptually rather than by the exact pinned Ruff formatter before publishing the commit.

**Corrective change:** dispatch the specific ownership-query marker before the broad role-catalog marker, preserve the production probe unchanged, and apply the exact formatter output reported by CI to both affected Python files.

**Permanent regression/guard:** the positive readiness test now traverses the ownership branch successfully, while the existing negative ACL/RLS cases continue through the same fake. Future fake SQL dispatchers must order predicates from most specific to least specific or use exact normalized statement keys.

**Future prevention rule:** when a test double routes by substring, perform an overlap audit of all predicates before publication; when CI has an exact formatter gate, reproduce that formatter scope before creating the next exact-head checkpoint.

---

## Entry template

```text
## FL-NNN — Short failure-class title

Date:
WP / PR / reference:
Symptom / failing gate:
Root cause:
Blast radius searched:
Why preflight missed it:
Corrective change:
Permanent regression/guard:
Future prevention rule:
Dependency/tooling knowledge change:
```
---

## FL-027 — Runtime readiness must cover secondary PostgreSQL authority and schema invariants

**Date:** 2026-09-24  
**WP / PR / reference:** TIMEWEB-PLATFORM-CONSOLIDATION TW-B / PR #584 / pre-merge whole-branch audit

**Symptom / failing gate:** the exact-head CI and hosted readiness tests were GREEN while the runtime probe still had three blind spots: it rejected memberships held by the runtime role but did not inspect roles that were members of the runtime role; it compared table-level grants but did not inspect explicit column ACLs; and it checked auth/session relation existence without proving the security-critical FK/UNIQUE/CHECK constraints used for identity-to-tenant binding and one-time browser authorization.

**Root cause:** bootstrap-time PostgreSQL hardening and runtime-start readiness evolved independently. The canonical bootstrap SQL had stronger PostgreSQL 18 creator-membership semantics than the runtime probe, while the runtime probe treated exact table/routine grants and table existence as a sufficient proxy for the full authority/schema contract.

**Blast radius searched:** provider-neutral hosted PostgreSQL bootstrap SQL and contract, PostgreSQL 18 creator-edge rehearsal, product identity repository, session registry, durable provider-auth transaction store, current Timeweb runtime composition, tenant RLS policies, all runtime-role grants and the focused Timeweb hosted-runtime regression surface.

**Why preflight missed it:** current guards proved direct role grants, ownership, PUBLIC table/routine privileges and FORCE-RLS policy shape, but no regression mutated pg_auth_members on the granted-role side, created a column-specific ACL, or removed a critical account-plane constraint while leaving the relation present.

**Corrective change:** runtime readiness now permits at most the PostgreSQL 18 safe creator-admin membership shape (ADMIN=true, INHERIT=false, SET=false), rejects any wider/member drift, rejects explicit runtime/PUBLIC column ACLs, and verifies the named validated PK/UNIQUE/FK/CHECK constraints required for session scope, external identity scope and browser-auth replay protection.

**Permanent regression/guard:** focused tests cover the safe PostgreSQL 18 creator edge and fail closed on inherited member authority, column-level privilege drift and missing identity-scope constraints. The SQL test double is also dispatched through specific query handlers instead of one long overlapping conditional chain.

**Future prevention rule:** when bootstrap authority is strengthened, enumerate every catalog surface that can carry equivalent authority (pg_auth_members, object ACLs, column ACLs, ownership, constraints, policies) and make runtime readiness verify the same security class rather than only the most common representation.

**Dependency/tooling knowledge change:** PostgreSQL 18 records role-membership ADMIN, INHERIT and SET options in pg_auth_members; column-specific privileges live in pg_attribute.attacl, separately from ordinary table ACLs.

---

## FL-028 — Fake SQL dispatch must prefer specific catalog queries over nested broad markers

**Date:** 2026-09-24  
**WP / PR / reference:** TIMEWEB-PLATFORM-CONSOLIDATION TW-B / PR #584 / exact head `edd78c6f9f31f7b849c45b8d913fdcb72f186f47`

**Symptom / failing gate:** the column-ACL readiness query was correct, but Regression Shield produced seven focused failures because the test double interpreted a nested `FROM pg_catalog.pg_roles` subquery as the top-level role query.

**Root cause:** the dispatcher retained a broad role marker before more specific catalog-query markers. The representation changed while the prior substring-shadowing defect class survived.

**Blast radius searched:** every query emitted by `apps/api/hosted_database_runtime.py`, the focused Timeweb runtime fake and the prior FL-026 failure class. No production SQL defect was found from this failure.

**Why preflight missed it:** the new focused tests were not executed before the published verification head.

**Corrective change:** specific catalog markers precede the broad role fallback, and exact Ruff output from the completed verification batch is applied in the same correction.

**Permanent regression/guard:** the positive runtime probe traverses the column-ACL query and fails if broad role matching shadows it.

**Future prevention rule:** test SQL dispatchers are parsers; use the most specific match first and any broad fallback last.

---

## FL-029 — Process-only liveness requires database-session recovery

**Date:** 2026-09-24  
**WP / PR / reference:** TIMEWEB-PLATFORM-CONSOLIDATION TW-B / PR #584 / pre-merge recovery audit

**Symptom / failing gate:** no CI gate found this first. Timeweb correctly uses process-only `/livez`, but the runtime held one PostgreSQL session for the process lifetime. A broken session could leave liveness healthy while readiness, login and private API remained unavailable until restart.

**Root cause:** liveness/readiness separation was corrected for Timeweb, but the old hosted runtime single-session lifecycle was carried forward without an independent reconnect path.

**Blast radius searched:** hosted runtime startup, serialized request transactions, session registry, product identity repository, durable provider-auth transactions, health/readiness behavior and Timeweb localhost health semantics.

**Why preflight missed it:** tests covered startup, serialization and degraded readiness but never transitioned the underlying PostgreSQL session from healthy to closed while the process remained alive.

**Corrective change:** the serialized connection replaces only an already-closed session before a later operation. The reconnect factory reapplies autocommit and the full PostgreSQL 18 authority/schema/RLS probe. The failed operation itself is never replayed. Startup/reconnect attempts use a bounded connection timeout.

**Permanent regression/guard:** focused tests prove closed-session replacement and prove that a failed operation is surfaced once and is not automatically replayed before the next request.

**Future prevention rule:** when liveness excludes an external dependency, that dependency needs its own bounded recovery path. Never retry a write whose commit outcome may be unknown.


---

## FL-030 — Guard fixtures must mirror the guard's complete repository dependency set

**Date:** 2026-09-24  
**WP / PR / reference:** TIMEWEB-PLATFORM-CONSOLIDATION / V9C-B / PR #584 / superseded exact head `8aef5013439bb69d8feca846426fba5513f1feaf`

**Symptom / failing gate:** V10 Engineering Governance passed the real V9C-B convergence guard against the full repository but two negative unit tests errored with `FileNotFoundError` for `.github/workflows/v10-pr-fast-checks.yml` instead of reaching their intended fail-closed assertions.

**Root cause:** V9C-B expanded `_validate_verifier_ownership()` to read three current verifier workflows, while the temporary-repository test fixture copied only the original governance workflow and canonical documents. The guard dependency graph and its fixture dependency graph had diverged.

**Blast radius searched:** every V9C-B guard input, all negative tests using `_copy()`, the three verifier workflows, parity-ledger fixture data, the whole-tree legacy import scan and the current repository execution path. The real repository guard itself passed; no product/runtime semantic defect was found from this RED.

**Why preflight missed it:** the current-repository positive guard path had all files available, so it could not expose an incomplete isolated fixture. The dependency set was duplicated implicitly between production guard code and tests instead of being represented once.

**Corrective change:** define one canonical `_VERIFIER_WORKFLOW_RELATIVE_PATHS` tuple in the guard, derive verifier reads from it, and make the isolated fixture copy the same tuple.

**Permanent regression/guard:** the existing negative tests now traverse verifier ownership before reaching their intended parity/merge-authority failures. Any future verifier workflow dependency added to the canonical tuple is automatically included in the fixture.

**Future prevention rule:** a repository guard that reads additional files must expose its dependency set as data and test fixtures must consume that same data; never maintain a second manually duplicated dependency list.

**Dependency/tooling knowledge change:** none.


---

## FL-031 — Relocated legacy modules must satisfy the destination static-quality baseline

**Date:** 2026-09-24  
**WP / PR / reference:** TIMEWEB-PLATFORM-CONSOLIDATION / V9C-B / PR #584 / exact head `ce09e9149b261a1f9549aa98efadcc42e22aa9f9`

**Symptom / failing gate:** multiple otherwise unrelated WP workflows failed at the same repository-wide mypy invocation in `omni_cio/pretrade/purchase_capacity_v1.py`, while Fast PR and the authoritative merge gate independently reported Ruff-format drift across 20 relocated/current Python files.

**Root cause:** V9C-B moved behavior-preserving legacy modules into canonical typed/formatted V10 package paths, but the relocation checkpoint did not fully apply the destination package's static-quality contract. In `select_price()`, one local name represented both an always-present manual `Decimal` and a market-derived `Decimal | None`, causing incompatible mypy inference. Separately, `Decimal.as_tuple().exponent` retains a special-value union in its type even after the runtime finite-value check. The relocated files also preserved historical layout that differs from the pinned Ruff 0.16.1 formatter.

**Blast radius searched:** all exact-head failed workflow logs, every file reported by the changed-file Ruff formatter, all relocated V9C-B deterministic source targets, the purchase-capacity tests, and the whole-repository mypy consumers. The profile-specific WP tests reached static quality and converged on the same four mypy diagnostics rather than independent product failures.

**Why preflight missed it:** relocation parity focused on behavior/import convergence and whole-tree structural integrity. Those checks proved source presence, syntax and parity contracts, but did not certify the exact destination mypy/formatter baseline before publication.

**Corrective change:** apply the exact pinned Ruff formatter output to all 20 reported files; give the manual-price branch a distinct local; explicitly fail closed if a Decimal exponent is not an integer before scale comparison; and add regression coverage for non-finite manual Decimal input.

**Permanent regression/guard:** existing global mypy plus changed-file Ruff formatting remain mandatory; the purchase-capacity regression now freezes fail-closed non-finite input behavior. No ignore, cast, formatter exclusion, coverage weakening or security-gate suppression is introduced.

**Future prevention rule:** every source relocation into a stricter package boundary must pass the destination lint/type/format baseline as part of the relocation preflight, even when runtime behavior is intentionally unchanged.

**Dependency/tooling knowledge change:** Python Decimal tuple exponents are typed as an integer or special-value marker; runtime finite checks do not necessarily narrow that union for static type checkers.

---

## FL-032 — Provider adapters must bind authority to fields that the live API actually owns

**Date:** 2026-09-26  
**WP / PR / reference:** TIMEWEB-PLATFORM-CONSOLIDATION / existing-IPv4 custody gate / live PLAN run `36230181006`

**Symptom / failing gate:** the protected-main `V10 RU-PG-B Timeweb Existing IPv4 Allocation` PLAN passed exact-main, source-contract and GitHub-environment gates, then stopped before any provider mutation with `TIMEWEB_ALLOCATION_OBSERVATION_UNAVAILABLE`.

**Root cause:** the allocation provider adapter tried to derive private account scope from `DatabaseCluster.account_id`. Current Timeweb API schema exposes `Project.account_id` and `DatabaseCluster.project_id`; the database cluster does not own an `account_id` field. The adapter therefore rejected a valid live cluster response. A second producer/consumer defect hid that safe diagnosis: `ProviderStopped` inherited directly from `RuntimeError`, so the protocol's read boundary converted its fixed provider code into the generic observation-unavailable code.

**Blast radius searched:** Timeweb project/cluster/floating-IP provider schema, allocation snapshot construction, transport prerequisite identity, closed-journal serialization, PLAN/APPLY/RECONCILE consumers, live adapter fixtures, provider-error sanitization and the machine allocation guard. The closed snapshot schema can remain stable because account scope is still available from the selected Project object.

**Why preflight missed it:** the live adapter fixture invented `account_id` on the DatabaseCluster payload and omitted `account_id` from the Project payload, so the synthetic contract encoded the same false assumption as production code. Unit tests therefore certified the fixture rather than the provider schema.

**Corrective change:** source account scope from the exact selected `Project.account_id`; require the live `DatabaseCluster.project_id` to equal that selected project; remove the non-existent cluster-account dependency; make sanitized `ProviderStopped` a protocol `AllocationStopped` subtype so fixed fail-closed provider diagnostics cross the read boundary without exposing raw payloads.

**Permanent regression/guard:** live adapter fixtures now mirror the current provider ownership split, tests prove no cluster `account_id` is required, project drift is rejected, and provider-stop inheritance is machine-guarded. Unknown raw provider exceptions remain sanitized by the existing generic read-failure regression.

**Future prevention rule:** provider fixtures must be derived from current provider schemas for every authority-bearing field. Never infer identity/authority from a convenient adjacent resource when the provider schema assigns it to another object, and never let a sanitization boundary erase already-sanitized fixed error codes.

**Dependency/tooling knowledge change:** current Timeweb schema places account identity on Project (`account_id`) and project identity on DatabaseCluster (`project_id`).

---

## FL-033 — Published repair checkpoints must reproduce the pinned formatter before CI

**Date:** 2026-09-26  
**WP / PR / reference:** TIMEWEB-PLATFORM-CONSOLIDATION / PR #587 / exact head `3da2dc6e8a7a97e5e5eb61d46d7a8f114eb8b5e9`

**Symptom / failing gate:** twelve repository workflows completed successfully, but both `V10 Fast PR Checks` and the authoritative Windows merge gate rejected the same repair head before tests because Ruff 0.16.1 would reformat `scripts/timeweb_ipv4_allocation_provider.py` and `tests/test_v10_timeweb_ipv4_allocation_live.py`. Sonar also reported one new maintainability issue on the repair diff.

**Root cause:** the source correction was published from a connector-only environment where a local repository checkout and the pinned Ruff runtime were unavailable. Manual formatting review did not exactly reproduce Ruff 0.16.1, and the new regression used a generic `unittest.assertTrue` shape instead of a more specific assertion.

**Blast radius searched:** every changed Python file in PR #587, Fast PR changed-file formatting, authoritative repository-wide formatting, the live allocation regression tests, the allocation machine guard and Sonar's new-code maintainability surface. No runtime, tenant, broker, provider-mutation or schema behavior failure was found in this CI batch.

**Why preflight missed it:** formatter equivalence was assumed from visual review after local tool bootstrap failed. Existing FL-026/FL-031 already require exact formatter reproduction, but the fallback path for a connector-only repair checkpoint did not enforce that rule before publication.

**Corrective change:** apply the exact Ruff diff emitted by CI and strengthen the provider guard to inspect field ownership inside the exact AST functions instead of relying on file-wide string presence. Remove the duplicate forbidden-method literal while touching that guard. When Sonar still reported one new issue on replacement head `640eea8f679864582981da0a696403839a66e3b4`, split the dense cluster validator into identity/storage/network units and move new AST ownership checks out of the already-dense provider guard without changing fail-closed codes or provider capabilities. Class-introspection and direct/public boundary-test variants were removed after exact-head Sonar evidence showed each test form added a separate maintainability finding; the deterministic machine guard remains the regression protection for the inheritance boundary, while live PLAN re-execution is the external behavioral proof after merge.

**Permanent regression/guard:** Fast PR and the authoritative merge gate remain unchanged and fail closed on formatter drift; the allocation guard proves `account_id` belongs to `_select_project`, is absent from the cluster-identity validator, `project_id` is required there, and `_cluster` must call that validator.

**Future prevention rule:** inability to run the pinned formatter locally is not a formatting waiver. Before treating a connector-only checkpoint as final, reproduce the exact formatter output from the first available targeted verifier and fold all formatting/static-analysis findings into the same RED-repair batch before recertification.

**Dependency/tooling knowledge change:** none.

---

## FL-034 — Exception regressions must isolate the single operation expected to fail

**Date:** 2026-09-26  
**WP / PR / reference:** TIMEWEB-PLATFORM-CONSOLIDATION / PR #587 / exact head `fd4888c2e76f4a2875aafd4229bf78284822cdf3`

**Symptom / failing gate:** the exact-head authoritative Windows Regression Shield failed with one focused guard failure after 3,805 tests passed, and Sonar reported the same new-code maintainability defect in `test_snapshot_rejects_cluster_project_drift`: the expected-exception context contained three nested invocations instead of one isolated operation.

**Root cause:** the negative regression constructed `_ReadApi`, constructed `TimewebAllocationProvider`, and called `snapshot()` inside one `assertRaisesRegex` body. This made the intended throw site ambiguous and could let a setup/construction failure satisfy a test meant to prove cluster/project drift rejection.

**Blast radius searched:** every `assertRaises` / `assertRaisesRegex` block in the Timeweb IPv4 allocation test family, the existing protocol AST guard, the provider constructor/read boundary, and exact-head Sonar plus Regression Shield evidence. The guard identified this as the only remaining multi-call exception body in that test family.

**Why preflight missed it:** focused source/static checks were GREEN, but this invariant is enforced by the full Regression Shield guard and Sonar. The test was introduced while iterating on the provider-schema defect and retained nested setup in the exception body.

**Corrective change:** construct the read adapter and provider before the exception context, then execute only `adapter.snapshot()` inside `assertRaisesRegex`. Setup failures now fail independently instead of falsely satisfying the expected cluster/project-drift exception.

**Permanent regression/guard:** `ProtocolGuardTests.test_exception_assertions_isolate_the_operation_under_test` scans every `test_v10_timeweb_ipv4_allocation*.py` expected-exception body and requires exactly one call. Sonar independently checks the same maintainability class.

**Future prevention rule:** exception tests must complete all non-target setup before entering the expected-exception context; the body must contain exactly the operation whose failure semantics the test proves.

**Dependency/tooling knowledge change:** none.

---

## FL-035 — Provider state transitions must follow documented prerequisite order

**Date:** 2026-09-26  
**WP / PR / reference:** TIMEWEB-PLATFORM-CONSOLIDATION / RU-PG-B Public IPv4/TLS workflow ordinal #5 / exact main `7a87509258552db4b9ee0c2e762597e561a42fb6`

**Symptom / failing gate:** the manual Timeweb public-transport run passed exact-main/source policy, verifier `/32` validation, environment policy, cost confirmation and the durable existing-IPv4 allocation prerequisite. Provider inventory was `managed_unbound=1 unproven_unbound=0`. The first database v2 mutation then failed with `TIMEWEB_DATABASE_PUBLIC_NETWORK_PATCH_REJECTED http_status=400`.

**Root cause:** repository code modeled public IPv4 attachment/enablement and TLS enablement as one atomic database PATCH. Current Timeweb documentation requires public-IP connectivity before TLS enablement, and the generated `UpdateClusterV2` schema exposes both groups as optional fields suitable for separate partial updates. The live HTTP 400 proves the combined-transition assumption is not accepted for the current provider state. The exact provider validation message remains intentionally unknown because raw error bodies are not read or logged.

**Blast radius searched:** the database v2 mutation model, public IPv4 custody/receipt prerequisite, firewall-first ordering, public-IP binding reconciliation, secure-connection readiness, TLS certificate/domain wait, rollback, operation-specific diagnostics, contract guard and transport tests. The producer/consumer review also found an adjacent authority race: after a valid `ALLOCATED` receipt, the transport still called the legacy generic custody resolver whose `None -> create_once` path could purchase a second IPv4 if the accepted address disappeared between prerequisite GET and transport GET. No evidence points to the OWNER input, verifier CIDR or GitHub Environment policy as the failing boundary.

**Why preflight missed it:** unit coverage asserted the exact combined request body rather than independently modeling provider prerequisite states. The source guard therefore froze the same false atomic-transition assumption instead of testing the documented ordering between public IPv4 and TLS.

**Corrective change:** split first-time public IPv4 attachment from TLS enablement. After the public IPv4 PATCH, GET-reconcile cluster state and exact managed-IP binding, re-prove the DROP TCP/5432 verifier-only firewall/resource scope, then issue a TLS-only PATCH and wait for secure connection plus issued technical domain. Re-prove firewall/binding/TLS before success. In the same defect-class repair, remove floating-IP create/stamp/delete authority from the transport path entirely: after the allocation receipt, missing or drifting IPv4 state is terminal `TIMEWEB_ALLOCATED_IPV4_MISSING` / `TIMEWEB_ALLOCATED_IPV4_DRIFT`, never a new purchase opportunity.

**Permanent regression/guard:** tests require the public IPv4 PATCH to exclude `is_secure_connection_enable`, require the TLS PATCH to contain only the secure-connection field, prove TLS failure triggers public-network rollback, and prove missing/two-read-drifting allocated IPv4 state stops without write authority. The AST machine guard requires public IPv4 mutation -> scope reconciliation -> TLS mutation -> final scope verification, rejects any reintroduction of the combined transition and forbids current transport calls to create/stamp/delete or `custody.resolve`.

**Future prevention rule:** when provider documentation expresses one operation as a prerequisite for another, model them as separate observable state transitions unless live provider evidence proves the combined transition is supported. A shared endpoint does not imply atomic multi-state authority.

**Dependency/tooling knowledge change:** current Timeweb documentation says PostgreSQL TLS setup requires public-IP connectivity first; the generated v2 update model exposes public network, floating IP and secure connection as independent optional fields.

---

## FL-036 — Pre-secret environment gates and observe phases must expose the real failure boundary

**Date:** 2026-09-26  
**WP / PR / reference:** TIMEWEB-PLATFORM-CONSOLIDATION / P3 PostgreSQL production cutover / live workflow run `36259985639`

**Symptom / failing gate:** exact-main bootstrap and the P3 source contract passed, then the pre-secret GitHub production-environment verifier stopped with `TIMEWEB_GITHUB_ENVIRONMENT_GATE_UNAVAILABLE`; the production-cutover job was skipped.

**Root cause:** two producer/consumer assumptions overlapped. The shared environment verifier collapsed GitHub HTTP 401, 403 and 404 into one code, so missing `timeweb-production` configuration could not be distinguished from authentication/authorization failure. Separately, P3 documentation treated `observe` as the first read-only discovery step while the controller routed it through the prepared-schema runtime verifier and cross-tenant write probe, making observation depend on preparation it was meant to precede.

**Blast radius searched:** the shared GitHub Environment verifier, every Timeweb production-environment workflow consumer, P3 contract/runbook/workflow/controller/tests, production DSN secret scope, PostgreSQL 18/TLS/runtime-role checks, migration/RLS preparation, P4/P5 downstream gates and provider/broker authority boundaries. The failed run never consumed production DSNs or the Timeweb provider token.

**Why preflight missed it:** production-environment tests used synthetic successful payloads and did not freeze fixed 401/403/404 classification. Repository tests also validated P3 source shape but did not assert that `observe` bypasses migration/schema/cross-tenant mutation paths. No prior `timeweb-production` workflow had executed live.

**Corrective change:** classify 401, 403 and 404 with separate sanitized codes; make `timeweb-production` existence, exact Branch `main` policy and production DSN custody explicit pre-dispatch prerequisites; re-verify the environment immediately before secret-bearing P3 steps; and route `observe` through a preparation-independent SQL-read-only PostgreSQL 18/TLS/authority/residue probe.

**Permanent regression/guard:** environment-gate tests freeze fixed HTTP classifications; the P3 controller test proves `observe` calls only the read-only observation path; the P3 machine contract requires mutation-free observation and two environment-policy verifications in the workflow.

**Future prevention rule:** a pre-secret gate must preserve enough sanitized classification to identify whether configuration is absent, credentials are invalid, or authority is denied. An operation named `observe` must never perform schema/data mutation or require the state created by a later `prepare` phase.

**Dependency/tooling knowledge change:** GitHub Environment read/policy inspection uses Actions-read authority; environment creation/update and deployment-policy mutation are repository-administration actions and are not granted to the P3 workflow token.

---

## FL-037 — Machine guards must freeze the exact canonical prose and pinned formatter shape

**Date:** 2026-09-26  
**WP / PR / reference:** TIMEWEB-PLATFORM-CONSOLIDATION / P3 PostgreSQL production cutover / PR #590 exact head `d8b776767144d35511ef3875b9b2b6718477c51c`

**Symptom / failing gate:** DRAFT exact-head verification produced three repository-owned REDs with one coupled source cause. Engineering Governance and Fast PR stopped at `TIMEWEB_PG_CUTOVER_RUNBOOK_DRIFT:observe is SQL read-only`; the authoritative Windows merge gate independently reported Ruff 0.16.1 formatting drift in `scripts/check_v10_timeweb_postgres_production_cutover.py`.

**Root cause:** the P3 guard required a paraphrased prose substring that did not exactly exist in the updated runbook, and the connector-authored Python guard had not yet been projected through the pinned formatter. Runtime/controller behavior was not the failing boundary in this batch.

**Blast radius searched:** all PR #590 changed files, the P3 contract/runbook/controller/guard/tests, all three failed job logs, exact-head review threads, and the formatter diff emitted by the authoritative merge gate. The other repository-owned DRAFT workflows completed successfully before this repair.

**Why preflight missed it:** the connector-only publication path could validate source relationships by inspection but did not execute the pinned Ruff formatter locally, and the prose guard was compared conceptually instead of byte-for-byte against the canonical runbook sentence.

**Corrective change:** align the guard with the exact canonical runbook phrase and apply exactly the Ruff 0.16.1 formatting changes reported by CI. No assertion, permission, secret scope, provider mutation, database authority, tenant isolation, public-user gate, broker-write gate, or Real-money boundary is weakened.

**Permanent regression/guard:** the existing P3 machine guard continues to require the canonical runbook language, while Fast PR and the authoritative merge gate remain unchanged as the exact formatter authority.

**Future prevention rule:** source guards that freeze human-readable documentation must use the exact canonical sentence they intend to protect, and connector-only edits must treat the first authoritative formatter result as required source output rather than optional style feedback.

**Dependency/tooling knowledge change:** none.

---

## FL-038 — New provider-named runtime surfaces must update the canonical inventory atomically

**Date:** 2026-09-26  
**WP / PR / reference:** TIMEWEB-PLATFORM-CONSOLIDATION / P3 PostgreSQL production cutover / PR #591 exact head `0745343806719a699a4cd9ce664d1113b11fb240`

**Symptom / failing gate:** the DRAFT exact-head `V10 Timeweb Worktree Convergence Audit` failed after the primary worktree-convergence guard passed. The nested platform-inventory guard stopped with `TIMEWEB_INVENTORY_PROVIDER_SURFACE_COUNT_DRIFT`.

**Root cause:** PR #591 intentionally added two provider-named files — the current runtime adapter `apps/api/timeweb_postgres_tls.py` and its regression suite `tests/test_v10_timeweb_postgres_tls.py` — but the canonical Timeweb provider inventory still froze the pre-change exact count of 256. The test path was already classified by the existing Timeweb-test rule, while the new runtime adapter also required an explicit KEEP classification because no current `apps/api` path rule covers provider-named files.

**Blast radius searched:** every PR #591 changed path, the provider-keyword detector, explicit-path classifications, Timeweb test path rules, the current TW-B runtime KEEP regression list, worktree-convergence consumers, and the new P3 CA helper/test pair. No retired-provider authority, product activation, database mutation, tenant boundary or broker/Real-money change is implicated.

**Why preflight missed it:** the focused P3 contract/CA review validated the new runtime boundary but did not run the whole-tree provider inventory, whose exact-cardinality invariant is intentionally repository-global. The connector-only environment has no mounted repository or pinned project toolchain, so this adjacent whole-tree ownership guard was first exercised by authoritative CI.

**Corrective change:** register `apps/api/timeweb_postgres_tls.py` explicitly as KEEP, raise the exact provider-named file count from 256 to 258 for the two added Timeweb paths, and freeze both the runtime helper and its test in the current TW-B KEEP regression list.

**Permanent regression/guard:** `test_provider_named_inventory_uses_exact_cardinality` continues to require exact provider-surface cardinality, and `test_tw_b_current_source_runtime_surfaces_are_keep` now proves the CA adapter and its regression suite remain current Timeweb surfaces.

**Future prevention rule:** every branch that adds or removes a provider-keyword path must update the canonical provider inventory and its ownership regression in the same source checkpoint before publication; provider-specific runtime adapters are inventory changes, not merely implementation details.

**Dependency/tooling knowledge change:** none.


---

## FL-039 — Raw-string regex escapes must be proven by a positive contract path

**Date:** 2026-09-26  
**WP / PR / reference:** TIMEWEB-PLATFORM-CONSOLIDATION / P3 PostgreSQL production cutover / PR #591 exact head `78594915cfbf7474f30c86838cf0b2cfc4ca9fd1` / Self-Hosted Windows CI run `36270486914`

**Symptom / failing gate:** every repository-owned exact-head workflow except the authoritative Windows merge gate completed `success`. The Windows Regression Shield reached 3,875 passing tests and 960 passing subtests, then failed four focused TLS tests. A syntactically valid hostname such as `db.example.com` was rejected as `TIMEWEB_PG_TLS_TECHNICAL_DOMAIN_REQUIRED`, so the later negative predicates for port, TLS mode and CA path could not reach their intended checks.

**Root cause:** the DNS-label separator in `_DOMAIN_RE` was written as `\\\\.` inside a Python raw string. Raw strings do not require that second escape; the compiled expression therefore expected a literal backslash before the separator instead of a normal dot. The validator rejected every ordinary dotted hostname, including the Timeweb technical-domain shape required for verify-full TLS.

**Blast radius searched:** `_connection_params`, `resolve_timeweb_postgres_dsn`, `prepare_timeweb_postgres_tls`, the P3 bootstrap/runtime DSN preparation path, hosted-runtime startup, the port/TLS/root-cert negative predicates, and the exact-head P3 machine guard. The defect is fail-closed: it blocks PostgreSQL connectivity but does not widen provider, tenant, public-user, broker-write or Real-money authority.

**Why preflight missed it:** connector-only source review and Ruff formatting prove syntax/shape, not regular-expression semantics, and the local execution environment cannot install the repository dependency set. The first authoritative workflow that executes the complete regression suite exposed the semantic escape error.

**Corrective change:** replace the over-escaped raw-string separator with the canonical `\.` form and add an explicit positive regression proving that a valid dotted PostgreSQL hostname reaches the accepted port and verify-full predicates.

**Permanent regression/guard:** `test_connection_contract_accepts_valid_domain` freezes the positive hostname contract, while the existing parametrized negative suite separately proves IP-host rejection, exact port 5432, `verify-full`, and the portable root-certificate path.

**Future prevention rule:** every regex used as an authority or transport validator must have at least one positive-path regression that proves representative valid input reaches downstream predicates; negative-only regex tests can pass for the wrong rejection reason.

**Dependency/tooling knowledge change:** none.
