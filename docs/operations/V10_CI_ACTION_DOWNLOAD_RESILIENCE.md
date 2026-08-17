# V10 CI Action Download Resilience

Status: MAINTENANCE IN PROGRESS

## Root causes reproduced

Mandatory self-hosted V10 jobs can fail before repository code executes when the runner cannot download pinned external Actions from `codeload.github.com`. The reproduced failures on PR #327 include HTTP 429 and 503 while preparing `actions/checkout` and `actions/upload-artifact`.

After external Action preparation was removed, PR #328 exposed a second pre-test failure mode on the persistent Windows service account: the runner was online and assigned to the job, but manual `git fetch` remained in progress at repository bootstrap. The bootstrap must therefore be explicitly non-interactive and independent of inherited Windows Git credential helpers.

Pre-CI/full-diff review also caught a compatibility regression before acceptance: Fast PR cleanup had been moved from native Windows `cmd` to Bash. The accepted FL-010/cost-control contract requires those cleanup steps to remain native `cmd`; the maintenance branch restores that contract while retaining explicit credential-helper cleanup.

## Required correction

The mandatory PR and post-merge authority plane must not depend on downloading non-authoritative helper Actions before project checks can execute. Repository bootstrap must remain exact-SHA, fail closed, use only job-scoped repository read authority, and remove temporary Git credentials immediately after fetch.

For headless Windows service execution, every current self-hosted authority bootstrap must additionally:

- set `GIT_TERMINAL_PROMPT=0`;
- set `GCM_INTERACTIVE=0`;
- reset inherited credential helpers with an empty local `credential.helper` entry;
- append only the temporary job-token helper needed for the fetch;
- remove all local credential-helper entries immediately after fetch;
- verify the checked-out SHA is exactly the reviewed/event SHA.

This changes repository bootstrap only. It does not mutate the runner account's persistent Git configuration or write a token into the remote URL.

## Applicability

The protected bootstrap contract covers the current self-hosted PR/post-merge authority plane, including:

- core Engineering Governance, Fast PR, Toolchain Compatibility and Self-Hosted Windows authority workflows;
- the active `V10 Live Gateway Authority Contract` routing/governance lane;
- the path-triggered WP6 identity audit;
- WP15 deterministic Web support;
- WP16-WP22A deterministic Web gates;
- post-merge Regression Shield.

The WP6 identity workflow is included because changing the authoritative self-hosted workflow makes its path filter applicable; leaving its historical `actions/checkout` path would preserve the same codeload failure domain.

The live gateway authority contract is included because it is an active self-hosted governance/routing check and shared the same `actions/checkout` failure domain. This does **not** move actual V9 live-authority evidence onto Lenovo: the actual deployed live probe remains the existing manual GitHub-hosted workflow and remains deferred under the accepted zero-budget policy.

Historical OWNER physical-evidence workflows and the GitHub-hosted release-provenance workflow are not bulk-rewritten by this maintenance package. Their authority/evidence semantics are outside this generic self-hosted bootstrap correction and must not be rebound merely to reduce diff size or CI cost.

## Acceptance evidence boundary

A codeload transport failure, a headless credential/bootstrap hang, a lost-runner event, queued work, cancellation, or a test failure is never PASS. The maintenance package itself requires a fresh exact-head applicable CI cycle after the source-controlled correction; no prior red, cancelled, partial, superseded-head, or pre-fix run is reusable as acceptance evidence.

The repository-wide resilience regression test is executed by Engineering Governance on every PR and by the full authoritative/post-merge test suite. It rejects reintroduction of codeload checkout/artifact Actions, interactive Git/GCM bootstrap, inherited credential-helper dependence, missing exact-SHA checks, or weakened job authority across the active self-hosted authority set above.

## Invariants

- no weakening of tests, Regression Shield, dependency audit, SAST, secret scanning, or exact-head verification;
- no repository, provider, broker, Telegram, portfolio, or runtime secrets;
- no change to the actual V9 live-authority route or evidence semantics;
- `app:app` remains protected;
- `trading_methods=false`;
- `REAL_TRADING_ENABLED=false`;
- no broker-write expansion;
- WP22A remains current; WP23+ remains locked.

This maintenance package carries zero product-progress credit.
