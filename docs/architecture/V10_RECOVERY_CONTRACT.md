# Omni-CIO V10 — Recovery Contract

Status: **WP0 architecture freeze**  
Protected runtime baseline: **Omni-CIO v9.0.0**  
Protected rollback evidence: **v8.6.1 real execution acceptance**

## 1. Purpose

V10 must be recoverable without chat history, the original ChatGPT account, a specific developer, a specific hosting provider or the original Lenovo hardware.

Recovery is part of correctness, not an afterthought.

## 2. Recovery sources of truth

### Engineering source

Private GitHub repository:

- accepted source code;
- architecture/ADRs;
- dependency locks;
- DB migrations;
- tests/CI policy;
- bootstrap/deployment/recovery automation;
- non-secret release manifests;
- AI policy/tool/eval definitions;
- documentation/runbooks.

### Private durable state

Local V10 database and approved encrypted backups:

- portfolio snapshots/state required for operation;
- evidence/research metadata;
- incidents/decisions/plans;
- execution/reconciliation state;
- Decision Journal/audit trail;
- job/system-health state where required.

### Secret state

Separately restored owner-controlled secrets:

- read-only broker credential;
- Real trading credential;
- Telegram bot token;
- encryption/recovery material;
- other approved external credentials.

Secret values are not recovered from GitHub.

## 3. Protected V9 fallback

Until V10 final owner acceptance, V9 remains a separate recovery path.

Current protected runtime facts remain:

- existing Custom GPT v9.0.0 owner-accepted;
- production Gateway `app:app` on Render;
- current read-only/Sandbox/Real separation;
- `REAL_TRADING_ENABLED=false` master Real rollback;
- protected v8.6.1 commit `baba0fb73e0483fc82b3f0bc7c2f15cbd71d804e`;
- canonical invariant: idempotent replay verified with no second submit.

A failed V10 experiment must not require weakening V9 to recover.

## 4. Recovery scenarios

### R1 — Single V10 service crash

Expected response:

- supervisor detects unhealthy service;
- bounded restart/backoff;
- dependent services remain fail-closed/degraded;
- owner receives health state when alerting is available;
- no Real submit occurs from a restart alone.

### R2 — Windows reboot / update

Expected response after Block C:

- DB starts;
- Core starts only after dependencies are ready;
- Web/Telegram/Watchtower/AI workers start in dependency order;
- system reports HEALTHY or explicit DEGRADED without manual terminal work;
- Real remains disabled unless all required readiness state is valid.

### R3 — Database corruption

Expected response:

- stop state-mutating/Real paths;
- identify last valid backup/hash;
- restore to controlled replacement/recovery DB;
- run integrity/migration/reconciliation checks;
- do not infer missing execution state;
- ambiguous broker state is reconciled before further execution.

### R4 — SSD/Lenovo loss

Expected response:

1. provision replacement approved Windows node;
2. clone accepted GitHub source;
3. run documented bootstrap;
4. restore encrypted backup;
5. restore secrets separately;
6. validate DB/migrations/integrity;
7. run Regression/health/recovery checks;
8. reconnect read-only broker first;
9. keep Real disabled until explicit recovery acceptance.

### R5 — GitHub working branch corruption

Expected response:

- discard/revert unaccepted branch;
- recover from accepted `main`/reviewed release;
- never deploy unreviewed workspace merely to preserve progress.

### R6 — AI provider/model failure

Expected response:

- AI becomes unavailable/degraded;
- deterministic Core/read-only monitoring continues where inputs permit;
- no replacement model is silently trusted without model/eval gate;
- no Real authority expansion occurs as fallback.

### R7 — Telegram failure/token compromise

Expected response:

- disable Telegram adapter;
- revoke/rotate token;
- Web/local Core remain operational;
- Telegram outage cannot authorize or block safe shutdown of Real contour.

### R8 — Broker API uncertainty

Expected response:

- reads show stale/degraded state explicitly;
- Real preflight fails closed when freshness/readiness unavailable;
- possible-submit ambiguity is reconciled, never auto-resubmitted.

## 5. Backup contract

Block C WP10 must define measurable:

- **RPO** — maximum tolerable loss of durable private state;
- **RTO** — maximum tolerable time to restore the Personal node.

Backup design must include:

- automated DB backup;
- encryption;
- integrity hash;
- retention/rotation;
- off-device copy;
- corrupt-backup detection;
- periodic automated/manual restore rehearsal;
- proof that raw secrets do not leak into unprotected backup.

Exact RPO/RTO values are intentionally selected only after WP5 hardware/storage audit.

## 6. Release rollback contract

Every V10 release capable of changing runtime behavior records:

- semantic version;
- Git SHA;
- dependency lock/build identity;
- DB migration version;
- AI model/prompt/schema identity when relevant;
- compatibility requirements;
- rollback instructions.

Rollback must distinguish:

1. code rollback;
2. DB/schema forward-recovery or reviewed reversal;
3. AI model/policy rollback;
4. external configuration rollback;
5. broker reconciliation state that must never be discarded.

## 7. Real-execution recovery rule

Execution recovery prioritizes **broker truth and idempotency state** over convenience.

Never recover by:

- deleting unknown submit state and trying again;
- treating local `submitted` as fill proof;
- restoring an old DB snapshot and resubmitting an old approved plan;
- reusing expired approval after plan/market drift.

After recovery, any unresolved possible submit remains blocked until broker reconciliation resolves it.

## 8. Clean-room portability acceptance

Before V10 can reach 100%, project must prove on a clean/replacement node:

`GitHub + documented bootstrap + authorized encrypted backup + separately restored secrets -> working V10 node`.

The test must verify at minimum:

- version/Git SHA identity;
- DB migration/integrity;
- read-only broker connection;
- Web/Core health;
- Watchtower/Job state as designed;
- AI disabled/enabled behavior as appropriate;
- Real remains disabled until its own recovery/readiness gate.

## 9. Recovery documentation rule

A recovery procedure is not accepted merely because it is written. Exit Gates later require executed recovery evidence.

No recovery procedure may depend on hidden account-only configuration that is not represented by repository-controlled schemas/runbooks plus separately documented runtime-secret provisioning.
