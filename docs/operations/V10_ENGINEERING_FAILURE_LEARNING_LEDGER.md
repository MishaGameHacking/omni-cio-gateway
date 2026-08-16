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
