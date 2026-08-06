# Omni-CIO V10 — Web Product Blueprint

**Status:** OWNER-APPROVED V10 WEB PRODUCT BLUEPRINT / IMPLEMENTATION AUTHORITY FOR BLOCK E  
**Date:** 2026-08-06  
**Program amendment:** `docs/master-plan/OMNI_CIO_V10_WEB_PRODUCT_BLUEPRINT_AMENDMENT.md`  
**Visual direction:** approved planning presentation/mockups; this Markdown remains the implementation authority even if visual assets are stored separately.  
**Machine-readable companion:** `docs/architecture/V10_WEB_PRODUCT_BLUEPRINT.json`

## 0. Purpose

This document answers, before frontend implementation begins, **what exact Web product Omni-CIO V10 must become**.

The Web cabinet is not a marketing page and not a mock terminal. It is the primary OWNER interface to the real V10 Core, portfolio state, Watchtower, Research, Guardian, Plans, Execution, Journal and System Health.

The frontend must never manufacture financial truth. It renders reviewed domain/API contracts and makes uncertainty, freshness, degraded dependencies and authority boundaries visible.

---

# 1. Product vision

The target experience is a professional investment operating console that can be understood in seconds and investigated deeply when needed.

The owner should be able to answer five questions from the product without opening GitHub, PowerShell or the current Custom GPT:

1. **What is my portfolio state now?**
2. **What materially changed?**
3. **Why does Omni-CIO think it matters?**
4. **What exact decision/plan is proposed and what evidence supports it?**
5. **Is the system healthy enough to trust the displayed state or perform the allowed action?**

Visual quality is important, but visual effects are subordinate to information integrity, speed, accessibility and action clarity.

---

# 2. Non-negotiable UI Reality Contract

A production-visible interactive element is permitted only when one of these is true:

- it is backed by a real reviewed capability and performs the documented action; or
- it is intentionally disabled and explicitly explains the missing prerequisite/authority.

Forbidden examples:

- button visually enabled but handler is empty;
- dashboard card fed by hard-coded/demo portfolio data;
- filter control that does not affect backend/client data;
- `Refresh` that only animates but does not create/observe refresh work;
- `Export` that downloads a placeholder file;
- AI chat that invents portfolio facts rather than retrieving canonical state;
- `Approve` that only changes local browser state;
- `Real` badge when real prerequisites/authority are not proven.

Mock/demo fixtures are allowed only in tests, Storybook/design-system development or explicit non-production preview environments and must be impossible to confuse with live OWNER state.

---

# 3. Capability-driven frontend architecture

The preferred direction is a source-controlled React + TypeScript + Vite application using the exact toolchain selected by WP2, with implementation technology finalized in the owning WP.

UI visibility and enablement must derive from a reviewed capability/authority model rather than scattered local flags.

Conceptual capability response:

```json
{
  "portfolio_read": "available",
  "watchtower": "healthy",
  "research": "degraded",
  "ai_copilot": "unavailable",
  "shadow_execution": "available",
  "real_execution": "disabled",
  "real_execution_reason": "OWNER gate not accepted"
}
```

The exact schema belongs to the implementing API contract, but the invariant is binding:

**frontend cannot infer authority merely from the existence of a route or button.**

Frontend/backend compatibility must be explicit. The UI must detect incompatible API/schema versions and fail into an understandable upgrade/degraded state rather than rendering partially broken pages.

---

# 4. Information architecture and route map

The final route names may be normalized by the implementation router, but the product information architecture is locked to these conceptual destinations:

```text
/login

/overview
/portfolio
/assets/:instrumentId
/analytics
/risk

/watchtower
/watchtower/:incidentId
/research
/research/:dossierId

/decisions
/decisions/:decisionId
/plans
/plans/:planId

/copilot

/execution
/execution/:executionId
/journal

/system
/settings
```

Telegram/Mini App deep links must open an exact safe route/object (incident, decision, plan) after server-side identity/session/freshness validation. A deep link never grants action authority by itself.

---

# 5. Global application shell

Every authenticated page uses one coherent shell.

## 5.1 Desktop

