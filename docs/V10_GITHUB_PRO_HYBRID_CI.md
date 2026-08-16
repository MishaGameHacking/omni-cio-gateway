# V10 GitHub Pro Hybrid CI

## Purpose

Use GitHub-hosted capacity for disposable acceleration/clean-room compatibility when it is actually available, while keeping the dedicated Lenovo Windows runner as the independent merge authority and continuity path.

## Architecture

### GitHub-hosted acceleration / clean-room evidence

When OWNER-controlled hosted capacity is available, GitHub-hosted runners are intentionally disposable and are used for:

- fast Linux policy/source checks where useful;
- clean Windows Python 3.14.6 compatibility;
- clean Windows Node.js 24.18.0 / npm 11.16.0 compatibility;
- frontend type/lint/unit/build acceleration;
- SBOM and dependency-audit outputs;
- dependency caching and parallel execution.

Hosted acceleration is valuable for speed and clean-room compatibility, but it is not the sole merge authority. Repository development must remain possible through the self-hosted authority path when hosted capacity is unavailable, without fabricating clean-room evidence.

### Current capacity-degraded mode — OWNER observation 2026-08-16

The OWNER-observed GitHub Actions account state is currently `USD 0` budget with `Stop usage = Yes`. The machine-readable engineering quality contract therefore records:

`current_hosted_capacity_state = BLOCKED_OWNER_ZERO_BUDGET_HARD_STOP`.

While that state remains current:

- deterministic fast policy/source checks run on the Lenovo continuity lane;
- frontend fast checks may use the already accepted exact Node.js 24.18.0 / npm 11.16.0 installation on Lenovo;
- the `V10 Toolchain Compatibility` workflow executes capacity/applicability checks on Lenovo rather than starting a known budget-blocked hosted VM;
- a green capacity/applicability job **does not mean** Python 3.14.6 or disposable hosted Node compatibility passed;
- the workflow explicitly reports `NOT_APPLICABLE` or `REQUIRED_BY_PATH but CURRENTLY_CAPACITY_BLOCKED` while itself executing successfully;
- job-level `skipped` is not used as V10 GREEN evidence for these lanes;
- the mandatory `V10 authoritative merge gate` remains unchanged and must still pass on exact head;
- STABLE release provenance may not invent missing hosted compatibility evidence.

There is one important non-equivalent case: the protected V9 deployed-authority probe is external evidence, not deterministic source validation. A bounded diagnostic established that the Lenovo Personal Node can resolve the protected Render hostname but cannot establish the required TCP/443 path, so Lenovo is not an equivalent observer for that evidence. The actual `Live Gateway Authority Acceptance` therefore remains a manual GitHub-hosted workflow and its current evidence state is `DEFERRED_NO_TRUSTED_ZERO_COST_ROUTE_NOT_PASS`. A separate self-hosted PR contract validates that this evidence is not fabricated or silently dropped. Any V9 runtime/deployment/Action-authority release that owns production acceptance remains blocked until real hosted live acceptance is available and succeeds.

This is a controlled capacity mode, not a permanent deletion of the hosted clean-room or independent-live-evidence architecture. Before restoring hosted jobs or automatic live probing, engineering must re-verify current OWNER-controlled billing/budget state and the required trusted network route, then land the routing change through a normal all-GREEN PR.

### Lenovo authoritative continuity

The repository-level runner `omni-cio-ci` uses labels:

- `self-hosted`
- `Windows`
- `X64`
- `omni-cio-ci`

The required `V10 authoritative merge gate` runs the protected production-runtime checks on the Lenovo runner:

- verified Python 3.12.10 bootstrap owned by the repository;
- isolated virtual environment under `RUNNER_TEMP`;
- hash-locked dependency installation and lock verification;
- repository/CI/V10 policy contracts;
- compilation, Ruff, formatting and mypy;
- stable `app:app` and read-only release contract;
- full pytest Regression Shield with coverage threshold;
- dependency audit, Bandit SAST and detect-secrets;
- deterministic workspace cleanup.

The Lenovo authoritative gate deliberately does **not** install Python 3.14 during a PR job. Runtime installation inside a self-hosted Windows service account introduced unnecessary MSI/administrator coupling and made merge authority less deterministic. The currently installed Node.js toolchain is separately pinned and exercised by accepted Web gates; it is not represented as a disposable clean-room VM.

The architectural separation remains: Lenovo proves the protected production runtime and security invariants; actual GitHub-hosted clean-room runs, when available, provide independent modern-toolchain compatibility evidence. External deployed-authority evidence likewise stays bound to a genuinely independent reachable observer rather than being silently moved to the Personal Node.

## Why this split is faster and safer

- Heavy deterministic regression/security work stays on the always-available Lenovo runner and does not require hosted minutes.
- No workflow repeatedly starts a hosted job already known to be blocked by OWNER budget state.
- Exact Python 3.14.6 / Node 24.18.0 clean-room claims are made only when a disposable compatibility environment actually ran.
- External live authority is claimed only when an independent trusted observer actually reached and validated the deployment.
- The authoritative Lenovo gate never depends on MSI installation, administrator escalation, or a mutable machine-wide Python toolchain during a PR run.
- Missing hosted acceleration/live evidence is classified truthfully rather than converted into either a code failure or a fake PASS.

## Security invariants

- repository remains private;
- `main` remains protected;
- squash is the only normal merge method;
- force pushes and branch deletion remain blocked by repository policy;
- workflow token defaults to read-only;
- Actions cannot approve pull requests;
- external Actions are pinned to full commit SHAs;
- self-hosted jobs reject fork PRs where required;
- no repository secrets are consumed by ordinary PR validation jobs;
- `app:app` remains the protected V9 compatibility entrypoint;
- `trading_methods=false` remains protected;
- `REAL_TRADING_ENABLED=false` remains protected until its owning later WP.

## Capacity / outage behavior

A provider outage, exhausted quota, OWNER hard budget stop or unavailable network path is an infrastructure/capacity condition, not permission to weaken code/security gates or mislabel missing evidence as PASS.

The accepted response is:

`classify capacity/network semantics -> avoid guaranteed RED -> execute only semantically equivalent zero-cost deterministic/authoritative lanes -> report missing clean-room/live evidence explicitly -> merge only if every applicable exact-head check is success -> preserve missing evidence as a blocker for any later release claim that owns it`.

When hosted capacity or a trusted live-observer route recovers, it must be re-verified rather than assumed. A focused CI/governance PR then restores the corresponding lanes and must itself satisfy the same GREEN merge law.
