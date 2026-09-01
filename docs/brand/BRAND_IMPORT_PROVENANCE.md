# Omni-CIO Brand Assets v1 — repository import provenance

Status: **OWNER-PROVIDED ORIGINAL ASSET PACKAGE / GITHUB CANONICAL MATERIALIZATION COMPLETE / DETERMINISTIC INTEGRITY GUARDED**

Import date: 2026-09-01

This record preserves the source, repair, materialization and recovery history for the `Omni Sentinel Core` asset family prepared for the canonical `MishaGameHacking/omni-cio-gateway` repository.

## Product identity and scope

- Public/product brand: **Omni-CIO**.
- Mark: **Omni Sentinel Core**.
- The previously proposed `KURS` public branding was superseded by the OWNER on 2026-09-01 and is not part of this asset package.
- This work is an asset-preservation/integrity `FOCUSED_CHANGE`. It does not start `WEB-VISUAL-INTEGRATED`, activate public users, change Cloudflare/domain state, or expand broker/Real-money authority.

## OWNER source declaration

The package was supplied by the PROJECT OWNER as original OWNER-created work and was explicitly authorized for permanent storage and future Omni-CIO product use. No third-party asset/license dependency is introduced by this import.

## Original shared Drive source — provenance only

Original OWNER shared folder ID:

`1sRk82V647KjfSCV7OJQfxvX_wJqJ1BYx`

Original archive file ID:

`1VrGniNzt7ZEjpkTC0dml5SuEZ5H77z8Z`

Original archive filename: `omni-cio-brand-assets-v1.zip`

Original archive SHA-256:

`351aad1b6bb52125c7f67a3755281d595e1c6d7b9b4dc045901a90771038ed6d`

The original archive contains 37 package files. It is retained only as provenance because `transparent/omni-sentinel-core-color-1024.png` in that archive has an incomplete PNG `IDAT` stream. The shared source remains read-only to this integration and was not mutated in place.

## Ingestion defect and deterministic repository repair

Strict PNG validation found that the original transparent derivative had a truncated `IDAT` stream. Its original stored bytes were stable across the shared Drive/ZIP source, but the image itself was incomplete.

Original broken transparent derivative SHA-256:

`55ca090ac7a66c987b3ec4695765d3e4dada29dbfc32d8e7f9ff3a1998e82120`

The transparent derivative is reconstructed without redesign from `source/omni-sentinel-core-foreground-source-1254.png` using the approved recipe: RGBA source; alpha `< 8` normalized to transparent black; crop `(96, 120, 1160, 1142)`; LANCZOS resize to `640 x 615`; composite at `(192, 204)` on transparent `1024 x 1024`.

The first corrected private Drive package used a PNG encoding whose transparent derivative was:

- bytes: `264293`;
- SHA-256: `d1e69a10dd56ac11ce70d8de81589a3a1c0875108b1d161183337b48df658236`.

During GitHub materialization, the same approved reconstruction recipe was made byte-deterministic for repository custody. The final repository derivative uses PNG RGBA8, filter `0` for every scanline and zlib level `9`. The approved decoded RGBA pixel identity is pinned independently from PNG compression bytes.

Repository-canonical deterministic transparent derivative:

- bytes: `383535`;
- SHA-256: `1f1b2a44dbf3c55b485c478f39f114072dca3658c9c912e317ca2c487cbb3095`;
- decoded RGBA pixel SHA-256: `28a922764fed4ce5311a9c2071e43da61fd65f41837f643d0d1f3cf39fbc4499`.

This distinction is intentional: the earlier corrected Drive ZIP remains recovery/provenance evidence, while GitHub's manifest and tracked file tree are the canonical engineering byte identity.

## Maskable PWA derivative repair

Independent review found that the first materialized `web/pwa-maskable-512.png` was byte-identical to the ordinary `web/pwa-icon-512.png`. That was not acceptable for a `purpose: "maskable"` resource because a maskable icon must keep its important mark content inside the platform safe zone.

The defect was corrected without redesigning the frozen Omni Sentinel composition. A one-shot deterministic repair used the already accepted transparent foreground, centered the important foreground inside the Web App Manifest minimum safe-zone circle, and composited it over the approved opaque Omni-CIO diagonal background. The Web App Manifest safe zone is a centered circle with radius 40% of the icon size; the package records this as an 80% guaranteed-visible diameter contract.

Repository-canonical maskable derivative:

- path: `web/pwa-maskable-512.png`;
- dimensions: `512 x 512`;
- mode: `RGB` with opaque brand background;
- bytes: `136162`;
- SHA-256: `7ed01bd30c062d9b459f7208718fa350ab316b3d2c4b0f70549444e5288c2280`;
- generated foreground extent: `380 px`;
- source alpha bbox: `(192, 204, 832, 819)`;
- important-alpha threshold used by the deterministic fit check: `8`.

The ordinary 512 PWA icon remains unchanged and has SHA-256 `349ccd7642f0e05d67a96d4e6af3b643aa1b7c2a8f1ad853b0090abd3377cb86`. The permanent guard requires the ordinary and maskable resources to remain different and binds the maskable byte identity and safe-zone metadata through the custody contract.