- persistent/collapsible left navigation;
- page title + context controls;
- global freshness/health indicator;
- notification/incident indicator;
- OWNER/session control;
- content region using the shared grid/spacing system;
- no page-specific duplicate navigation.

## 5.2 Mobile

From 360px:

- compact top bar;
- bottom navigation or reviewed equivalent for the highest-frequency destinations;
- secondary sections through a clear menu/drawer;
- safe-area support;
- no horizontal-scroll dependency for core tasks;
- dense desktop tables convert to cards/priority columns/details rather than unreadable mini-tables.

## 5.3 Global health/freshness

The shell must make the difference visible between:

- HEALTHY;
- DEGRADED;
- STALE DATA;
- BROKER OFFLINE;
- DB/CORE unavailable;
- AI unavailable;
- recovery/maintenance state.

The global badge is a summary, not a replacement for detailed System diagnostics.

---

# 6. Design system contract (WP16)

## 6.1 Visual direction

Professional fintech/investment-operating-console aesthetic:

- calm, high-density information layout;
- restrained motion;
- clear hierarchy;
- strong numeric typography;
- minimal decorative gradients/glass effects;
- no animation that obscures changing financial values;
- charts support analysis rather than decoration.

## 6.2 Themes

Light and Dark are equal supported themes. Theme choice must not change semantic meaning.

Semantic colors are reserved:

- healthy/success;
- informational/action;
- degraded/warning;
- critical/blocked;
- unknown/disabled;
- Shadow vs Real authority.

Do not use critical/red simply as branding decoration on neutral elements.

## 6.3 Required reusable components

At minimum:

- AppShell / navigation;
- KPI/metric card;
- freshness badge;
- health badge;
- severity badge;
- capability/authority badge;
- table + responsive table/card adapter;
- filter/sort/search controls;
- chart wrapper with empty/stale/error states;
- tabs;
- tooltip/popover;
- drawer;
- modal/dialog;
- confirmation/step-up dialog;
- toast/notification;
- skeleton;
- empty state;
- degraded/error panel;
- source/evidence link;
- timeline;
- plan hash/identity display;
- code/correlation-id copy component;
- AI fact-vs-interpretation block.

No downstream page may create a conflicting local status system merely for convenience.

---

# 7. Complete UI state model

Every data-bearing screen/component declares the states that apply to it. The baseline vocabulary is:

- `loading` — request/job not yet resolved;
- `ready` — current sufficient data;
- `empty` — successful response but no objects;
- `partial` — some required domains are missing/incomplete;
- `stale` — data exists but freshness policy is breached;
- `degraded` — dependency unavailable but safe partial product remains usable;
- `error` — request/process failed and no safe normal rendering is available;
- `offline` — network/broker/runtime connection unavailable;
- `forbidden` — authenticated identity lacks authority;
- `blocked` — safety/prerequisite prevents an otherwise known action;
- `owner_action_required` — user must provide/confirm something outside autonomous workflow;
- `recovering` — restart/reconciliation/restore is in progress.

A spinner that never resolves without context is not an accepted error state.

---

# 8. Financial display standard

The same value must never be formatted differently on different pages without a domain reason.

## 8.1 Money and quantity

- money/prices/quantities originate from Decimal/numeric domain values, never reconstructed from float UI math;
- currency always explicit where ambiguity exists;
- thousands/decimal formatting consistent by locale/product policy;
- negative values use sign plus semantic styling; color is never the only carrier of meaning;
- rounded display may exist, but detail/tooltip exposes sufficient precision when material;
- `0`, `unknown`, `not applicable` and `not available` are distinct states.

## 8.2 Time

- canonical persisted timestamps remain UTC;
- user display follows the approved presentation timezone policy (MSK under current V10 architecture);
- source time, published time, retrieved time and local receive time are not collapsed into one ambiguous timestamp;
- important data exposes `as_of` and freshness.

## 8.3 Source identity

A material portfolio/risk/decision value should be traceable to one of:

- broker snapshot/operation;
- deterministic Core calculation;
- evidence/Research source;
- plan/execution state;
- explicit AI interpretation.

AI-generated interpretation must never be styled as canonical broker fact.

---

