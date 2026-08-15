# Omni-CIO V10 — Cloud Personal Node / Phone-First Migration Amendment

Status: **OWNER-DIRECTED PLANNING AMENDMENT — DRAFT UNTIL MERGED**  
Owner direction date: **2026-08-15**  
Implementation position: **after accepted WP22A and before WP23**  
Progress effect: **zero additional weight; no percentage credit**

This amendment records the OWNER decision to remove the Lenovo laptop as a mandatory 24/7 runtime dependency and to make a private cloud Personal Node the normal V10 runtime. The primary mobile product entry remains Telegram `/app` into the same V10 Web/Mini App once Block F is implemented.

An unmerged version of this document is planning evidence only. It becomes accepted amendment authority only after merge under the repository authority rules.

## 1. Non-negotiable sequencing

The active program remains at the current accepted percentage and WP22A remains the only active implementation package.

1. Finish, accept and merge WP22A using its existing exact-head and physical-phone evidence gates.
2. Update the canonical current-program status after WP22A acceptance.
3. Execute the zero-weight transition gate defined here as **WP22B — Cloud Personal Node Migration**.
4. Accept WP22B only after its Linux, security, backup, restore, cutover and rollback evidence passes.
5. Start WP23–WP26 Telegram implementation only after both WP22A and WP22B are accepted.

The amendment/documentation PR may merge before WP22A finishes because it changes no runtime. WP22B implementation must not begin out of sequence, must not be mixed into the active WP22A PR, and must not unlock or claim credit for WP23 or later work.

## 2. Product and operational decision

The V10 operating model is phone-first, not phone-hosted:

- the cloud Personal Node runs the deterministic Core, Web/API, PostgreSQL and approved background jobs continuously;
- the phone is the OWNER control surface through Telegram and the same V10 Web application;
- Telegram long polling is outbound-only and does not require a public webhook;
- Telegram `/app` opens the same frontend as ordinary Web access; it does not create a second UI or second Core;
- Telegram Mini App authentication must validate `initData` server-side, enforce freshness/replay controls and issue a short-lived V10 session;
- ordinary private-browser authentication remains available for recovery, testing and Telegram-provider outages;
- the Lenovo laptop becomes a powered-off/cold rollback node after cloud acceptance, not the architectural owner and not a permanent 24/7 dependency.

During WP22B, before Block F exists, the phone uses the private Tailscale Web route and the existing approved browser-auth path. The Telegram front door is activated only by WP23–WP26.

## 3. Initial provider and size baseline

The initial implementation candidate is **Timeweb Cloud**, selected for a simple mobile-capable control panel, Russian payment paths, hourly billing, Linux images and an adequate small-server tier. This is a replaceable deployment choice, not vendor ownership of V10.

| Item | Initial decision |
|---|---|
| Project/environment | one private `v10-staging` Personal Node, promoted/reprovisioned as the primary node only after acceptance |
| Region | Moscow |
| Server | MSK 50 / Premium baseline: 2 vCPU, 4 GB RAM, 50 GB NVMe |
| OS | Ubuntu 24.04 LTS, or the current supported Ubuntu LTS if that exact image is unavailable at purchase time |
| Billing | hourly/month-to-month; no annual prepayment during migration and stabilization |
| Application ingress | Tailscale Serve HTTPS inside the OWNER tailnet only |
| Public Web ingress | disabled; Tailscale Funnel disabled; no public application ports |
| Domain | not purchased for the owner-only private phase |
| Database | self-hosted PostgreSQL on the Personal Node, loopback/private-container network only, with a dedicated least-privilege application role |
| CI | never on the production Personal Node; use an isolated ephemeral/on-demand Linux self-hosted runner |

A provider-assigned public address may exist for outbound connectivity and tightly limited infrastructure checks, but the provider firewall and host firewall remain default-deny for inbound application traffic. Remote administration is Tailscale-only after bootstrap. Direct remote root login is disabled after bootstrap.

Use a neutral Tailscale machine name because HTTPS certificate issuance can expose the machine name through public certificate-transparency logs. No OWNER name, project secret, broker name, account number or financial meaning may appear in hostnames.

## 4. Cost contract

All prices below are planning references checked on **2026-08-15**, not permanent provider promises. The purchase gate must revalidate the cart, taxes, public-IP charges, traffic terms and payment method before the OWNER pays.

