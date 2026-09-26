# V10 CI Action Download Resilience

Status: MAINTENANCE IN PROGRESS

## Root causes reproduced

Mandatory self-hosted V10 jobs can fail before repository code executes when the runner cannot download pinned external Actions from `codeload.github.com`. The reproduced failures on PR #327 include HTTP 429 and 503 while preparing `actions/checkout` and `actions/upload-artifact`.

After external Action preparation was removed, PR #328 exposed a second pre-test failure mode on the persistent Windows service account: the runner was online and assigned to the job, but manual `git fetch` remained in progress at repository bootstrap. The bootstrap must therefore be explicitly non-interactive and independent of inherited Windows Git credential helpers.

Pre-CI/full-diff review also caught a compatibility regression before acceptance: Fast PR cleanup had been moved from native Windows `cmd` to Bash. The accepted FL-010/cost-control contract requires those cleanup steps to remain native `cmd`; the maintenance branch restores that contract while retaining explicit credential-helper cleanup.

On PR #402 exact head `b912625592e7f51eb298738475b57ae395c79bfa`, the authoritative merge gate then exposed a third pre-test failure mode. The source-controlled headless bootstrap reached `git fetch`, but Git for Windows / Schannel failed with `curl 56`, `early EOF`, and `invalid index-pack output`. A targeted rerun of that one failed authoritative job reproduced the same failure on the same exact SHA before checkout or project code executed. The always-run cleanup then failed derivatively because `HEAD` did not exist.

That repeated same-SHA failure is classified as `INFRASTRUCTURE_BOOTSTRAP`, not a code/test defect. A third blind workflow rerun is not valid engineering evidence; the source-controlled bootstrap contract must absorb bounded transient transport failure and remain fail-closed after retry exhaustion.

## Required correction

The mandatory PR and post-merge authority plane must not depend on downloading non-authoritative helper Actions before project checks can execute. Repository bootstrap must remain exact-SHA, fail closed, use only job-scoped repository read authority, and remove temporary Git credentials immediately after fetch.

For headless Windows service execution, every protected bootstrap retains the accepted security properties:

- set `GIT_TERMINAL_PROMPT=0`;
- set `GCM_INTERACTIVE=0`;
- reset inherited credential helpers with an empty local `credential.helper` entry;
- append only the temporary job-token helper needed for the fetch;
- remove all local credential-helper entries immediately after fetch;
- verify the checked-out SHA is exactly the reviewed/event SHA.

For the dependency-closed blocker set required to repair PR #402, repository transport additionally must:

- retry only the Git fetch/bootstrap transport operation, never tests, lint, security scans or quality gates;
- use exactly three bounded attempts with short bounded backoff;
- delete partial `.git` state before each new attempt so an incomplete pack/index cannot poison the next attempt;
- remove the temporary local credential helper after every fetch attempt, including failed attempts;
- emit an explicit terminal bootstrap diagnostic and non-zero exit after retry exhaustion;
- keep exact-SHA verification mandatory after a successful fetch;
- make always-run cleanup idempotent when checkout never produced `HEAD`.

This changes repository bootstrap only. It does not mutate the runner account's persistent Git configuration, write a token into the remote URL, soften any project check, or convert infrastructure RED to PASS.

## Immediate targeted-repair execution law

The CI control loop is fail-fast and repair-oriented rather than queue-oriented.

When one applicable job becomes terminal RED, engineering does not wait for all remaining applicable jobs to finish before starting diagnosis. The failed job is classified immediately, its directly related log findings are collected into one coherent failure-domain batch, and the smallest source correction is made. After that correction, only the failed job or the smallest dependency-closed gate set needed to prove the repair is rerun. Independent jobs may continue in parallel and are not restarted merely because a repair is underway.

This does not permit one-line thrash. Before a correction commit, inspect the failing step, adjacent failure modes, directly related producers/consumers, and the known blast radius. The distinction is that known actionable defects are repaired as they surface instead of being accumulated into a long queue.

A repeated same-root-cause infrastructure failure on a targeted rerun stops blind retry. The infrastructure contract itself becomes the defect, as happened on PR #402 / issue #404.

After all known repair domains are stable and the diff is final, run one fresh exact-head applicable acceptance cycle. That final cycle is the merge evidence; earlier targeted reruns remain diagnostic/repair evidence only.

## Applicability and blocker dependency closure

The accepted bootstrap architecture still covers the current self-hosted PR/post-merge authority plane, including core Engineering Governance, Fast PR, Toolchain Compatibility, Self-Hosted Windows authority, live-routing governance, WP6, WP15-WP22A deterministic gates, and post-merge Regression Shield.

However, knowing the full blast radius does not require every blocker PR to modify every historical workflow. Issue #404 deliberately changes only the dependency-closed set that is automatically required to prove the current authoritative bootstrap repair:

- `self-hosted-windows-smoke.yml` — contains the actually failing authoritative merge gate and smoke companion;
- `v10-engineering-governance.yml` — always applicable to the repair PR;
- `v10-pr-fast-checks.yml` — always applicable routing/policy plane;
- `v10-toolchain-compat.yml` — always applicable routing/capacity plane;
- `v10-wp6-identity-audit.yml` — becomes applicable because its path filter owns `self-hosted-windows-smoke.yml`;
- `regression-shield.yml` — mandatory post-merge acceptance surface.