# 9. Screen specification — Login and first run

## 9.1 Login

Purpose: establish an OWNER session without exposing portfolio state before authentication.

Required states:

- normal login;
- invalid credentials/session;
- locked/rate-limited;
- expired session;
- server unavailable;
- step-up/recent authentication required for sensitive action.

No external Web access is accepted before WP22A security gate.

## 9.2 First-run/initialization

The product must not show a fake populated dashboard before real data exists.

Possible first-run states include:

- node initialized but broker read token not provisioned;
- broker configured but first snapshot pending;
- DB empty after clean installation;
- restore/reconciliation in progress;
- optional AI not configured;
- Telegram not configured.

The UI explains the next safe OWNER action and never fills missing financial state with demo values.

---

# 10. Screen specification — Overview / Dashboard

Goal: answer “what matters now?” in roughly one screen.

Priority content:

1. portfolio value + timestamp/freshness;
2. free cash/liquidity;
3. period/day change only where source/definition is valid;
4. overall risk + explain/drill-down;
5. asset allocation;
6. concentration/top positions;
7. active Watchtower incidents;
8. latest Guardian decision/status;
9. AI Copilot entry;
10. compact system health.

The dashboard is a summary. Every material card drills down to the owning page/object.

If data is partial/stale, the warning must remain visible next to the affected metric and at summary level when material.

---

# 11. Screen specification — Portfolio

Purpose: inspect exact current capital state.

Required capabilities:

- positions table/list;
- asset class / issuer / sector / currency allocation;
- top-position concentration;
- cash;
- filter/sort/search;
- current data timestamp and broker state;
- links to related incidents/research/decisions;
- clear distinction between broker truth and computed/market-derived values.

Desktop table columns are prioritized; mobile uses a condensed primary view with expandable details.

No average purchase price, P/L or return is presented as authoritative unless the relevant Core/data contract proves it can be calculated correctly.

---

# 12. Screen specification — Asset Detail

One instrument identity page must consolidate:

- canonical instrument identifiers;
- current holding/value/weight;
- market data with freshness;
- relevant risk metrics;
- concentration contribution;
- related Watchtower incidents;
- related Research Dossiers/evidence;
- related Decisions/Plans;
- relevant operations/history when available.

Instrument identity is never bound by a visually similar name/ticker alone.

---

# 13. Screen specification — Analytics and Risk

Purpose: expose deterministic portfolio analytics without requiring AI.

Required patterns:

- portfolio composition and concentration;
- risk decomposition;
- before/after comparison where a candidate plan exists;
- explainable calculations/drill-down;
- data timestamp/freshness;
- explicit unavailable/insufficient-data state.

A composite score must have an explanation path. “Risk 3.2/10” without decomposition/method/source is insufficient.

---

# 14. Screen specification — Watchtower / Incident

## 14.1 Incident list

- severity;
- subject/instrument/issuer;
- detected time;
- current lifecycle state;
- dedup/reopened state;
- risk impact summary;
- filters active/resolved/critical.

## 14.2 Incident detail

- exact timeline;
- evidence references;
- what changed;
- what is known/unknown;
- linked Research Dossier;
- linked Guardian Decision/Plan;
- system actions taken after detection;
- resolution/reopen history.

An alert is an auditable object, not transient notification text.

---

# 15. Screen specification — Research Dossier

Purpose: make evidence, provenance and uncertainty inspectable.

Required sections:

- canonical facts;
- source identity;
- published/retrieved timestamps;
- freshness;
- supporting evidence;
- contradictions;
- unknowns;
- confidence/coverage metadata where defined;
- event chronology;
- AI summary clearly separated from facts.

Malicious/untrusted source markup is sanitized. External content cannot execute in the app.

---

# 16. Screen specification — Guardian Decisions

Decision list shows materiality/status/main decision.

Decision detail must expose:

- `NO_ACTION | HOLD | REDUCE | EXIT | REALLOCATE | REVIEW_REQUIRED | INSUFFICIENT_EVIDENCE` as appropriate to the canonical contract;
- why the decision exists;
- evidence used;
- constraints/blockers;
- portfolio impact;
- risk before/after;
- proposed target outcome;
- link to exact plan when one exists;
- alternatives only as explanation, not as random menu asking OWNER to invent sizing.

