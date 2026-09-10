# V10 Engineering Failure Learning Ledger — FL119

## Failure class

`CF_D_NEON_FUNCTION_SOURCE_DEPLOYMENT_DRIFT`

## Accepted evidence

Exact accepted `main` `2130d65e306781884ee288ddb53b2cc5e80b83ea` is newer than the active `cfdprodbootstrap` Neon Function deployment that was present during the PR #482 repair review. PR #482 also changes `infrastructure/cloudflare/cf_d_neon_bootstrap/index.mjs` so the direct bootstrap client can use the dedicated `X-Omni-GitHub-OIDC` ingress namespace.

The exact-main production release workflow did not contain a source-controlled Neon Function code-deployment step. Therefore a repository change to the bootstrap Function could pass CI/Sonar and still leave the provider serving an older handler. The new client would then consume behavior that the active provider runtime did not contain.

No Function URL, project/branch identifier, deployment identifier, API key, OIDC token, database credential or private payload is recorded in this ledger.

## Root cause and blast radius

The CF-D release composition treated the Neon Function origin as trusted provider custody, but did not make Function **code provenance** part of the exact-main release transaction. Source authority and runtime authority could drift independently.

This is a deployment-composition defect, not a database-schema defect and not evidence that Neon/PostgreSQL 18 is incompatible with Omni-CIO. The blast radius is the one-time CF-D production database bootstrap helper only. Staging Worker/Container runtime, protected V9 `app:app`, tenant/RLS semantics, broker boundaries and Real execution are unchanged.

The adjacent failure mode is especially dangerous after an ingress-contract change: a new client can be published before the provider handler that understands the new request shape. A green source-only test suite cannot prove that provider ordering.

## Correction

1. Exact-main CF-D rehearsal checks whether the production runtime database secret already exists using the read-only Cloudflare secret-state surface.
2. When the production runtime secret is already present, no Neon Function code mutation is performed.
3. When bootstrap is still required, the exact-main rehearsal deploys the source-controlled `infrastructure/cloudflare/cf_d_neon_bootstrap/index.mjs` to the **existing** canonical `cfdprodbootstrap` Function before the direct bootstrap step can mint or transmit GitHub OIDC.
4. The deployer requires the exact Git checkout SHA, the restricted bootstrap target descriptor, the same default Neon branch, the exact Frankfurt Function origin and a previously healthy existing Function. It never creates an alternate Function or branch.
5. The deployment ZIP has one root entry, `index.mjs`, and uses the accepted Node.js 24 runtime. Omitted Function environment remains provider-managed; no database credential is copied into GitHub or artifacts.
6. The deploy POST is not automatically retried after an ambiguous transport result. The returned deployment identity must become both current and active with `completed` status within a bounded wait; concurrent/superseding deployment state fails closed.
7. Provider response bodies and provider identifiers are not reflected into logs or artifacts. Only sanitized failure codes and readiness state are emitted.
8. The existing direct Function handler preflights still execute after deployment, and real GitHub OIDC remains minted only after source-controlled GET and dedicated-header POST provenance checks pass.

## Permanent regression guard

Deterministic tests verify deterministic single-entry Function archive construction; exact handoff branch equals exact Neon default branch; exact Function origin and existing completed deployment requirements; returned deployment identity must become the active completed deployment; a concurrent/superseding deployment fails closed; production runtime-secret reuse suppresses unnecessary Function redeployment; exact-main candidate composition calls Function deployment only after bootstrap-origin custody; and the machine-readable release contract requires exact-main Function deployment before OIDC mint when bootstrap is still required.

## Prevention law

A source-controlled provider helper that participates in an exact-SHA security/release transaction must have an explicit runtime-provenance edge in the release graph. Client and server protocol changes may not be accepted merely because both source trees compile; the provider handler that consumes the protocol must be deployed and identified before the new client uses it. Provider mutation must remain bootstrap-if-needed rather than becoming an unconditional per-release side effect.

## Protected invariants

Unchanged: protected V9 `app:app`; `PUBLIC_MULTI_USER_ENABLED=false`; `trading_methods=false`; `REAL_TRADING_ENABLED=false`; broker write, transfer, withdrawal, margin, leverage and uncovered short remain OFF/FORBIDDEN; PostgreSQL 18 + RLS/FORCE RLS remains relational truth; no D1/Hyperdrive/Web Visual/Telegram/AI/Cortex scope; no real credential/provider identifier/private payload is written to source, logs or artifacts.
