# Omni-CIO V10 — WP9A Execution Contract

Status: **IMPLEMENTATION CANDIDATE — acceptance requires focused PR, exact-head CI, factual Lenovo evidence and WP9A Exit Gate**  
Work package: **WP9A — Runtime patching, time, observability и controlled restart policy**  
Accepted base at start: `f15ecba8b89649a8ea01cc0fe045f7f1b2a8c27e`

## 1. WP identity and prerequisite

WP9A is authorized only because WP9 was accepted after OWNER bounded recovery/dependency rehearsals, a full Windows reboot, fresh Lenovo supervision audit PASS, squash merge `b43da57e74e6c5d4735c2b4e96b6839a52b4d1dc`, canonical status PR #260 and successful post-merge Regression Shield.

The protected baseline remains V9 `app:app` plus accepted WP5–WP9 node/security/supervision boundaries. `trading_methods=false` remains unchanged.

## 2. Purpose

Create one deterministic operations contract for 24/7 node maintenance and observability without silently changing product behavior or money authority.

WP9A owns policy/evidence for:

- Windows security-update/reboot maintenance windows;
- GitHub self-hosted runner update health;
- NVIDIA driver update policy;
- PostgreSQL minor/security update policy;
- Ollama runtime/model update policy **without installing or activating Ollama**;
- inherited WP9 bounded restart/backoff plus crash-loop/OWNER-alert semantics;
- Windows Time / NTP drift monitoring;
- CPU/RAM/GPU/VRAM/temperature/disk guardrails by reference to accepted WP5 thresholds;
- structured privacy-safe local logging, rotation/retention and crash-dump policy;
- staging/regression/eval/rollback requirements for behavior-changing updates.

## 3. Existing implementation to reuse

- `infrastructure/windows/wp5_node_thresholds.json` — **REUSE_AS_IS** for clock/storage/memory/thermal limits; no threshold relaxation is allowed to make WP9A pass.
- `infrastructure/windows/collect_owner_node_profile.ps1` — **WRAP_ADAPTER** for already-sanitized machine/time/resource facts when needed; do not fork a second hardware truth model.
- WP9 Windows Task Scheduler / `LOCAL SERVICE` supervision — **REUSE_AS_IS**; WP9A may observe/extend operations evidence but must not create a competing supervisor.
- GitHub hybrid CI / Regression Shield — **REUSE_AS_IS** with a path-aware WP9A compatibility/audit lane.
- V9 `app:app` and current Gateway — **REUSE_AS_IS** and untouched.

No financial-domain or broker-execution component is rewritten in WP9A; parity-ledger financial entries therefore remain unchanged.

## 4. Allowed changes

WP9A may add or change only:

- WP9A architecture/operations contracts and ADR notes;
- passive Windows operations collector/assessor;
- guarded OWNER-local operations policy provisioning if factual audit proves a required setting is absent;
- sanitized local operations status/log evidence under the accepted ProgramData Omni-CIO infrastructure boundary;
- path-aware hosted Windows compatibility and Lenovo authoritative audit workflows;
- deterministic tests/checkers for policy, privacy and failure semantics.

## 5. Explicit non-goals

WP9A must not:

- begin WP10 backup/off-device recovery;
- install or activate Ollama, Qwen, Cortex, V10 Core, Web, Telegram, Watchtower or AI worker runtime;
- change V9 production routes or `app:app`;
- set `trading_methods=true` or add broker-write methods;
- provision any real broker/Telegram/AI/API secret;
- alter PostgreSQL major version or perform a database migration;
- silently install NVIDIA/PostgreSQL/Ollama/model updates;
- grant CI/LocalService access to WP8 protected secret payloads;
- upload private logs/dumps/portfolio/account identifiers to GitHub.

## 6. Update policy

`docs/architecture/V10_WP9A_OPERATIONS_CONTRACT.json` is machine-readable authority.

Windows security updates remain OS-managed but V10 defines a reviewed local maintenance window, pre/post health gates and a post-reboot WP9 audit. WP9A must not directly edit Windows Update registry policy as an implementation shortcut; Microsoft-recommended Windows policy surfaces remain authoritative.

GitHub Runner retains its vendor-default automatic self-update behavior and is monitored for service/update health. Disabling runner auto-update is not part of WP9A.

NVIDIA updates are manual/reviewed. PostgreSQL stays on accepted major 18; minor/security candidates require compatibility/regression and rollback planning before application. Ollama/model updates are policy-only until the owning AI WP installs the runtime.