AI wording cannot alter deterministic decision/plan numbers.

---

# 17. Screen specification — Plans

Plan detail is an immutable-object review surface.

Must show before any possible Real approval:

- plan ID/version/hash;
- creation time and expiry;
- exact legs/instruments/actions/lots;
- price/limit constraints;
- expected costs/commissions/slippage model where applicable;
- cash before/after;
- risk before/after;
- required prerequisites;
- current blocker list;
- evidence/Decision link;
- Shadow vs Real eligibility.

If any material plan field changes, prior approval UI/state is invalidated and a new plan identity is required.

---

# 18. Screen specification — AI Copilot

AI Copilot is a conversational analysis/orchestration surface over reviewed tools and data.

Required UX rules:

- show whether response is grounded in current portfolio/system evidence;
- citations/source objects when material;
- visually separate **facts**, **calculations**, **interpretation**, **uncertainty** and **possible actions**;
- show degraded/unavailable AI state without breaking deterministic pages;
- never claim an action was executed unless canonical execution evidence says so;
- no direct broker-write capability;
- conversation memory is context, not financial source of truth.

Example user question:

“Почему сегодня вырос риск?”

Expected response flow:

`retrieve current RiskSnapshot + contributing positions/incidents/evidence -> explain exact contributors -> link to drill-down`.

Not accepted: generic market commentary with invented portfolio facts.

---

# 19. Screen specification — Shadow Execution

Shadow mode must be unmistakable.

Required content:

- mode banner/status;
- plan evaluated;
- simulated legs/result;
- assumptions/market timestamp;
- what would have been submitted;
- no implication that broker writes occurred;
- comparison/evaluation history where implemented.

A Shadow screen may never use language that implies a real broker fill.

---

# 20. Screen specification — Real Execution

Real execution UI exists only after the corresponding V10 safety gates.

Before approval it shows the exact immutable plan and prerequisites.

Consequential controls require:

- current OWNER session;
- recent/step-up auth where specified;
- exact plan hash/version;
- expiry countdown/state;
- data/time/durable-state/audit readiness;
- no unresolved blocker;
- explicit confirmation wording.

After submission, UI follows the canonical state machine:

`PRE-FLIGHT -> SUBMIT -> RECONCILE -> VERIFY -> NEXT LEG -> FINAL RECONCILIATION`.

`submitted` is never displayed as `filled` without broker evidence.

Network ambiguity after possible submit must display `UNKNOWN / RECONCILING` and disable unsafe repeat submit.

---

# 21. Screen specification — Journal / Audit

The owner can reconstruct what the system did.

Required filters/details:

- incidents;
- decisions;
- plans;
- approvals;
- execution transitions;
- jobs;
- relevant system events;
- timestamps;
- correlation/object IDs;
- actor/authority class;
- safe error summary.

No raw secrets/private diagnostic payloads are exposed merely for convenience.

---

# 22. Screen specification — System / Admin

This page must make ordinary operation possible without command line.

Required domains:

- Core/API health;
- installed release/Git SHA/build timestamp;
- DB/migration state;
- last successful backup + restore-readiness summary;
- broker connection/freshness;
- Watchtower;
- Research;
- AI provider;
- Telegram;
- job queue/failed jobs;
- CPU/RAM/GPU/VRAM/temperature/free disk where available;
- time/NTP health;
- recent sanitized errors;
- kill-switch/readiness state where safe to expose.

The System page is diagnostic, not a secret/configuration dump.

---

# 23. Settings and security

Settings are grouped by responsibility, not as one unstructured page.

Potential categories:

- profile/presentation;
- theme/accessibility;
- notification policy;
- safe portfolio/analysis preferences owned by the corresponding V10 contract;
- session/security;
- integrations status;
- data/retention where owner-controlled;
- advanced/system settings behind appropriate confirmation.

Secret values are never displayed in full. Provisioning/rotation flows obey the local secret-store authority.

---

# 24. Interaction Contract

Every consequential interactive control must document:

