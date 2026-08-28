# V10 CI Action Download Resilience

Status: MAINTENANCE IN PROGRESS

## Root causes reproduced

Mandatory self-hosted V10 jobs can fail before repository code executes when the runner cannot download pinned external Actions from `codeload.github.com`. The reproduced failures on PR #327 include HTTP 429 and 503 while preparing `actions/checkout` and `actions/upload-artifact`.

After external Action preparation was removed, PR #328 exposed a second pre-test failure mode on the persistent Windows service account: the runner was online and assigned to the job, but manual `git fetch` remained in progress at repository bootstrap. The bootstrap must therefore be explicitly non-interactive and independent of inherited Windows Git credential helpers.

Pre-CI/full-diff review also caught a compatibility regression before acceptance: Fast PR cleanup had been moved from native Windows `cmd` to Bash. The accepted FL-010/cost-control contract requires those cleanup steps to remain native `cmd`; the maintenance branch restores that contract while retaining explicit credential-helper cleanup.

On PR #402 exact head `b912625592e7f51eb298738475b57ae395c79bfa`, the authoritative merge gate then exposed a third pre-test failure mode. The source-controlled headless bootstrap reached `git fetch`, but Git for Windows / Schannel failed with `curl 56`, `early EOF`, and `invalid index-pack output`. A targeted rerun of that one failed authoritative job reproduced the same failure on the same exact SHA before checkout or project code executed. The always-run cleanup then failed derivatively because `HEAD` did not exist.

That repeated same-SHA failure is classified as `INFRASTRUCTURE_BOOTSTRAP`, not a code/test defect. A third blind workflow rerun is not valid engineering evidence; the source-controlled bootstrap contract must absorb bounded transient transport failure and remain fail-closed after retry exhaustion.

PR #405 / issue #404 repaired the narrow dependency-closed authority set needed to unblock that first failure. Fresh verification of PR #402 after #405 acceptance then proved that the remaining debt had become a current blocker rather than only a future migration concern. `V10 Live Gateway Authority Contract` #72 failed on the re-anchored #402 head `6b65c9c8c57e2803478a3ceddd68e9f783fb1018` with the same Schannel `curl 56` -> incomplete body -> unexpected disconnect -> `early EOF` -> `invalid index-pack output` chain before project code. The same root cause independently failed accepted-main `V10 Phase 4 Free Preview Deploy` #29 on `698be470048f100546354a3ac78d112e8cec7519`; every provider/deploy step was skipped, so no Render or Neon mutation occurred.

The failed Phase-4 workflow also triggered its direct `V10 Hosted Release Alignment` consumer. That workflow still contained a single-attempt initial bootstrap plus a second post-probe fetch used to protect runtime PASS publication from main-advance TOCTOU. The current repair therefore must harden both the bootstrap and that post-probe read-only refresh without weakening the runtime-alignment identity check.

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
- delete partial `.git` state before each new bootstrap attempt so an incomplete pack/index cannot poison the next attempt;
- configure Git low-speed abort with `http.lowSpeedLimit=1000` and `http.lowSpeedTime=60` so a stalled HTTPS transfer reaches the bounded retry path instead of consuming the whole job timeout;
- remove the temporary local credential helper after every fetch attempt, including failed attempts;
- emit an explicit terminal bootstrap diagnostic and non-zero exit after retry exhaustion;
- keep exact-SHA verification mandatory after a successful fetch;
- make always-run cleanup idempotent when checkout never produced `HEAD`.

Hosted Release Alignment additionally isolates its post-probe current-main refresh in a fresh temporary Git repository for each bounded attempt. Runtime PASS remains withheld until that refresh succeeds and proves `main` still equals the expected exact SHA. Retry exhaustion fails non-zero; it never publishes the buffered hosted-alignment PASS.

This changes repository bootstrap/read-only refresh only. It does not mutate the runner account's persistent Git configuration, write a token into the remote URL, soften any project check, retry provider mutations, or convert infrastructure RED to PASS.

## Immediate targeted-repair execution law

The CI control loop is fail-fast and repair-oriented rather than queue-oriented.

When one applicable job becomes terminal RED, engineering does not wait for all remaining applicable jobs to finish before starting diagnosis. The failed job is classified immediately, its directly related log findings are collected into one coherent failure-domain batch, and the smallest source correction is made. After that correction, only the failed job or the smallest dependency-closed gate set needed to prove the repair is rerun. Independent jobs may continue in parallel and are not restarted merely because a repair is underway.

