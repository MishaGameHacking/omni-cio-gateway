# V10 Engineering Failure Learning Ledger — FL072

## Scope

Current System Update: `CLOUDFLARE-PUBLIC-PRODUCT-INTEGRATED`, CF-D production
release/cutover design after real CF-C staging acceptance.

This entry records release-boundary defects discovered before production promotion.
No production cutover, public multi-user activation, broker write or Real execution is
authorized by this ledger.

## Findings

### A. Direct Cloudflare Git production deploy would bypass post-merge authority

The branch release contract previously required automatic Git deployment from `main`.
Cloudflare Git-integrated production builds are push-triggered, while Amendment 14
requires exact-new-main post-merge repository gates to succeed before production
promotion. Those two requirements cannot both be true if Cloudflare deploys the
production Worker directly on the initial `main` push.

Root cause: the initial CF-D contract described the desired continuous-release outcome
but did not model the temporal ordering between Git push, repository post-merge gates
and Cloudflare production mutation.

Correction: direct Cloudflare Git production auto-deploy is forbidden. A default-branch
GitHub `workflow_run` release waits for successful `Regression Shield`, verifies every
observed latest same-SHA push workflow, rechecks current `main`, rehearses the exact
accepted SHA on isolated staging, then performs a gated production Workers Build.

### B. Re-provisioning the production database role on every release could cause outage

The Neon runtime provisioner intentionally creates/rotates runtime credentials. That is
safe for isolated staging, but using the same operation on every production release can
invalidate the database secret used by the currently serving production Worker before
the replacement release is accepted.

Root cause: a bootstrap primitive was at risk of being reused as a normal release
primitive even though credential rotation changes runtime authority state.

Correction: production probes the existing Cloudflare `OMNI_V10_POSTGRES_DSN` secret.
If it exists, the production database role/secret is reused unchanged. Provisioning and
secret upload occur only when the production Worker secret is absent during first
bootstrap. Secret values are never logged.

### C. Production Container deployment cannot depend on local Lenovo image tooling

CF-C already proved that the accepted Container path is Cloudflare Workers Builds. The
self-hosted Windows runner is an authority/orchestration node, not an accepted Docker
image builder. A local `wrangler deploy` for the full Container release would therefore
reintroduce an unproven local build dependency.

Correction: production uses a temporary Cloudflare Workers Build trigger with an
impossible sentinel branch and a manual exact-`main` build request. The trigger is
quarantined after terminal execution; unknown production triggers fail closed.

### D. A provider build can outlive a failed orchestration job

A GitHub job timeout, runner loss or provider/API interruption can terminate the
orchestrator while a Cloudflare production Workers Build remains queued or running.
Starting the next release by snapshotting the current Worker first would leave a race:
the stale build could complete after the snapshot and replace production with an older
SHA outside the new release's rollback evidence.

Root cause: GitHub job concurrency serializes orchestrators, but it does not by itself
cancel provider-side work that already escaped the runner lifecycle.

Correction: CF-D has an explicit production quarantine before the rollback snapshot.
It validates/deletes only the owned sentinel-gated production trigger, fails closed on
any unknown trigger, cancels every nonterminal Workers Build targeting the exact
production Worker, verifies cancellation reached a terminal state, and then captures
the rollback version. The normal production runner repeats the quarantine immediately
before creating its new gated trigger to close the orchestration/provider race window.

### E. Failed live acceptance requires a precise rollback target

Container deployment completion is not equivalent to application readiness. A failed
release/domain/health check could otherwise leave a bad version active.

Correction: CF-D snapshots the current single-version 100% Worker deployment before
promotion and rolls back explicitly to that version on production deploy/domain/live
failure. First bootstrap creates a 503/no-store, no-`workers.dev` version, so even the
first cutover has a bounded rollback target.

## Blast radius and coupled surfaces

The review covered:

- Cloudflare Workers Builds trigger lifecycle;
- GitHub post-merge workflow ordering;
- `wrangler.jsonc` production/staging exposure;
- Neon runtime credential provisioning;
- Cloudflare Worker secret custody;
- Custom Domain authority;
- Container rollout/live health behavior;
- rollback/recovery;
- exact-SHA release identity;
- protected V9 and broker/security locks.

No database schema, tenant contract, product-auth provider or broker authority change is
required.

## Permanent learning

1. Continuous deployment must be modeled as an authority timeline, not merely as a
   provider trigger.
2. Bootstrap credential rotation must never be silently reused as a normal production
   release step.
3. A build substrate proven for candidate Containers should remain the build substrate
   for production unless a separate compatibility gate proves a replacement.
4. Provider-side builds can outlive CI orchestration; quarantine stale production
   work before taking a rollback snapshot or starting a new release.
5. Provider deployment success is not live acceptance; snapshot rollback authority
   before mutation and verify health after it.
6. Production custom-domain attachment is a service/zone authority mutation and must
   fail closed on any ownership drift.

## Security invariants preserved

- Protected V9 `app:app` remains unchanged.
- `PUBLIC_MULTI_USER_ENABLED=false` remains unchanged.
- Telegram/VK production activation remains outside CF-D infrastructure cutover.
- Broker write remains OFF.
- `trading_methods=false` and `REAL_TRADING_ENABLED=false` remain unchanged.
- No real provider, database or broker secret value is added to source or logs.
