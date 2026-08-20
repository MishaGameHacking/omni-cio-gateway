# FL-027 — Non-secret security contracts must pass the same tracked-content secret scan

Status: **ADDITIVE FAILURE-LEARNING ENTRY FOR PR #343; PRIMARY LEDGER REMAINS `V10_ENGINEERING_FAILURE_LEARNING_LEDGER.md`**  
Date: **2026-08-20**  
WP / PR / reference: **WP22A Phase 3 hosted runtime/data/credential/recovery source increment / PR #343 / authoritative Windows CI run `32335169886`**

## Symptom / failing gate

PR #343 exact head `1fab71216a7492f1a4f94d98a339df6bc2850fd2` completed the protected runtime regression, dependency audit and SAST successfully, including `2204 passed` and coverage above the required threshold, but the mandatory tracked-content scan failed.

`detect-secrets` reported `Secret Keyword` findings in the newly added non-secret hosted-runtime JSON contract. The flagged content contained policy field names describing broker credential access/custody; it contained no provider credential, broker credential, recovery key, private portfolio data or other secret value.

The authoritative gate therefore remained RED. Passing tests, SAST and dependency audit did not override the failed secret-scan stage.

## Root cause

The source contract used machine-readable key names containing a detector-sensitive security noun. The heuristic correctly treated those names as suspicious input requiring review, while the implementation preflight had not exercised the exact repository-wide tracked-content scan against the new JSON file before the expensive authoritative cycle.

This was a source/preflight defect, not an infrastructure failure and not grounds for weakening the scanner.

## Blast radius searched

The review isolated the finding to the newly added hosted-runtime contract and its deterministic consumer test. The Phase-3 Python custody interface contained no flagged value, and the earlier authoritative stages had already proved the protected `app:app` runtime, read-only release contract, full regression suite, dependency audit and SAST on the same head.

The correction did not change:

- `provider_apply_authorized=false`;
- `public_ingress_enabled=false`;
- recurring OWNER infrastructure authorization of `0 RUB/month`;
- `PUBLIC_MULTI_USER_ENABLED=false`;
- protected V9 `app:app`;
- `trading_methods=false`;
- `REAL_TRADING_ENABLED=false`;
- tenant isolation, RLS, encryption, browser-readback denial or recovery requirements;
- the WP23+ lock.

## Corrective change

Rename only the two non-secret machine-contract fields that described broker credential access and custody using detector-sensitive wording. Their replacement names use explicit `broker_credential_*` terminology while preserving every policy value and meaning.

Update the deterministic test to consume the renamed custody field. Do not add a file exclusion, broad allowlist, baseline suppression or lower the tracked-content scan requirement.

## Permanent regression / guard

The authoritative tracked-content scan remains unchanged and fail-closed. Any new source-controlled provider/runtime/security contract must pass the same repository-wide scan as application code and configuration.

For synthetic/non-secret security metadata, prefer precise semantic names that do not resemble credential assignment/storage syntax when an equivalent representation exists. If a future detector finding cannot be removed without reducing semantic clarity, any exception must be narrow, reviewed and demonstrably synthetic; blanket path or file-type exclusions are not acceptable.

## Future prevention rule

Before declaring a security-sensitive source increment pre-CI ready, run the exact tracked-content secret-scan path against every new configuration/JSON/IaC/document artifact, not only executable code. A file being intentionally non-secret does not exempt it from the scanner.

When a heuristic finding occurs, classify it from the actual line and value. Preserve the security control, remove the ambiguous representation where possible, and require a fresh exact-head all-GREEN cycle after the source correction.

## Dependency/tooling knowledge change

`detect-secrets` `Secret Keyword` detection can flag field names in policy/configuration files even when no secret value is present. That behavior is useful as a review tripwire. The correct default response is to make non-secret source unambiguous rather than suppressing the detector.
