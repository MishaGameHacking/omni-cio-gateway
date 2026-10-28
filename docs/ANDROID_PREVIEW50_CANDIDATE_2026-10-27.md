# Android preview50 — build and delivery candidate, not a release

Owner request at 2026-10-27 17:31 UTC prioritizes a real signed APK built on
LAPTOP-NPSGA016 and delivered to existing Timeweb9417611, not another source-only
status report. This candidate starts at the freshly read PR888 HEAD
45168fa6ec2a5d98ba72ea013ed2a7b34a4d7201 and therefore includes the accumulated
source changes without overwriting that feature branch or the immutable backup.

Native change: the existing analysis-monitor panel exposes the deployed
/workspace/system-readiness API, separates valuation time from status time,
shows the five source lanes, and never treats fresh evidence as trading approval.
Only existing authenticated read transport is used. No runtime settings or
broker/model calls are enabled. JVM tests use synthetic payloads.

Candidate identity: 0.14.3-preview, versionCode50, ru.omnicio.app.debug.
Preserve the existing signing certificate
bbce9534fd4cfee8f3bdcaf51a31cce384a4f303f090c8cae9ec558227d59eb1.
minSdk37 is unchanged; support for Android15/16 is not claimed.

The integration PR targets main to request the already-existing Android/backend
CI, not to merge unchecked source. No workflows, transports, cloud permissions,
keys, secrets, main or production data are edited by this candidate. PR888 and
its immutable base remain unchanged. All build, installation and execution
evidence must come from the already-authorized owner host; do not manufacture
results, weaken gates or recreate a previously denied remote operation.

At source preparation: no new build, install/upgrade test, APK checksum,
publication or physical-phone installation exists. Those states remain unknown
until actual results are recorded. No automatic merge. No server deployment of
untested migrations. Before publishing, re-read the live channel and refuse a
version downgrade or existing conflicting code50. APK publication and owner
phone installation must be recorded separately. Full N00–N11 remains unfinished.

## Resumption — 2026-10-28: actual build result and remaining blockers

Fresh PR read still identified HEAD edbceab18555d6e2566387d951bcd9ef5cdefe39
and base f54912165127bfab42673743cd141d635e20881f. Android CI40563355274
completed. Its laptop job122398103370 passed the complete host-check/signed-build
step, but failed the exact-head Sonar step. The runtime installation/upgrade
matrix, evidence retention and publication jobs were skipped. This is NOT a
verified release, and the previous failures are retained unchanged.
Backend CI40563355336 completed its source/backend checks but also failed Sonar.
No active Actions run was reported before preparing these independent fixes.

This source batch addresses the unrestricted path input in the offline evidence
inspector, documents live-sync 401/429/499/503 responses, and shares the Android
live-revision grammar without weakening it. New synthetic regressions cover
named input selection, links, size/identity changes, duplicate/nonfinite JSON,
exclusive output, database-unavailable 503, disconnect and waiter cleanup.
These changes require fresh execution on the existing authorized laptop; no
project tests or builds have been executed in the chat scratch environment.

The inspector now accepts only `--snapshot snapshot.json`, optionally
`--strategy strategy.json`, from `.runtime-inspection/inputs/` in its checkout.
An aware `--at` is still mandatory with a snapshot. `--output hierarchy.json`
creates `.runtime-inspection/reports/hierarchy.json` exclusively. Arbitrary
absolute or relative path arguments are deliberately no longer supported.
Default hierarchy output remains stdout. No credentials or production database
are read, and no HTTP operation is performed by the inspector.

A separate attempted source update to `.github/scripts/windows_android_ci.py`
was refused by the tool safety layer. It was NOT committed or applied and was
NOT retried through another encoding, transport, helper or delegated executor.
The existing Windows controller, its release gates, workflows and permissions
remain unchanged. Its Sonar findings, the publisher advisory and the remaining
quality findings are still open. Do not claim those fixes or a clean gate.

The live policy could not be retrieved from this chat network during this
resumption. Do not infer its current version from historical49 documentation.
No APK was delivered, no production configuration/data was changed, and no
physical-phone installation was performed by this source batch.