1. visibility condition;
2. enablement condition;
3. required authority/capability;
4. exact request/job created;
5. pending/loading representation;
6. success evidence;
7. partial/degraded outcome;
8. error/retry policy;
9. idempotency/double-action policy;
10. audit event;
11. mobile/keyboard behavior.

## Example: Refresh portfolio

`click -> create/trigger reviewed refresh job -> button/job state -> refresh/reconciliation -> new snapshot or explicit partial/error -> UI invalidates/reloads affected queries -> audit/correlation id available`.

The control cannot merely refresh local React state and call that a broker refresh.

## Example: Real plan approval

Double click, network retry, stale page or repeated browser event cannot create a second execution identity. Client-side disabling is UX only; server-side idempotency/authority remains mandatory.

Dangerous operations do not use optimistic UI that claims success before durable/server/broker evidence.

---

# 25. Notifications

Use notification levels consistently:

- critical/action-required;
- important/warning;
- informational;
- silent/background.

In-app toasts are transient confirmations, not the only durable incident/audit record.

Telegram alert and Web incident must reference the same canonical object identity.

---

# 26. Search, filtering, sorting and large data

Tables/lists with non-trivial size must support predictable filtering/sorting and preserve query state where useful.

Rules:

- filters have visible active state and reset;
- result count/empty state is explicit;
- server/client responsibility is defined per dataset;
- large lists use pagination/virtualization where measurement shows need;
- URL/query state may encode safe navigation/filter context but never secrets or authorization tokens.

---

# 27. Performance budget

Performance is a release property, not final polish.

Baseline acceptance direction:

- meet or beat current Core Web Vitals good thresholds in the intended production/browser environment where measurement is meaningful: LCP <= 2.5s, INP <= 200ms, CLS <= 0.1 at the 75th percentile;
- local/private OWNER deployment should target faster warm navigation where realistic;
- shell remains usable when optional AI/Research dependencies are slow;
- heavy charts/modules use code splitting/lazy loading when useful;
- no full-page rerender caused by every background tick when localized updates suffice;
- large tables avoid rendering thousands of hidden rows;
- network polling/streaming is bounded and backoff-aware.

Exact measured budgets may be tightened by WP16/WP17 using the real Lenovo/network/browser profile, but they may not be removed without review.

---

# 28. Responsive and accessibility contract

Required layout checkpoints:

- 360px mobile;
- ~390-430px common mobile;
- 768px tablet/small viewport;
- 1024px;
- 1440px desktop;
- larger desktop without uncontrolled line lengths/stretching.

Accessibility baseline:

- keyboard navigation for core desktop tasks;
- visible focus state;
- accessible labels/names;
- semantic headings/landmarks;
- status not conveyed by color alone;
- target sizes consistent with WCAG 2.2 expectations;
- reduced-motion support;
- readable contrast in Light and Dark;
- accessible authentication; no unnecessary cognitive test requirement;
- charts have textual/table alternatives for material values.

---

# 29. Security and privacy UI contract

The Web surface follows WP22A and V10 security boundaries.

Required principles:

- authenticated OWNER session before private data;
- CSRF/origin/host/CORS/session protections as applicable;
- session expiry/revocation visible and safe;
- no secret values in client bundles, HTML, local-storage shortcuts or URLs;
- no private payloads in frontend telemetry by default;
- external source HTML sanitized;
- dangerous approval endpoint never trusts route/deep-link/client state alone;
- browser dev tools should not reveal hidden server secrets merely because the UI uses them;
- masked account identity in ordinary UI/logging.

---

# 30. Frontend observability

The owner needs useful failures; developers need correlation without private-data leakage.

Frontend/API errors should support:

- safe error class/message;
- correlation/request ID;
- component/route context;
- retry eligibility;
- sanitized visibility in System UI;
- no raw Authorization headers, tokens, full account IDs or portfolio dumps in telemetry.

An error boundary may keep the shell alive when one page/component fails.

---

# 31. Browser/device acceptance matrix

At implementation time, CI/E2E must cover the browser engines needed for a reliable OWNER product.

Baseline target:

