# Omni-CIO V10 — WP10 CI Continuity Decision

Status: **ACTIVE WP10 defect-resolution evidence**  
Scope: **WP10 only; no WP11 work is authorized by this decision**

## Authority

This decision applies the already OWNER-approved GitHub Pro / migration amendment and its machine-readable utilization contract to the current WP10 hosted-runner billing outage.

The higher program authority explicitly requires all of the following:

- no intentional paid GitHub Actions overage is required for V10 Definition of Done;
- hosted Actions minutes are a finite acceleration budget, not the only compute path;
- when included hosted capacity is exhausted or unavailable, hosted acceleration may degrade while authoritative Lenovo safety gates remain available;
- direct pushes, disabled safety checks, ruleset bypasses, or a competing CI architecture remain forbidden.

The permanent hybrid architecture is not changed: GitHub-hosted Ubuntu/Windows remain the preferred disposable acceleration and clean-room lanes whenever included capacity is available. Lenovo `omni-cio-ci` remains the authoritative/heavy continuity lane.

## Incident evidence

At exact PR #263 head `b8f7c21e3c17b35f1dba40c2ccde2cc58b273610`, GitHub-hosted jobs failed before executing normal workflow steps. GitHub's check annotation for `V10 WP10 Recovery Compatibility #63` states that the job was not started because recent account payments failed or the spending limit needed to be increased.

This is classified as:

`DEGRADED_HOSTED_ACCELERATION / ACCOUNT_BILLING_OR_SPENDING_BLOCK`

It is not classified as a source/test failure because the hosted job had zero normal steps executed.

## No-overage WP10 continuity proof

While that external account condition persists, WP10 obtains equivalent current-WP compatibility evidence through `.github/workflows/v10-wp10-recovery-continuity.yml` on the existing repository-level Lenovo runner.

The continuity lane must:

- run only on `[self-hosted, Windows, X64, omni-cio-ci]`;
- reject fork PR execution through same-repository gating;
- use read-only GitHub contents permission and no repository secrets;
- bootstrap the existing protected Python 3.12.10 CI runtime for dependency staging only;
- acquire the official CPython **3.14.6** NuGet package into `RUNNER_TEMP`, because CPython documents the NuGet package specifically for CI/build systems that do not have a system-wide Python install;
- pin the NuGet package to exact version `3.14.6`, resolve its NuGet registration/catalog metadata, verify the downloaded package against the catalog `SHA512` package hash before extraction, and independently verify the extracted interpreter version;
- stage exact `pytest==9.0.2` and its pure Python dependencies into a separate temporary target, then execute the WP10 suite with the isolated 3.14.6 interpreter through `PYTHONPATH`;
- keep ordinary workflow steps on `cmd`, avoiding GitHub-generated PowerShell temporary scripts on this locked-down service token;
- invoke the repo-owned Windows PowerShell 5.1 parser probe explicitly with per-process `-ExecutionPolicy Bypass`, without changing `CurrentUser` or `LocalMachine` policy;
- run the deterministic WP10 recovery/manifest/profile/OWNER-boundary tests plus the continuity-contract regression test;
- leave production private database access, private portfolio data, recovery keys, and real secret values unused;
- remove the portable interpreter/dependency state and clean the worktree even on failure.

The early continuity attempts failed closed before compatibility tests ran. Investigation established two host-local differences from the disposable hosted image: the self-hosted service token could not resolve the OWNER-visible Python 3.14.6 installation, and its default Windows PowerShell execution policy rejected GitHub-generated temporary `.ps1` files (including the helper used by `actions/setup-python`). The continuity lane therefore avoids persistent machine mutation and those service-token assumptions: Python acquisition/integrity validation is performed by a repo-owned standard-library helper on the protected 3.12.10 runtime, the official portable CPython NuGet CI distribution stays under `RUNNER_TEMP`, and only the repo-owned PowerShell 5.1 parser probe is launched with a per-process bypass.

This lane deliberately does **not** claim to turn the persistent Lenovo host into a disposable GitHub-hosted VM. The missing disposable-image signal is recorded as degraded acceleration. The safety/correctness evidence is preserved through exact toolchain checks, isolated temporary state, the existing authoritative merge gate, the existing WP10 synthetic recovery audit, the existing off-device access-denial audit, and the OWNER physical recovery rehearsal.

## Exit-gate interpretation during this incident

For this billing/spending incident only, the WP10 phrase `hosted Windows compatibility passes` is interpreted consistently with the higher OWNER-approved no-paid-overage authority as:

- hosted Windows compatibility PASS when included hosted capacity is available; **or**
- exact-head `V10 WP10 Recovery Continuity` PASS when GitHub-hosted jobs are externally prevented from starting by quota/billing/spending state, with the hosted degradation explicitly recorded.

This substitution is valid only while all non-negotiable gates remain intact:

- `V10 authoritative merge gate` PASS remains mandatory;
- WP10 Recovery Audit PASS remains mandatory;
- WP10 Off-Device Audit PASS remains mandatory;
- OWNER off-device rehearsal evidence remains mandatory;
- `app:app`, `trading_methods=false`, and `REAL_TRADING_ENABLED=false` remain unchanged;
- no direct-main push, ruleset bypass, secret exposure, production DB access, or real-money authority expansion is permitted.

Global `V10 Fast PR Checks` and `V10 Toolchain Compatibility` remain hosted acceleration lanes. A billing-blocked red result with zero executed normal steps is retained as incident evidence rather than converted into a false source failure. They resume normally when included hosted capacity/account billing becomes available again.

## Completion rule

This decision does not itself make WP10 complete. After the continuity change, the new exact PR head must be revalidated. WP10 may proceed to merge only if the self-hosted continuity workflow and all authoritative/current-WP safety gates pass on that exact head and review-thread requirements are satisfied. Post-merge Regression Shield remains required before WP11 may start.
