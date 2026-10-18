# F01 / F22 / F23 — software navigation on the owned AVD

## 2026-10-19 repair, based on 2ab8337

The exact-head Android job stops at `System Back gesture never reached the production predictive handler`. The input driver acknowledges DOWN/MOVE, but the app reports back-progress=0 and the SystemUI diagnostic includes a disabled handler. The previous pass counters and speculative font-200 diagnosis must not be used as proof for this head.

The AVD is created without an explicit `--device`. The previous config writer only normalised disk size, leaving hardware Back/Home capability dependent on defaults. The emulator hardware property `hw.mainKeys=yes` describes a device with hardware navigation keys. Android can remove its software navigation bar/edge monitor in that configuration; switching the navigation overlay alone is not sufficient.

The owned pre-boot config now explicitly uses `hw.mainKeys=no`. Duplicate entries are replaced, other settings and the official system image remain unchanged. The actual guest property `qemu.hw.mainkeys` is added to the read-only provenance record, so the next device run can confirm the effective configuration rather than infer it from an overlay.

No product callback, PNG, MotionEvent sequence, UI assertion, duration, rendering threshold or navigation implementation is replaced or relaxed. The application binary content and required Android 15/16 workflows remain subject to the existing full validator.

## Verification boundary

Six local real-file regression tests pass: missing/default setting, duplicate hardware-key settings, idempotence, other AVD/SDK isolation, disk failure, symlink guard. Python compileall passes. Full emulator verification is still required and is not claimed by this document; the workflow and PR record its eventual result against the resulting SHA.

OWNER requested a private device-test APK only. No merge, published release, Timeweb deployment, server APK or update-channel change is authorised by this repair. The existing `[private-apk]` retention gate must still require successful complete API35/API36 runtime, backend and exact-head quality checks.

## Primary references

- [Emulator hardware schema](https://chromium.googlesource.com/android_tools/+/refs/heads/main/sdk/emulator/lib/hardware-properties.ini): hardware Back/Home keys are distinct from the navigation overlay.
- [Chromium emulator configuration](https://chromium.googlesource.com/chromium/src/build/+/997a9d9ea2162136e497bd8c9e4544c3bf969fff/android/pylib/local/emulator/avd.py): explicitly configures software navigation before boot.
- [AOSP edge handler](https://android.googlesource.com/platform/frameworks/base.git/+/ae9ca52c9da54c6253a1fba318de816fdb0f79df/packages/SystemUI/src/com/android/systemui/navigationbar/gestural/EdgeBackGestureHandler.java): handling depends on an attached navigation/task bar, not only a mode value.
