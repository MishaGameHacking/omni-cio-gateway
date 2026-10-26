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

## Android result and next nested report-tab failure

Run40257272188 completed02:05:51Z–02:10:15Z on measured16384-byte pages.
The original discovery case passed again. Dossier passed contextual navigation,
both rating-source opening/closing transitions, exact publication dates and URLs,
and the existing conflicting-period/currency assertions.
It then failed at List target not reachable: Опубликованы in _reports.
This is not completion of all14 portfolio cases.

The33-file archive is786410 bytes, SHA256
647588b9f9f7c65dda0770daf02694395195f3514dc92a1cdf87e92540580b3d.
Timeweb9417611 confirmed receipt at02:11:10Z under
/var/lib/analyst-ai-build/incoming/windows-development-40257272188-1/.
Collector and cleanup succeeded; failed runtime status is preserved.

[Read-only evidence40258014046](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/40258014046)
returned297289 bytes SHA256c219bab35e45f51607471def50f4b19bac4fd53dd167bf78c5c0ede7a8f12691.
The archive and all9 manifest entries were verified; its failure PNG was
visually inspected. PNG52640 bytes SHA25645a4a04eb154a18ff3fe7086f4e319feb8f57bf17aabf09048a6110ad5357859;
XML24002 bytes SHA2569de6134681e820df7676e0c8a46bea3f6de00454df3e92c9db8e54a0ede5fafd.

The tree shows workspace-content at[0,319][320,552] and dossier-tabs
at[38,519][282,552]: only33px of the rail is visible vertically.
Опубликованы is inside that clipped rail; ten horizontal gestures cannot
restore its vertical tap area. Returning to Календарь отчётности reveals
the heading, not necessarily the entire nested rail below it.

## Parent visibility before horizontal report navigation

The two-file repair first reveals dossier-tabs inside workspace-content
with for_capture=True and minimum_size=(48,48), then performs the original
horizontal label action with its existing three-frame native stability check.
Before Объявлены it moves toward the start from the already revealed month
label; before Опубликованы it moves toward the end from the calendar heading.
No tap threshold, label, source-data assertion, driver or APK changes.

The regression uses the real ProfileProbe reveal and tap methods with
conditional nested clipping at two scales, starting both with an already
visible rail and a rail clipped above the viewport. Returning to the
calendar clips it below the viewport. Four variants prove the parent list
must move in the appropriate direction before horizontal actions.
Unrelated report content is fixture scaffolding, not Android acceptance.

[First attempt40258503020](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/40258503020)
failed before any Android work: the new test fixture initially omitted its
ProfileProbe inheritance, producing AttributeError instead of the required
original traversal failures. The red gate rejected it.
Its5-file archive14324 bytes SHA256
a1347f1175b94f9df5ed5931286aee11ac72ec05978d97ae028ac6c9c6056c5e
was received by9417611 at02:21:07Z; cleanup succeeded. This is not a patch PASS.

[Corrected40258706962](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/40258706962)
applied the two files at02:22:10Z on LAPTOP-NPSGA016 /omni-cio-ci from
base46f36b824fc008fce6115423a5e57c8ddc095621.
The fixture inherits the genuine helper, preserving its native lookup logic.
The original research probe then failed all4 subtests with unreachable
Объявлены/Опубликованы (Ran1 test in8.448s, failures4).
After restoring the reviewed probe, all1071 host tests passed49.643s with
the same3 platform skips, plus diff check; host finished02:23:15Z.
Source and APK identity checks passed.

| Windows-applied source | SHA256 |
|---|---|
|.github/scripts/portfolio_research_probe.py|7b364a9a895129aecb67c1c13999750159fe8a558b50274efba4cfb765785689|
|.github/scripts/tests/test_portfolio_research_traversal.py|8700a52ca6c12ddfbba2a97a99743be849af3ecbe903c9c25ef5a8b8b7129d70|

Current code inventory72d26c91967cc92c84c608830a04b011aea7b65cdacae0736dd0a0ba170b9382.
Patch SHA25601edc5058f0c8f6f6235cde97502faa0290fe696e853f74d7802b8c43aeb5715;
Windows wrapper SHA2560f591779f97fb2ea541548387094af546ddaa4b435679f35f051b1cdaf5c788e.
The canonical lease and1200s wait limit remain unchanged.

## Report tabs passed on Android; event traversal remained too short

