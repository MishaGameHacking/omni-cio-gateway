# Dependency maintenance policy

This repository uses strict, reproducible dependency inputs and hash-locked outputs.

## Sources of truth

- `requirements.in` — direct runtime dependency constraints.
- `requirements.txt` — generated/hash-locked runtime dependency set.
- `requirements-dev.in` — direct CI, test and security tooling constraints; includes `requirements.in`.
- `requirements-dev.txt` — generated/hash-locked development dependency set.
- `.github/dependabot.yml` — automated version-update policy.
- `.github/workflows/regression-shield.yml` — exact-head quality, lock, contract, coverage and security gate.

Generated Windows projection files are CI artifacts and must not be committed. `scripts/windows_ci_lock.py` derives/compares them from the canonical root lock files.

## Update rules

1. Dependabot PRs are proposals, not automatic authorization to merge.
2. Each dependency change must be tested against the current `main`, not an obsolete merge base.
3. A Python dependency update must update both its `.in` source and the corresponding generated hash lock when resolution changes.
4. Exact-head Regression Shield and security must be green before merge.
5. Major runtime/SDK upgrades receive dedicated compatibility review even if resolution succeeds.
6. Do not weaken lock verification, security checks, `app:app`, GPT Action boundaries or real-money execution safeguards to make an update green.
7. If an upstream toolchain version is known-incompatible, pin the last verified version and record a narrow Dependabot ignore for only the incompatible release/range. Remove the ignore after upstream compatibility is available and verified.

## Current temporary compatibility hold

`pip==26.2` is intentionally deferred. The current supported `pip-tools==7.6.0` imports a pip internal symbol removed by pip 26.2, causing lock regeneration to fail before project tests can run. The repository therefore keeps the last verified pip version while retaining all other Dependabot/security monitoring.

This hold affects CI/dependency tooling only; it does not alter Gateway runtime behavior or GPT configuration.
