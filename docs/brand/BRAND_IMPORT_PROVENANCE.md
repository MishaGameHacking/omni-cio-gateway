# Omni-CIO Brand Assets v1 — repository import provenance

Status: **OWNER-PROVIDED ORIGINAL ASSET PACKAGE / CORRECTED CANONICAL CUSTODY PRESERVED / REPOSITORY BINARY MATERIALIZATION INCOMPLETE**

Import date: 2026-09-01

This record preserves the source, repair and custody history for the `Omni Sentinel Core` asset family prepared for the canonical `MishaGameHacking/omni-cio-gateway` repository.

## Product identity

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

The original archive contained 37 package files. The shared source is retained only as provenance and is **not canonical** because it contains the pre-correction transparent derivative described below. The current integration has read access but not write permission to that shared source folder, so it was intentionally not mutated in place.

## Ingestion defect and deterministic repair

During repository ingestion, strict PNG validation found that `transparent/omni-sentinel-core-color-1024.png` had a truncated `IDAT` stream. The original stored bytes were stable (Drive and ZIP copies matched), but the PNG itself was incomplete. Its original SHA-256 was:

`55ca090ac7a66c987b3ec4695765d3e4dada29dbfc32d8e7f9ff3a1998e82120`

The derived transparent asset was reconstructed without redesign from `source/omni-sentinel-core-foreground-source-1254.png`: RGBA source; alpha `< 8` normalized to transparent black; crop `(96, 120, 1160, 1142)`; LANCZOS resize to `640 x 615`; composite at `(192, 204)` on transparent `1024 x 1024`; then complete PNG/CRC/image-decode validation.

Corrected transparent asset:

- bytes: `264293`;
- SHA-256: `d1e69a10dd56ac11ce70d8de81589a3a1c0875108b1d161183337b48df658236`.

## Frozen canonical master

`raster/omni-sentinel-core-1024.png` remains byte-identical to the OWNER package.

SHA-256:

`6ab10a3546dc57c0d88b352ab052db4e8f9b6464d52b4b4616b991c370bd805f`

## Corrected canonical archive identity

- canonical filename: `omni-cio-brand-assets-v1-CANONICAL-4c6c83a8881d43a5.zip`;
- SHA-256: `4c6c83a8881d43a59eace38ff677e4fe0ef98271f67e0e50d8e7ff2a33bb5718`;
- archive bytes: `6589504`;
- package paths: `37`;
- ZIP CRC validation: **PASS**;
- manifest size/hash verification: **PASS**;
- image/ICO decode verification: **PASS**.

## Private canonical Drive custody

Because the OWNER shared source folder is read-only to this integration, a new private custody root was created in the connected OWNER Drive:

- archive root folder ID: `1xViZ4jtS0mv10fnnjjPHsbOmCsy1GcVy`;
- canonical expanded folder ID: `19JbZCt5lFbL97hZ6ZHj7mJC_vavPy693`;
- canonical archive file ID: `12Zg5A0P__n_lMr3LYmDZdzESnFZ37Vxc`;
- canonical archive filename: `omni-cio-brand-assets-v1-CANONICAL-4c6c83a8881d43a5.zip`;
- visibility of the new expanded custody tree: **private / not shared**;
- expanded canonical files: **37/37 present**.

The uploaded canonical archive was downloaded again from Drive and re-hashed. Its SHA-256 remained exactly:

`4c6c83a8881d43a59eace38ff677e4fe0ef98271f67e0e50d8e7ff2a33bb5718`

The re-downloaded ZIP also contains the expected 37 file entries and passes ZIP integrity validation.

## Historical pre-correction quarantine copy

A separate historical copy of the original archive is retained so provenance is not lost:

- file ID: `1vYBw3_MwD7tH6sSynV57CaekVwNwWzfx`;
- filename: `omni-cio-brand-assets-v1-PRE-CORRECTION-2026-09-01.zip`;
- status: **HISTORICAL ONLY — DO NOT USE AS CANONICAL PRODUCT ASSETS**.

This keeps the original OWNER-delivered byte history without allowing the known broken transparent PNG to be mistaken for the canonical derivative.

## GitHub repository custody state

GitHub remains engineering/provenance authority rank 1. The branch `assets/omni-cio-brand-assets-v1` currently stores the manifest, provenance/custody records, tokens/prompts/integration descriptors and the existing safely materialized binary sample. The complete 37-file binary family is **not yet physically materialized in GitHub**.

The available GitHub connector creates binary Git blobs from inline UTF-8/base64 `content`; it does not expose a file-reference upload parameter. Serializing the full multi-megabyte compressed binary family through model text is not used as a workaround because it is unnecessarily fragile and difficult to review.

Until a reviewed binary-capable Git transport is available, the private corrected Drive archive plus expanded 37-file tree are the lossless recovery custody for the binaries. PR #427 must remain DRAFT and must not be merged as though GitHub binary materialization were complete.

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
