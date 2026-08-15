# Omni-CIO V10 — WP22B Cloud Personal Node Migration Checklist

Status: **PLANNING CHECKLIST — IMPLEMENT ONLY AFTER WP22A ACCEPTANCE**  
Parent authority: `OMNI_CIO_V10_CLOUD_PERSONAL_NODE_MIGRATION_AMENDMENT.md`

This checklist turns the cloud/phone-first amendment into bounded, reviewable evidence. It does not authorize out-of-sequence work and awards no V10 progress percentage.

## Gate 0 — Preconditions

- [ ] WP22A is accepted and merged at an exact commit.
- [ ] Current-program status records WP22A acceptance and authorizes WP22B.
- [ ] No WP23–WP26 implementation has started.
- [ ] The planning amendment and machine-readable contract are merged and synchronized.
- [ ] The Timeweb/Tailscale/Telegram/GitHub prices and terms are rechecked against official sources.
- [ ] A dated cart proves normal recurring cost at or below 1,400 RUB and the all-in monthly cap at or below 1,800 RUB.
- [ ] The implementation PR declares exact scope, rollback path and evidence directory.

Stop if any prerequisite is false.

## Gate 1 — OWNER account protection and purchase

- [ ] Timeweb account uses a unique credential and 2FA.
- [ ] Recovery codes are stored offline and are absent from GitHub/chat.
- [ ] Billing, security and incident notifications are enabled.
- [ ] Only the approved month-to-month/hourly baseline is ordered.
- [ ] No domain, managed DB, Kubernetes, GPU, CDN/WAF or annual prepayment is added.
- [ ] Tailscale OWNER account/device approval is protected and current plan eligibility is recorded.

Evidence stores redacted settings and totals only. It never stores credentials, recovery codes, full account identifiers or payment data.

## Gate 2 — Reproducible Linux foundation

- [ ] Ubuntu LTS image and patch level are recorded.
- [ ] Infrastructure/bootstrap files are deterministic, reviewed and secret-free.
- [ ] Neutral hostname contains no private/financial meaning.
- [ ] Provider and host firewalls are default-deny.
- [ ] No public HTTP/HTTPS/SSH/database port is reachable.
- [ ] Remote root login is disabled after bootstrap.
- [ ] Tailscale is approved; Serve exposes private HTTPS; Funnel is confirmed off.
- [ ] Optional provider Ping check permits ICMP only from revalidated monitor addresses.
- [ ] Time synchronization, unattended security updates policy and reboot behavior are tested.
- [ ] Production user/service identity is non-root `app`.

## Gate 3 — Application and database parity

- [ ] Accepted exact-head release artifact and manifest/digest are available.
- [ ] Production node pulls/verifies the artifact with a read-only deploy credential.
- [ ] Production node is not registered as a GitHub Actions runner.
- [ ] CI uses a separate ephemeral/on-demand Linux runner with no production secrets.
- [ ] Canonical ASGI target is `app:app`.
- [ ] Web/API, workers, scheduler and PostgreSQL have explicit startup ordering and bounded restart policy.
- [ ] PostgreSQL listens only on loopback/private-container networking.
- [ ] Application DB role cannot perform administrative operations.
- [ ] Windows-to-Linux path, locale, timezone, line-ending and filesystem case-sensitivity tests pass.
- [ ] Deterministic Core parity tests pass against accepted fixtures/oracles.
- [ ] `trading_methods=false` and `REAL_TRADING_ENABLED=false` are proven.
- [ ] Broker write/trade/withdrawal/transfer negative tests pass.

## Gate 4 — Secret boundary

- [ ] No Windows DPAPI blob is copied to Linux.
- [ ] Required secrets are re-provisioned by the OWNER through the protected private path.
- [ ] Secrets use root-owned/systemd credentials and are unreadable to unrelated users.
- [ ] Only broker READ authority is provisioned; no TRADE token exists on the WP22B node.
- [ ] Logs, process listings, health output, artifacts and backups reveal no secrets.
- [ ] Secret rotation/revocation and disaster re-provisioning steps are tested/redacted.

## Gate 5 — Backup and clean restore