| Component | Normal monthly planning amount | Decision |
|---|---:|---|
| MSK 50 server | 1,200 RUB reserve | page showed 1,080 RUB/month with a 12-month 10% discount; V10 deliberately budgets the undiscounted equivalent and does not prepay initially |
| Private S3 backup allocation, 10 GB | 79 RUB | required; store only client-side encrypted backup objects with lifecycle/versioning controls |
| Provider Ping monitoring | 30 RUB | recommended; ICMP only from current documented monitor addresses, never a public HTTP/TCP application endpoint |
| Tailscale Personal | 0 RUB incremental | allowed only while current owner-only personal/noncommercial eligibility remains true; revalidate before any commercial activation |
| Telegram Bot API / Mini App | 0 RUB incremental | no paid bot middleware is authorized |
| GitHub Actions | 0 RUB incremental | stay inside the existing GitHub Pro allowance and isolated self-hosted capacity; paid overage is not authorized |
| Domain, managed DB, Kubernetes, GPU, CDN/WAF | 0 RUB | not purchased in this phase |
| **Normal steady target** | **about 1,309 RUB** | keep normal operation at or below 1,400 RUB/month |
| **Hard monthly cap** | **1,800 RUB** | includes steady services and temporary runner/snapshot spend; existing GitHub Pro is excluded because it is already owned |

Additional cost rules:

- a provider full backup is currently documented at 6 RUB per GB of the existing backup, so one retained 50 GB backup would cost about 300 RUB/month; it is not a permanent baseline;
- the provider emergency copy is currently documented at a fixed 200 RUB/month; it is optional and must not be enabled together with redundant paid protection without a recorded reason;
- use the provider's temporary snapshot before risky infrastructure changes when its current free/retention terms are suitable, but never treat a same-provider snapshot as the only backup;
- transient runner and temporary snapshot/backup costs must fit inside the hard cap;
- no annual prepayment is allowed until at least 30 stable days, one successful restore drill and a written cost review;
- any recurring total above 1,800 RUB/month, any GPU, managed database, paid AI/search service, paid Tailscale plan or new provider requires a separate OWNER-approved budget amendment;
- if the selected service cannot stay within the cap at purchase time, stop rather than silently selecting a weaker/unsafe configuration or spending more.

## 5. Capacity and upgrade policy

The 2 vCPU / 4 GB baseline is intentionally small. It hosts the deterministic application stack, not local LLM inference.

An upgrade may be proposed only from measured evidence such as:

- seven-day p95 memory above 75%, any OOM kill or repeated memory-pressure restart;
- seven-day p95 CPU above 70% together with breached request/job latency objectives;
- sustained job backlog, missed scheduler deadlines or database latency attributable to resource saturation;
- disk above 70% after safe log/artifact retention cleanup, or measured I/O saturation;
- a Block G benchmark proving that an approved workload cannot meet its objective on the baseline.

The MSK 80 class (4 vCPU / 8 GB / 80 GB) is only a future comparison candidate. Its undiscounted equivalent is expected to exceed this amendment's hard cap, so it cannot be selected without a new OWNER cost decision. Because provider disks/tariffs may not shrink, prefer a tested new-node migration over irreversible in-place growth when practical.

Ollama/local Cortex inference and GPU compute are outside WP22B. The deterministic Core must migrate first; Block G must benchmark and separately select any AI execution location.

## 6. Private network and authentication boundary

The baseline network is fail-closed:

- provider firewall default-deny;
- host firewall default-deny;
- no public HTTP/HTTPS/SSH/database ports;
- Tailscale Serve for private HTTPS; Funnel remains off;
- PostgreSQL is never internet-routable;
- Tailscale device enrollment requires OWNER account protection, device approval and 2FA where available;
- remote root login is disabled after bootstrap; routine service execution remains `app:app`;
- provider Ping monitoring, if enabled, permits only ICMP from the currently documented monitor source addresses and is revalidated when provisioned;
- no domain or public certificate endpoint is required for the private phase.

Telegram is a convenient primary entry point, not the sole root of trust. Loss of the Telegram account or an in-app browser failure must not make recovery impossible. Recovery uses the OWNER's protected provider/Tailscale accounts and the ordinary private Web authentication path.