## Frozen canonical master

`raster/omni-sentinel-core-1024.png` remains byte-identical to the OWNER package.

SHA-256:

`6ab10a3546dc57c0d88b352ab052db4e8f9b6464d52b4b4616b991c370bd805f`

## GitHub canonical repository custody

GitHub remains engineering/provenance authority rank 1. Commit `492055d15d3361d2c1857f3b87d12ee6c816cf7e` on the focused staging branch physically materialized the complete package under:

`docs/brand/omni-cio-brand-assets-v1/`

Repository custody contains all **37/37** package paths, including all PNG/ICO binaries referenced by the Android and Web/PWA descriptors.

The package manifest is:

`docs/brand/omni-cio-brand-assets-v1/asset-manifest.json`

Current repository manifest SHA-256:

`a0ef0746a1bd25aeda03570d011e95b7f3844f22e95cf68101237fce1a9c4cf6`

The machine-readable manifest digest authority is `docs/brand/OMNI_CIO_BRAND_ASSETS_CUSTODY.json`. `scripts/check_v10_brand_assets.py` reads that custody pin instead of carrying a second independent manifest-hash constant, so legitimate reviewed manifest updates cannot silently drift between two code constants.

The manifest records per-file byte counts and SHA-256 identities. Permanent verification is provided by:

- `scripts/check_v10_brand_assets.py`;
- `tests/test_v10_brand_assets.py`.

The guard verifies the exact package path set, manifest/custody hash binding, per-file hashes/sizes, PNG headers, the deterministic transparent PNG's chunk/CRC/decoded-pixel identity, the multi-frame favicon, ordinary-versus-maskable PWA separation, maskable safe-zone metadata, PWA manifest semantics, Android adaptive-icon descriptor completeness, custody state and the no-authority-expansion boundary.

The one-shot binary materialization and maskable-repair workflows/scripts were used only to bridge connector/binary-generation limitations. They are not part of the permanent package after materialization and repair are complete. The machine custody flag is therefore `binary_materialization_blocker_active=false`; this clears only the artifact-materialization blocker. It does **not** bypass or pre-satisfy the independent exact-head CI/review/merge gate. After acceptance, the permanent repository branch is `main`; the focused asset branch is retained only as staging provenance.

## Private Drive recovery/provenance custody

The earlier corrected package is retained privately in the connected OWNER Drive as independent recovery/provenance evidence:

- archive root folder ID: `1xViZ4jtS0mv10fnnjjPHsbOmCsy1GcVy`;
- expanded corrected folder ID: `19JbZCt5lFbL97hZ6ZHj7mJC_vavPy693`;
- corrected archive file ID: `12Zg5A0P__n_lMr3LYmDZdzESnFZ37Vxc`;
- archive filename: `omni-cio-brand-assets-v1-CANONICAL-4c6c83a8881d43a5.zip`;
- archive SHA-256: `4c6c83a8881d43a59eace38ff677e4fe0ef98271f67e0e50d8e7ff2a33bb5718`;
- archive bytes: `6589504`;
- expanded path count previously verified: `37/37`;
- current archive visibility: **private / not shared**.

An additional private recovery copy is retained as `OMNI-CIO-BRAND-ASSETS-V1-RECOVERY-COPY-4c6c83a8881d43a5.zip` at file ID `1k_4lm8RUg7LYgv8yX0JWd4MjP-rHLQe3`.

These Drive artifacts predate the deterministic repository PNG encoding and therefore are **not** the authority for current GitHub per-file bytes. They must not overwrite `asset-manifest.json` or the repository-canonical deterministic transparent/maskable derivatives during normal development.

## Historical pre-correction quarantine copy

A separate historical copy of the original archive is retained so provenance is not lost:

- file ID: `1vYBw3_MwD7tH6sSynV57CaekVwNwWzfx`;
- filename: `omni-cio-brand-assets-v1-PRE-CORRECTION-2026-09-01.zip`;
- status: **HISTORICAL ONLY — DO NOT USE AS CANONICAL PRODUCT ASSETS**.

This keeps the original OWNER-delivered byte history without allowing the known broken transparent PNG to be mistaken for a usable product derivative.

## Future product integration readiness

The repository package contains the complete reusable delivery family for later authorized product integration:

- Web/PWA: favicon, Apple Touch Icon, 192/512 icons, distinct maskable icon and manifest snippet;
- Android: background, foreground, monochrome layers and v26/v33 adaptive-icon XML resources;
- general product use: canonical raster sizes, transparent and monochrome marks, source layers, QA references and brand tokens.

Physical availability in GitHub does not by itself start a visual redesign. Applying these assets to the canonical `apps/web` product remains part of the separately authorized `WEB-VISUAL-INTEGRATED` work after its OWNER start gate.

## Authority effect

This custody work does **not**:

- start the Web Visual System Update;
- change Cloudflare/domain/provider state;
- activate public users;
- change `PUBLIC_MULTI_USER_ENABLED=false`;
- change `trading_methods=false`;
- change `REAL_TRADING_ENABLED=false`;
- expand broker-write or Real-money authority;
- modify protected V9 `app:app`.
