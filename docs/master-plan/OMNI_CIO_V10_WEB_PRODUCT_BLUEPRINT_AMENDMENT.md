# Omni-CIO V10 — Web Product Blueprint Program Amendment

**Status:** OWNER-APPROVED PROGRAM AMENDMENT / BINDING ELABORATION  
**Date:** 2026-08-06  
**Applies to:** V10 Block E (WP16-WP22A) and every later V10 capability rendered or operated through Web/Mobile/Mini App  
**Current program sequencing:** unchanged; this amendment does not authorize implementation ahead of the current V10 work package  
**Canonical detailed Web authority:** `docs/architecture/V10_WEB_PRODUCT_BLUEPRINT.md`  
**Productization/account authority:** `docs/master-plan/OMNI_CIO_V10_PRODUCTIZATION_AND_OWNER_ACCOUNT_AMENDMENT.md`  
**OWNER/T-Invest connection authority:** `docs/architecture/V10_OWNER_ACCOUNT_AND_TINVEST_CONNECTION_CONTRACT.md`  
**Machine-readable companion:** `docs/architecture/V10_WEB_PRODUCT_BLUEPRINT.json`  
**Owner-readable visual companion:** `docs/presentation/Omni-CIO_V10_Web_Blueprint_Presentation_RU.pdf`

## 1. Why this amendment exists

The V10 Master Plan already defines the Web Platform as a major product block, but the owner explicitly requires that Web must not be designed ad hoc when WP16 begins. The intended result is a real operating investment cabinet, not a visually modern shell with disconnected cards, dead controls, placeholder numbers or decorative AI.

This amendment therefore converts the agreed visual/product direction into a binding implementation contract before Web coding starts.

## 2. Program-level decision

V10 Web is defined as the primary professional OWNER interface to the real Omni-CIO system.

The Web implementation MUST be built from real Core/DB/API capabilities and MUST expose truthful system state. A UI element that appears functional but has no real capability behind it is forbidden in accepted production V10.

The required implementation chain is:

`system capability -> domain contract -> persistence/job state where required -> API DTO -> frontend component -> explicit UI state -> user interaction -> audit/evidence -> deterministic/E2E acceptance`.

A visual mockup is design evidence only. It is never capability evidence.

## 3. Binding product principles

1. **No fake functionality.** No dead buttons, decorative filters, fake refresh, fake export, fake AI, fake execution, static portfolio numbers or production demo data.
2. **Capability-aware UI.** If the backend/runtime capability is absent, disabled, degraded or unauthorized, the UI must reflect that state rather than pretending the feature is available.
3. **State-complete UI.** Material components must define loading, ready, empty, partial, stale, degraded, error/offline, forbidden and owner-action-required states where applicable.
4. **Source-visible finance.** Material numbers must expose source/provenance and `as_of`/freshness semantics; incomplete data cannot be styled as complete truth.
5. **One design system.** Pages may not invent local button/table/status conventions that conflict with WP16 tokens/components.
6. **Desktop and mobile are one product.** Mobile is designed deliberately from 360px, not produced by shrinking desktop tables.
7. **Light and dark are first-class.** Financial severity/status colors remain semantically stable in both themes.
8. **AI is explanatory/orchestration UI, not authority.** AI interpretation is visually separated from canonical facts and cannot bypass deterministic Risk/Plan/Execution contracts.
9. **Dangerous actions are explicit.** Real-money approval requires exact plan identity, current prerequisites, recent OWNER authentication and a clear irreversible-action boundary.
10. **Failures are a product state.** Broker offline, AI unavailable, stale data, partial sync, failed backup and recovering services must remain understandable without opening a terminal.
11. **No silent double action.** Double tap, retry, stale page, duplicate submission and network ambiguity are handled idempotently/fail-closed for consequential actions.
12. **Visual quality is regression-tested.** Accepted key-screen screenshots become CI baselines after WP16/WP17 establish the real frontend.
13. **READ-first broker onboarding.** Portfolio-dependent UI is unavailable until a validated T-Invest READ connection exists; no demo truth substitutes for it.
14. **Optional execution authority.** TRADING connection is a separate optional capability and never required for normal analysis/monitoring.

## 4. Scope locked by this amendment

The detailed blueprint must cover at minimum:

- login/session, personal OWNER account and first-run state;
- Account/Connections with mandatory T-Invest READ and optional isolated TRADING credential status;
- application shell and global health/freshness;
- Dashboard/Overview;
- Portfolio and Assets;
- Asset Detail;
- Analytics/Risk;
- Watchtower/Incident lifecycle;
- Research Dossier and evidence/provenance;
- Guardian Decisions;
- Plans and immutable plan review;
- AI Copilot;
- Shadow execution;
- Real execution/approval/reconciliation status;
- Journal/Audit;
- System/Admin diagnostics;
- Settings/Security;
- Telegram -> Web/Mini App deep-link behavior;
- responsive/mobile layouts;
- all critical degraded/error/empty/stale states.

## 5. Required pre-WP16 design lock

Before WP16 implementation is considered ready to start product UI work, the following must be treated as the approved Web design baseline:

- complete route/information architecture;
- screen catalog and screen purpose;
- design tokens and semantic severity model;
- component catalog;
- UI <-> API/capability binding matrix;
- financial display standard;
- interaction contracts for consequential controls;
- state matrix;
- accessibility/responsive matrix;
- performance budget;
- security/session requirements;
- E2E critical journeys;
- visual-regression baseline policy;
- Web Definition of Done.

Implementation may refine spacing, typography or chart implementation when required by real data/accessibility/performance, but it may not silently remove the product contract or replace real capability with decorative UI.

## 6. Relationship to the locked V10 Master Plan

This amendment **does not change V10 sequencing, block weights, broker authority, AI authority or Real execution safety**. It adds concrete acceptance requirements to the already approved Web scope and later Web-facing capabilities.

The existing synchronized `OMNI_CIO_V10_MASTER_PLAN.md` / `Omni-CIO_V10_Master_Plan_RU.pdf` pair remains intact. This file is an owner-approved program amendment under the amendment mechanism already defined by `AGENTS.md`, `OMNI_CIO_V10_PROGRAM_LOCK.md` and the ADR process.

At the next intentional canonical Master Plan synchronization, this amendment may be folded into the paired Master Plan artifacts without changing its meaning. Until then, it remains the binding elaboration for V10 Web implementation where it does not conflict with higher program authority.

## 7. No implementation authorization

This amendment is planning/governance work only. It does not authorize creating `apps/` early, starting WP16 before predecessor Exit Gates, changing the current V9 runtime, exposing external ingress, enabling public/multi-user production, or expanding broker-write authority.

