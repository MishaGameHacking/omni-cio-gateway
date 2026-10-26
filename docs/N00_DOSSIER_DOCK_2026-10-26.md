# N00 — the dossier action dock is outside the scrolling body

N00 remains open; N01–N11 are not implemented. Published APK38 is unchanged.
Candidate41 /0.13.3-preview has a successful full laptop build, but no
complete15-stage Android matrix or exact-head external quality result.

## Actual candidate41 result and evidence

[Focused40253475330 /attempt2](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/40253475330)
ran on LAPTOP-NPSGA016, omni-cio-ci-2, source6b6a359dfffdb61626c6766fc5952900761b7015,
inventory8d309ea0b418dcf125957d72806bde5dd6fa65db716d8024e02e2ca406cfbef9.
It measured16384-byte pages and passed baseline38 installation,38→41 upgrade,
candidate41 clean installation/launch and the debug fixture.
The original discovery/ready/font1 case passed all its checks, including
comparison, common period, payouts, archive, selected research and watch dossier.
The next dossier/ready/font1 case failed at its first action:
List target not reachable: instrument-context-actions.
Runtime01:19:02Z–01:23:03Z; this is1/14 cases passed, not full acceptance.

The27-file runtime archive is623225 bytes, SHA256
3b595f497b146099837248407135d3811ad457085f4f3bdf06f6c669dd012070.
Timeweb9417611 confirmed receipt at01:24:07Z under
/var/lib/analyst-ai-build/incoming/windows-development-40253475330-2/.
Collector/cleanup succeeded; the original failed result is preserved.

Read-only [evidence40254224584](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/40254224584)
retrieved the actual PNG/XML, earlier passing screenshots and runtime log.
The287182-byte archive SHA256
17063cc807bda1fdcb21391851945741210abb65f2a69955105ddcd7268a0c78
and all9 manifest entries were verified. The failure PNG was visually inspected.
Failure PNG46306 bytes SHA2564ebe113c2a15b039c2c0dec4b04601008332cea836879421a9fd034837ef19f9;
XML23037 bytes SHA256a01ec458cb19e8b9d94163652ad57177eaec6b481b8adaec5013f3a8e5f1209f.

The native tree records workspace-content at[0,319][320,552], while the
enabled, visible, clickable action is at[20,560][300,608].
Its dock is a sibling at[0,552][320,640], with no scrolling ancestor.
InstrumentDetailsScreen places InstrumentContextActions in Scaffold.bottomBar.
Thus the test's attempt to reveal that action inside workspace-content
necessarily clips it out. No production layout repair is warranted here.

## Minimal repair first applied and verified on Windows

[Run40255133373](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/40255133373)
applied two files in an isolated checkout on omni-cio-ci-3, starting from
958616b8b73d5a869aff632742c55bd155a7d82d at2026-10-26T01:38:08Z.
The sole traversal change uses tap_visible("Действия с бумагой").
This existing helper resolves the unique native action owner, checks visible
enabled ancestry and actual display/ancestor clipping, requires a48px tap area,
and waits for three fresh stable frames before the ordinary coordinate tap.
The following new-window, selected UID, risk isolation and source checks remain.

The existing regression fixture now puts the fixed action outside the list.
It exercises the real native label helper and modal transitions at both
conditional scales; these fixture extents are not claimed as measured Android pixels.
It asserts four source frames (one initial plus three stable tap frames),
no source-list scrolling, and the original ordered risk/event actions.

| Windows-applied source | SHA256 |
|---|---|
|.github/scripts/portfolio_research_probe.py|c4fb5c912f802f01bed8686304787fb9b97f66c911a021b7d3eb9a510c8c2f22|
|.github/scripts/tests/test_portfolio_research_traversal.py|767b26e33eda59180a3a0285ff05a949b7f602f88679969c849b110834a5f7ce|

New code inventory6b793696cf0fd5cf30cfe44a19c55453a6ead01be1526ea6eeb5a0a48ea05052.
Patch transport SHA256f2492e70d35fb326887910694e4716f6206e2f142f255896c1afdde32b092fc2;
Windows wrapper SHA2561a7534277b512a0416741ed2a65d5e9a5b264662faa89e12c05217a09ea70eb5.
The canonical lease and its1200s wait limit are unchanged.

The original probe was temporarily restored under that lease: the named
regression failed in both subtests with the exact unreachable-dock error
(Ran1 test; FAILED failures2). After restoring the reviewed patch, all1066
host tests passed in45.414s with the same three platform skips; diff check passed.
Source/APK identity checks passed. Host stage finished01:39:00Z.

The focused runtime now runs all14 original portfolio cases on measured16KB,
using exactly the preview41/debug41/driver bytes from
[build40252011635](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/40252011635).
No APK is rebuilt for this harness-only change.
Focused runtime results are pending; no full-matrix result is claimed.
The external diagnostic hook preserves the first actual failure PNG/XML and
deliberately does not report full-suite success even if all14 cases pass.

## Continue in order

1. Inspect all14 original portfolio cases at fonts100/200 and preserve actual failures.
2. After focused acceptance, run the original15-stage suite on both4096/16384
   measured profiles with baseline38→41 upgrade and candidate41 clean installation.
3. Move obsolete hosted application CI to the existing laptop/WSL and baseline34→38,
   preserving exact-head Sonar, private transport, signatures and all acceptance gates.
4. Close N00 only when its criteria are evidenced, then implement N01.
   No new publication, paid AI, real orders or physical-phone acceptance is implied.
