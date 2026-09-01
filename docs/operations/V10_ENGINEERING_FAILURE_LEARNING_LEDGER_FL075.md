# V10 Engineering Failure Learning Ledger — FL075

## Scope

Focused Omni-CIO Sentinel brand-asset custody/materialization work in issue #426 / PR #427.

This entry records a defect class discovered while turning the OWNER-provided asset package into a repository-canonical, integrity-guarded 37-file delivery family. It does not start `WEB-VISUAL-INTEGRATED`, activate public users, change Cloudflare/domain state, or expand broker/Real-money authority.

## Exact failure evidence

Exact head `48b2834036e9afe421078b5711fa35bdbdd33650` ran `Self-Hosted Windows CI` workflow run `33550298566`. The authoritative merge-gate job `99998639492` failed in `Run protected runtime static quality` because `ruff format --check .` found the one-shot `scripts/_temporary_generate_maskable_brand_asset.py` unformatted. All preceding protected-runtime bootstrap, dependency and policy stages had passed.

The same exact head received a successful SonarCloud Quality Gate but still reported **9 new maintainability issues** in the newly added permanent brand integrity guard, including duplicated literals, excessive cognitive complexity and an exception-handling quality finding. A green Quality Gate therefore did not prove that the new guard itself was sufficiently maintainable.

Independent Gitar review also found three adjacent correctness/custody defects:

- `web/pwa-maskable-512.png` was byte-identical to the ordinary 512 PWA icon despite being declared `purpose: maskable`;
- the manifest SHA-256 was pinned independently in multiple places, creating legitimate-update drift risk;
- the machine custody merge/materialization wording conflicted with the PR's actual DRAFT verification state.

Earlier review had separately found that Android adaptive-icon XML referenced foreground/monochrome drawables that were not yet physically materialized in the repository. That finding was resolved by completing 37/37 repository materialization before this final correction batch.

## Root cause

The package migration temporarily mixed three different concerns that require separate authority boundaries:

1. one-shot transport/generation mechanics used only to bridge connector/binary-generation limitations;
2. permanent repository asset custody and byte identity;
3. independent merge/readiness evidence produced by exact-head CI and review.

Because those concerns were not separated early enough, temporary repair code remained inside the protected static-quality surface, a platform-specific derivative inherited bytes from the ordinary icon instead of a maskable-safe composition, and custody metadata carried duplicated or ambiguous readiness signals.

The permanent guard also accumulated parsing, custody and delivery validation in functions that were correct enough for early regression protection but unnecessarily complex for long-term maintenance.

## Blast radius searched

The review covered all directly coupled producers and consumers of the brand package:

- all 37 paths in `docs/brand/omni-cio-brand-assets-v1/`;
- `asset-manifest.json` per-file byte/hash records;
- Web/PWA manifest/icon consumers;
- Android v26/v33 adaptive-icon descriptors and referenced drawables;
- `docs/brand/OMNI_CIO_BRAND_ASSETS_CUSTODY.json`;
- `docs/brand/BRAND_IMPORT_PROVENANCE.md`;
- `scripts/check_v10_brand_assets.py`;
- `tests/test_v10_brand_assets.py`;
- the one-shot materialization/maskable-repair workflow and helper scripts;
- PR #427 review threads and merge-state narrative.

No `apps/web` integration, Cloudflare runtime, broker-write, Real-money, Telegram/VK, or protected V9 entrypoint change was required or authorized by this defect class.

## Corrective change

The correction ending at parent head `44da2c09be1f6f1e1efb44ec6bcaf2fc12f0c0fd` before this ledger-only commit:

1. generated a distinct repository-canonical maskable PWA derivative from the accepted Omni Sentinel foreground over the approved opaque brand gradient;
2. pinned its 512×512 RGB byte identity and a Web App Manifest safe-zone contract using an 80% guaranteed-visible diameter (40% radius);
3. required the ordinary and maskable 512 icons to remain byte-distinct;
4. moved the machine-readable manifest digest authority to custody schema v4 and made the permanent guard read that pin instead of duplicating a second source-code constant;
5. replaced ambiguous merge-like custody wording with `binary_materialization_blocker_active=false`, which clears only the completed artifact-materialization blocker and does not assert merge readiness;
6. separated permanent acceptance branch `main` from the focused materialization staging branch in custody metadata;
7. decomposed the permanent guard into smaller PNG, Android descriptor, custody and delivery-contract validators and consolidated repeated path/marker literals;
8. added deterministic fail-closed regression cases for stale custody manifest pins and maskable safe-zone semantic drift;
9. removed the completed one-shot maskable repair workflow/helper from the permanent branch state instead of weakening Ruff or excluding temporary code from quality checks;
10. resolved the related Gitar review threads only after repository evidence matched the correction.

## Why prior checks missed it

Early integrity checks focused on package completeness, manifest byte identity, frozen master preservation and the deterministic repair of a truncated transparent PNG. Those checks correctly prevented corruption but did not initially assert that a `maskable` Web resource must be semantically distinct from the ordinary icon.

The first one-shot generation path was also treated as temporary operational scaffolding, but protected CI correctly evaluates every tracked Python file. Leaving a temporary helper tracked even for one verification cycle therefore exposed a legitimate formatting failure.

Finally, Sonar's Quality Gate was configured such that it could return `passed` while still reporting maintainability findings on new code. Independent review of the annotations was therefore necessary; the project rule that a green card does not replace code review was correct.

## Permanent learning

- One-shot migration/materialization helpers must be removed before final exact-head quality evidence; do not solve their failures by excluding them from lint/format/SAST surfaces.
- Delivery semantics matter in addition to byte validity: platform-specific assets such as `maskable` icons need explicit semantic invariants and regression guards.
- A manifest digest should have one machine-readable authority. Consumers should verify that authority, not duplicate independent constants that must drift together.
- Custody completion and PR merge readiness are different states and must never share an ambiguous boolean or narrative.
- A successful external Quality Gate does not waive its own reported issues; inspect annotations and fix material findings before merge.
- When review finds one delivery defect, inspect adjacent producers, consumers, descriptors, provenance and recovery metadata rather than patching only the named file.
- Exact-head evidence is invalidated by every new commit, including documentation/handoff commits; final DRAFT and READY gates must run on the final unchanged head.

## Security and authority invariants preserved

- Protected V9 `app:app` remains unchanged.
- `PUBLIC_MULTI_USER_ENABLED=false` remains unchanged.
- Telegram/VK activation remains outside this correction.
- Broker write remains OFF.
- `trading_methods=false` remains unchanged.
- `REAL_TRADING_ENABLED=false` remains unchanged.
- No provider, broker, database, account or other production secret is added to source, logs, comments or artifacts.
- No Cloudflare production mutation is performed by this correction.
