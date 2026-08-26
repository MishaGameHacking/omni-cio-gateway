# FL-047 — Synthetic authentication credentials must not be hard-coded in test source

Status: **ADDITIVE FAILURE-LEARNING ENTRY FOR WP22A PHASE 5; PRIMARY LEDGER REMAINS `V10_ENGINEERING_FAILURE_LEARNING_LEDGER.md`**  
Date: **2026-08-26**  
WP / PR / reference: **WP22A Phase 5 integrated technical closeout / PR #391 / SonarQube Cloud Security Rating follow-up after exact head `080bcab4`**

## Symptom / failing gate

PR #391 remained DRAFT because SonarQube Cloud continued to report **Security Rating on New Code = B** while the accepted quality gate requires A. The exact private Sonar issue text is not available through the current GitHub/Sonar read surface, so this entry does not claim a private rule annotation that cannot be retrieved.

Historical exact-head evidence nevertheless exposed a strong source correlation. Sonar annotation count remained 14 across several runtime authority refactors, increased to 15 on the commit that added the Telegram fixed-endpoint regression, and increased to 17 on the later provider-start authority commit. Those new authentication tests introduced literal synthetic values at `client_secret` and related secret-key configuration surfaces.

Independent source review then found the same hygiene class in the original Phase-5 test population: synthetic provider client secrets and server-side binding keys were represented as hard-coded string expressions even though they were not real credentials.

Sonar's current Python rule inventory classifies **Credentials should not be hard-coded** as a Vulnerability. Therefore analyzer-visible literal authentication material is a legitimate merge blocker to remove regardless of whether the unavailable private issue text ultimately proves this was the sole Sonar finding.

## Root-cause analysis

The tests correctly avoided real secrets, but several fixtures encoded synthetic authentication material directly in source, for example through literal `client_secret` values and literal values assigned to the runtime environment keys for provider secrets or server-side binding keys.

That creates two problems:

1. a static analyzer cannot safely infer that a credential-looking literal is harmless merely because the surrounding file is a test;
2. hard-coded credential-shaped fixtures normalize a source pattern that must be forbidden in production authentication code.

The mistake was treating "synthetic" as sufficient credential hygiene. For authentication tests, synthetic values should also be generated as ephemeral test material when the value itself is supposed to model a secret.

## Blast radius searched

The review covered the Phase-5 new-code tests that configure Telegram client authentication or the deployed provider-auth binding keys:

- `tests/test_v10_wp22a_phase5_runtime_composition.py`;
- `tests/test_v10_wp22a_phase5_runtime_verifier_wiring.py`;
- `tests/test_v10_wp22a_phase5_telegram_fixed_endpoints.py`;
- `tests/test_v10_wp22a_phase5_provider_start_authority.py`;
- `tests/test_v10_wp22a_phase5_telegram_jwks.py`.

The review distinguished public identifiers: from credentials. Public client IDs, callback URLs, provider endpoints, JWT/JWK public-key vectors and hostile callback strings remain deterministic literals. Only values occupying secret/credential authority are changed.

Protected production composition already reads real provider secrets and binding keys exclusively from runtime environment variables. No production credential storage, browser authority, tenant binding, broker boundary, V9 entrypoint or public-production lock requires modification.

## Corrective change

Authentication test credentials are now generated at test-process startup with Python's `secrets` module:

- Telegram client secrets use `secrets.token_urlsafe(...)`;
- 32-byte binding-key environment values use `secrets.token_hex(32)`;
- deliberately invalid binding material includes a guaranteed non-hex prefix plus generated opaque material.

The generated values are used only as opaque fixtures. No assertion depends on their exact bytes, so the semantic test result remains deterministic while credential contents are no longer committed to source.

An AST regression guard scans the exact Phase-5 authentication-test surface corrected here. It rejects static string/bytes literals used directly as `client_secret`, as values for the known secret environment keys, or as assignments to credential-like names. Literal concatenation and multiplication are treated as static literals as well, preventing trivial source obfuscation from becoming the fixture convention.

No real secret is introduced. No Sonar suppression, `NOSONAR`, quality-profile change, test exclusion or CI weakening is used.

## Permanent regression / guard

`tests/test_v10_wp22a_phase5_test_credential_hygiene.py` fails if the corrected authentication test surface reintroduces hard-coded credential material through:

- a literal `client_secret=` argument;
- a literal value for `OMNI_V10_TELEGRAM_OIDC_CLIENT_SECRET`;
- a literal value for `OMNI_V10_CSRF_BINDING_KEY_HEX`;
- a literal value for `OMNI_V10_IDENTITY_BINDING_KEY_HEX`;
- a literal assignment to a credential-like `SECRET`, `PASSWORD`, `TOKEN` or `KEY` name.

The guard is intentionally source-structural. It does not inspect or expose runtime secret values.

A fresh exact-head Sonar result is still mandatory. If Security Rating remains B, this correction must be treated as one independently valid security-hygiene fix rather than proof that the inaccessible Sonar finding has been fully resolved.

## Future prevention rule

For tests that exercise authentication, session, cryptographic binding or provider configuration:

1. never place real credentials in source, logs, fixtures or CI artifacts;
2. do not hard-code synthetic values into parameters or configuration fields whose semantic role is a password, secret, token or private binding key;
3. generate opaque synthetic credential material at runtime when exact bytes are irrelevant to the assertion;
4. keep public identifiers, public keys and protocol constants deterministic and clearly separate from secret material;
5. add source guards around security-sensitive fixture conventions instead of relying on reviewer memory;
6. never suppress a credential vulnerability merely because the occurrence is in test code;
7. require a fresh exact-head independent analyzer result after the correction.

## Dependency/tooling knowledge change

No dependency update is required. Python's standard-library `secrets` module is sufficient. SonarQube Cloud Security Rating A remains the independent acceptance gate.
