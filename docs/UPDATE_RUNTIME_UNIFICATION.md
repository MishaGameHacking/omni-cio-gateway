# One update runtime: integration of #832 into Spectrum #833

This change ports the canonical runtime from #832 at f963508b4767344b62a982dd5c4e7ec5a6d989b3. It is an integration checkpoint, NOT a published APK, server deployment, completed migration or claim of a successful device self-update.

## Implemented

- One `MandatoryUpdateHost` owns policy checks, permission and installer handoff. It accepts a presentation-only renderer; Spectrum does not run another updater.
- One transport contract: `/client/update-policy`, `/client/ready`, `/client/apk/...`, `X-Analyst-Version-Code` and `X-Analyst-Package`.
- The #832 guarded native installer, typed release metadata, bounded checksummed stream and authenticated server pause/resume are retained.
- The former AppRelease/AppUpdateClient/AppUpdateVerifier/AppUpdateInstaller/UpdateCheckStore runtime is removed. Its pure UpdateFlow research checks are retained, not used as a second network or installer path.
- BootstrapActivity is a routing-only exported launcher. It forwards only the documented `analystai://auth` data to private MainActivity. The one mandatory gate is inside MainActivity. Arbitrary external extras are not forwarded. The former Application lifecycle gate is removed.
- Existing Telegram code exchange/session storage, five tabs, education entry, theme preference, package/signature and versionCode remain intact.
- Spectrum update rendering respects safe drawing insets, 48 dp controls, scrolling and the persisted RGB motion preference. System installation consent is never bypassed or guaranteed to be silent.
- #832 backend modules/tests are included, while Spectrum's original risk_preview/release_contract and their tests remain available. No source or risk result is fabricated.
- Fourteen source-boundary tests verify this wiring. They do not establish that a real APK was downloaded/installed.

## Still blocks merge and publication

1. Exact-head Android compile/lint, profile/layout checks and real old-to-new-to-next self-update on supported emulators are required. Pure JVM success is not a substitute.
2. The legacy #833 release builder/publisher still emits `/releases/current.json`. It MUST be migrated to the canonical server ReleaseChannel and verified immutable publication protocol before any release. Do not run the existing publishing workflow for this checkpoint.
3. Production backend has not received this integration. Do not enable `ANDROID_UPDATES_ENABLED` until the verified updater-capable bootstrap APK is accessible and the end-to-end recovery path is tested.
4. Review remaining Sonar findings. No test, quality threshold, authorization check or source-integrity requirement is disabled.
5. Reconcile the separate #831 evidence/rebalancing work and all remaining design/data-source scope before claiming the whole update complete.

Version headers are compatibility claims, never authentication or cryptographic attestation. Previously installed 0.5.1 has no updater and requires one manual bootstrap upgrade. Android may require source permission, installation consent and a tap on Open.