The deterministic resilience test keeps the existing whole-plane exact-SHA/read-only/headless contract while requiring bounded transport retry and pre-`HEAD`-safe cleanup across that blocker dependency closure.

PR #405 accepted that narrow dependency-closed repair on `main`. Its intentionally deferred adjacent transport domain remained documented rather than silently treated as solved.

## Current critical follow-up closure — issue #406

Fresh verification after PR #405 proved that part of the deferred adjacent domain had become a **direct current dependency** rather than merely future migration debt.

On PR #402 exact head `6b65c9c8c57e2803478a3ceddd68e9f783fb1018`, current applicable single-attempt workflows reproduced the same Windows Schannel / `curl 56` / `early EOF` / `invalid index-pack output` bootstrap failure before repository code could execute. The accepted-main `V10 Phase 4 Free Preview Deploy` lifecycle also reproduced the same pre-provider bootstrap failure. No provider mutation occurred in that failed deployment run because checkout never completed.

Issue #406 therefore activates bounded transport retry only for the direct current critical closure:

- `v10-live-gateway-authority-contract.yml`;
- `v10-wp16-web-design-system-audit.yml`;
- `v10-wp17-application-shell-audit.yml`;
- `v10-wp18-portfolio-dashboard-audit.yml`;
- `v10-wp19-watchtower-incidents-audit.yml`;
- `v10-wp20-research-dossier-audit.yml`;
- `v10-wp21-decision-risk-plan-audit.yml`;
- `v10-wp22-system-admin-audit.yml`;
- `v10-timeweb-worktree-convergence-audit.yml`;
- `v10-wp22a-phase2-product-auth-audit.yml`;
- `v10-phase4-free-preview-deploy.yml`;
- `v10-hosted-release-alignment.yml`.

The first eleven workflows receive the same accepted three-attempt bootstrap transport contract and pre-`HEAD`-safe cleanup used by PR #405. Project tests, Web builds, security gates and provider mutations remain outside the retry loop.

`v10-hosted-release-alignment.yml` additionally owns a second, post-probe current-main fetch that protects against a TOCTOU race before runtime PASS is published. That reconfirmation now has its own bounded three-attempt read-only transport retry. It does **not** delete or recreate the already verified working repository; exhaustion fails non-zero and withholds runtime PASS. A successful reconfirmation still compares current `main` with the exact expected SHA and reports `SUPERSEDED_BY_NEWER_MAIN` rather than publishing stale PASS when main moved.

The deterministic regression guard now distinguishes:

1. the historical six-workflow PR #405 closure;
2. the current issue #406 critical follow-up closure;
3. the Hosted Release Alignment dual-fetch/TOCTOU contract.

This scope does not silently bulk-rewrite every historical self-hosted workflow. Historical one-shot acceptance workflows, unrelated WP15 surfaces, and the future #401 verifier/provider migration remain outside issue #406 unless direct accepted evidence makes them current dependencies.

The live gateway authority contract remains part of the accepted bootstrap architecture, but hardening its source checkout does **not** move actual V9 live-authority evidence onto Lenovo: the actual deployed live probe remains the existing manual GitHub-hosted workflow and remains deferred under the accepted zero-budget policy.

Historical OWNER physical-evidence workflows and the GitHub-hosted release-provenance workflow are not bulk-rewritten by this maintenance package. Their authority/evidence semantics are outside this focused bootstrap correction and must not be rebound merely to reduce diff size or CI cost.

## Acceptance evidence boundary

A codeload transport failure, a headless credential/bootstrap hang, a Git/Schannel fetch failure, retry exhaustion, a lost-runner event, queued work, cancellation, or a test failure is never PASS.

Targeted job reruns are valid repair diagnostics only when they execute against the intended source state. They do not replace final acceptance. Any new code commit invalidates prior final exact-head merge evidence and requires a fresh final applicable cycle once the branch is stable.

The resilience regression test is executed by Engineering Governance and the full authoritative/post-merge suite. It rejects reintroduction of codeload checkout/artifact Actions, interactive Git/GCM bootstrap, inherited credential-helper dependence, missing exact-SHA checks, weakened job authority, missing bounded retry on the protected current closures, or cleanup that assumes `HEAD` exists after a failed bootstrap.

## Invariants

- no weakening of tests, Regression Shield, dependency audit, SAST, secret scanning, or exact-head verification;
- no retry wrapper around project tests or security/quality gates;
- no repository, provider, broker, Telegram, portfolio, or runtime secrets added to maintenance code or evidence;
- no change to the actual V9 live-authority route or evidence semantics;
- `app:app` remains protected;
- `trading_methods=false`;
- `REAL_TRADING_ENABLED=false`;
- no broker-write expansion;
- product implementation remains paused; WP23+ remains locked.

This maintenance package carries zero product-progress credit.


### 2026-09-25 P5.5 worktree convergence

P5.5 worktree convergence replaces the dormant WP22A clientless audit workflow with the
Timeweb current-worktree convergence audit. The replacement keeps the same bounded
self-hosted repository-bootstrap transport behavior but installs no WP22A/Cloudflare
dependency stack and executes only stdlib-based Timeweb inventory/convergence guards.

The historical check-run context is retained temporarily as a compatibility boundary
because the GitHub App connection cannot read branch-protection administration settings.
This avoids silently removing a potentially required status context while the workflow
path and executable implementation are fully Timeweb-converged.
