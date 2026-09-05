# V10 Engineering Failure Learning Ledger — FL094

## Scope

Current System Update: `CLOUDFLARE-PUBLIC-PRODUCT-INTEGRATED`, CF-D focused recovery PR `#450` after accepted main `2491ad5fb95321970d63e41ae36d3c30d04dbb3c`.

This entry records the remaining security-analysis failure after exact head `88d33b7e1ce5ead7a2d1364fd40636e85f1a51f6`. It does not authorize public multi-user activation, Telegram/VK activation, broker write, Real execution or a new Work Package.

## Failure evidence

Exact head `88d33b7e1ce5ead7a2d1364fd40636e85f1a51f6` completed all 13 repository pull-request workflows with `success`. Gitar also completed `success` with no remaining open finding. SonarQube Cloud still failed the same exact head with **Security Rating on New Code = D** where A is required and exposed three annotations through the GitHub check summary.

The connected GitHub surface does not expose the private Sonar annotation payload, so this entry does not invent the rule text or exact flagged line. The previous canonicalization correction is therefore proven insufficient by exact-head evidence.

Public SonarSource SSRF guidance confirms that its server-side request analysis is taint-flow based and focuses on whether attacker-influenced data can reach an outbound request destination. That public guidance is supporting context only; it is not represented as the unavailable private annotation text.

## Refined root cause class

`CF_D_PROVIDER_DESTINATION_AUTHORITY_NOT_SEPARATED_FROM_PROVIDER_RESPONSE`

The exact-head code no longer fetched the raw candidate request URL, but two weaknesses remained in the changed security boundary:

1. the generic network-sink helper still accepted a destination URL as a function argument, leaving a reusable API surface whose caller could supply destination authority; and
2. the Neon Function hostname was still constructed from `neon.branch_id` returned by an outbound database response before being used as the provider destination.

Strict syntax and exact candidate equality reduce SSRF surface, but they do not create the strongest authority separation available here. Provider destination authority should come from protected runtime configuration, while provider/network responses may only prove that the configured destination still belongs to the currently bound staging branch.

## Coherent correction

The CF-D bootstrap egress boundary is changed as one unit:

1. Introduce runtime binding name `OMNI_V10_CF_D_NEON_BOOTSTRAP_ORIGIN` for the exact Neon bootstrap Function origin. Its value is external provider/runtime custody and must never be committed, commented, logged or returned to users.
2. Validate that binding as a bounded HTTPS-only Frankfurt Neon Function URL with no userinfo, custom port, path, query or fragment.
3. Validate its provider cell against the already-required staging `OMNI_V10_POSTGRES_DSN` binding before any branch metadata request.
4. Query `neon.branch_id` only as branch-consistency evidence, then require it to equal the branch encoded by the protected bootstrap-origin binding.
5. The database/network response can therefore reject a stale or wrong configured origin, but it can no longer choose the Function fetch destination.
6. Remove the exported generic `fetchCfDTrustedNeonRequest` destination-taking network API. The database lookup sink privately derives its URL only from the validated runtime database binding; the Function sink privately derives its URL only from protected bootstrap-origin custody.
7. Reconstruct both outbound requests with explicit destination-specific header allowlists, bounded bodies and fixed redirect behavior.
8. Add executable Node negatives for missing/external/wrong-scheme/wrong-port/wrong-path/wrong-cell/wrong-branch bootstrap origins and keep existing malformed/oversized branch metadata negatives.
9. Record the required binding in the machine-readable Cloudflare release acceptance contract with fail-closed missing-binding semantics.
10. Do not suppress Sonar, weaken the Quality Gate, loosen hostname validation, introduce Neon management credentials or commit a branch/project/provider identifier.

## External custody boundary

The source correction deliberately does not fabricate or expose the actual bootstrap-origin value. After source review/verification, the exact provider Function origin must exist in approved runtime secret custody before the CF-D production bootstrap can succeed. Missing or stale custody remains an external fail-closed blocker, not a reason to hardcode the provider identifier or restore broad Neon management API authority.

## Blast radius searched

Directly coupled surfaces reviewed:

- staging-only Container bootstrap route;
- trusted Worker `outboundByHost` HTTPS interception;
- Worker runtime PostgreSQL binding validation;
- Neon SQL-over-HTTP branch metadata lookup;
- Neon Function destination selection;
- OIDC/body/header forwarding;
- source-controlled Neon Function exact-workflow verification;
- release-acceptance contract and bootstrap fail-closed behavior;
- executable Node/Python regression wiring;
- production bootstrap/release ordering and rollback.

Alternatives reviewed and not adopted:

- hardcoding branch/project/Function provider identifiers in source;
- restoring broad `NEON_API_KEY` management-plane dependency;
- marking Sonar findings false positive or suppressing the rule;
- adding a second Worker/service merely to move the same dynamic fetch;
- Workers VPC Service, which is designed for private services reachable through Tunnel/Mesh rather than this public Neon Function endpoint;
- dependency/toolchain migration to a new database/HTTP client solely to avoid an analyzer finding.

## Permanent prevention rules

For future privileged provider egress:

- destination authority must not be accepted as an exported network-helper argument when it can instead be derived from protected runtime custody;
- a provider/network response may validate configured authority but must not become privileged destination authority itself;
- exact provider destinations that contain provider identifiers belong in approved secret/runtime custody, not source/comments/logs/artifacts;
- independent provider identity evidence should be compared before the privileged request, not only after mutation;
- analyzer RED after a complete repository GREEN batch is a new evidence state and requires a fresh root-cause inventory, never suppression by default.

## Protected invariants

- protected V9 `app:app` unchanged;
- `PUBLIC_MULTI_USER_ENABLED=false` unchanged;
- Telegram/VK public activation remains outside this correction;
- broker write OFF;
- `trading_methods=false`;
- `REAL_TRADING_ENABLED=false`;
- no transfer/withdrawal/margin/leverage/uncovered-short authority;
- no provider token, provider identifier value, database credential, OIDC assertion or private tenant payload is committed or logged;
- CF-D production promotion remains gated by exact-main SUCCESS-only evidence.
