# Omni-CIO V10 — GitHub Pro Plan Limits / Planning Facts Snapshot

**Status:** planning reference, not product/runtime code  
**Captured:** 2026-08-07  
**Purpose:** prevent future V10 engineering sessions from assuming Enterprise-only/private-repository features are available on the OWNER's current GitHub Pro subscription.

This file records only planning facts needed by the V10 program. GitHub features and billing can change; the owning implementation WP must re-check official GitHub documentation before depending on a plan-specific feature.

## Current planning facts

For a personal GitHub Pro account, official GitHub documentation currently describes:

- 3,000 GitHub Actions hosted minutes per month;
- 1 GB GitHub Actions storage allowance under the current included-usage table;
- 2 GB GitHub Packages storage and 10 GB Packages data transfer per month;
- 180 Codespaces core-hours per month;
- 20 GB Codespaces storage per month;
- 10 GB Git LFS storage and 10 GB Git LFS bandwidth per month;
- protected branches/rulesets and advanced private-repository collaboration controls such as CODEOWNERS;
- GitHub Actions self-hosted runner usage does not consume GitHub-hosted Actions minutes;
- Actions cache has a separate 10 GB per-repository included allowance under the current billing model;
- personal accounts can configure GitHub budgets/alerts for metered products and receive included-usage alerts at 90% and 100%; where GitHub exposes a stop-usage budget guard, it can prevent unplanned paid overage;
- GitHub Environments can be created for private repositories on Pro and can provide environment secrets/variables and branch/tag deployment scoping supported by the plan;
- required environment reviewers and wait timers are not available for private repositories on GitHub Free/Pro/Team under the current documented availability;
- repository rulesets can target branches and tags in private GitHub Pro repositories;
- GitHub provides repository release immutability: future published immutable releases lock the associated tag to the commit and protect release assets from later modification/deletion while the release exists;
- native artifact attestations on private/internal repositories require GitHub Enterprise Cloud even though immutable releases can provide their own release-integrity mechanism;
- native GitHub code scanning/CodeQL for private repositories is not available on personal GitHub Pro without upgrading to an eligible organization plan/security product;
- native GitHub secret scanning/push protection for a user-owned private Pro repository is not assumed available as a repository security feature.

## V10 consequence

V10 must maximize the features above that are already included, while preserving repository-controlled substitutes for private-repository security/provenance features that the current plan does not provide.

The program must not silently add GitHub Enterprise Cloud, GitHub Code Security, GitHub Secret Protection, or another paid CI/security service to satisfy V10 Definition of Done.

WP4 should prefer native immutable releases plus repository-controlled release manifest/SBOM/CI evidence over depending on Enterprise-only private artifact attestations.

The OWNER billing configuration should use GitHub's included-usage alerts and, where available, hard budget/stop-usage controls to prevent accidental metered overage. This is account-level configuration and is requested from the OWNER only if/when the owning implementation WP actually needs it.

Before implementing any plan-gated feature, re-check current official GitHub documentation and record the result in the owning PR/runbook if it changes this snapshot.