Run40258706962 completed its measured16KB runtime at02:27:51Z.
The original discovery case passed. Dossier then passed both historical rating
sources, metric conflicts, scheduled versus published reports, exact report and
primary-news source URLs, publication roles, independent news identity, and
fact → issuer → the exact holding on account B.

It failed at the final event action:
List target not reachable: dossier-impact-event:synthetic-reviewed-event.
The38-file archive1061139 bytes SHA256
5d86b5252de8635d7ae2182e39340d9e97fac40a74d5f2c9dd6b10091ab25e3e
was received by9417611 at02:29:11Z under
/var/lib/analyst-ai-build/incoming/windows-development-40258706962-1/.
Collector and cleanup succeeded; failed runtime status is preserved.

[Read-only evidence40259436186](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/40259436186)
returned490412 bytes SHA25612322913c1c5d9c94d413b63686e26f1b60e0e68ad3acbd5edcf03af1b4859c9.
All13 manifest entries were verified. The failure PNG and the four scheduled
report, published report, primary source and selected-holding PNGs were viewed.
Failure PNG47722 bytes SHA256139cf376f12070443ea54ab3f04c9ed43f64a31edfca4fb3cf425ce136f61f8f;
XML24033 bytes SHA25633e97d31d4ca2fd1eb6b55aa066944d7a9847442bb392ae2a99e6040ed283937.
Selected-holding PNG44559 bytes SHA256145a526f6f587a26609f60a04332ee93b5eaa1f485ebca211f00429d38158599.

The selected position opens on account B. After returning to its Dossier tab,
ten forward workspace-content actions only reached the metric-conflict
section. The body remains[0,319][320,552], active window20, keyboard hidden,
five successful fixture requests, zero errors. No absent/disabled event
button or product defect is inferred from that short search.

## Bounded section traversal to the exact event

The repair follows the visible holdings, ratings, metrics, report calendar and
news headings with the existing per-section bound20 and12-second deadline.
It then uses the existing scoped record_text helper to reach the fact action
inside dossier-news-event:synthetic-reviewed-event, followed by the original
exact event resource tap with unchanged48px and three-frame native checks.
The assistant context, instrument UID, event ID, native input/keyboard checks,
and GET-only/no-paid-request assertions remain intact. No app or driver change.

A conditional long dossier contains an earlier unrelated event action and an
identical metric fact label. The regression uses actual reveal helpers,
PortfolioCase.record_text, settled resource lookup and native draft evidence
at two scales; unrelated assistant navigation is scaffolding. Fixture sleeps
are skipped only inside this synchronous unit test. Device results are separate.

[Windows40260472248](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/40260472248)
applied the two source files from0e08f16ac0595613797fcf8e76c3d3022aa1bbf1
at02:43:43Z on LAPTOP-NPSGA016 /omni-cio-ci-2.
The original research probe failed both long-dossier variants in0.039s
(Ran1 test, failures2) at the exact event action. The reviewed probe was
restored; all1072 host tests passed48.838s with the same3 platform skips.
Diff/source/APK identity checks passed; host finished02:44:39Z.

| Windows-applied source | SHA256 |
|---|---|
|.github/scripts/portfolio_research_probe.py|87b9787fed6faefd32ccd6ffb70a7442b339cd998e75427f07ca6d2cd5401ab8|
|.github/scripts/tests/test_portfolio_research_traversal.py|5eed6f76c00cc1cb4fadc4e0980e66796c83052106d700d24be6aa99103137eb|

Code inventory01b1bd5116e497bb43f35f2568d9c0e9186591e7059a736b224ef64194673085.
Patch SHA256c12cc2b08faf2ebd13923f9842a3e58a8b645cef3640b84bdba8b5334349312c;
Windows wrapper SHA2568a20acd224bc90642d8e98204eba114b1b0ec67de68c00316c8631fa6f518a5c.
The canonical lease and1200s wait limit remain unchanged.

## Continue in order

Run40260472248 is repeating all14 original portfolio cases at fonts100/200
on the measured16KB emulator with the exact preview41/debug41/driver.
Actual runtime results remain pending; no complete UI acceptance is claimed.
The older prepared full wrappers have obsolete harness inventories.

After all14 focused cases pass, regenerate the full original15-stage wrapper
from this exact backed source and run both4096/16384 profiles, including
baseline38→41 upgrade and clean installation. Then finish the laptop/WSL CI
migration and exact-head Sonar gates before closing N00 and moving to N01.
No release41, real orders, paid AI activation or physical-phone acceptance
is implied by these results.
