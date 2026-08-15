# Omni-CIO V10 — WP22A Local Web Recovery Diagnostic

Status: **WP22A RECOVERY SUPPORT / OWNER-ADMIN ONLY AFTER EXACT-HEAD CI GREEN**

## Purpose

This procedure exists only for the WP22A recovery case where the accepted WP15 local Web reconstruction fails with `WP15_LIVE_LOOPBACK_RUNTIME_NOT_READY` and Task Scheduler Operational history is unavailable. It does not enable Tailscale Serve, Funnel, public ingress, broker-write authority or Real trading.

The source-controlled helper is:

```text
infrastructure/windows/recover_wp22a_local_web_diagnostic.ps1
```

It must not be used as a substitute for the normal WP22A Exit Gate.

## Safety contract

The helper requires:

- Windows Administrator context;
- an exact clean reviewed Git head supplied through `-ExpectedImplementationSha`;
- the existing accepted WP15 provisioner;
- the existing protected `omni-cio-runtime` identity and PostgreSQL boundary.

The diagnostic performs one bounded recovery rehearsal. WP15 Apply deliberately enters through the accepted `start_wp15_live_web_acceptance.ps1` OWNER boundary rather than calling the low-level provisioner directly. That starter temporarily grants `SeBatchLogonRight` to the non-admin runtime identity only while the task is registered and started, then restores the original account-right state.

1. accepted WP15 `Cleanup` to normalize any partial local state;
2. accepted WP15 starter → `Apply` to reconstruct the loopback Web runtime;
3. if Apply succeeds, leave the accepted local Web runtime running and report PASS;
4. if Apply fails, extract only the accepted WP15 reason token plus, when available, the already-computed scheduled-task state and numeric `LastTaskResult` from `WP15_LIVE_LOOPBACK_RUNTIME_NOT_READY`;
5. after a failed Apply, execute accepted WP15 `Cleanup` again so the runtime identity/task/root are returned to the accepted fail-closed cleanup state.

The helper never prints captured child stdout/stderr. It must not emit command lines, Task Scheduler event messages, Windows identities/SIDs, tailnet hostnames, OWNER login, credentials, broker data or portfolio payloads.

## Result classification

The runtime launcher invokes `probe_wp15_live_session_runtime.py` before Uvicorn. Therefore numeric task results 71–76 are useful bounded classifications:

- `71` — session probe connection failure;
- `72` — session create failure;
- `73` — session resolve failure;
- `74` — session revoke failure;
- `75` — session cleanup failure;
- `76` — session probe bootstrap/import failure.

Known Task Scheduler status values are also classified without expanding them into potentially sensitive event messages. In particular, decimal `267009` corresponds to Task Scheduler `SCHED_S_TASK_RUNNING` (`0x00041301`), meaning the task remained running while the WP15 readiness endpoint still did not become available.

Any other result remains `WP15_RUNTIME_RESULT_OTHER` until engineering reviews it. The helper must not invent a more specific cause.

## Sanitized partial remote-state classification

The separate non-mutating `diagnose_wp22a_local_state.ps1` helper also classifies remote-cutover state without emitting the tailnet hostname, OWNER login, runner identity/SID, consent URL or secrets.

The specific combination below is authoritative evidence of a partial remote Apply boundary:

- remote task `RUNNING`;
- backend listener present and loopback-only;
- runner loopback firewall present;
- Tailscale Serve absent/not targeting the backend;
- Funnel/public ingress false.

It is reported as `deployment_state_class=WP22A_REMOTE_RUNTIME_SERVE_PENDING` and `apply_in_progress_or_blocked=true`. It is not an accepted remote runtime. The OWNER must not repeat Apply, run Verify/finalizer, enable Funnel or manually delete tasks/firewall/runtime state. Engineering first repairs or confirms the bounded Serve-consent path, obtains exact-head GREEN, and then authorizes replacement-head Cleanup.

## OWNER boundary

Do not ask the OWNER to run this diagnostic until the exact implementation containing the helper has passed focused WP22A checks and the authoritative self-hosted Windows gates. After execution, only its sanitized JSON output is acceptable as chat/GitHub diagnostic evidence.

A diagnostic FAIL is not WP22A acceptance. Engineering must fix the root cause, obtain a new exact-head GREEN cycle and only then resume normal WP22A recovery/apply/phone evidence.
