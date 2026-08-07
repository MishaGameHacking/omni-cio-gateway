# Omni-CIO V10 — Release Provenance and GitHub Pro Budget Runbook

Status: **WP4 operating contract**  
Scope: repository release provenance, hosted CI routing, Actions budget/cache/artifact discipline, release/tag administration.

## 1. Current GitHub Pro facts re-verified for WP4

Official GitHub documentation was re-checked on 2026-08-07 before implementation. Current personal GitHub Pro planning values remain:

- 3,000 included GitHub Actions hosted minutes/month;
- 1 GB included Actions artifact storage;
- 10 GB Actions cache storage per repository;
- 180 Codespaces core-hours/month and 20 GB Codespaces storage/month;
- repository rulesets can protect tags in private GitHub Pro repositories;
- repository release immutability can protect future published release tags/assets;
- included-usage alerts are available at 90% and 100%;
- budgets may warn at 75/90/100% and can stop usage where GitHub exposes that control.

Official references:

- https://docs.github.com/en/billing/reference/product-usage-included
- https://docs.github.com/en/billing/concepts/product-billing/github-actions
- https://docs.github.com/en/actions/reference/workflows-and-actions/dependency-caching
- https://docs.github.com/en/billing/concepts/budgets-and-alerts
- https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/about-rulesets
- https://docs.github.com/en/code-security/how-tos/secure-your-supply-chain/establish-provenance-and-integrity/prevent-release-changes

The implementation must re-check these facts before depending on a plan-specific feature after material GitHub billing/feature changes.

## 2. Hosted-minute operating budget

Use the accepted 50/25/15/10 target against the 3,000-minute monthly allowance:

| Bucket | Target | Planning minutes |
|---|---:|---:|
| Fast PR / ordinary hosted validation | 50% | 1,500 |
| Clean-room hosted compatibility | 25% | 750 |
| Release / recovery validation | 15% | 450 |
| Incident / emergency reserve | 10% | 300 |

These are planning buckets, not GitHub hard quotas. Review actual billed usage in GitHub Billing rather than assuming raw wall-clock minutes equal billed consumption.

When pressure rises:

1. keep the Lenovo authoritative gate;
2. keep fast policy/source checks on every PR;
3. let path routing skip irrelevant hosted Windows jobs;
4. reduce optional clean-room frequency before touching safety gates;
5. preserve the 10% incident reserve where practical;
6. never use direct pushes or disabled checks as a quota workaround.

## 3. Path-aware routing

Top-level PR workflow path filters remain forbidden for safety-critical workflows. Every PR still enters the workflow and runs policy checks.

`v10_ci_router.py` decides only which expensive hosted compatibility jobs are necessary:

- docs/program only -> policy checks, no hosted Windows compatibility;
- backend/Core/broker/infrastructure -> hosted Windows Python;
- frontend -> hosted Windows frontend;
- dependency/toolchain/release/security -> both hosted Windows lanes;
- unknown new path -> conservative backend + release/security routing.

`workflow_dispatch` intentionally routes the full repository for clean-room/release evidence.

## 4. Cache policy

Allowed: pip/npm and later bounded tool caches that contain only reproducible public dependency/build material.

Forbidden:

- broker reports or private portfolio payloads;
- credentials/tokens/private keys;
- DB backups;
- release authority/provenance as cache;
- large model weights that displace CI cache value.

Cache keys must remain bound to runner OS and relevant lock identity. Cache miss is an acceleration loss, never a correctness failure.

## 5. Artifact policy

PR artifacts are transient evidence. Current default remains 1–3 days; WP4 release provenance candidates use 3 days.

Release candidates may contain only:

- release manifest;
- CI evidence JSON;
- lock-derived SBOMs;
- exact-SHA source archive.

They must not contain secrets/private portfolio/account data or private signing keys.

Durable release truth is the reviewed Git commit/tag/release identity plus manifest/digests, not an expiring Actions artifact.

## 6. Release-candidate procedure

Before running `V10 Release Provenance` for a future release candidate:

1. candidate code is already accepted on `main`;
2. run `Self-Hosted Windows CI` manually on that exact `main` SHA and record the successful run ID;
3. run `V10 Toolchain Compatibility` manually on the same SHA and record the successful run ID;
4. confirm the automatic `Regression Shield` run on the same SHA is successful;
5. dispatch `V10 Release Provenance` from `main` with `v10.*` version/tag identity and those exact run IDs;
6. the workflow verifies each run through the GitHub Actions API, generates source/SBOM/manifest evidence and fails closed on drift;
7. inspect the manifest and candidate artifact before any tag/release publication;
8. future release publication must use the reviewed tag identity and immutable-release control.

WP4 intentionally does not publish V10 or deploy a runtime.

## 7. Tag / release protection

Required repository state before the first actual `v10.*` release:

- apply `docs/architecture/V10_RELEASE_TAG_RULESET.json`;
- verify no bypass actor;
- enable repository release immutability;
- create release as draft, attach all intended assets, then publish so immutable-release protection locks tag/assets.

Do not reuse or move a published release tag.

## 8. OWNER-only GitHub account/repository actions

These are administration/billing controls, not code tasks, and must not be faked by CI:

- GitHub Billing -> Budgets and alerts -> enable included-usage alerts at 90/100%;
- create an Actions metered budget with stop-usage / zero unintended overage where available and appropriate;
- repository Settings -> Releases -> enable release immutability;
- repository Settings -> Rules -> import/apply the `v10.*` tag ruleset recipe.

After configuration, record verification evidence in the WP4 PR/issue. If an integration receives a future safe administration capability, it may perform these actions directly instead of asking the OWNER.

## 9. Fail-closed incidents

If provenance validation, CI evidence lookup, tag protection, release immutability, or digest verification fails:

- do not publish/promote/deploy;
- do not invent missing run IDs or SHA values;
- do not weaken the schema/validator;
- fix the source evidence or GitHub control and rerun;
- keep V9 as the operating fallback.

If GitHub hosted quota is exhausted, retain the Lenovo authoritative gate and postpone optional hosted acceleration/release candidate publication rather than bypassing controls.
