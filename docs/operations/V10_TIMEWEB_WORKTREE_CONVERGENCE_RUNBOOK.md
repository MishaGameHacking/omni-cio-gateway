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
its complete `infrastructure/cloudflare/wp22a/` subtree, Windows/bootstrap code,
dedicated workflow and tests. These surfaces
have no current Timeweb runtime authority and no current deployed consumer.

The phase is accepted only when:

- every path in the convergence contract is physically absent from the current tree;
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