- Chromium family (Chrome/Edge current supported stable);
- Firefox current supported stable for Web compatibility checks;
- WebKit/Safari behavior through Playwright where applicable;
- mobile viewport/touch flows, especially Android/Chromium and iOS/WebKit-equivalent test coverage when available.

The exact support policy is versioned; “works on my browser” is not acceptance evidence.

---

# 32. Test strategy for Web

## 32.1 Component/unit

- formatting;
- state transitions;
- permission/capability rendering;
- deterministic data-to-view mapping;
- key interaction reducers/hooks.

## 32.2 Contract

- generated/validated API schemas;
- incompatible version behavior;
- exact financial DTO semantics;
- no hidden authority inference.

## 32.3 E2E critical journeys

At minimum, when the owning capabilities exist:

1. login -> overview;
2. overview -> portfolio -> asset detail;
3. incident -> Research Dossier -> Guardian Decision;
4. AI question -> evidence-backed answer -> drill-down;
5. Shadow plan -> inspect -> no broker write;
6. Real plan -> approval prerequisites -> execute/reconcile states (only after Real gates, using safe test/fake environment);
7. broker offline -> stale/degraded UI;
8. AI unavailable -> Core/portfolio remains usable;
9. expired session/forbidden action;
10. mobile critical navigation.

## 32.4 Visual regression

After the real design system stabilizes, accepted screenshots become repository baselines for key combinations such as:

- Overview Light 1440;
- Overview Dark 1440;
- Portfolio desktop;
- Portfolio mobile 390;
- Incident critical detail;
- Research contradictions;
- Guardian Decision;
- AI grounded response;
- System degraded;
- Shadow plan;
- Real approval state when authorized.

Visual-diff tests must run in a controlled consistent rendering environment. Baseline updates require intentional review, not automatic overwrite.

---

# 33. UX language contract

The product uses consistent terminology. The following concepts are not casually renamed per page:

- Portfolio / Портфель;
- Asset / Актив;
- Incident / Инцидент;
- Evidence / Доказательство;
- Research Dossier / Досье исследования;
- Decision / Решение;
- Plan / План;
- Shadow / Симуляция без broker-write;
- Real / Реальное исполнение;
- Reconciliation / Сверка;
- Fresh / Stale / Partial / Degraded / Blocked;
- OWNER action required.

Errors should answer, where safe:

- what failed;
- what data is still trustworthy;
- what action is blocked;
- whether retry is safe;
- what the owner can do next.

---

# 34. Visual baseline

The visual companion is an approved **direction and screen architecture reference**, not pixel-level proof of the final implementation.

The intended product character is locked:

- professional investment dashboard;
- modern but restrained;
- information-dense without clutter;
- strong desktop experience;
- deliberate mobile experience;
- Light/Dark parity;
- clear Watchtower/Guardian/AI/Execution identity;
- visible health/freshness/safety state;
- no decorative control without functionality.

During WP16, the implementation design system may adjust colors, spacing, icon set, chart library or exact component geometry to satisfy accessibility, performance and actual data density. Such refinement must preserve this blueprint's information hierarchy and reality contract.

---

# 35. Web Definition of Done

Block E/Web is not accepted merely because all routes render.

Web acceptance requires, for the capabilities scheduled in V10 at that point:

- one coherent source-controlled Web application;
- all planned pages wired to reviewed real API/domain contracts;
- no production hard-coded/demo financial state;
- no enabled dead controls;
- complete critical state handling;
- mobile 360+ and desktop matrix green;
- Light/Dark usable;
- accessibility smoke/critical-path review green;
- performance budget measured and acceptable;
- security/session/authorization negative tests green;
- E2E critical journeys green;
- visual regression baselines reviewed;
- material numbers expose source/time/freshness semantics;
- AI facts vs interpretation separated;
- System page explains degraded dependencies;
- Shadow/Real language cannot misrepresent broker state;
- error/telemetry paths do not leak secrets/private payloads;
- owner can perform ordinary diagnosis and navigation without terminal/GitHub;
- exact implementation release is identified by V10 version + Git SHA.

The objective is not “a beautiful website”. The objective is **a beautiful, truthful, testable operating interface to the real Omni-CIO V10 system**.
