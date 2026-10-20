# Android 17 APK signing report audit — 20 October 2026

Work continues only in the existing `codex/spectrum-3d-100` / PR #880.
Baseline: e8e4a939ac9cec10d447440fcf3a0f2539fcb813.

Android CI #661, run 39396139876, job 118539579705 passed SDK37,
unit tests, lint, all app assemblies and exact-head Sonar, then stopped before
emulator startup with `Signing certificate changed` in verify_apk.py. The log
redirected apksigner output to a file and did not expose the actual fingerprint.
Consequently that log alone does NOT establish an actual signing-key change.

The old regular expression recognized only `Signer #N` and also classified a
missing/unrecognized record as a changed certificate. The official apksigner
source additionally prints SDK-range signer labels for v3.1 verification:
https://android.googlesource.com/platform/tools/apksig/+/refs/heads/main/src/apksigner/java/com/android/apksigner/ApkSignerTool.java

A bounded, separately tested report parser now recognizes these exact forms,
requires a successful report, exactly one signer, unambiguous verified v2,
and the SAME pinned certificate in EVERY reported signer record. SDK ranges
must be valid, nonoverlapping, cover API37 and have verified v3.1. Source-stamp
and public-key hashes cannot substitute for the application certificate.
Malformed reports and real certificate mismatches remain blocking errors.
Only public certificate hashes appear in a mismatch diagnostic.

The certificate pin, keystore configuration, version/package, official tool
verification and upgrade fixture are unchanged. No emulator assertion, Sonar
gate or publication condition is relaxed. Read size is bounded before decoding.

21 local unittest methods passed, including regression of the old empty match,
wrong/extra identities, duplicated and malformed records, source stamps, range
bounds and bounded file reading. Source bytes match the published Git blobs.
These are parser tests, not cryptographic validation of the actual APK and not
an emulator result. Final-head CI must determine whether #661 was a reporting
format problem or a genuine certificate mismatch. No such conclusion is
claimed before that run.

No Timeweb, live backend, broker operation, paid model or public release is
changed. The intended manual device is Samsung Galaxy S25 Ultra / Android17.
