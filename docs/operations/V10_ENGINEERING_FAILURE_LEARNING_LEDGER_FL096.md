# V10 Engineering Failure Learning Ledger — FL096

Date: 2026-09-06  
Scope: CF-D exact-main production database bootstrap origin custody  
Authority: Amendment 14 + Amendment 15 + `V10_CLOUDFLARE_RELEASE_ACCEPTANCE_CONTRACT.json`

## Observed failure

Accepted `main` `80d1cfdba1073ef7a5c20033c266a3d92edee576` completed the
exact-main post-merge gate, isolated staging Worker/Container rehearsal, staging live
acceptance, domain validation, and production Worker-anchor bootstrap. The production
release then stopped before any production deploy at:

`Reuse production database secret or bootstrap it once`

with the sanitized evidence:

- production database binding state: `BOOTSTRAP_REQUIRED`;
- CF-D staging bootstrap: `STOPPED`;
- code: `CLOUDFLARE_CF_D_STAGING_BOOTSTRAP_FAILED`;
- production Build, Custom Domain mutation, and live acceptance: not attempted;
- cleanup/quarantine: completed.

Provider-side Function telemetry for the failure window contained no Function invocation.
Therefore the failure remained on the trusted staging Worker/configuration side, before
the source-controlled Neon Function could authenticate the GitHub OIDC request.

## Root cause

PR #450 hardened the runtime consumer so that external CF-D Function egress can only use
`OMNI_V10_CF_D_NEON_BOOTSTRAP_ORIGIN`, a secret-bound Worker value which is independently
validated against the staging database branch and Frankfurt cell.

The accepted release path did not add a matching producer/convergence mechanism for that
new binding. Existing staging secret convergence only managed `OMNI_V10_POSTGRES_DSN`.
Consequently an exact-main staging candidate could be healthy while the later production
bootstrap route remained unable to resolve its trusted external Function origin.

This was a producer/consumer configuration-authority defect, not a reason to weaken the
secret-bound egress guard and not a reason to restore the long-lived Neon management API
key as production bootstrap authority.

## Blast radius

The defect affects the one-time CF-D production database-role bootstrap when the
production runtime database secret does not yet exist. It does not authorize or change:

- V9 production/recovery behavior or the stable `app:app` entrypoint;
- broker write authority;
- `trading_methods=false`;
- `REAL_TRADING_ENABLED=false`;
- `PUBLIC_MULTI_USER_ENABLED=false`;
- Telegram/VK provider authority;
- an already-present production database secret reuse path.

The failed run stopped before production Worker promotion, so no failed production
mutation required rollback.

## Corrective design

The staging exact-SHA candidate now converges bootstrap-origin custody after its gated
Build reaches terminal success and before the staging trigger is quarantined:

1. GitHub Actions generates a fresh 256-bit random synchronization token in runner memory.
2. The token is stored temporarily as the staging Worker secret
   `OMNI_V10_CF_D_ORIGIN_SYNC_TOKEN` and is never passed into the Container.
3. A staging-only Worker route accepts only `POST`, the exact compiled source SHA, the
   staging runtime role, and a constant-time match of that short-lived token.
4. The Worker reuses the accepted bounded Neon branch-proof path from the trusted staging
   database secret and derives the canonical same-cell Frankfurt Function origin.
5. The authorized runner receives the origin without logging it, removes the ephemeral
   synchronization token, then stores the result as the persistent secret
   `OMNI_V10_CF_D_NEON_BOOTSTRAP_ORIGIN`.
6. The runner verifies the persistent binding exists and the synchronization token is
   absent before candidate acceptance continues.
7. The production bootstrap consumer still revalidates the stored origin against the
   runtime database branch before any Function egress. No Container-selected or
   caller-selected external target is introduced.

Cloudflare secret mutation remains inside existing Workers Scripts authority. No new
Neon management credential, provider identifier in logs, repository secret, or durable
synchronization credential is introduced.

## Permanent regression guards

The correction is guarded by deterministic tests for:

- exact staging Worker-origin scope;
- bounded Frankfurt Function-origin syntax;
- ephemeral-token cleanup before persistent origin write;
- cleanup on fetch failure and fail-closed cleanup failure;
- bounded propagation retry only for transient/rejected states;
- Worker-only route ordering ahead of the generic Container `/api/*` proxy;
- production-role invisibility of the custody route;
- exact SHA/token rejection before provider egress;
- branch-proof failure returning only a sanitized 502 response;
- gated-candidate cleanup after custody failure;
- machine-readable release-contract requirements forbidding token persistence and Neon
  management API dependence.

## Acceptance law

This defect is not accepted as resolved merely because the branch tests are green.
Acceptance requires the focused PR exact-head checks to succeed, merge by normal protected
workflow, post-merge Regression Shield success on the new exact `main`, and a fresh
`V10 Cloudflare Production Release` reaching the formerly failing production database
bootstrap step successfully without weakening any protected V9, broker, Real, or public
multi-user invariant.
