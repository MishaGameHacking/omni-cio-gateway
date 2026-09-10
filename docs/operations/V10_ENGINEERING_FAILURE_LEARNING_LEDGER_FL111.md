# V10 Engineering Failure Learning Ledger — FL111

## Failure class

`CF_D_RELEASE_CONTROL_BOOTSTRAP_UNNECESSARY_PUBLIC_RELAY_BOUNDARY`

## Accepted evidence

Exact accepted `main` `6b28198550adc09a001de8779df900b13caa5c42` proved the complete staging Worker + Container + PostgreSQL 18 path, exact Worker/Container source identity, bootstrap-origin custody and production Worker anchor, then stopped before production deployment at the one-time production database bootstrap with bounded outer evidence `CLOUDFLARE_CF_D_STAGING_HTTP_403_UNCLASSIFIED`.

The exact upstream component that emitted the raw 403 is not fabricated. The source graph proves a broader architectural defect independent of that unknown subtype: the release control plane already receives the exact derived Neon bootstrap Function origin during authenticated exact-SHA custody, but then persists the origin back into a Worker secret and later re-enters the public staging HTTP path only to recover and use the same destination through Worker -> Container -> Worker virtual egress.

## Root cause

A release-control responsibility was implemented as an ordinary public staging relay:

`GitHub OIDC release control -> public staging Worker -> staging Container -> Worker virtual HTTP egress -> Neon Function -> PostgreSQL`

The extra public edge and application relay do not add an independent identity proof. GitHub OIDC and exact source-SHA verification are ultimately enforced by the Neon Function itself.

The final convergence architecture requires release/bootstrap orchestration to remain in the release control plane and the application Worker to remain thin.

## Correction

The already-authorized staging custody step continues to validate the exact derived Function origin. For an exact-main release, it now reduces that origin to the minimum validated target descriptor (`branch_id` and `cell`) and hands only that descriptor to the same release job through one fixed restricted `RUNNER_TEMP` file:

- fixed filename only;
- exact JSON keys only;
- no complete URL in the handoff;
- no symlink;
- exclusive creation;
- POSIX 0600 or the existing hardened Windows ACL path;
- values must reconstruct through the single canonical Neon Function-origin pattern;
- never printed;
- never a GitHub output;
- never an artifact;
- deterministic cleanup.

For the one-time production database bootstrap, the release control plane reconstructs the single allowed Neon Function hostname from those validated components and source-controlled suffixes, then sends the existing short-lived GitHub OIDC assertion through `http.client.HTTPSConnection` on port 443 with the default certificate-validating TLS context and fixed `/` request target. The Function retains the existing exact repository/main/workflow/SHA/runner/time/RS256 validation and performs the existing least-privilege PostgreSQL role/grant/RLS convergence. The resulting production DSN keeps the existing restricted temporary-file custody before Cloudflare Secret convergence.

The former public staging relay remains source-present only until the direct path is proven by exact-main production acceptance. It is no longer the active production bootstrap transport. After real acceptance and consumer proof, the legacy relay and its now-unused Worker/Container responsibilities are eligible for removal in the final cleanup checkpoint.

## Security properties preserved

- no static Neon management credential is added to the production bootstrap;
- no provider identifier or private Function URL is logged or stored in GitHub metadata;
- a complete dynamic network URL is not accepted by the direct release bootstrap;
- the request target is fixed and TLS hostname verification is required;
- inherited proxy/redirect URL routing is not used by the direct transport;
- failure bodies remain bounded and only source-controlled Function classes cross the trust boundary;
- unknown failures remain fail-closed and non-retryable;
- production role remains least privilege with no SUPERUSER/CREATEDB/CREATEROLE/REPLICATION/BYPASSRLS authority;
- Cloudflare deployment does not grant broker or Real-money authority.

## Prevention law

Before introducing an internal/public relay for release-control data, prove that the relay adds a distinct required security authority. If the terminal verifier can be called directly by the trusted release control plane with equal or stronger authentication and narrower exposure, prefer the direct bounded control-plane path. The direct path must carry the minimum validated target identity and must not broaden that identity back into an arbitrary network destination.

## Protected invariants

Unchanged: V9 `app:app`; `PUBLIC_MULTI_USER_ENABLED=false`; `trading_methods=false`; `REAL_TRADING_ENABLED=false`; broker write, transfer, withdrawal, margin, leverage and uncovered short remain OFF/FORBIDDEN; no Web Visual, Telegram/VK, AI/Cortex, D1 or speculative Hyperdrive scope.
