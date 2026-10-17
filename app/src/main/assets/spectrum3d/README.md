# Spectrum catalogue 1

88 first-party GLB meshes: 44 identities with standard/economy geometry.
Recreate them with `python3 tools/generate_spectrum_meshes.py` at the repository root.
Verify deterministic bytes with `--check` and geometry with
`python3 tools/test_spectrum_meshes.py`.

All geometry is authored by the checked-in generator. No stock models, copied
broker logos, external textures, raster images, external URIs or network downloads
are embedded. Runtime animation changes real mesh transforms and materials.
`catalogue.json` records the version, byte size, SHA-256 and triangle count of every
distributed model. Runtime checks the selected model against that catalogue.
