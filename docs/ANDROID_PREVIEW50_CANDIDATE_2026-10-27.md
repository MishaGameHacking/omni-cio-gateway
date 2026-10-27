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
