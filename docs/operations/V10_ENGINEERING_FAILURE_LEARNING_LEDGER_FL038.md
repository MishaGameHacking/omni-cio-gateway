# FL-038 — Untrusted-data validators must type the pre-validation value, not the post-validation value

Status: **ADDITIVE FAILURE-LEARNING ENTRY FOR WP22A PHASE 5; PRIMARY LEDGER REMAINS `V10_ENGINEERING_FAILURE_LEARNING_LEDGER.md`**  
Date: **2026-08-24**  
WP / reference: **WP22A Phase 5 / PR #385 / DRAFT head `a1f65a98492e0d6558615223f57f0494bb1a1fc6`**

## Symptom / failing gate

The first exact-head DRAFT cycle for PR #385 reached `V10 WP20 Research Dossier Audit` run `32679858247`. Frontend typecheck/lint/unit tests/build, browser evidence and npm audit all completed successfully. The Python static-contract step then ran the repository-wide `python -m mypy` and failed with two errors in the new dormant Telegram OIDC adapter:

- `jwk.get("n")` had type `Any | None`, but `_b64url_decode` declared its input as `str`;
- `jwk.get("e")` had the same mismatch.

The step exited with code 42. The following repository-guard step was therefore skipped. Under V10 policy, the run is RED and the old head cannot be used as GREEN evidence.

## Root cause

`_b64url_decode` is itself the validation boundary for untrusted provider JSON. Its implementation intentionally starts with `isinstance(value, str)` and fails closed for every non-string value before length, regex or base64 processing.

The implementation contract and static type contract disagreed: the function accepted an untrusted pre-validation JSON value at runtime, but its annotation described only the already-validated post-narrowing type `str`.

The two `jwk.get(...)` callers were therefore correct to expose `Any | None`; the validator signature was too narrow. Adding casts or `# type: ignore` at those call sites would have hidden the design mismatch instead of correcting it.

## Blast radius searched

The review covered:

- every `_b64url_decode` call in the new Telegram OIDC adapter;
- the `n` / `e` JWK parsing path and its existing runtime rejection of missing/non-string values;
- JWT compact-segment callers, which already provide strings after `split(".")`;
- the accepted `omni_cio/watchtower/qstash_v1.py` base64url helper, whose callers originate from string JWT segments rather than arbitrary JSON members;
- the directly coupled `AuthorizationTransactionRegistryV1` and `VerifiedExternalIdentityV1` boundaries;
- the exact failing workflow log to distinguish application behavior from a runner/tooling problem.

No evidence showed a provider-auth runtime bypass, secret exposure, dependency defect, WP20 defect or need to weaken mypy. The defect class is local to the new untrusted-value validator contract, while the prevention rule is repository-wide.

## Why preflight did not catch it

Scratch preflight compiled the module and ran the focused provider tests, but the scratch environment did not have the repository's exact `mypy==2.3.0` toolchain and full source graph. Compile/runtime tests therefore proved executable behavior but not the accepted repository-wide static contract.

The branch was opened as DRAFT only after that scratch preflight, so CI correctly acted as the independent verifier and found the missing static-contract evidence before READY or merge.

## Corrective change

Change `_b64url_decode` from accepting `str` to accepting `object`.

This matches the actual trust boundary:

`untrusted JSON value: object -> isinstance(value, str) -> bounded base64url decode`

The runtime validation remains unchanged and fail-closed. No cast, ignore, mypy suppression, workflow narrowing or dependency change is introduced.

The focused runtime suite remains GREEN after the correction. The next exact-head CI cycle must independently prove the repository-wide mypy contract on the new head.

## Permanent regression / guard

The permanent guard is the existing repository-wide `python -m mypy` gate, which checks all source modules from workflows such as the WP20 audit and authoritative Windows CI. Because `_b64url_decode` now declares the pre-validation type truthfully, future `jwk.get(...)` / arbitrary JSON callers can pass through the same validator without requiring unsafe casts.

The adapter's runtime checks already deterministically reject non-string base64url inputs with `TELEGRAM_OIDC_JWKS_INVALID` / `TELEGRAM_OIDC_ID_TOKEN_INVALID` as appropriate; the static gate now verifies that those untrusted values are allowed to reach the validator rather than being falsely declared valid beforehand.

## Future prevention rule

For parsers and security validators at an external-data boundary:

1. annotate the value type that exists **before** validation (`object`, `Any`, or a precise union), not the type expected after validation;
2. narrow with explicit runtime checks inside the validator;
3. do not use `cast`, `# type: ignore` or workflow exclusions to make untrusted JSON look already validated;
4. include exact repository mypy (or a provably equivalent focused invocation) in pre-CI whenever new typed parser code is introduced;
5. treat compile/runtime tests and static-contract tests as complementary evidence rather than substitutes.

## Dependency/tooling knowledge change

No dependency update is required. The accepted repository toolchain remains `mypy==2.3.0`. The failure was a source annotation defect, not a mypy regression or platform-specific behavior.
