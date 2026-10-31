# Jarvis: selected-route diagnostics and isolated process acceptance

Date: 2026-10-31. Development candidate, not a live deployment.
Base: 47cbb9c74a6f1d6a0ec7e965a4defeeaa77015de.

## Closed previous verification

The exact base's full Linux backend run 41228665846 / job124618214623
completed successfully on LAPTOP-NPSGA016, runner omni-cio-ci-3,
Ubuntu-24.04 WSL / Python3.12.3. Observed log:
2838 passed, 1 warning, 1619 subtests passed in 332.13s.
All eight guest steps passed; changed_sources=[]; health/openapi passed.
488 Python sources compiled, 34 Sonar-result helper tests (NOT a new Sonar scan)
and 20 source-transport/evidence checks passed. Artifact13053699742,
jarvis-backend-41228665846-1, retained seven days.
The Starlette/AnyIO BlockingPortal deprecation remains visible.
This result applies to the base, not automatically to the new candidate.

## Actual status integration

`agent_routing_status.route_status` now supplies the existing `/analysis/status`
response. It uses the same flag/route validators and per-call environment builder
as the real portfolio worker. With agent routing enabled, status no longer checks
an unrelated global AI_TRANSPORT route. Local absence cannot trigger cloud work;
cloud approval/key/catalogue/pricing/region guards remain in effect.

Existing response fields remain available. Added `agent_routing` describes:
- agent vs legacy vs blocked control;
- the selected route for NEW portfolio tasks (running tasks keep their receipt);
- configuration-only readiness, explicitly not verified live inference;
- the budget scope. Hybrid status reports the effective 95/day and 2000/month
  maximum envelope or stricter configured amounts, not the old 2900 envelope.

Only bounded known reason codes are returned; arbitrary exception bodies and
provider settings are not returned. Status calls do not invoke a model, reserve
paid funds or submit trades. Existing endpoint/schema startup behavior is retained;
this is not a claim that every status request makes zero database writes.
A cloud reconciliation pause is reported separately from local socket readiness.

## Stronger acceptance than in-process mocks

`test_agent_runtime_process.py` runs on the existing Linux build WSL, not the
protected AnalystAI-Service runtime. It starts separate child processes for:
1. a SYNTHETIC model speaking real HTTP over a private Unix socket;
2. the actual queue/portfolio worker/analysis and local transport;
3. actual Uvicorn/FastAPI HTTP readers, then a fresh restarted HTTP process.

The inputs and model output are fixtures. Only broker collection and the test-only
socket location are redirected; worker, queue, receipt, guards, Unix HTTP parser,
model-hash check, report validation and database persistence execute real code.
HTTP readers exercise `/health`, session-authenticated `/analysis/status` and
`/analysis/feed`; absent/invalid sessions fail. Android attestation alone is
bypassed in the TEST CHILD, not in production. This is not device/Telegram testing.

Two scenarios: valid model identity and rejected hash. The valid response yields
a completed analysis/card; invalid hash yields a deterministic fallback, not a
model success. Stopping the fixture model and restarting HTTP retains the card
and last-run state while reporting the missing local socket. Exactly one model
request is expected; no paid reservation or hidden fallback may occur.

Each scenario owns a private mode0700 temporary directory and fresh SQLite DB.
Inherited listeners eliminate find-free-port races. Children receive an explicit
non-secret environment; socket audit guards reject external network connections.
A denied TEST-NET address check proves the guard is active without sending traffic.
Cleanup stops only child PIDs and removes only its own temporary socket/tree.
No existing service, WSL distribution, model weights, microphone or owner DB is
read or modified. No server or paid model is ordered.

## Acceptance boundary and continuation

Run the targeted Windows status/worker suite and the full existing Linux backend
suite at the exact final commit. Record actual outcomes in issue898; do not infer
passes from a prior SHA. Unix tests are intentionally Linux-only and must execute
(not skip) in the full Linux gate.

Even successful process probes do NOT establish real-model quality, GPU speed,
voice latency, production deployment, real-account migration or autonomous trading.
Remaining before live routing rollout: controlled actual-model acceptance in the
existing protected runtime, rollback/configuration verification and app checks.
Companion conversation without broker binding, durable personal memory and local
voice remain separate stages; no synthetic broker binding may be installed to
work around that real permission boundary.
