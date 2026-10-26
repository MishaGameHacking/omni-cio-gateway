# N00 — stable native actions for exact rating source folds

N00 is open; N01–N11 are not implemented. Published APK38 is unchanged.
Candidate41 /0.13.3-preview remains the exact application built in
[40252011635](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/40252011635).
This change repairs test traversal, with no new APK or publication.

## Measured failure

[40255133373](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/40255133373)
passed the original discovery case and the dossier's dock/risk navigation,
then failed to read the exact historical rating publication. Details and the
original archive are in [the fixed dock checkpoint](N00_DOSSIER_DOCK_2026-10-26.md).

[Diagnostic40256049480](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/40256049480)
used unchanged source722adbe43c8bf1604ec89c0469a4b1ff40e6119e,
inventory6b793696cf0fd5cf30cfe44a19c55453a6ead01be1526ea6eeb5a0a48ea05052,
and the same APKs on omni-cio-ci-4, measured16384-byte pages.
Runtime:2026-10-26T01:49:34Z–01:53:54Z. The original assertion still failed.

It recorded58 native frames from the original traversal and subsequent
bounded reverse inspection. Before the raw tap, the text was at
[80,410][270,449], inside a clickable owner at[38,398][282,461].
The original code immediately tapped the text's coordinates after scrolling.
The next frames still showed that owner's content without an expanded source.
After preserving the original failure,21 reverse scrolls returned to the
same source fold at[38,396][282,459], still explicitly Свёрнуто.
The publication value was not found in the reverse inspection.

This proves the raw action did not expand the selected fold. The frames do
not independently identify Android's exact input-dispatch reason. The repair
uses the existing settled native-action contract and requires the real fold
state transition before looking for data; it does not substitute another date.

The35-file archive is776944 bytes, SHA256
9343e996dda14bfd2fd20e81329f65450eaf61970df418a380f5fa1d97e917c4.
Timeweb9417611 confirmed receipt at01:55:09Z in
/var/lib/analyst-ai-build/incoming/windows-development-40256049480-1/.
Collector and cleanup succeeded; diagnostic/runtime failure remains recorded.

Read-only [evidence40256460327](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/40256460327)
returned154764 bytes SHA256d0cba8b91b9138f25453b313f640ea3804f73f449baa559e25e5b478bf9db20a.
The archive and all7 manifest entries were verified. The reverse-fold PNG
was visually inspected and shows the collapsed plus control.
Before-tap XML SHA256daa368a8ba3df523a5b62d5607a554a87fa0990737cf6134412562ded35a1406;
reverse-fold XML SHA256920759a250dd8a4ada927d41cbbb2bd5dcfbc7786fef273c240e3cb9d9e5d75e;
reverse-fold PNG SHA25662c17e951e44b934cafc85e20d919ccbb4ad3687d22e7a1fb2d31de134cc91d8;
all-frame JSON SHA2566ab110485f884f464731a994a20704c1b2eeba48b56d08c5e8ddc626fab46569.

## Windows-applied repair

[40257272188](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/40257272188)
applied three files on LAPTOP-NPSGA016 /omni-cio-ci-3 at02:04:55Z,
starting from5bfec1ab339da82478c8d6123b64ba2d4de9f33e.

PortfolioCase.record_fold retains the selected source record and every real
ancestor while excluding other records' identical labels. It reveals the
native action with the existing48px margin, waits for three fresh identical
native target frames, requires the expected initial fold state, taps once,
and waits for that same record's explicit Развёрнуто/Свёрнуто state.
A missing transition fails without repeated taps or scrolling for absent data.
Both historical rating folds now use this method for opening and closing.
The exact publication date, agency, grade, scale, subject UID/status and source
URL assertions are unchanged. Generic source-value binding is unchanged.

The fixture models an early tap being consumed during scrolling and delayed
native fold transitions at two conditional scales. These are unit conditions,
not claimed device measurements. The regression exercises original
_rating_history and the real scoped reveal/stability/state helpers.
Other checks cover identical sibling labels, disabled/clipped ancestors,
duplicate/foreign/hidden records, an absent transition and an unexpected state.

| Windows-applied file | SHA256 |
|---|---|
|.github/scripts/portfolio_ui_probe.py|01beff567b8af78b61270a50529f8e57230c167869e2835e848530de24ce81d2|
|.github/scripts/portfolio_research_probe.py|f6d7a771076bb8f07dde4a43c002b76a3cd65089d4fc0c0cf7bc9c0b6fd6dd86|
|.github/scripts/tests/test_portfolio_controls_evidence.py|978601b5ae4e78767236b7f34a5a47f3adfb5f47f7773eea11ec21c3823412d2|

Code inventory9c0e24a49ae94e38642254d53d7de81688af569496dcf73d08b2d346db28bdb7.
Patch SHA2561d023008a1a28be4b6b6567129a94705ea696f0e697412379492c231b55a47b3;
administrative wrapper SHA256c3a7c414c05371f8e23a1ab5955da69737d8c607eb6bb6b29158fe632c0faf33.
The canonical lease and1200s wait limit remain unchanged.

Under that lease, the original research probe was temporarily restored.
The named regression failed both subtests with Selected rating source remained
collapsed (Ran1 test, failures2). The reviewed probe was then restored.
All1070 host tests passed in47.426s (same3 platform skips), plus diff check.
Source and APK identity checks passed; host stage finished02:05:49Z.

## Runtime and continuation

The same run now exercises all14 original portfolio cases at fonts100/200
on the measured16KB emulator with preview41/debug41/driver7fb9ad41.
No application is rebuilt for this harness-only change. Actual runtime
results are pending; unit success alone does not prove the Android repair.
The focused diagnostic hook cannot claim the complete UI acceptance gate.

After all14 focused cases pass, regenerate the full original15-stage wrapper
from this exact backed source and run both4096/16384 profiles, including
baseline38→41 upgrade and clean installation. Older prepared wrappers have
obsolete harness inventories and must not be dispatched.
Then finish the laptop/WSL CI migration and exact-head Sonar gates before
closing N00 and moving to N01. No release41, real orders, paid AI activation
or physical-phone acceptance is implied by these results.
