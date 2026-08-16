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
**Symptom / failing gate:** after the scheduled live V9 authority probe was correctly moved to the Lenovo Windows runner, its dependency-install step failed before the read-only live probe could run. The runtime lock attempted to build `uvloop` on Windows and failed because that dependency is not supported on Windows.

**Root cause:** the runner OS was changed from GitHub-hosted Linux to self-hosted Windows, but the dependency install command was not changed with it: the workflow installed the canonical POSIX `requirements.txt` directly instead of generating and installing the repository's established Windows projection.

**Blast radius searched:** every workflow moved between runner operating systems, especially self-hosted Windows jobs that install runtime or development locks; the canonical `windows_ci_lock.py` projection and existing accepted Windows workflows were reviewed as the established solution.

**Why preflight missed it:** the zero-budget routing review focused on applicability, runner choice, secrets and merge semantics but did not include an OS-transition audit of every platform-sensitive dependency/toolchain command.

**Corrective change:** make `live-gateway-authority.yml` build `windows-requirements.txt` with `scripts/windows_ci_lock.py project requirements.txt windows-requirements.txt` and install that hash-locked Windows projection. Do not remove `uvloop` from the canonical POSIX lock and do not soften the failure.

**Permanent regression/guard:** the CI cost-control validator and focused governance tests now require the Windows projection in the scheduled live-authority workflow and reject direct installation of the POSIX runtime lock on that Windows lane.

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

**Corrective change:** move the warm-up logic into source-controlled `scripts/warm_live_gateway.ps1`, hard-bind it to HTTPS and the protected V9 host, and invoke it from the workflow's existing `cmd` shell with explicit `-NoProfile -ExecutionPolicy Bypass -File`. The strict Python authority validator remains mandatory afterward; the warm-up cannot produce acceptance by itself.

**Permanent regression/guard:** the CI cost-control validator and deterministic governance tests now require both the reviewed warm-up script and its explicit-bypass invocation, including bounded timing, approved-host validation and fail-closed exit code 41.

**Future prevention rule:** on protected self-hosted Windows nodes, do not assume GitHub's temporary PowerShell shell scripts are executable. Prefer a source-controlled reviewed `.ps1` entrypoint invoked through the repository's established explicit-bypass boundary, and test that shell path before the expensive exact-head cycle.

**Dependency/tooling knowledge change:** Windows PowerShell execution policy is part of the self-hosted runner contract. A change from hosted runners or `cmd` to implicit `shell: powershell` is a platform-boundary change that requires explicit preflight.

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
