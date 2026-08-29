# FL-060 — Parallel browser verifiers must not share a fixed localhost preview port

Status: **ADDITIVE FAILURE-LEARNING ENTRY FOR PR #408; PRIMARY LEDGER REMAINS `V10_ENGINEERING_FAILURE_LEARNING_LEDGER.md`**  
Date: **2026-08-29**  
WP / PR / reference: **Cloudflare platform authority transition / PR #408 exact-head DRAFT verification**

## Symptom / failing gate

Two independent browser-oriented repository gates ran concurrently on separate self-hosted runner instances attached to the same physical host. Both used the Web E2E harness, which started Vite preview on fixed localhost port `4173` with `--strictPort` and configured Playwright to the same fixed base URL.

One gate failed immediately with `Port 4173 is already in use`. The neighboring gate initially reached the shared endpoint and later observed unstable browser behavior followed by `ERR_CONNECTION_REFUSED` when the competing preview lifecycle ended.

## Root cause

The Web browser harness treated `127.0.0.1:4173` as job-local state, but TCP ports are host-global. Adding parallel self-hosted runner instances therefore created an unmodeled shared-resource collision even though each runner had an isolated workspace and virtual environment.

The cleanup logic was correct for a single job but could terminate the process that happened to own the shared endpoint, making the other job's evidence non-authoritative.

## Blast radius searched

The review covered:

- `apps/web/scripts/run-e2e.mjs`;
- `apps/web/playwright.config.ts`;
- the Web npm test/e2e scripts;
- WP17 and WP20 browser gates that invoke the common harness;
- parallel self-hosted runner topology on one host;
- local developer behavior that expects the canonical `4173` preview fallback.

No product-runtime, Cloudflare provider, tenant, broker or V9 runtime behavior is changed by this correction.

## Why preflight missed it

The browser harness had previously been exercised in effectively single-runner conditions, where the fixed port was deterministic and harmless. The later CI-fleet expansion increased runner concurrency without a corresponding shared-host resource audit for localhost ports.

Workspace, temp directory and virtual-environment isolation were reviewed, but host-global sockets were not included in the concurrency inventory.

## Corrective change

- preserve `4173` as the local fallback when no GitHub run identity exists;
- derive a bounded deterministic preview port from the GitHub run/job/attempt/runner identity for CI;
- allow an explicit validated `OMNI_WEB_PREVIEW_PORT` override for controlled use;
- keep Vite `--strictPort` so accidental collisions still fail closed instead of silently drifting to an unknown endpoint;
- pass the exact selected preview URL into Playwright through `OMNI_WEB_PREVIEW_URL`;
- add deterministic regression tests for local fallback, validation, per-job isolation and harness propagation.

## Permanent regression / guard

The Web unit suite now verifies that concurrent representative GitHub browser jobs resolve to different bounded ports, malformed GitHub identity fails closed, the E2E launcher no longer hardcodes `--port 4173`, and Playwright consumes the propagated preview URL.

## Future prevention rule

When multiple self-hosted runner instances can execute on one physical host, treat localhost ports, system services, shared caches and other host-global resources as explicit concurrency boundaries. Workspace isolation alone is not evidence of job isolation.

For browser/server test harnesses, either allocate a per-job endpoint deterministically or introduce an accepted serialization boundary; do not assume a fixed localhost port is private to one runner.

## Dependency/tooling knowledge change

Vite `--strictPort` is intentionally retained as fail-closed behavior. Playwright base URL is runtime-configurable, so endpoint isolation does not require changing product routing or weakening browser assertions.
