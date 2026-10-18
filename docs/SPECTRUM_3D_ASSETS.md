# Spectrum catalogue 1

90 first-party GLB meshes: 45 identities with standard/economy geometry.
Recreate them with `python3 tools/generate_spectrum_meshes.py` at the repository root.
Verify deterministic bytes with `--check` and geometry with
`python3 tools/test_spectrum_meshes.py`.

All geometry is authored by the checked-in generator. No stock models, copied
broker logos, external textures, raster images, external URIs or network downloads
are embedded. Runtime animation changes real mesh transforms and materials.
`app/src/main/assets/spectrum3d/catalogue.json` records the version, byte size,
SHA-256, triangle count and material family of every distributed model. Runtime
checks the selected model against that catalogue.

The runtime asset directory contains exactly 91 files: the 90 GLBs and
`catalogue.json`. Developer documentation stays in `docs/`; a README placed in
Android's `assets/` source directory becomes an extra packaged runtime asset.
After building preview, `python3 tools/generate_spectrum_meshes.py --check --check-apk`
verifies the exact names and bytes in `app/build/outputs/apk/preview/app-preview.apk`.
Missing, duplicate or extra entries remain errors, including documentation files.
The source-tree ZIP regression checks these same bytes without claiming to replace
the actual Android package check in CI.
