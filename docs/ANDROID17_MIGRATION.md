# Android 17-only platform contract — Analyst AI 0.11.0

Owner requirement: Android 17 / API 37 and newer. Primary physical target is
Samsung Galaxy S25 Ultra, Android 17 / One UI 9.0. No physical-device test is
claimed by an emulator or build result. Device serials/IMEIs are not needed.

## One development branch

All 0.11.0 work continues in `codex/spectrum-3d-100`, existing PR #880.
The reviewed source migration from `1d99dc8` is integrated here, preserving the
existing application, 3D assets, investment features and security fixes. The
one-off audit workflows and rewrite scripts are retired, not the functional
tests. No additional feature branch or replacement application is created.

## Release boundary

Application and test-driver min/compile/target SDKs are 37. Build Tools are
37.0.0 with the existing AGP 9.4 / Gradle 9.6 / JDK17 chain. JDK version, DEX
format, APK versionCode and memory page size are NOT OS versions. Supported
public APIs do not become deprecated merely by predating API37.

Only API37/4096-byte and API37/16384-byte runtime profiles authorize a candidate.
Each requires actual installation, upgrade from the previous signed APK, launch,
full native/UI scenarios at both font scales and measured `getconf PAGE_SIZE`.
Static ELF/ZIP alignment does not replace runtime evidence. Reusing one profile
cannot certify the other. Historical reports must not be relabelled. The prior
signed app is an upgrade fixture installed on the current OS, not older OS support.

The official SDK inventory previously inspected through Android CLI 1.0.16625370
contains `platforms/android-37.0`, `build-tools/37.0.0`,
`system-images/android-37.0/google_apis/x86_64` and
`system-images/android-37.0/google_apis_ps16k/x86_64`. Installed payload metadata
and the booted guest must still be checked; availability is not runtime success.

## API and behavior

The test driver uses public getChecked() without the deprecated fallback.
Network Security Configuration explicitly rejects cleartext connections.
Public UiAutomation input, predictive-back progress/cancel/commit, process
identity, rotation, accessibility, native rendering and strict pixels remain.
Failed UI scenarios must be diagnosed, not skipped or hidden by longer deadlines.
Historical audit/release records remain immutable and are not current guidance.

## Evidence and delivery

Prior migration branch build audit 39389618307 successfully built/linted the app
and driver at e2d63de6. It did NOT test the integrated commit or emulate the app.
The integrated PR must pass Backend CI, Sonar and the full Android CI again.
A private draft APK is permitted only after its exact commit and bytes satisfy
those gates. This is a manual-test attachment, not a server release.
No Timeweb/backend deployment, server APK/update-channel change, paid model call
or brokerage order is performed by this consolidation. Single-owner runtime and
live source integration need their own end-to-end checks; do not equate this
platform migration to completion of every product requirement.

Primary contracts:
- https://developer.android.com/about/versions/17/setup-sdk
- https://developer.android.com/about/versions/17/behavior-changes-all
- https://developer.android.com/build/releases/agp-9-4-0-release-notes
- https://developer.android.com/guide/practices/page-sizes
- https://developer.android.com/tools/agents/android-cli