Any update capable of changing deterministic calculations, AI behavior, DB compatibility or broker execution behavior requires the exact gates declared in the machine-readable contract before acceptance.

## 7. Time and resource safety

WP9A imports WP5 time/resource limits exactly:

- clock warning at 500 ms absolute offset;
- sensitive operations blocked at 2,000 ms or unknown offset;
- Windows Time service must be running;
- disk warning below 20% or 50 GiB free; block below 10% or 20 GiB;
- memory warning at 85%; new heavy work blocked at 95%;
- GPU warning 80 °C / controlled-load abort above 87 °C;
- CPU-core warning 90 °C / controlled-load ceiling 95 °C;
- accepted throttling and manufacturer-lower-limit rules remain unchanged.

Time failure is a deterministic security gate for future short-lived confirmations, Telegram freshness and Real execution. It does not itself grant or enable any trading capability.

## 8. Observability and privacy

WP9A structured operational logs use an explicit allowlist and local retention. They may contain only operational class/state/reason/timing/version-band/resource-band/correlation evidence.

They must not contain secret/token/password/Authorization values, ciphertext, raw usernames/hostnames/IP/MAC addresses, full account IDs, private portfolio payloads, unrestricted process command lines or process dumps. Automatic private process dumps are disabled as V10 evidence; any later crash artifact collection requires an owning WP privacy contract.

CI may receive sanitized PASS/FAIL/profile evidence only.

## 9. Normal-path acceptance tests

- machine-readable contract parses and matches the accepted WP5/WP9 invariants;
- hosted Windows can execute the passive WP9A collector and assessor without mutation;
- absent Ollama is represented as `NOT_READY_ALLOWED`, not a failure or installation trigger;
- PostgreSQL major 18 and runner service/update health are classified deterministically;
- Windows Time and drift map to PASS/WARN/BLOCK using WP5 thresholds;
- disk/memory/resource states reuse WP5 values without relaxation;
- sanitized logging allowlist rejects forbidden/private fields;
- inherited WP9 bounded restart state remains valid;
- `app:app`, `trading_methods=false` and no-broker-write invariants remain green.

## 10. Negative/failure tests

WP9A must fail closed for:

- Windows Time stopped, drift unknown for sensitive-operation readiness, or absolute drift >2 s;
- blocked disk/memory guard state;
- disabled/unhealthy GitHub runner service or invalid update health evidence;
- PostgreSQL outside accepted major 18 or unknown version;
- pending reboot combined with attempted new heavy work;
- forbidden/private logging field;
- unreviewed behavior-changing update marked auto-approved;
- infinite restart policy / restart attempts above accepted WP9 bound;
- any detected broker/Real-money authority change.

A missing later product runtime such as Ollama remains an explicit allowed `NOT_READY` state rather than a fabricated failure or implicit install request.

## 11. CI routing

- Fast hosted checks: static contract/tests and privacy/money boundary assertions.
- Hosted Windows clean-room compatibility: **YES**, because Windows Time/service/update/task semantics are Windows-specific.
- Lenovo authoritative check: **YES**, factual update/time/resource/runner/PostgreSQL profile without private identifiers.
- GPU AI eval: **NO**; no AI/model runtime is installed or updated by WP9A.
- Release/recovery matrix: update-impact contract is checked, but actual backup/restore implementation remains WP10.

## 12. Rollback/recovery

WP9A default implementation is monitor/policy first. Any OWNER-local mutation must be marker-owned, idempotent and reversible without changing WP6–WP9 identities, secret ACLs or product tasks. Existing WP9 supervision remains the recovery boundary.

No database/model/driver update is applied merely to make the WP9A Exit Gate pass.

## 13. Binary Exit Gate

WP9A is COMPLETE only when all are true:

- focused WP9A PR is based on accepted status `main`;
- contract/checker/negative tests pass;
- hosted Windows compatibility passes;
- authoritative Lenovo operations audit produces privacy-safe PASS evidence;
- time, disk/memory/resource, Windows Update, runner-update, PostgreSQL and logging policy states satisfy the contract;
- inherited WP9 supervision/reboot evidence remains valid;
- later product slots remain sealed/inactive;
- no real secret/private payload enters GitHub evidence;
- `app:app`, `trading_methods=false` and Real-money authority are unchanged;
- exact-head required gates and review-thread resolution pass;
- squash merge lands on `main`;
- post-merge Regression Shield passes.

Only then may WP10 begin.
