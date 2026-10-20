# F22 / F23 — Android 17 preparation contract repair

## Reproduced blocker

Baseline: PR #880, `codex/spectrum-3d-100`,
`f798d840bca37496df5861ebb7b421204e972f7c`.
Android CI #664 (run `39404974966`, job `118568585801`) built and linted
successfully, but stopped in `emulator_boot_readiness._verify_target` with
`ValueError: Preparation requires the supported Android matrix` before candidate
installation. This run is NOT evidence of a renderer defect.

The installation driver and `backend/android_runtime_contract.py` already select
API37 with 4096/16384-byte profiles. The boot guard still independently allowed
only API35/36; its positive unit fixtures repeated the same stale assumption.
Both configured API37 profile requests reproduce the rejection without issuing
a device command. Earlier UI/renderer failures remain separate, unresolved
runtime questions; changing this guard cannot certify them.

## Repair

The boot guard imports the existing immutable `RUNTIME_PROFILES` and accepts only
an integer API present in that contract. There is no older-platform fallback or
open-ended `>=37` acceptance of an untested future emulator. Product minSdk and
the finite test matrix have different purposes. Repository-root import setup
also works when the script is launched outside the checkout working directory.

Both original boot/console suites now use the canonical minimum/current profiles.
All existing ownership, exact guest SDK, PackageManager barriers, original-error
preservation, system_server identity and setup restoration checks are retained.
No device API calls, retry counts, timeouts, renderer, publication gate or
workflow assertions are removed or relaxed. Actual kernel page size is still
measured separately by the unchanged installation driver before installation.

Five new methods cover all below-minimum APIs, noninteger/future APIs, wrong guest
SDK, an empty contract and import from a different working directory. Invalid
requests fail before any settings mutation. Positive cases cover both configured
profile requests, not a claim that a mocked device measured both page sizes.

## Local evidence and limits

Original source bytes for the boot guard, setup context, runtime contract and
both original suites were verified against Git blob hashes before patching.
The four uploaded Python blobs match the locally executed files byte-for-byte.

**38 focused test methods passed** and compileall passed on the retrieved source
subset. One original source-structure test needs the complete installation driver
and was not selected in the local subset harness. That method remains unchanged
in the committed suite and MUST execute in ordinary full-checkout CI. No skip is
added to the repository. Local tests use a deterministic disposable-device double;
no local emulator, whole-project build, live backend or physical phone is claimed.

Full CI command (includes the unchanged source-structure regression):

```text
py -3 -m unittest discover -s .github/scripts/tests -p "test_*.py" -v
```

Exact-head Sonar, Backend CI and complete API37 runtime checks for both page sizes
remain required after publication. The 0.10.0 APK is an upgrade fixture on the new
OS, not support for an old Android OS. A private device-test APK remains gated on
complete acceptance, with no Timeweb/backend/server APK/update-channel change.

Technical references: Android 17 setup
https://developer.android.com/about/versions/17/setup-sdk
and actual page-size testing
https://developer.android.com/guide/practices/page-sizes#test.
