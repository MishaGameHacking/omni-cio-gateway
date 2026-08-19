# FL-026 — External vulnerability-service timeout is RED until the exact security job completes

Status: **ADDITIVE FAILURE-LEARNING ENTRY FOR PR #336 POST-MERGE ACCEPTANCE; PRIMARY LEDGER REMAINS `V10_ENGINEERING_FAILURE_LEARNING_LEDGER.md`**  
Date: **2026-08-19**  
WP / PR / reference: **WP22A Phase 2 Product-auth / tenant-security correction / PR #336 / Regression Shield #1508 run `32277165957`**

## Symptom / failing gate

After PR #336 was squash-merged to exact `main` `00fc692710aa9eaf02ca78ea0535b51600020768`, mandatory post-merge Regression Shield #1508 completed its quality job successfully but the security job failed at `Audit runtime dependencies`.

The log showed `pip-audit` using the OSV vulnerability service and then raising a `requests.exceptions.ReadTimeout` for `api.osv.dev` with a 15-second read timeout. Because the dependency-audit step failed, the later SAST and tracked-content secret-scan steps in that first security attempt did not execute and were not acceptance evidence.

## Root cause

The failed attempt did not report a package vulnerability or a source-code security defect. The authoritative failure was an external network/service read timeout while querying OSV.

The distinction is diagnostic only: under V10 Green-Merge/Regression-Shield rules an infrastructure/network RED still blocks acceptance. It cannot be reclassified into PASS, and skipped downstream security steps cannot be counted as successful.

## Blast radius searched

The failure was isolated to the post-merge security job's external vulnerability-service query on the already accepted exact source tree.

The same exact-main run showed:

- `Quality, contracts and coverage` — SUCCESS;
- dependency installation and Windows lock projection — SUCCESS;
- failure only when querying the OSV service;
- no vulnerability finding before the timeout;
- no SAST/secret-scan result in the failed security attempt.

No source, dependency lock, security threshold, broker authority, product flag or provider configuration was changed to address the transient.

## Corrective change

Re-run only the failed `Dependency, code and secret security` job on the same exact main SHA using GitHub's job re-run mechanism.

No source commit was created and no check was weakened. On run attempt 2 the same security job completed:

1. hash-locked tool installation;
2. runtime dependency audit — SUCCESS;
3. medium/high-confidence SAST — SUCCESS;
4. tracked-content secret scan — SUCCESS.

The Regression Shield workflow then concluded SUCCESS with both required jobs GREEN on exact main `00fc692710aa9eaf02ca78ea0535b51600020768`.

## Permanent regression / guard

Existing governance remains the guard:

- infrastructure/network classification never converts RED to PASS;
- exact-main post-merge acceptance waits for the required job to actually complete SUCCESS;
- skipped downstream security stages are never counted as evidence;
- a job re-run is acceptable only when it preserves the same source SHA and unchanged security checks;
- repeated/non-transient external-service failures must be investigated as a CI resilience defect rather than endlessly retried.

The current workflow continues to fail closed if the vulnerability service is unavailable; this entry does not add retries or reduce audit strictness.

## Future prevention rule

When a mandatory external security service times out, first determine from logs whether the failure is a vulnerability finding, deterministic tool/configuration defect or external transport/service failure. Do not patch product code for a proven transient and do not call the failed attempt GREEN.

If the source SHA and checks are unchanged and the failure is clearly external/transient, re-run only the failed job. Acceptance occurs only after every required security stage actually executes and succeeds. If the same external failure repeats materially, stop retrying and implement a reviewed resilience strategy without weakening the security requirement.

## Dependency/tooling knowledge change

`pip-audit` with the OSV service is network-dependent. A strict audit can fail because the vulnerability API cannot be read even when dependency installation and the source tree are healthy. GitHub Actions job re-runs preserve the original workflow event's source/ref, which makes a focused same-SHA retry suitable for proving a transient without creating a new source head.