# Omni-CIO V10 — GitHub Pro Utilization Implementation Checklist

**Status:** PLANNING-ONLY CHECKLIST  
**Implementation starts:** only when the owning WP is authorized by `knowledge/17_V10_CURRENT_PROGRAM_STATUS.md`.

This checklist translates the approved GitHub Pro utilization policy into concrete future work without prematurely changing runtime behavior.

## WP4 — release / provenance / CI utilization

- [ ] confirm current GitHub Pro plan facts against official GitHub documentation;
- [ ] implement release manifest generator and validator against `V10_RELEASE_MANIFEST.schema.json`;
- [ ] bind release manifest to exact Git SHA and selected toolchain/lock digests;
- [ ] include SBOM digest(s) and exact CI run evidence;
- [ ] create release/pre-release naming contract under `v10.*`;
- [ ] enable native GitHub immutable releases if still available/suitable for this private personal repository;
- [ ] verify immutable release behavior for future published releases: tag pinned to commit and release assets protected from later modification/deletion;
- [ ] add tag ruleset/protection only where it complements immutable releases and does not break the reviewed release workflow;
- [ ] implement path-aware hosted CI classifier/routing;
- [ ] keep fast policy/source checks on every PR;
- [ ] keep authoritative exact-head gate required for merge candidates;
- [ ] route heavy repeatable checks to Lenovo when safe;
- [ ] preserve hosted Windows as disposable compatibility lane, not authoritative production state;
- [ ] document 50/25/15/10 hosted-minute planning budget and usage-review procedure;
- [ ] document current included quotas used by V10 planning: Actions minutes/storage, cache, Codespaces, Packages and LFS;
- [ ] enable GitHub included-usage alerts at 90% and 100% if not already enabled;
- [ ] configure account/repository metered-product budget guard(s) so unintended paid overage is blocked where GitHub supports a hard stop; OWNER performs only the account-level step if the connector cannot;
- [ ] tune cache keys/retention for pip/npm and later Playwright where applicable;
- [ ] enforce short-lived PR artifacts and job-summary preference;
- [ ] fail closed when required provenance fields are missing/invalid;
- [ ] do not require Enterprise-only private artifact attestations;
- [ ] do not install/configure Qwen/Ollama in WP4;
- [ ] do not start Block C in WP4.

## Block C — Personal Node / clean-room development

- [ ] add reviewed `.devcontainer` only if useful for clean-room development/handoff;
- [ ] prove Codespaces is optional and contains no production broker/private state by default;
- [ ] prefer smaller Codespaces machine/short idle timeout for clean-room work so included core-hours are not wasted;
- [ ] keep Lenovo runtime identity isolated from GitHub runner identity;
- [ ] implement bootstrap/recovery from GitHub-controlled configuration;
- [ ] document/verify environment topology migration for `v9-recovery`, `v10-staging`, `v10-production` as appropriate;
- [ ] inventory/retire unexplained legacy GitHub environments only through reviewed deployment work;
- [ ] keep broker/Telegram/encryption secrets in local runtime secret custody.

## Block D/E/F/G/H/I/J — continuous GitHub integration

For every owning WP:

- [ ] update parity ledger objects owned by the WP;
- [ ] update component reuse decisions before rewrites;
- [ ] use `OMNI_CIO_V10_WP_EXECUTION_TEMPLATE.md`;
- [ ] add/adjust path-aware CI only for the risk domain changed;
- [ ] keep canonical contracts in GitHub and private data out;
- [ ] attach exact acceptance evidence to PR/status/release records;
- [ ] keep AI policy/tool/eval definitions source-controlled;
- [ ] run Qwen/Ollama GPU evals on Lenovo only when relevant;
- [ ] preserve deterministic Core operation when AI is unavailable;
- [ ] prohibit AI/broker-write/admin authority coupling;
- [ ] preserve V9 recovery until the relevant cutover gate;
- [ ] never retire a material V9 capability before parity evidence.

## GitHub project-management adoption

- [ ] use Issues for WP/blocker/defect records when operationally useful;
- [ ] if a GitHub Project board is created, include Block/WP/Status/Risk/Exit Gate/V9 Parity/Owner Action/PR/CI/Release fields where supported;
- [ ] Project board must remain an operational view, not a replacement for Master Plan/status authority;
- [ ] do not create duplicate parallel roadmaps with conflicting statuses.

## Dependency/supply-chain maintenance

- [ ] maintain Dependabot coverage for actual ecosystems only;
- [ ] group safe minor/patch dependency updates to reduce CI noise/minute waste;
- [ ] prioritize security updates;
- [ ] require relevant V10 gates for dependency PRs;
- [ ] keep GitHub Actions pinned to reviewed immutable commit SHAs;
- [ ] keep least-privilege workflow permissions;
- [ ] keep repository-controlled SAST/dependency/secret/SBOM checks where native private-repo Pro features are unavailable;
- [ ] use Git LFS only if a later WP truly needs large non-secret versioned fixtures; do not use it for model weights, private broker reports, DB backups or secrets.

## Subscription gate

Before introducing any new recurring paid service:

- [ ] document exact missing capability;
- [ ] prove GitHub Pro + Lenovo + open-source/self-hosted option is inadequate;
- [ ] document price and cancellation/fallback path;
- [ ] document data/privacy/vendor-lock consequences;
- [ ] obtain OWNER-approved amendment.

No unchecked item in this section may be bypassed merely for development convenience.
