# V10 Engineering Failure Learning Ledger — FL113

## Failure class

`CF_D_DIRECT_BOOTSTRAP_EXPLICIT_TLS_AND_COMPLEXITY_REPAIR`

## Exact-head evidence

PR #478 exact replacement head `3da2e1c2b9d3f866a45007ca6fbdd7aaefddde50` remained `RED_REPAIR_ONLY`. The exact-head V10 Engineering Governance job consumed SonarQube Cloud findings and reported two concrete annotations in `scripts/bootstrap_v10_cloudflare_production_database_direct.py`:

1. line 209: `Use a stronger protocol, or upgrade to Python 3.10+ which uses secure defaults.`
2. line 106: `Refactor this function to reduce its Cognitive Complexity from 17 to the 15 allowed.`

SonarQube Cloud therefore rated Security on New Code `D` where `A` is required. The first annotation is security-significant and the second is maintainability-significant; both are blocking under the exact-head zero-findings law.

The previous exact head also established that the authoritative Windows static-quality lane rejects a non-canonical Ruff format. No suppression, exclusion or Quality Gate change is authorized.

## Root cause

The direct release-control bootstrap used `ssl.create_default_context()`. The accepted Python runtime provides secure defaults, but the privileged transport policy was implicit in a convenience constructor and the independent analyzer could not prove the intended protocol floor from source. A release-control network boundary should not rely on version-sensitive implicit protocol policy when an explicit client TLS contract is available.

Separately, `write_bootstrap_origin_handoff()` combined descriptor validation, exclusive file creation, OS-specific hardening, stream conversion, write, descriptor cleanup and failure mapping in one function. The behavior was correct in intent but exceeded the repository's accepted Cognitive Complexity threshold and made the custody lifecycle harder to audit.

## Correction

The transport now creates an explicit `ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)`, sets `minimum_version = ssl.TLSVersion.TLSv1_2`, loads default server-authentication roots and verifies that hostname checking and `CERT_REQUIRED` remain active before the connection is created. The exact destination is still reconstructed only from the validated branch/cell descriptor, port remains 443, and the request path remains `/`.

The handoff writer is decomposed into narrow helpers for descriptor-size validation, exclusive descriptor creation, descriptor closing, OS-specific permission hardening and protected payload writing. `write_bootstrap_origin_handoff()` now orchestrates those helpers without carrying the lower-level exception/cleanup branching itself. Error classes, exclusive-create semantics, no-symlink custody, hardened ACL/POSIX mode and deterministic cleanup are unchanged.

The machine-readable release contract now freezes `TLSv1.2` as the minimum direct-bootstrap protocol and tests assert the explicit client TLS context, certificate validation and hostname verification.

## Prevention law

1. Privileged outbound release-control transports must encode protocol purpose and minimum TLS version explicitly in source.
2. Certificate validation and hostname verification are mandatory and must be machine-testable.
3. Security-sensitive custody functions must remain small enough that creation, hardening, write and cleanup branches are independently auditable.
4. Independent Sonar annotations are blocking even when runtime defaults are believed to be safe; source must make the security contract provable to the verifier.
5. No finding is closed by suppression, exclusion, severity change or Quality Gate weakening.

## Protected invariants

Unchanged: protected V9 `app:app`; `PUBLIC_MULTI_USER_ENABLED=false`; `trading_methods=false`; `REAL_TRADING_ENABLED=false`; broker write, transfer, withdrawal, margin, leverage and uncovered short remain OFF/FORBIDDEN; PostgreSQL 18 + RLS/FORCE RLS remains relational truth; no D1/Hyperdrive/Web Visual/Telegram/AI/Cortex scope; no real credential/provider identifier/private payload is written to source, logs or artifacts.
