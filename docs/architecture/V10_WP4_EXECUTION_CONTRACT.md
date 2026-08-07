# Omni-CIO V10 — WP4 Execution Contract

Status: **IMPLEMENTATION CANDIDATE — acceptance requires focused PR + exact-head gates + squash merge**  
Work package: **WP4 — Release, build provenance and deployment contract**  
Accepted base at start: `d072fbf9a061f98bc8d6d44d8732254bea06991b`

## 1. Purpose

Finish Block B by adding deterministic release/build provenance and a deployment identity contract without changing V9 production runtime, financial semantics, broker credentials, or Real-money authority.

## 2. Accepted baseline and reuse decisions

- V9 `app:app`: `WRAP_ADAPTER`; no WP4 runtime cutover.
- GitHub CI/control plane: `REUSE_AS_IS`; extend accepted WP0-WP3 workflows incrementally.
- V9 recovery: `WRAP_ADAPTER`; keep V9 as rollback target while V10 is incomplete.
- No V9 deterministic financial component is rewritten or retired in WP4.

## 3. Allowed changes

- release manifest generator/validator around `V10_RELEASE_MANIFEST.schema.json`;
- exact SHA/toolchain/dependency-lock/SBOM/CI/rollback provenance;
- future AI and signed-updater provenance fields with runtimes disabled/not installed;
- `v10.*` release/tag naming contract;
- repository tag-ruleset recipe and immutable-release operating gate;
- path-aware hosted CI routing without top-level PR path exclusion;
- Actions minute/cache/artifact operating controls;
- release/deployment/recovery runbooks and tests.

## 4. Explicit non-goals

WP4 does **not** install or implement Ollama/Qwen/Cortex, V10 Web, Telegram runtime, Portfolio Guardian, Watchtower V10 runtime, broker HTML runtime, Block C node runtime, billing/license service, automatic updater runtime, or any new broker write method.

WP4 does **not** modify `app.py`, `app_v371.py`, `app_v360.py`, `main.py`, broker execution packages, broker credentials, production Render configuration, or the Custom GPT runtime.

## 5. Security and authority effects

- GitHub remains engineering authority only.
- `REAL_TRADING_ENABLED=false` remains the master Real rollback.
- Existing `trading_methods=false` read-only health invariant remains protected.
- Release provenance contains no broker tokens, account IDs, private portfolio data, private DB backups, signing private keys, or model weights.
- Release validation fails closed on malformed schema data, SHA drift, failed/mismatched CI evidence, missing artifacts, digest mismatch, invalid rollback references, or incomplete STABLE signing metadata.

## 6. Interfaces created

### `scripts/v10_release_manifest.py`

Commands:

- `generate-sbom` — deterministic lock-derived CycloneDX release SBOMs;
- `verify-ci` — verifies exact-SHA GitHub Actions evidence and authoritative job success;
- `generate` — creates the manifest candidate;
- `validate` — validates against the canonical JSON schema plus semantic/digest rules.

### `scripts/v10_ci_router.py`

Classifies changed paths into the approved domains and emits conservative hosted-CI routing decisions. Unknown paths fail closed into backend + release/security review.

### `.github/workflows/v10-release-provenance.yml`

Manual release-candidate workflow. It validates only accepted `main`, requires exact-SHA authoritative/hosted/Regression Shield evidence, creates an exact-SHA source archive + SBOMs + manifest, and uploads only a short-lived candidate artifact. It does **not** create a Git tag, publish a GitHub Release, deploy V10, or mutate production.

## 7. Normal-path acceptance tests

- complete manifest conforms to `V10_RELEASE_MANIFEST.schema.json`;
- release version and tag identity are identical and `v10.*`;
- exact Git SHA is bound through build and every CI evidence record;
- dependency-lock and SBOM hashes match referenced files;
- exact successful `Self-Hosted Windows CI` authoritative job is required;
- exact successful hosted compatibility and Regression Shield runs are required;
- rollback instructions and contract references exist;
- docs-only PRs skip unnecessary hosted Windows jobs while policy checks remain;
- release/security/dependency changes route to both hosted Windows lanes;
- current full V9 test, security, dependency, SAST/secret, and `app:app` gates remain unchanged.

## 8. Negative tests

- missing required provenance;
- invalid or non-V10 tag/version;
- release/tag mismatch;
- CI SHA mismatch or non-success conclusion;
- missing authoritative job;
- missing/damaged dependency lock, SBOM, or update artifact;
- STABLE metadata without signing identity, signed metadata reference, expiry, or rollback compatibility;
- unknown path classification attempts;
- non-main release candidate;
- malformed or non-existent Git rollback commit identity.

## 9. Observability and cost controls

- hosted routing prints selected categories;
- release candidate writes manifest digest and identity to the job summary;
- routine PR artifacts remain 1–3 day evidence; WP4 release candidate artifact retention is 3 days;
- heavy authoritative validation stays on Lenovo;
- GitHub Pro hosted-minute allocation target remains 50/25/15/10 for fast PR, clean-room compatibility, release/recovery, and incident reserve.

## 10. Rollback

WP4 changes are repository/CI controls only. Rollback is a normal reviewed revert of the WP4 squash commit. V9 remains running through the protected `app:app` baseline.

Release rollback metadata defaults to the exact last completed V9 feature-program acceptance commit: `git:b9e4fabcb54f8f6e0ba206f030c35f2fafa2ce62@app:app`. A later owning release may supply a newer approved exact Git rollback identity; the release workflow rejects malformed or non-existent commit targets.

## 11. Server-side GitHub controls

Required strongest-safe controls:

1. active `Protect main` ruleset remains untouched;
2. tag ruleset for `refs/tags/v10.*` blocks tag deletion and non-fast-forward updates;
3. repository release immutability is enabled for future releases;
4. no permanent bypass actor is added.

The repository contains an importable tag-ruleset recipe. If the connected GitHub integration cannot mutate repository-administration settings, application of the tag ruleset and immutable-release toggle is an explicit non-delegable OWNER admin action and blocks final WP4 Exit Gate until verified.

## 12. Binary Exit Gate

WP4 is COMPLETE only when all are true:

- focused WP4 PR is based on current `main`;
- release generator/validator and fail-closed tests are green;
- path-aware hosted routing is green;
- exact-head fast/hosted/authoritative CI is green;
- exact-head Regression Shield/security is green;
- no unresolved review blockers;
- tag protection + immutable-release state are verified or the program explicitly records an accepted platform limitation with the strongest safe alternative;
- V9 `app:app` and money-authority invariants are unchanged;
- squash merge lands on `main`;
- post-merge Regression Shield is successful.

Only then may canonical status mark WP4 / Block B complete and unlock Block C.
