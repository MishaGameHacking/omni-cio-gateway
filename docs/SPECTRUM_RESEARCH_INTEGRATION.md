# Historical combined-source review: research, updates and Spectrum

## Current status — 2026-10-17

The source-merge record below is historical. Its branch heads, old release
baseline and unfinished-work list describe that integration, not the current
application. Current navigation is **«Капитал», «Портфель», «Действия», «Риски»,
«Профиль»**; the research panel is under **«Действия → Анализ»** and inside
instrument details. `MandatoryUpdateHost` is integrated, and subsequent APK
releases and Moscow delivery evidence are recorded in [PLAN_STATUS.md](PLAN_STATUS.md).

Use [WORKSPACE_UI.md](WORKSPACE_UI.md) for current screens,
[UPDATE_RUNTIME_UNIFICATION.md](UPDATE_RUNTIME_UNIFICATION.md) for the single
update runtime, [APK_INSTALLATION.md](APK_INSTALLATION.md) for Android 15/16
verification, and [RISK_REBALANCING.md](RISK_REBALANCING.md) for live research limits.
F09/F16/F17 remain unfinished; the historical merge does not prove a complete
planner, conversational backend or a physical-phone self-update.

## Historical source-merge record

This integration merges the current updater/research branch into Spectrum as a
real two-parent source merge. It does not publish or deploy the resulting APK.

## Preserved boundaries

- Keep the backend tree from updater head 50fa40279c3ffda10e9c83f23494d939698683b5,
  which already contains main 001f7c1aeebb19b4f590018d37337802c0b82f64.
- Retain Spectrum's separate offline risk_preview/release_contract modules and
  test_spectrum_core tests; they do not replace production research or updates.
- Bring the current research client, panel, evidence/mathematics, regressions
  and API registration into Spectrum. Research participates in the same version
  gate and the main Ideas list owns scrolling. The research section is present
  independently of the optional ideas response, including loading/error states.
- Preserve Spectrum's theme, education, portfolio/instrument UI, Telegram entry,
  screenshot preference and single shared updater. Keep both sets of debug
  checks, rather than resolving a conflict by choosing either fixture wholesale.
- Preserve main's source-only push behavior: all build/install checks remain,
  while publishing is a separate explicit main operation. The legacy Spectrum
  manifest/remote publication scripts are not invoked by this workflow. They
  remain guarded and are NOT a completed production publication path.

## Verification required

Run the full combined Backend CI, Android lint/build/install/profile checks and
Sonar against the new merge head, not either parent. Source regression checks
only establish wiring invariants; they do not prove pixel layout, real network
quality, signing-key availability, device installation or runtime correctness.
Verify the actual PortfolioResearchPanel on narrow screens and large fonts.

## Not completed by a source merge

The first-party update channel, retained APK, matching release text/size contract
and in-app download/PackageInstaller/new-process/authenticated-resume scenario
still need release verification. Do not activate legacy-client lockout or ship
an APK whose startup gate has no usable server policy. Existing 0.5.1 clients
need a one-time bootstrap installation. Real market evidence collectors and a
complete constrained personalized asset optimizer are separate unfinished work.
