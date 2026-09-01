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

During repository ingestion, strict PNG validation found that `transparent/omni-sentinel-core-color-1024.png` had a truncated `IDAT` stream. The original stored bytes were stable (Drive and ZIP copies matched), but the PNG itself was incomplete. Its original SHA-256 was `55ca090ac7a66c987b3ec4695765d3e4dada29dbfc32d8e7f9ff3a1998e82120`.

The derived transparent asset was reconstructed without redesign from `source/omni-sentinel-core-foreground-source-1254.png`: RGBA source; alpha `< 8` normalized to transparent black; crop `(96, 120, 1160, 1142)`; LANCZOS resize to `640 x 615`; composite at `(192, 204)` on transparent `1024 x 1024`; then complete PNG/CRC/image-decode validation.

Corrected transparent asset SHA-256: `d1e69a10dd56ac11ce70d8de81589a3a1c0875108b1d161183337b48df658236`.

## Frozen canonical master

`raster/omni-sentinel-core-1024.png` remains byte-identical to the OWNER package.

SHA-256: `6ab10a3546dc57c0d88b352ab052db4e8f9b6464d52b4b4616b991c370bd805f`.

## Corrected archive identity

- filename: `omni-cio-brand-assets-v1.zip`
- SHA-256: `4c6c83a8881d43a59eace38ff677e4fe0ef98271f67e0e50d8e7ff2a33bb5718`
- package paths: `37`
- ZIP CRC validation: PASS

## Durable binary custody mirror

A byte-identical corrected archive is stored in the PROJECT OWNER's connected Google Drive so future authorized engineering sessions can recover the complete binary package even when a GitHub client cannot stream local binary files into the Git data API.

- Drive file ID: `18B0OCxuU36BUEzbz8nr2dIiSj9wjsqF-`
- filename: `omni-cio-brand-assets-v1.zip`
- MIME type: `application/zip`
- SHA-256: `4c6c83a8881d43a59eace38ff677e4fe0ef98271f67e0e50d8e7ff2a33bb5718`

This mirror is custody/recovery evidence only. GitHub remains engineering authority rank 1. It does not authorize branding deployment, public cutover, or runtime/broker capability transitions.
