# V10 Engineering Failure Learning Ledger — FL064

## Scope

Current System Update: `CLOUDFLARE-PUBLIC-PRODUCT-INTEGRATED`, gate CF-C LIVE.

This entry records a provider-gate ordering defect discovered while validating Cloudflare Workers Builds authority. It does not grant CF-C acceptance and does not authorize CF-D.

## Failure

`V10 Cloudflare Provider Readiness` correctly detected that the protected Cloudflare API token lacked Workers Builds API authority and stopped fail-closed.

`V10 Cloudflare Candidate Deployment` is an independent push workflow. It resolved provider identity, provisioned the isolated Neon staging runtime role, and bootstrapped the isolated staging Worker before `bootstrap_v10_cloudflare_builds.py` reached the same insufficient Workers Builds authority condition.

The failure was therefore not a reason to weaken the provider gate. It exposed a sequencing defect: a mutating workflow relied on a sibling readiness workflow that can race independently.

## Root cause

The non-mutating Workers Builds authority probe existed only in the readiness workflow. GitHub Actions does not provide an ordering guarantee between these independent push workflows, so Candidate could begin provider mutation before Readiness finished.

## Blast radius

The pattern applies to any independently triggered provider workflow that assumes another workflow has already proved downstream authority. The immediate blast radius is CF-C Candidate Deployment; no broader provider workflow is granted an exception.

## Durable prevention

1. Candidate Deployment must execute `scripts.probe_v10_cloudflare_workers_builds_authority.py` after protected provider identity resolution and before its first provider mutation.
2. Candidate must fail closed on missing or insufficient Workers Builds authority. It must not provision Neon, deploy a Worker, configure Workers Builds, or trigger a build after that failure.
3. Repository validation must assert that the authority probe exists and precedes all known CF-C provider mutation steps.
4. Regression tests must reject both a missing probe and a probe moved after the first provider mutation.
5. The separate Provider Readiness workflow remains a useful independent signal but is not a substitute for the mutating workflow's own pre-mutation authority gate.

## Security invariants preserved

- No provider token or identifier is logged.
- Protected GitHub Actions secret custody remains unchanged.
- No permission check is bypassed or downgraded.
- `REAL_TRADING_ENABLED=false` remains protected.
- `trading_methods=false` remains protected.
- CF-C remains not accepted until exact-head live provider evidence succeeds.
- CF-D remains blocked until CF-C is accepted.

## External authority blocker

Cloudflare documents that the Workers Builds API requires a user-scoped API token with Workers Builds configuration authority. Until the protected token has the required authority, the correct result is a fail-closed provider gate rather than a code workaround.