Any later public/no-VPN or multi-user deployment requires a separate gate covering public ingress, domain/DNS, rate limits, WAF/DDoS posture, tenant isolation, legal/personal-data duties, capacity and commercial Tailscale eligibility.

## 7. Linux runtime and secret migration

WP22B must produce a reproducible Linux deployment rather than copying the Windows machine image.

Required properties:

- the canonical ASGI target remains `app:app`;
- services run as a non-root `app` identity with least privilege;
- systemd and/or reviewed containers define startup order, restart policy, health checks and log rotation;
- PostgreSQL uses a dedicated database and least-privilege role; administrative credentials are not available to the application process;
- background jobs use durable state and cannot duplicate work after restart;
- release artifacts are built from an accepted exact commit and verified against a manifest/digest before activation;
- production pulls an approved artifact using a read-only deployment credential; CI does not receive arbitrary production shell or production secrets;
- rollback activates a previously verified artifact and compatible database state;
- the production Personal Node is never registered as a general GitHub Actions runner.

Windows DPAPI-protected blobs must not be copied to Linux. The OWNER re-provisions required secrets into the Linux secret boundary through the protected provider console or Tailscale administration path. Secrets are injected through root-owned/systemd credential mechanisms and are unreadable to unrelated users.

The migration never places broker tokens, Telegram bot tokens, database passwords, Tailscale enrollment material, private portfolio data or server credentials in GitHub, Actions artifacts/logs, PR comments or chat. Broker access remains READ-only at this stage. A TRADE token is not provisioned by WP22B.

## 8. Backups, restore and data integrity

The steady backup design is independent from the server disk:

- encrypted PostgreSQL logical backup at least every six hours;
- encrypted daily application/configuration backup excluding secrets and reproducible binaries;
- private S3 bucket with least-privilege credentials, versioning/lifecycle rules and no anonymous/public access;
- backup age, upload failure and restore-verification alerts;
- periodic temporary provider snapshot/full backup before high-risk changes, never as the only copy;
- documented restore into a clean isolated node and integrity verification before cutover.

Initial recovery objectives are:

- **RPO:** no more than six hours for non-reconstructible PostgreSQL/application state;
- **RTO:** no more than four hours for a practiced owner-assisted restore during the private phase.

Tokens/credentials are deliberately excluded from backups and must be re-provisioned during disaster recovery. Broker-derived portfolio facts must be reconcilable against a fresh read-only broker import; the backup is not trusted merely because an archive exists.

## 9. Cutover, split-brain prevention and rollback

The Lenovo and cloud nodes may run concurrently only for bounded read-only comparison. There must never be two active writers/schedulers or two active Telegram long-polling consumers.

Cutover order:

1. pass Linux synthetic/parity/negative tests on `v10-staging`;
2. restore a fresh encrypted backup into an isolated target and reconcile deterministic outputs;
3. freeze mutable jobs on Lenovo and create a final verified migration backup;
4. activate exactly one cloud scheduler/worker set;
5. confirm Lenovo schedulers/tasks and any Telegram poller are disabled;
6. verify phone access, jobs, database, backup age, restart behavior and outbound alerts;
7. observe the cloud node for at least 72 continuous hours;
8. record an explicit acceptance decision; keep Lenovo as a cold rollback node for at least 14 days afterward.

Rollback must be practiced, not theoretical. It stops the cloud scheduler/poller first, restores/reconciles state, activates one Lenovo runtime and proves health. Destructive deletion of the Lenovo runtime, provider backups or migration evidence requires a later explicit OWNER decommission gate.

## 10. Monitoring and phone operations

Normal operation must not require a laptop or routine shell access.

Required observability includes:

- systemd/container restart-on-failure and bounded restart loops;
- local health supervisor for Web/API, PostgreSQL, workers, scheduler and backup freshness;
- outbound OWNER notifications for failures and recoveries without exposing a public callback;
- provider incident/billing/security notifications to protected OWNER channels;
- optional paid Ping monitoring for whole-node reachability using ICMP-only allowlisting;
- disk, memory, CPU, database, queue/job lag, certificate, release and rollback telemetry;
- secret-safe structured logs with bounded retention.

Before the V10 Telegram bot is implemented, provider notifications and the existing approved private channels cover infrastructure alerts. WP23–WP26 then route canonical V10 product/incident notifications through the OWNER-only bot.

