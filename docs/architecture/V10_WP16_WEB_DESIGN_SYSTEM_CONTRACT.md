# Omni-CIO V10 WP16 — Web Design System Contract

Status: **WP16 IMPLEMENTATION CONTRACT**  
Block: **E — Omni-CIO Web Platform**

## Purpose

Create the single reusable visual/component foundation for the one source-controlled Omni-CIO Web App at `apps/web/`. WP16 owns no financial business logic and does not implement the WP17 application shell.

## Toolchain

The product Web App reuses the accepted WP2 baseline: Node 24.18.0, npm 11.16.0, React/React DOM 19.2.8, Vite 8.1.5 and TypeScript 7.0.2. Direct versions remain exact and package-lock v3 is authoritative. Playwright Test is an exact-pinned WP16 test-only dependency for browser accessibility/responsive/visual evidence.

## Design-system requirements

- one token layer for typography, spacing, surfaces, borders, focus, semantic operational states and risk severity;
- light/dark tokens without encoding financial warning/error only as decoration;
- reusable cards, tables, chart frame, dialog, drawer, buttons, badges, form field, toast, skeleton and empty/error/warning states;
- mobile-first 360px baseline plus explicit 768px and 1440px acceptance matrix;
- keyboard focus visibility, accessible labels/status roles and reduced-motion handling;
- no raw HTML injection, browser credential storage or direct Real authority references;
- synthetic gallery data only; no broker token, account ID or private portfolio payload.

## CI / evidence

WP16 must prove exact-head:

1. npm lock reproducibility and approved registry/license policy;
2. TypeScript typecheck, source lint, unit tests and Vite production build;
3. Playwright browser smoke on the Lenovo node with accessibility/keyboard/reduced-motion checks;
4. screenshot evidence for 360/768/1440 and structural layout assertions;
5. current repository/security/Regression Shield remains GREEN;
6. no Web business/auth/broker provisioning or execution authority is introduced.

## Exit Gate

WP16 is complete only after the exact reviewed head proves the design system is the reusable source for later Web pages, the required responsive/accessibility/visual evidence is GREEN, zero blocking review threads remain, the PR is squash-merged and post-merge Regression Shield succeeds.

WP17 remains locked until that acceptance. Block D remains uncredited and WP18 real-data acceptance remains locked behind deferred WP15 live evidence.
