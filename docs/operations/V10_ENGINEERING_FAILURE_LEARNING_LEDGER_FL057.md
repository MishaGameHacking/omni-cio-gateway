# FL-057 — Repeated same-SHA bootstrap transport RED requires source repair, not blind reruns

Status: **ADDITIVE FAILURE-LEARNING ENTRY; PRIMARY LEDGER REMAINS `V10_ENGINEERING_FAILURE_LEARNING_LEDGER.md`**  
Date: **2026-08-28**  
WP / PR / reference: **Governance PR #402 blocker / issue #404 / exact failing head `b912625592e7f51eb298738475b57ae395c79bfa`**

## Symptom / failing gate

The mandatory `Self-Hosted Windows CI / V10 authoritative merge gate` for PR #402 failed before checkout or project code execution while running the accepted manual exact-SHA repository bootstrap.

Git for Windows / Schannel reported `curl 56`, `early EOF`, and `invalid index-pack output` during `git fetch`. The always-run cleanup then produced a second error because bootstrap had never created `HEAD`.

A targeted rerun of only the failed authoritative job on the same exact SHA reproduced the same transport failure before project tests executed.

## Root-cause analysis

The accepted headless bootstrap contract correctly removed external Action/codeload dependence, credential prompts, inherited credential-helper dependence and persisted credentials, but it still treated one `git fetch` transport attempt as authoritative.

That assumption is too brittle for a persistent self-hosted Windows runner using HTTPS/Schannel: a bounded transient connection/pack interruption can occur before any repository code runs. Re-running the whole workflow graph wastes runner time, while repeatedly pressing rerun without changing the bootstrap contract merely retries the same unhandled failure mode.

The cleanup path also assumed that a repository `HEAD` existed. That assumption is false when failure occurs before checkout, causing a derivative cleanup RED that obscures the primary transport error.

## Blast radius searched

The accepted self-hosted authority-plane list in `tests/test_v10_ci_action_download_resilience.py` was reviewed. The same single-attempt Git bootstrap pattern exists beyond the one failing authoritative job.

For the urgent blocker correction, the dependency-closed set is narrower than the whole historical blast radius:

- `self-hosted-windows-smoke.yml` contains the failing authoritative gate and smoke companion;
- `v10-engineering-governance.yml`, `v10-pr-fast-checks.yml` and `v10-toolchain-compat.yml` are automatically applicable to the repair PR;
- `v10-wp6-identity-audit.yml` is triggered because its path filter owns `self-hosted-windows-smoke.yml`;
- `regression-shield.yml` is the mandatory post-merge acceptance surface.

WP15-WP22A and other historical self-hosted bootstrap consumers remain a known adjacent failure domain, but changing them in this blocker would trigger unrelated expensive jobs. Their broader migration belongs to the adaptive verifier/dispatcher follow-up rather than the immediate PR #402 unblock.

## Why preflight missed it

The existing deterministic bootstrap guards validated security semantics — exact SHA, read-only authority, non-interactive Git/GCM, temporary credential-helper removal and no codeload Actions — but did not model transport interruption after authentication had succeeded.

Previous successful fetches made the single-attempt transport assumption appear stable. The failure only became material when the same exact-head job reproduced the Schannel/pack interruption twice.

## Corrective change

The blocker dependency closure now wraps **only repository fetch transport** in exactly three bounded attempts with short bounded backoff.

Each attempt starts from fresh `.git` state, installs only the temporary job-token credential helper, removes that helper immediately after the fetch attempt, and deletes partial `.git` state before retrying a failed fetch. Retry exhaustion emits an explicit bootstrap diagnostic and fails non-zero.

After a successful fetch, exact reviewed/event SHA verification remains mandatory. Project tests, lint, type checks, dependency audits, SAST, secret scanning and acceptance checks are never placed inside the retry loop.

Always-run cleanup now verifies that `HEAD` exists before `git reset --hard HEAD`; if checkout never completed, cleanup removes partial `.git` state instead of generating a derivative false lead.

## Permanent regression / guard

`tests/test_v10_ci_action_download_resilience.py` retains the whole-plane headless exact-SHA/read-only bootstrap guard and adds a deterministic blocker-dependency-closure guard requiring:

- exactly bounded three-attempt bootstrap loops;
- fetch-status capture rather than softening the job;
- temporary credential-helper removal between attempts;
- partial `.git` reset;
- bounded backoff;
- explicit non-zero retry-exhaustion behavior;
- pre-`HEAD`-safe cleanup.

The guard is executed by Engineering Governance and the protected authoritative/post-merge test suites.

## Future prevention rule

CI response is **fail fast -> diagnose immediately -> repair narrowly -> rerun narrowly -> final exact-head acceptance once stable**.

Do not wait for the entire applicable workflow graph to finish after a meaningful RED appears. Collect the directly related findings from that failed job, perform root-cause/blast-radius analysis, make one coherent correction batch, and rerun only the failed job or smallest dependency-closed gate set needed to prove the fix.

Do not accumulate known actionable failures into a queue for later repair. Conversely, do not thrash one line at a time: inspect the full failed step/log and adjacent failure modes before the correction commit.

If a targeted rerun reproduces the same infrastructure root cause on the same source state, stop blind retries and repair the infrastructure contract itself.

Final merge acceptance still requires one fresh exact-head applicable cycle after the branch is stable. Targeted reruns are repair evidence, not a bypass for final acceptance.

## Dependency/tooling knowledge change

Git HTTPS/Schannel transport behavior is part of the self-hosted Windows CI execution environment. Exact-SHA and credential security are necessary but not sufficient for a resilient bootstrap; bounded transport retry and bootstrap-failure-safe cleanup are now explicit CI contract properties.