## 11. Preserved V10 safety invariants

Cloud placement changes no financial authority:

- `trading_methods=false`;
- `REAL_TRADING_ENABLED=false`;
- no broker write/trade/withdrawal/transfer methods;
- no public ingress unless a later explicit gate authorizes it;
- canonical `app:app` and least-privilege `app` runtime;
- no secrets/private portfolio data in GitHub or chat;
- exact-head CI, evidence and rollback gates remain mandatory;
- deterministic Core remains the source of financial truth;
- Telegram, Web and later Cortex consume shared canonical contracts rather than duplicating calculations.

## 12. Explicitly excluded from WP22B

WP22B does not authorize:

- a public website, Tailscale Funnel, public webhook, domain or public application port;
- commercial/multi-tenant activation;
- Kubernetes, managed PostgreSQL, load balancer, CDN or paid WAF;
- GPU/local LLM hosting, paid AI/search API or paid agent middleware;
- permanent production CI runner access;
- direct replacement of existing V10 Core/Web contracts;
- real trading, broker-write capability or custody of user money/assets;
- deletion of the Lenovo rollback path;
- any purchase before the price/security/provisioning gate is revalidated.

## 13. WP22B acceptance gate

WP22B is accepted only when all checklist evidence is exact-head and demonstrates:

1. reproducible Ubuntu deployment from an accepted release artifact;
2. unchanged financial/security invariants and Linux negative tests;
3. PostgreSQL role/network isolation and no public application ingress;
4. Tailscale phone access to the private Web route with ordinary-browser recovery;
5. encrypted off-node backup plus a successful clean-node restore within RPO/RTO targets;
6. reboot, crash-restart, deployment rollback and database recovery evidence;
7. one active scheduler/writer and, when present, one active Telegram poller;
8. 72-hour soak without unexplained divergence, missed critical jobs or backup failure;
9. a practiced Lenovo rollback and a recorded cold-node retention window;
10. actual recurring forecast at or below the 1,800 RUB hard cap;
11. accepted documentation/runbook and current-program status update.

Only that acceptance unlocks WP23. It awards no separate progress percentage and does not change existing block weights.

## 14. Minimal OWNER actions

The OWNER should be asked only for actions that cannot be safely performed through repository automation:

1. create/protect the Timeweb account, enable 2FA, store recovery codes offline and configure billing/security notifications;
2. approve the revalidated cart and fund only the required month-to-month services;
3. approve the cloud device in the protected Tailscale account;
4. enter/re-provision secrets through the protected private channel without copying them into GitHub/chat;
5. perform the required phone acceptance and explicit cutover/decommission decisions.

No server purchase is required merely to merge this planning amendment. Purchase occurs only when WP22A is accepted and the WP22B implementation issue/PR is ready.

## 15. Official references checked 2026-08-15

- Timeweb Cloud server tiers, billing selector and scaling constraints: <https://timeweb.cloud/services/cloud-servers>
- Timeweb Cloud account balance/prepayment discounts: <https://timeweb.cloud/docs/service-payments/balance-top-up>
- Timeweb Cloud S3 pricing: <https://timeweb.cloud/services/s3-storage>
- Timeweb Cloud server backups/snapshots/emergency copy: <https://timeweb.cloud/docs/cloud-servers/manage-servers/backup>
- Timeweb Cloud monitoring price/types/source addresses: <https://timeweb.cloud/docs/monitoring>, <https://timeweb.cloud/docs/monitoring/types>, <https://timeweb.cloud/docs/monitoring/monitoring-server-addresses>
- Tailscale plans: <https://tailscale.com/pricing>
- Tailscale Serve/private HTTPS behavior: <https://tailscale.com/docs/features/tailscale-serve>
- Telegram Bot API long polling/webhook mutual exclusion: <https://core.telegram.org/bots/api>
- Telegram Mini Apps and server-side `initData` validation: <https://core.telegram.org/bots/webapps>
- GitHub Actions billing/self-hosted runner behavior: <https://docs.github.com/en/actions/concepts/billing-and-usage>
- GitHub product allowances: <https://docs.github.com/get-started/learning-about-github/githubs-products>

Pricing and plan eligibility must be checked again immediately before any paid or commercial activation.
