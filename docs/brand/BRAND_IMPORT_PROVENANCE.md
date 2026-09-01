# Omni-CIO Brand Assets v1 — repository import provenance

Status: **OWNER-PROVIDED ORIGINAL ASSET PACKAGE / REPOSITORY CUSTODY AUTHORIZED**

Import date: 2026-09-01

This record preserves the source and integrity history for the `Omni Sentinel Core` asset family imported into the canonical `MishaGameHacking/omni-cio-gateway` repository.

## Product identity

- Public/product brand: **Omni-CIO**.
- Mark: **Omni Sentinel Core**.
- The previously proposed `KURS` public branding was superseded by the OWNER on 2026-09-01 and is not part of this asset package.
- This import is an asset-preservation/integrity `FOCUSED_CHANGE`. It does not start `WEB-VISUAL-INTEGRATED`, activate public users, change Cloudflare/domain state, or expand broker/Real-money authority.

## OWNER source declaration

The package was supplied by the PROJECT OWNER as original OWNER-created work and was explicitly authorized for permanent storage and use in the private canonical GitHub repository. No third-party asset/license dependency is introduced by this import.

## Original Drive package

Original archive filename: `omni-cio-brand-assets-v1.zip`

Original archive SHA-256:

`351aad1b6bb52125c7f67a3755281d595e1c6d7b9b4dc045901a90771038ed6d`

The archive contained 37 package files.

## Ingestion defect and deterministic repair

During repository ingestion, strict PNG validation found that:

`transparent/omni-sentinel-core-color-1024.png`

had a truncated `IDAT` stream. The original stored bytes were stable (Drive and ZIP copies matched), but the PNG itself was incomplete. Its original SHA-256 was:

`55ca090ac7a66c987b3ec4695765d3e4dada29dbfc32d8e7f9ff3a1998e82120`

The derived transparent asset was reconstructed without redesign from the package's approved high-resolution transparent foreground source:

`source/omni-sentinel-core-foreground-source-1254.png`

Deterministic reconstruction recipe:

1. use RGBA source;
2. remove source extraction noise with alpha threshold `< 8 -> transparent black`;
3. crop the resulting approved foreground bounds `(96, 120, 1160, 1142)`;
4. resize with LANCZOS to `640 x 615`;
5. composite at `(192, 204)` on a transparent `1024 x 1024` canvas;
6. save as a complete PNG and rerun chunk CRC/image-decode validation.

The reconstructed image matches the surviving valid portion of the damaged derivative at greater than 99.8% exact pixel identity and restores the missing lower portion from the approved source geometry.

Corrected transparent asset SHA-256:

`d1e69a10dd56ac11ce70d8de81589a3a1c0875108b1d161183337b48df658236`

The package `asset-manifest.json` was updated only for the corrected derivative's byte length and SHA-256/integrity fields.

## Frozen canonical master

The full-background canonical master remains byte-identical to the OWNER package:

`raster/omni-sentinel-core-1024.png`

SHA-256:

`6ab10a3546dc57c0d88b352ab052db4e8f9b6464d52b4b4616b991c370bd805f`

## Corrected archive identity

Corrected archive filename: `omni-cio-brand-assets-v1.zip`

Corrected archive SHA-256:

`4c6c83a8881d43a59eace38ff677e4fe0ef98271f67e0e50d8e7ff2a33bb5718`

The corrected archive contains the same 37 package paths and passes ZIP CRC validation.

## Durable binary custody mirror

A byte-identical corrected archive is also stored in the PROJECT OWNER's connected Google Drive so future authorized engineering sessions can recover the complete binary package even when the GitHub connector in a given ChatGPT runtime cannot stream local binary files into the Git data API.

- Drive file ID: `18B0OCxuU36BUEzbz8nr2dIiSj9wjsqF-`
- Filename: `omni-cio-brand-assets-v1.zip`
- MIME type: `application/zip`
- SHA-256: `4c6c83a8881d43a59eace38ff677e4fe0ef98271f67e0e50d8e7ff2a33bb5718`
- Package paths: `37`

This mirror is custody/recovery evidence only. GitHub remains engineering authority rank 1; the manifest and provenance committed to GitHub define the expected package identity. The Drive file does not authorize branding deployment, public cutover, or any runtime/broker capability transition.

## Validation

The prepared deterministic guard `check_v10_brand_assets.py` verifies manifest path coverage, byte lengths, SHA-256 values, PNG chunk structure/CRC/IEND and IHDR dimensions, JSON/XML parsing, favicon frame inventory, Android safe-zone metadata, and the frozen canonical master digest.
