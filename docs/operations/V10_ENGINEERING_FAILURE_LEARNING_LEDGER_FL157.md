# V10 Engineering Failure Learning Ledger — FL157

## Classification

- Work unit: `CLOUDFLARE-PUBLIC-PRODUCT-INTEGRATED / CF-D`
- State at discovery: `MAIN_RED_STOP`
- Failure class: `CF_D_NEON_SELF_HOSTED_EGRESS_BLOCKS_RUNTIME_BOOTSTRAP`
- Scope: missing staging/production runtime-secret recovery inside the exact-main Cloudflare release

## Symptom

Exact protected main `aa2c4397eefdc6d3ddb26d2054cf66de64c39cfd` carried the accepted secret-free egress diagnostic from PR #534. Its post-merge run reproduced a stable egress split for one synthetic anonymous Neon management-API request: self-hosted Windows received `403 / HTML`, while GitHub-hosted Ubuntu received `401 / JSON`.

Production Release #71 then passed exact-main provenance, the post-merge release gate, Cloudflare authority, pinned delivery tooling, exact-SHA staging Worker + Container rehearsal, staging live acceptance, canonical-domain validation and the production Worker anchor. The production runtime secret was absent, so the canonical project-scoped Neon provisioner ran on the self-hosted Windows runner and failed before database mutation with the bounded `403 / HTML` denial. Authenticated, anonymous, request-fingerprint and independent curl controls remained observationally unchanged.

## Root cause

The active release workflow still executed an egress-sensitive Neon management/bootstrap transaction on the self-hosted Windows contour after accepted evidence proved that contour receives a different provider-edge response class than the hosted Ubuntu control.

The credential, ordinary request fingerprint and Python-versus-curl implementation were no longer useful variables to perturb. Re-running the canonical provisioner on the same egress could not resolve the external boundary that the repository does not control.

The defect is architectural placement, not a reason to weaken project/branch authority: the rare missing-secret recovery transaction must execute from a controlled egress that reaches the provider API layer while the exact-main release, Cloudflare promotion and protected database semantics remain unchanged.

## Blast radius

The same workflow contained two missing-secret Neon producer paths:

- staging bootstrap, before the exact staging Worker + Container rehearsal;
- production bootstrap, after the exact staging rehearsal and production Worker anchor.

Both used the same self-hosted Windows network boundary. Repairing production only would leave a latent failure when the reusable staging runtime secret is absent. The focused CF-D repair therefore moves both **missing-secret recovery** paths, while leaving normal secret-reuse releases on the self-hosted authority contour.

Production has an additional security boundary from FL138: once exact branch custody exists, production must use the exact branch resource and must not regress to branch collection enumeration. The repair must preserve that rule even though the hosted recovery job is a new process boundary.

## Permanent correction

- Keep the canonical `scripts/provision_v10_cloudflare_neon_runtime.py` as the only active database producer.
- Keep the accepted project-scoped `NEON_API_KEY`; do not broaden to organization/admin authority.
- Probe Cloudflare runtime-secret state on the self-hosted release contour before any hosted Neon job is applicable.
- If staging is missing, run the canonical staging provisioner on an ephemeral GitHub-hosted Ubuntu runner and write its DSN directly to the existing staging Worker secret in the same job.
- Complete the exact-main staging Worker + Container rehearsal and live acceptance on the self-hosted authority contour as before.
- If production is missing, let the hosted job reacquire exact production branch custody from the **already accepted exact-SHA staging release** using the existing ephemeral origin-sync token protocol.
- Validate and write that bootstrap target only to the hosted job's restricted `RUNNER_TEMP` handoff, then invoke the unchanged canonical production provisioner. Its existing exact project/branch/default/ready checks remain authoritative.
- Write the production DSN directly to the Cloudflare Worker secret in the same hosted job. Do not transfer DSNs or raw Neon identifiers through outputs or artifacts.
- Return to a fresh self-hosted promotion job, re-probe the production secret through Cloudflare authority, and preserve stale-Build quarantine, rollback snapshot, exact-current-main recheck, gated production Workers Build, domain attach, live acceptance and bounded rollback.
- Keep the retained Neon Function transport inactive.

## Why production custody is resynchronized instead of exported

FL138 explicitly rejected production branch collection enumeration when trusted exact branch custody exists. Exporting the raw branch identifier as a normal cross-job output would also widen identifier custody unnecessarily.

The accepted staging runtime already exposes a bounded, token-gated custody endpoint whose response is tied to the exact release SHA. The hosted production recovery therefore creates a fresh short-lived sync token, requires the existing staging release to attest the exact accepted SHA, fetches the validated bootstrap-origin custody, deletes the token, writes the established restricted target descriptor locally, and immediately invokes the canonical exact-branch provisioner.

This preserves the original authority chain without branch collection fallback and without raw branch/project identifiers crossing a job boundary.

## Dependency and source integrity

The hosted recovery job manually fetches the exact accepted repository SHA and uses the repository-pinned `actions/setup-python` commit for Python `3.12.10`. It generates a minimal Linux control-plane dependency projection from canonical `requirements.txt` and installs it with hash enforcement. No dependency is upgraded or independently pinned by this repair.

Provider credentials remain step-scoped. No DSN, provider credential, raw branch/project identifier, response body, private portfolio payload, or account identifier may be logged or stored as an artifact.

## Permanent regression / guard

Deterministic coverage requires:

- hosted staging/production jobs to be conditional only on proven missing runtime secrets;
- self-hosted release jobs to receive no Neon credential;
- hosted provider credentials to be step-scoped and unavailable to setup/bootstrap steps that do not need them;
- exact repository SHA bootstrap on every job;
- hosted Python version and external Action SHA to remain pinned;
- hosted dependency projection to be derived from canonical `requirements.txt` with hash enforcement;
- production hosted recovery to require exact-SHA staging release attestation before custody fetch;
- production custody to use the existing ephemeral sync-token protocol and restricted runner-temp handoff;
- production canonical provisioning to retain exact branch authority and never use branch collection enumeration after custody exists;
- DSNs and raw Neon project/branch identifiers never to cross job outputs, artifacts or summaries;
- applicable hosted recovery to require terminal `success`; skipped is acceptable only when the corresponding secret probe proved reuse;
- downstream exact-main, Cloudflare, domain, live-acceptance and rollback gates to remain unchanged;
- the legacy Neon Function transport to remain inactive.

## Prevention law

When a provider control-plane failure is proven sensitive to the runner egress boundary, move the **minimum egress-sensitive transaction** to a clean controlled runner instead of weakening authentication or retrying the same blocked contour. Preserve existing resource-custody laws across the process boundary: reacquire trusted custody through an already accepted bounded protocol when possible, rather than exporting raw identifiers or falling back to broader provider enumeration.

## Protected invariants

Unchanged: protected V9 `app:app`; PostgreSQL 18 + RLS/FORCE RLS; `PUBLIC_MULTI_USER_ENABLED=false`; broker write OFF; `trading_methods=false`; `REAL_TRADING_ENABLED=false`; transfer/withdrawal/margin/leverage/uncovered-short remain OFF/FORBIDDEN; no provider secret/private payload disclosure; WP23+, WEB-VISUAL, Telegram and AI/Cortex remain out of scope.
