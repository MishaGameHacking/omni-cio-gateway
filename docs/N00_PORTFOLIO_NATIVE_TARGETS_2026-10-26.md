# N00 — compound native portfolio targets

N00 is open; N01–N11 are not implemented. Published APK38 is unchanged.
Candidate40 has a successful full laptop build, but no complete Android
matrix, external quality result, publication40 or physical-phone result.

## Actual complete-suite failure

[Full run40247318025](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/40247318025)
uses source46158e9a5b8da09f0188fc882154a455d119f127 and inventory
770337e637aadcccec66047048aa7e696a58524d2536f2f66d4d20a16b633bac.
It has no diagnostic hook. The16KB profile ran
2026-10-26T00:01:43.753376Z–00:18:40.039512Z and failed.
Page measurement, genuine38 installation,38→40 upgrade/launch,40 clean
installation/launch and debug fixture installation all passed.

The first five stages passed: native2D, session, privacy, goals, and all60
business cases (30 each at font100% and200%). All eight catalogue case/font
combinations completed. The saved business-verification.json confirms the
price guard, typed request, displayed constraints, invalidation after editing
and no-order checks for ready/partial at both fonts.

The next stage failed in discovery/ready/font1:
"ValueError: Unknown list or invalid native reveal target".
The exact call chain is exercise_discovery → tap_resource → partial native
alignment → FrameReader.show_on_screen. Discovery constructs the existing
resource ID discovery-compare-<account>:<instrument>. Both the Python wire
validator and Java NodeRevealAction.readTarget currently reject a colon.
This is a confirmed test-protocol defect, not an absent application control.

The failure image was visually inspected. It shows the actual discovery
screen, native query SYN, one selected comparison item and a partly clipped
next control. It does not itself prove the repaired action works.

[Evidence run40248845961](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/40248845961)
artifact12619897319:111,959 bytes, SHA256
be661ad1cea8be5f8e339b2e38e5a4ebf4b16ad96b1ece75a1b1746dd3c153db.
The downloaded archive and all three manifest file hashes were verified.

| Evidence | SHA256 |
|---|---|
|business-verification.json|494896dec4bea74f3aefa3b20e5027c08d26e5dd0bca83d03cfd2b64b188203d|
|failure.png|ec411b7242f7f04933fd22f12b04673b0e31419b3ee786c0bcd3b29ab12e9cf2|
|runtime-16384.log|d135d7a9a358d281eb45964073f72d3b5608601ffaa90d067a4ad2147d8c6430|

The4KB profile also failed at the same compound target after all five stages
and60 business cases passed. It ran00:18:42.967641Z–00:36:19.390312Z.
The full workflow concluded FAILURE. The238-file archive is9,746,314 bytes,
SHA2564270e98b4b3ae40014322201f670c08aa45d4288b2a5c73c0446db15f79a12d8.
Timeweb9417611 confirmed receipt at2026-10-26T00:37:07Z under
/var/lib/analyst-ai-build/incoming/windows-development-40247318025-1/.
No application source ran on Timeweb.

[Independent4KB evidence40250377192](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/40250377192)
artifact12619633604 is112,681 bytes, archive SHA256
f68f43668d4200d03d350240dccfbd2c22ad464c9f4ae8b0fbc9f2a8512b8540.
The archive and all three manifest file hashes were verified. The second
business report contains exactly30 cases at each font and60 total; its
SHA256 is299e5dfe4a4f76c3d24cb9a1fd8c9ed6bd24b82ea891d15bf502fcb92be532d9.
The second failure PNG was visually inspected; SHA256
9301d78b5671ba97bac607a5ac77775891c04265ca4128945f032a2fd49659cb.

## Windows repair, original failure and complete host verification

Four files extend the test-only grammar to nonempty colon-separated bounded
ASCII components. The96-byte limit, exact whitelisted list, focused app
window, matching native descendant, public ACTION_SHOW_ON_SCREEN, subsequent
fresh geometry, minimum48px tap area and three-frame stability remain required.
No click or application-state operation was added to the protocol.
Invalid separators, paths, foreign resources, duplicate nodes, disabled/hidden
targets, oversized names and wrong acknowledgements remain rejected.

| Windows-applied file | SHA256 |
|---|---|
|persistent_ui.py|889064aafdf7a1dcf6f0c9f324c5ae79d162f21a342c947271ae5f13c68328d8|
|NodeRevealAction.java|85b040f815ce7795cb419a7c7d9016855f9e41d0797d8c58ded14ee93449575f|
|test_native_target_reveal.py|94d44c8d2a1dbc086a7c22e02eb75cfbce3edbbd6f8aa007811712bb9101ffed|
|NodeRevealActionTest.java|43e0d801bf0ab065046f39d20f1f8b8364b7e1aaf1ebaeb12d66eefc0cff7686|

Base cf6d0fee70ebceabfa63267a28fc03ea8d9cbf3c.
Payload41f58966198f2e2875296de620e4eea6c43514e2066e3ce4bbf12026c0921587.
Applied inventory4aa72786eeb5021e012e97b1d4ad12fabb7336c1d43721d8b477f5736f159025.

Run40249378336 applied those exact files on LAPTOP-NPSGA016 at00:27:10Z,
then stopped BEFORE running tests because its administrative wrapper asked
for a7200s lease wait although the canonical lease allows at most1200s.
That failed result is preserved. The15,001-byte private evidence archive,
SHA2565348635034b5e42f4a49df43a994930f7eac14fd38f6057106bc2db154c696a8,
was received by9417611 at00:28:06Z. No application code ran on Timeweb.

[Retry40249497543](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/40249497543)
uses the unchanged four-file patch and the original canonical lease contract.
Its corrected administrative wrapper SHA256 is
cf690a0ba993dfe70882726f23266e4e93f6378a9bc396e63e256c7f6b7d3311.
It applied the same patch at00:28:59Z and waited for the original full run
to release the canonical host lease. The new Python regression first failed
against the original code in all eight compound-ID/qualification variants;
the actual original Java class also rejected the compound ID as expected.
The repaired sources were restored before verification.

All1066 host tests passed in48.413s with the same three platform skips,
including the actual Java guard program's65 cases. git diff --check passed.
The separate driver lint/assemble tasks passed in1m14s. Source inventory
and the existing signing key were checked unchanged. The host stage completed
at2026-10-26T00:38:29.828314Z.

New test-only driver:2,683,192 bytes, SHA256
7fb9ad4121c2a1e981cacc611522941122c9fe3178e2eeb3849683200f3c7705,
built at00:38:28Z from inventory4aa72786….
Exact Windows source receipts match all four backed-up file bytes.

All14 existing portfolio cases are now executing on measured16KB Android37.
The focused workflow deliberately fails after success because it cannot
claim the complete15-stage suite. Actual focused results are still pending.

Application preview40/debug40 remain the exact bytes from40239983022.
Only the test-only driver requires recompilation. After focused acceptance,
repeat the complete matrix on both page sizes using the exact verified driver.
Do not publish or merge while applicable gates are incomplete.

## CI follow-up

Read-only review found obsolete hosted-Linux backend/runtime jobs, an APK34
upgrade baseline, and old release notes. Preserve the exact-head Sonar and
other quality gates while moving actual tests to the owner's Windows/WSL
environment and updating the baseline to published38. No PR has been opened.
An untested backend WSL draft is not applied or part of the repository change;
the current Android failure takes priority.
