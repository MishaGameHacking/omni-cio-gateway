# V10 Engineering Failure Learning Ledger — FL077

## Scope

Focused Omni-CIO Sentinel brand-asset custody/integrity work in issue #426 / PR #427.

This entry records the SAST defect exposed after the Windows byte-portability correction was proven by Regression Shield. It does not authorize `WEB-VISUAL-INTEGRATED`, Cloudflare/domain mutation, public-user activation, broker write, or Real execution.

## Exact failure evidence

Exact head `5bf3703382106eaace2b8a039fbade8d97a691b1` ran `Self-Hosted Windows CI` workflow run `33563609290`, authoritative job `100041631907`.

The job proved the preceding EOL correction before reaching SAST:

- repository/CI policy contracts: success;
- compile: success;
- Ruff lint and exact formatter scope: success;
- mypy: success;
- protected V9 `app:app`: success;
- read-only GPT Actions release contract: success;
- Regression Shield: **2846 passed**, 57 subtests passed, 62.20% coverage: success;
- protected dependency audit: success, no known vulnerabilities.

Bandit then failed with one medium/high-confidence issue:

- `B314` / CWE-20 at `scripts/check_v10_brand_assets.py` in `_verify_xml`;
- the guard used `xml.etree.ElementTree.parse` on Android XML descriptors from the package being integrity-checked.

The tracked-secret stage did not run because SAST correctly failed closed first.

## Root cause

The brand guard treated descriptor XML as trusted because the expected package is repository-controlled and hash-pinned. That assumption is too weak for an integrity verifier: its purpose includes inspecting deliberately tampered or malformed package state, so every parser inside the verifier must safely handle hostile input before the verifier can reject it.

The standard-library `xml.etree.ElementTree.parse` call therefore created an unnecessary XML entity/DTD attack surface and Bandit correctly rejected it.

## Blast radius searched

Repository search found no other direct `ET.parse` use matching this new branch implementation. Accepted main contains a separate CBR XML parser that already implements an explicit fail-closed Expat policy: DTD/entity declarations are rejected and parameter entity parsing is disabled. That existing pattern confirms XML parser safety is a deliberate repository boundary rather than a scanner-only concern.

The directly coupled consumers are the five Android XML resources verified by `ANDROID_XML_PATHS`. The PWA JSON, PNG/ICO parsers, manifest hashing, custody pins, Web product, Cloudflare runtime, database, identity/session, broker, Telegram/VK and Real-execution contours are not part of this correction.

## Corrective change

1. Replace the unsafe ElementTree parser call with `defusedxml.ElementTree.parse`.
2. Catch `DefusedXmlException`, normal XML `ParseError`, and `OSError`, then preserve the guard's existing fail-closed `ValueError` diagnostic boundary.
3. Reuse the already accepted/hash-locked `defusedxml==0.7.1` development dependency; do not add or upgrade dependencies.
4. Add deterministic regression coverage that feeds an Android-style descriptor containing a declared entity and requires the guard parser to reject it.
5. Do not add `# nosec`, Bandit exclusions, severity changes, or parser normalization bypasses.
6. Re-run the complete exact-head DRAFT gate because source changed after the SAST failure.

## Why prior preflight missed it

The permanent guard's functional tests validated well-formed descriptors, missing drawables, binary tampering, maskable semantics and byte-level custody. They did not include hostile XML syntax, and the earlier authoritative cycles stopped before SAST while formatter/Regression-Shield defects were still being resolved.

## Permanent learning

- Integrity verifiers must parse the object being verified as hostile input, even when the expected object lives in a private repository.
- A hash check does not justify an unsafe parser: negative/tamper tests intentionally move the verifier off the approved hash path.
- Fix scanner findings at the vulnerable primitive. Do not suppress a security rule when a reviewed safe parser is already in the locked toolchain.
- Security regression tests should exercise the rejected payload class, not merely assert that the scanner becomes quiet.
- When a later gate reveals a new defect after an earlier gate turns GREEN, preserve the earlier proof but invalidate final exact-head acceptance once source changes.

## Security and authority invariants preserved

- Protected V9 `app:app` remains unchanged.
- `PUBLIC_MULTI_USER_ENABLED=false` remains unchanged.
- Broker write remains OFF.
- `trading_methods=false` remains unchanged.
- `REAL_TRADING_ENABLED=false` remains unchanged.
- No provider, broker, database, account or production secret is added to source, logs, comments or artifacts.
- No Cloudflare/provider mutation is performed by this correction.
