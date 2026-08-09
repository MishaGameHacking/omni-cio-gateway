# Omni-CIO V10 — WP9A Runtime Operations Runbook

## Purpose

WP9A defines how the accepted Lenovo node is patched and observed before 24/7 operation. It is an operations/safety package, not an application-runtime installation package.

## Fixed safety boundaries

- V9 `app:app` remains protected.
- `trading_methods=false` remains protected.
- WP6 identities, WP8 secret DACLs and WP9 `LOCAL SERVICE` supervision remain authoritative.
- No real broker, Telegram, AI or API secret is required for WP9A acceptance.
- No Core/Web/Telegram/Watchtower/Cortex/Ollama product runtime is activated here.
- Update availability is never broker-submit authority.

## Maintenance window

The reviewed V10 maintenance window is **03:00–05:00 machine-local time**. It is a V10 operations window, not permission to bypass Windows Update safeguards or force an unsafe reboot.

Before an update that can require restart:

1. confirm WP9 health is truthful and no required reconciliation/recovery operation is active;
2. confirm no V10 heavy job is beginning while a reboot is pending;
3. record only sanitized version/update class, never private payloads;
4. apply only an update allowed by the component policy;
5. reboot only in the reviewed maintenance window unless OWNER explicitly approves an emergency security maintenance event;
6. require automatic runner/WP9 return and fresh post-reboot health evidence.

WP9A itself does not directly modify Windows Update registry policy. Windows policy surfaces remain managed by Windows/OWNER; the collector audits V10-relevant facts.

## Component update rules

### Windows

Security/quality updates remain OS-managed. V10 requires a controlled reboot window and post-reboot WP9 health. Feature updates are reviewed changes, not routine automatic V10 maintenance.

### GitHub self-hosted runner

Keep GitHub's default automatic runner update behavior. Monitor service health and update diagnostics. Do not register the runner with `--disableupdate` without a reviewed amendment; a deliberately disabled updater creates its own version-staleness obligation.

### NVIDIA

Do not let Omni-CIO silently install a new display/compute driver. A candidate driver requires vendor provenance, rollback preparation and post-update WP5 thermal/telemetry compatibility evidence before being accepted as the V10 baseline.

### PostgreSQL

Accepted major version is 18 and accepted WP7/WP9A floor is 18.4. Monitor upstream minor/security releases. A minor update is reviewed and must preserve schema/runtime compatibility with rollback planning. Major-version migration is outside WP9A.

### Ollama/models

Policy only. An absent Ollama runtime is `NOT_READY_ALLOWED`. Do not install Ollama or model weights in WP9A. Once the owning AI WP exists, runtime/model updates require eval + rollback and may not silently replace an accepted model.

## Time guard

Reuse WP5 exactly:

- warning: absolute offset >500 ms;
- block sensitive-operation readiness: offset unknown or >2,000 ms;
- Windows Time must be running;
- application timestamps are UTC.

A blocked time state must prevent future short-lived approvals/freshness-sensitive/Real operations, but does not itself activate any execution path.

## Resource guard

Use `infrastructure/windows/wp5_node_thresholds.json` directly. WP9A is forbidden from copying and relaxing thresholds to obtain a PASS.

At minimum surface:

- system disk free-space band;
- memory utilization band;
- available NVIDIA temperature/VRAM telemetry;
- WP5 thermal limits and manufacturer-lower-limit precedence;
- whether a pending reboot should block new heavy work.

## Logging/privacy

WP9A operations evidence is local-first JSONL. The contract allowlist is authoritative. Logs are bounded to 10 MiB per file, seven files total and 30 days maximum local retention for this WP9A operations class.

`scripts/v10_wp9a_operations_log.py` is the deterministic journal writer. It accepts only the fixed operational field allowlist, rejects unknown/free-form private surfaces, rotates only `wp9a-operations.jsonl*` inside the caller-selected local log directory, fsyncs each append and links records with `previous_hash` / `event_hash` SHA-256 fields. The hash chain is tamper evidence, not a replacement for a future signed or append-only audit store.

Never emit to operations logs/CI:

- secret/token/password/Authorization values;
- WP8 ciphertext or credential hashes;
- full broker/account identifiers or portfolio payloads;
- raw Windows username/hostname/IP/MAC data;
- unrestricted process command lines;
- process dumps/private memory.

Crash dumps are not an automatic V10 evidence mechanism. A future owning WP must define a privacy-safe dump contract before private application dumps can be collected.

## Update-impact gate

Before accepting an update:

- deterministic calculation impact -> staging + Regression Shield + rollback;
- AI/model behavior impact -> staging + eval + rollback;
- PostgreSQL compatibility impact -> staging + regression + rollback;
- broker execution-path impact -> staging + regression + security + explicit OWNER review + rollback.

No update process may change `trading_methods=false` or bypass the later Real-execution gate.

## WP9A Exit Gate

PASS requires:

- static policy/negative tests green;
- hosted Windows compatibility green;
- authoritative sanitized Lenovo profile green;
- Windows Time/drift and WP5 resource guard green;
- runner service/update health green;
- Windows update/reboot state compatible with the maintenance policy;
- PostgreSQL major 18 state known and compatible;
- absent Ollama accepted as NOT_READY without installation;
- WP9 supervision/restart boundary still valid;
- bounded log allowlist/rotation/retention/hash-chain tests green;
- exact-head required CI green;
- squash merge and post-merge Regression Shield green.

Only then may WP10 begin.