This does not permit one-line thrash. Before a correction commit, inspect the failing step, adjacent failure modes, directly related producers/consumers, and the known blast radius. The distinction is that known actionable defects are repaired as they surface instead of being accumulated into a long queue.

A repeated same-root-cause infrastructure failure on a targeted rerun stops blind retry. The infrastructure contract itself becomes the defect, as happened on PR #402 / issue #404 and again on the still-single-attempt current-critical surfaces tracked by issue #406.

After all known repair domains are stable and the diff is final, run one fresh exact-head applicable acceptance cycle. That final cycle is the merge evidence; earlier targeted reruns remain diagnostic/repair evidence only.

## Applicability and blocker dependency closure

The accepted bootstrap architecture still covers the current self-hosted PR/post-merge authority plane, including core Engineering Governance, Fast PR, Toolchain Compatibility, Self-Hosted Windows authority, live-routing governance, WP6, WP15-WP22A deterministic gates, and post-merge Regression Shield.

Issue #404 deliberately changed only the six-workflow dependency closure that was required to prove its first authoritative bootstrap repair:

- `self-hosted-windows-smoke.yml`;
- `v10-engineering-governance.yml`;
- `v10-pr-fast-checks.yml`;
- `v10-toolchain-compat.yml`;
- `v10-wp6-identity-audit.yml`;
- `regression-shield.yml`.

That narrow repair remains valid historical evidence. Issue #406 is the next focused closure because the previously adjacent debt is now directly blocking the current governance PR and accepted-main deployment lifecycle.

The issue #406 current-critical PR set is:

- `v10-live-gateway-authority-contract.yml`;
- `v10-wp16-web-design-system-audit.yml`;
- `v10-wp17-application-shell-audit.yml`;
- `v10-wp18-portfolio-dashboard-audit.yml`;
- `v10-wp19-watchtower-incidents-audit.yml`;
- `v10-wp20-research-dossier-audit.yml`;
- `v10-wp21-decision-risk-plan-audit.yml`;
- `v10-wp22-system-admin-audit.yml`;
- `v10-wp22a-clientless-access-audit.yml`;
- `v10-wp22a-phase2-product-auth-audit.yml`.

The directly coupled accepted-main lifecycle set is:

- `v10-phase4-free-preview-deploy.yml`;
- `v10-hosted-release-alignment.yml`.

The deterministic resilience test keeps the existing whole-plane exact-SHA/read-only/headless contract, preserves the historical #404 retry closure, and separately requires bounded transport retry plus pre-`HEAD`-safe cleanup across the current #406 critical set. It also requires Hosted Release Alignment to keep its post-probe current-main refresh isolated, bounded, and before runtime PASS publication.

This #406 closure does not bulk-rewrite historical one-shot public-acceptance/technical-closeout workflows and does not start the future #401 Cloudflare/runtime/verifier-provider migration. Those changes require their own accepted authority and current dependency evidence.

The actual V9 deployed live probe remains the existing independent/manual hosted evidence route under the accepted zero-budget policy. Hardening the Lenovo-side live-routing contract does not reclassify Lenovo as deployed-live evidence.

## Acceptance evidence boundary

A codeload transport failure, a headless credential/bootstrap hang, a Git/Schannel fetch failure, retry exhaustion, a lost-runner event, queued work, cancellation, or a test failure is never PASS.

Targeted job reruns are valid repair diagnostics only when they execute against the intended source state. They do not replace final acceptance. Any new code commit invalidates prior final exact-head merge evidence and requires a fresh final applicable cycle once the branch is stable.

The resilience regression test is executed by Engineering Governance and the full authoritative/post-merge suite. It rejects reintroduction of codeload checkout/artifact Actions, interactive Git/GCM bootstrap, inherited credential-helper dependence, missing exact-SHA checks, weakened job authority, missing bounded retry on the protected blocker closures, unsafe pre-`HEAD` cleanup, or Hosted Alignment PASS publication before its bounded post-probe main recheck.

## Invariants

- no weakening of tests, Regression Shield, dependency audit, SAST, secret scanning, or exact-head verification;
- no retry wrapper around project tests, provider mutation, deployment mutation, or security/quality gates;
- no repository, provider, broker, Telegram, portfolio, or runtime secrets added to source or logs;
- no change to the actual V9 live-authority route or evidence semantics;
- `app:app` remains protected;
- `PUBLIC_MULTI_USER_ENABLED=false` remains protected;
- `trading_methods=false`;
- `REAL_TRADING_ENABLED=false`;
- no broker-write expansion;
- product implementation remains paused; WP23+ remains locked.

This maintenance package carries zero product-progress credit.
