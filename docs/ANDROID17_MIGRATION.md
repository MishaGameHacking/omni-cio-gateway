# Android 17-only platform contract — 0.11.0

Owner requirement: Android 17 / API 37 and newer. Primary physical target is
Samsung Galaxy S25 Ultra, Android 17 / One UI 9.0. No Xiaomi device is claimed.

## Release boundary

The application and test-driver min/compile/target SDKs must be 37. Current
Build Tools are 37.0.0, with the existing supported AGP 9.4 / Gradle 9.6 / JDK17
chain. JDK version, DEX format, APK versionCode and memory page size are NOT
Android operating-system versions. Supported public APIs are not deprecated
merely because they were introduced before API37.

Only current OS runtime profiles authorize a new APK: API37/4096-byte pages and
API37/16384-byte pages. Every profile needs real installation, upgrade from the
previous signed APK, launch, native/UI scenarios at both fonts, and measured
`getconf PAGE_SIZE`. Static ELF/ZIP alignment does not replace runtime evidence.
A reused first profile cannot stand in for the second. Historical reports cannot
be relabelled as Android17 results. The retained previous application version is
an upgrade fixture installed on the current OS, not support for an old OS.

Official package inventory was inspected through Android CLI 1.0.16625370:
`platforms/android-37.0`, `build-tools/37.0.0`,
`system-images/android-37.0/google_apis/x86_64` and
`system-images/android-37.0/google_apis_ps16k/x86_64` are available. Availability
is not a claim that an emulator test or build passed. Windows CLI uses android.exe.

## Runtime/API review

- Replace the deprecated checked-state fallback with `getChecked()` directly.
- Enforce no cleartext networking using Network Security Configuration, rather
  than relying on an application flag ignored for the new target.
- Preserve public UiAutomation input, real predictive-back progress/cancellation,
  process identity, rotation, accessibility, native rendering and strict pixels.
- Do not disable failing scenarios or treat a longer timeout as a verified fix.
- Keep immutable historical release/audit reports as history; current user-facing
  guidance and executable policy must no longer advertise an older OS floor.

## Status and deployment boundaries

This is a migration in review, not certification. Main and the development PR
are not updated until the integrated source and tests are reviewed. Remaining
runtime failures must be reproduced on API37, not declared fixed by SDK changes.
No Timeweb, backend deployment, server APK, channel, paid model or trading change
is authorized by this migration. Full CI and physical-device checks are separate.

Primary contracts:
- https://developer.android.com/about/versions/17/setup-sdk
- https://developer.android.com/about/versions/17/behavior-changes-all
- https://developer.android.com/build/releases/agp-9-4-0-release-notes
- https://developer.android.com/guide/practices/page-sizes
- https://developer.android.com/tools/agents/android-cli
