# V10 Timeweb Worktree Convergence Runbook

Status: branch-local implementation in PR #584.

## Purpose

Keep the current repository worktree aligned with the active V10 delivery architecture:

`GitHub -> Dockerfile -> Timeweb App Platform -> PostgreSQL 18 -> omnicio.ru -> Telegram Login`.

Git history remains the provenance source for ordinary retired implementation. Non-sensitive
legacy files do not need to remain in the current tree merely to preserve historical
evidence. History rewriting is not part of this cleanup. Any actual sensitive-data
incident remains a separate response boundary.

## Phase A — clientless Cloudflare removal

The first deletion phase removes the dormant Cloudflare/WP22A clientless remote stack,
its complete `infrastructure/cloudflare/wp22a/` subtree, Windows/bootstrap code and
dedicated tests. The legacy workflow path is replaced by
`.github/workflows/v10-timeweb-worktree-convergence-audit.yml`, which executes only
Timeweb convergence/inventory guards. These surfaces
have no current Timeweb runtime authority and no current deployed consumer.

The phase is accepted only when:

- every retired path/prefix in the convergence contract is physically absent;
- the Timeweb convergence workflow is present and contains no retired provider execution;
- current Timeweb runtime sources contain no import/reference to that stack;
- no remaining GitHub workflow invokes the retired scripts or modules;
- protected V9 `render.yaml` still starts `app:app`;
- accepted PostgreSQL migration files remain present and unchanged;
- Timeweb/Telegram/public-user and broker/Real-money authority remain fail-closed;
- exact-head CI, Sonar and the authoritative Windows merge gate are GREEN.

## Later internal phases

After Phase A is source-certified, the same PR may continue with separately reviewed
internal phases for retired Render/Neon/Cloudflare runtime removal, Telegram-only auth
source convergence, and legacy documentation pruning/canonicalization. Each phase must
close producers, consumers, tests and governance in one coherent batch.


## Required-check compatibility

The GitHub App connection used for repository automation cannot read branch-protection
administration settings. GitHub requires a configured required status check to report on
the latest commit before merge. P5.5 therefore preserves the historical check-run context
`WP22A clientless external-access gate` inside the new Timeweb-named convergence
workflow while deleting the old workflow path and every retired clientless implementation
consumer. This is a merge-safety compatibility alias, not provider/runtime authority.
It can be retired only after branch-protection configuration is independently proven not
to require that context.


## Orphan-consumer closure

The first Phase-A exact-head Regression Shield exposed one stale test consumer after the
OpenTofu bootstrap producer had been removed:
`tests/test_v10_wp22a_bootstrap_retry_contract.py` still opened
`scripts/bootstrap_wp22a_terraform.ps1`. The test protected only behavior of the retired
bootstrap implementation and had no Timeweb consumer.

The correction removes that orphan test and adds its path to the convergence contract's
required-absence set. This closes the producer/consumer pair instead of recreating the
retired OpenTofu bootstrap merely to satisfy historical tests.
