# V10 GitHub Pro Hybrid CI

## Purpose

Use GitHub Pro hosted capacity for fast, clean, parallel feedback while keeping the dedicated Lenovo Windows runner as the independent merge-authority and continuity path.

## Architecture

### GitHub-hosted acceleration

GitHub-hosted runners are intentionally disposable and are used for:

- fast Linux policy/source checks;
- clean Windows Python 3.14.6 compatibility;
- clean Windows Node.js 24.18.0 / npm 11.16.0 compatibility;
- frontend type/lint/unit/build checks;
- SBOM and dependency-audit outputs;
- dependency caching and parallel execution while hosted minutes are available.

Hosted acceleration is valuable for speed and clean-room compatibility, but it is not the sole merge authority. If the included hosted-minute quota is exhausted or GitHub-hosted capacity is unavailable, repository development must remain possible through the self-hosted authority path.

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

The Lenovo gate deliberately does **not** install Python 3.14 or Node.js during a PR job. Runtime installation inside a self-hosted Windows service account introduced unnecessary MSI/administrator coupling and made merge authority less deterministic. Exact V10 Python/Node compatibility remains an independent GitHub-hosted clean-room lane.

This separation is permanent architecture, not an outage workaround: the Lenovo lane proves the protected production runtime and security invariants; GitHub-hosted lanes prove clean modern-toolchain compatibility and provide acceleration.

## Security invariants

- repository remains private;
- `main` remains protected;
- squash is the only merge method;
- force pushes and branch deletion are blocked;
- workflow token defaults to read-only;
- Actions cannot approve pull requests;
- external Actions are pinned to full commit SHAs;
- self-hosted jobs reject fork PRs;
- no repository secrets are consumed by PR validation jobs;
- `app:app` remains the Render entrypoint;
- `trading_methods=false` remains protected.

## Outage behavior

During a GitHub Actions incident, `scripts/finalize_github_during_actions_outage.ps1` may skip GitHub-hosted acceleration and use only the exact-head Lenovo smoke + authoritative gate for the infrastructure cutover. It retains fail-closed behavior: no ruleset cutover or merge occurs unless both exact-head self-hosted checks are successful.

After GitHub-hosted capacity recovers, hosted acceleration resumes automatically on subsequent PR events.
