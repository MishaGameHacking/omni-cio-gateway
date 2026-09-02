# V10 Engineering Failure Learning Ledger — FL076

## Scope

Focused Omni-CIO Sentinel brand-asset custody/integrity work in issue #426 / PR #427.

This entry records the exact-head Windows portability defect discovered after the permanent brand guard and maskable-asset corrections. It does not start `WEB-VISUAL-INTEGRATED`, change Cloudflare/domain state, activate public users, modify protected V9 `app:app`, or expand broker/Real-money authority.

## Exact failure evidence

Exact head `66ac06ac03cf85e1d38d2c3938d2c776fb2c5439` ran `Self-Hosted Windows CI` workflow run `33556687433`. The authoritative merge-gate job `100019123983` passed repository bootstrap, PostgreSQL 18 rehearsal, lock verification, repository/CI policy guards, compile, Ruff lint/format, mypy, stable `app:app` verification and the read-only GPT Actions release contract. It then failed only in `Run protected Regression Shield with coverage`.

The Regression Shield reached 62.20% total coverage and reported 2841 passing tests plus four failures in `tests/test_v10_brand_assets.py`:

- the clean repository guard stopped at `asset manifest byte identity drifted from custody pin`;
- the tampered-binary negative stopped at the same manifest-pin boundary before reaching the intended SHA-256 mismatch;
- the missing-Android-drawable negative stopped at the same manifest-pin boundary before reaching the intended missing-file failure;
- the maskable safe-zone semantic-drift negative re-pinned its rewritten manifest and then stopped at `brand asset byte count mismatch: README.md` before reaching the intended safe-zone failure.

## Root cause

The manifest data itself was not stale. The package `README.md` still has exactly 5986 UTF-8 bytes and SHA-256 `6ea8569bc66328077581d074b23582446a4f01eae0ac868c0ae2c453ea69a371`, matching its manifest record.

The repository had no `.gitattributes` contract for the byte-hashed brand text files. On the trusted Windows checkout, Git's platform/global end-of-line policy converted canonical LF text to CRLF in the working tree. That changed the bytes of `asset-manifest.json` before the guard ran, so its raw SHA-256 no longer matched the custody pin. Once a negative test deliberately rewrote and re-pinned the manifest, the same checkout conversion became visible on the next hashed text record, `README.md`.

The defect was therefore a cross-platform repository-byte portability gap, not four independent test defects and not corrupt brand content.

Git's documented `text eol=lf` attribute is the correct source-controlled boundary: it normalizes text to LF in the repository and prevents CRLF conversion in the working tree. During checkout Git reads `.gitattributes` from the index, so the target commit can enforce the rule before the protected tests inspect byte identity.

## Blast radius searched

The directly coupled byte-hashed text surfaces are all text entries inside `docs/brand/omni-cio-brand-assets-v1/`:

- `README.md`;
- top-level and nested JSON (`asset-manifest.json`, `brand-tokens.json`, Web manifest snippet);
- Android XML descriptors/background resources;
- `source/PRODUCTION-PROMPTS.md`.

Binary PNG/ICO assets must not be marked as text and remain byte-exact binary files.

The failure can affect any Windows checkout with CRLF conversion enabled, including the authoritative self-hosted Regression Shield and future Windows developer/recovery checkouts. Linux/GitHub canonical blob review alone cannot prove this working-tree byte invariant.

No application Web source, Cloudflare runtime, database schema, identity/session, broker, Telegram/VK, or Real-execution surface is coupled to this repair.

## Corrective change

1. Add a repository-scoped `.gitattributes` contract only for `*.md`, `*.json` and `*.xml` inside the byte-hashed brand package, using `text eol=lf`.
2. Do not apply a blanket text attribute to the package because it also contains PNG/ICO binaries.
3. Keep the existing manifest/custody byte hashes unchanged because they already describe the correct canonical LF bytes.
4. Add a deterministic regression in `tests/test_v10_brand_assets.py` requiring the three scoped LF patterns to remain present.
5. Preserve the permanent guard's strict raw-byte verification; do not normalize bytes inside the guard and do not weaken the manifest/custody pin.
6. Re-run the complete exact-head DRAFT verification because the source head changed.

## Why prior preflight missed it

Earlier package validation reasoned over canonical repository bytes and deterministic generated assets. The first authoritative Windows cycles failed earlier at formatter boundaries, so the Regression Shield had not yet exercised the final byte-hashed package on a Windows working tree after all formatter findings were fixed.

The missing preflight dimension was explicit EOL portability for text files whose exact bytes are security/integrity data. A content hash is only portable when checkout rules preserve the intended bytes across supported platforms.

## Permanent learning

- If a repository manifest hashes text files by exact bytes, line-ending policy is part of the integrity contract.
- Cross-platform exact-byte packages must source-control `eol` behavior rather than depend on each runner's/global Git configuration.
- Prefer narrowly scoped `.gitattributes` rules; never classify adjacent binary assets as text merely to solve an EOL failure.
- Do not weaken a correct byte-level guard to tolerate platform mutation. Preserve canonical bytes at checkout instead.
- When several negative tests fail at the same earlier invariant, diagnose that shared invariant before modifying the individual assertions.
- A semantic negative that re-pins an outer digest is useful for exposing the next coupled stale/portable boundary; inspect that next failure rather than treating it as unrelated noise.

## Security and authority invariants preserved

- Protected V9 `app:app` remains unchanged.
- `PUBLIC_MULTI_USER_ENABLED=false` remains unchanged.
- Broker write remains OFF.
- `trading_methods=false` remains unchanged.
- `REAL_TRADING_ENABLED=false` remains unchanged.
- No provider, broker, database, account or other production secret is added to source, logs, comments or artifacts.
- No Cloudflare/provider mutation is performed by this correction.