- [ ] Private S3 bucket has no anonymous/public access.
- [ ] Backup objects are encrypted client-side before upload.
- [ ] Least-privilege S3 credential can access only the required bucket/prefix/actions.
- [ ] PostgreSQL logical backup runs at least every six hours.
- [ ] Daily application/config backup excludes secrets and reproducible binaries.
- [ ] Versioning/lifecycle/retention limits keep storage and cost bounded.
- [ ] Backup age and failure alerts work.
- [ ] A clean isolated node restores the newest backup.
- [ ] Restored state reconciles against deterministic fixtures and a fresh read-only broker import.
- [ ] Measured RPO is at most six hours and owner-assisted RTO is at most four hours.
- [ ] Same-provider snapshot/full backup is not the only recovery copy.

## Gate 6 — Failure and rollback drills

- [ ] Host reboot restores all required services in the correct order.
- [ ] Web/API crash triggers bounded recovery and notification.
- [ ] Worker/scheduler crash does not duplicate durable jobs.
- [ ] PostgreSQL restart/recovery preserves integrity.
- [ ] Disk-near-full and stale-backup conditions fail visibly.
- [ ] A failed release activation returns to the previous verified artifact.
- [ ] Lenovo cold rollback is executed with cloud writers/pollers stopped first.
- [ ] Recovery proves exactly one active scheduler/writer and, when applicable, one Telegram poller.

## Gate 7 — Phone and private-access acceptance

- [ ] OWNER phone reaches the private Web UI through Tailscale Serve HTTPS.
- [ ] Access fails from a device outside the tailnet.
- [ ] Ordinary private-browser login/recovery works without Telegram.
- [ ] Provider panel, billing alerts and incident notifications are usable from the phone.
- [ ] Routine status/restart/rollback decision flow does not require the Lenovo laptop.
- [ ] No public webhook or Funnel route exists.
- [ ] Telegram `/app` remains explicitly deferred to WP23–WP26.

## Gate 8 — Controlled cutover and soak

- [ ] Read-only Lenovo/cloud comparison produces no unexplained deterministic divergence.
- [ ] Mutable jobs are frozen before the final migration backup.
- [ ] Final backup is verified before activating cloud writers.
- [ ] Cloud has exactly one active scheduler/worker set.
- [ ] Lenovo scheduled tasks/services and any poller are disabled.
- [ ] Web/API, database, jobs, alerts and backups remain healthy for 72 continuous hours.
- [ ] Cost forecast remains within the approved cap.
- [ ] Lenovo cold rollback remains intact for at least 14 days after acceptance.

## Gate 9 — Acceptance and program handoff

- [ ] Exact implementation commit and all CI/evidence SHAs match.
- [ ] Security/negative/parity/restore/rollback evidence is reviewed.
- [ ] Operations runbook includes phone-first routine operation and emergency recovery.
- [ ] Actual provider resources and monthly forecast are recorded without secrets/private identifiers.
- [ ] OWNER explicitly accepts the cloud Personal Node as primary.
- [ ] Current-program status records WP22B acceptance with zero percentage credit.
- [ ] Only then is WP23 authorized.

## Required evidence summary

The WP22B implementation PR must provide machine-readable, secret-free evidence for:

- exact source/release/manifest digest;
- Linux image/runtime versions;
- firewall and public-ingress negative probes;
- Tailscale Serve/Funnel state;
- service identity and PostgreSQL role/network checks;
- safety-invariant and deterministic parity results;
- backup schedule, encrypted upload and clean restore timing;
- reboot/crash/release/database/Lenovo rollback drills;
- single-writer/scheduler/poller proof;
- 72-hour soak window and health summary;
- redacted cost totals and price-check date.

Evidence containing a secret, raw token, password, payment detail, private portfolio data or OWNER recovery material is invalid and must be revoked/removed through the repository incident process.

## Hard stop conditions

Stop WP22B and preserve the Lenovo rollback path if any of the following occurs:

- WP22A is not accepted;
- public application ingress is required unexpectedly;
- the cart exceeds 1,800 RUB/month;
- Linux parity changes canonical financial output without an approved contract change;
- a required secret must be placed in GitHub/chat/CI artifacts;
- backup restore, rollback, single-writer or safety-negative evidence fails;
- Tailscale Personal eligibility no longer matches the owner-only use;
- migration would require destructive deletion of the Lenovo recovery path.

Resolution requires a bounded correction PR or a new OWNER-approved amendment; it must not be bypassed by manual success claims.
