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

The first isolation correction widened the auto-derived CI port space without explicitly checking portable OS ephemeral-port defaults. Independent review then identified that the initial `18000..43999` range overlapped Linux's default ephemeral range and could therefore recreate a lower-probability collision on a portable verifier.

## Blast radius searched

The review covered:

- `apps/web/scripts/run-e2e.mjs`;
- `apps/web/playwright.config.ts`;
- `apps/web/scripts/e2e-preview-endpoint.mjs`;
- the Web npm test/e2e scripts and endpoint-isolation regression tests;
- WP17 and WP20 browser gates that invoke the common harness;
- parallel self-hosted runner topology on one host;
- local developer behavior that expects the canonical `4173` preview fallback;
- Linux default `ip_local_port_range` (`32768..60999`) and modern Windows default dynamic client range (`49152..65535`).

No product-runtime, Cloudflare provider, tenant, broker or V9 runtime behavior is changed by this correction.

## Why preflight missed it

The browser harness had previously been exercised in effectively single-runner conditions, where the fixed port was deterministic and harmless. The later CI-fleet expansion increased runner concurrency without a corresponding shared-host resource audit for localhost ports.

Workspace, temp directory and virtual-environment isolation were reviewed, but host-global sockets were not included in the concurrency inventory. The first correction also validated only uniqueness/bounds, not whether the automatic range stayed outside common OS ephemeral ranges.

## Corrective change

- preserve `4173` as the local fallback when no GitHub run identity exists;
- derive a bounded deterministic preview port from the GitHub run/job/attempt/runner identity for CI;
- constrain automatically derived CI ports to `18000..31999`, below the default Linux ephemeral start (`32768`) and therefore also below the modern Windows default dynamic start (`49152`);
- allow an explicit validated `OMNI_WEB_PREVIEW_PORT` override for controlled caller-owned use;
- keep Vite `--strictPort` so any remaining host-specific collision fails closed instead of silently drifting to an unknown endpoint;
- pass the exact selected preview URL into Playwright through `OMNI_WEB_PREVIEW_URL`;
- add deterministic regression tests for local fallback, validation, per-job isolation, portable automatic bounds and harness propagation.

## Permanent regression / guard

The Web unit suite verifies that concurrent representative GitHub browser jobs resolve to different deterministic ports, every automatically derived port is in `18000..31999` and below Linux's default ephemeral start, malformed GitHub identity fails closed, the E2E launcher no longer hardcodes `--port 4173`, and Playwright consumes the propagated preview URL.

An explicit override remains possible because host networking can be intentionally customized; the caller owns that override and `--strictPort` still prevents silent endpoint substitution.

## Future prevention rule

When multiple self-hosted runner instances can execute on one physical host, treat localhost ports, system services, shared caches and other host-global resources as explicit concurrency boundaries. Workspace isolation alone is not evidence of job isolation.

For browser/server test harnesses, either allocate a per-job endpoint deterministically outside known default ephemeral ranges or introduce an accepted serialization boundary. If the host customizes its dynamic-port range, revalidate the allocator or use a reviewed explicit override. Never assume a fixed localhost port or a broad high-port range is private to one runner.

## Dependency/tooling knowledge change

Official platform documentation reviewed on 2026-08-29 records Linux's default local ephemeral range as `32768..60999` and modern Windows' default dynamic client range as `49152..65535`. These defaults can be customized, so Vite `--strictPort` remains the final fail-closed collision guard.

Playwright base URL is runtime-configurable, so endpoint isolation does not require changing product routing or weakening browser assertions.
