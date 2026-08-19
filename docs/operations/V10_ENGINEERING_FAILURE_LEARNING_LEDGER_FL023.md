# FL-023 — Synthetic test fixtures must pass the same tracked-content secret scan before authoritative CI

Status: **ADDITIVE FAILURE-LEARNING ENTRY FOR PR #336; PRIMARY LEDGER REMAINS `V10_ENGINEERING_FAILURE_LEARNING_LEDGER.md`**  
Date: **2026-08-19**  
WP / PR / reference: **WP22A Phase 2 Product-auth / tenant-security correction / PR #336**

## Symptom / failing gate

On exact PR head `f34aaff9cd8f85f9868144afd768ea4dce8dfcd5`, **Self-Hosted Windows CI #1655** reached the authoritative security tail after all of these had succeeded:

- exact reviewed checkout;
- hash-locked dependencies and lock verification;
- repository/CI policy contracts;
- compile and Ruff/mypy static quality;
- stable `app:app` / `trading_methods=false` checks;
- protected Regression Shield: 2188 tests passed with required coverage;
- dependency audit;
- Bandit SAST.

The final tracked-content secret scan failed with one finding:

`scripts/rehearse_v10_wp22a_phase2_tenant_security.py:247 (Secret Keyword)`

The flagged value was an obvious synthetic `read-connection:v1:` fixture assigned to a local variable whose name began with `secret_`. No real credential was present. The RED remains blocking; a false-positive classification is not permission to bypass or weaken the scanner.

## Root cause

Phase-2 preflight considered real-secret exclusion and synthetic fixture safety semantically, but it did not execute the **same repository-wide `detect-secrets` pipeline used by the authoritative merge gate** against the final tracked content.

The synthetic fixture naming unnecessarily matched the scanner's Secret Keyword heuristic. Because the fixture can be expressed without secret-like variable naming, the correct fix is source hygiene rather than an allowlist or scanner exemption.

## Blast radius searched

The authoritative log identified exactly one finding. The correction renames only the two synthetic local fixture variables to neutral vault-reference names while retaining the existing `secret_ref` repository API contract and the synthetic `read-connection:v1:` reference values.

No change is made to:

- scanner configuration or exclusions;
- actual secret handling;
- broker credential storage/custody;
- identity HMAC key handling;
- tenant isolation/RLS;
- broker write authority;
- provider/public activation;
- protected V9 rollback.

## Corrective change

Rename the synthetic variables from secret-like identifiers to `vault_ref_a` / `vault_ref_b` and start a new exact-head cycle. Do not suppress the finding, add a baseline exception, or reduce scanner coverage.

All prior GREEN results belong to obsolete heads after this correction and cannot be reused as final acceptance evidence.

## Permanent regression / guard

The authoritative merge gate continues to run the repository-wide `detect-secrets` scan as its final security stage. The focused Phase-2 workflow also retains its fail-closed source assertions, while the authoritative gate remains the independent repository-wide secret-content verifier.

## Future prevention rule

Before declaring a change containing synthetic credentials, vault references, hashes, tokens or identity fixtures pre-CI ready, run the repository's exact tracked-content secret-scan pipeline over the final changed tree.

Prefer scanner-clean synthetic fixture naming and unmistakably non-secret data. If a heuristic fires on a safely renameable fixture, rename the fixture; do not teach the scanner to ignore a broader class that may later contain a real credential.

## Dependency/tooling knowledge change

Secret scanners intentionally use lexical heuristics as well as entropy/pattern detectors. A synthetic value can therefore trigger a keyword detector solely because of the assignment name. Preflight must validate synthetic fixtures with the same scanner/configuration/exclusions as authoritative CI, not infer safety only from the fixture's semantic intent.
