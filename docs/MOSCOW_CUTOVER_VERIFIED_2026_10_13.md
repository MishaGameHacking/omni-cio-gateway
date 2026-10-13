# Analyst AI: verified Moscow cutover, 13 October 2026

## Completed, with execution evidence
The owner confirmed the new Telegram callback at 07:12:51 UTC. Final cutover Actions run 38362757807, job 115180618223 (commit d3768bcff081a8ed39f22feebc4397b3a6cc63a4) completed successfully at 07:28:39 UTC.

- Production application server and only active scheduler/writer: VM 9334503, `analyst-ai-ru-stage-9326369`, Moscow ru-3 / msk-1, IPv4 176.98.178.81, 2 CPU / 2048 MB RAM / 40960 MB NVMe, Ubuntu 24.04.
- Source VM 9326369, Kazakhstan kz-1 / ala-1, IPv4 94.198.220.228 remains on ONLY as a compatibility HTTPS proxy for installed 0.5.0 clients. Its application service is stopped; a persistent systemd ConditionPathExists guard and `/etc/analyst-ai/source-retired.lock` prevent an accidental restart. Its old database is frozen, not the current writer.
- The final private database/file snapshot was made after stopping source writes, transferred via authenticated SSH and restored before target routes opened. Recorded snapshot timestamp: 2026-10-13T07:28:16.816589+00:00.
- Verified transported/restored file checksums, SQLite integrity_check=ok, equal table counts, original FERNET_KEY and decryption of all stored broker tokens. No token values or portfolio contents were printed.
- Local target API tests: anonymous requests rejected; correct new callback and PKCE/state; synthetic one-time-code exchange, valid session /me and replay rejection. Synthetic records were removed.
- Actual read-only portfolio retrieval with a stored user broker token passed on the target. This was not a trading operation.
- Target writer activation was recorded durably before scheduler/public routes were enabled; unsafe rollback to stale source is blocked after that boundary.
- Both public hostnames passed HTTPS health, authentication guard and OAuth redirect to the new Moscow callback. No claim is made that a real Telegram login on the owner's phone was tested.
- Temporary SSH key 813441 was detached and deleted. The one-time cutover workflow was removed after success to prevent accidental reruns.

## Recovery material (private, not attached here)
The cold final archive and manifests remain in `/root/analyst-migration-38362757807` on both servers. Target `/root/analyst-cutover-38362757807/previous-staging` contains the earlier isolated installation. These are migration recovery files on the VMs, NOT an independently administered remote disaster-recovery backup or an enabled scheduled provider backup.

## Android delivery
PR829 prepares 0.5.1, versionCode 22, the same package/signing line, direct `https://176.98.178.81.sslip.io`. Published 0.5.0 still has the old URL and needs the compatibility proxy until update. Do not remove that proxy before delivering and checking the new client.

## Deployment safety limitation
The existing automatic deployment script still selects the old source by name. The attempt to replace it with a strictly pinned Moscow deployment was blocked by the tool; that replacement was not committed, and no alternative route was used to install it. PR829 instead explicitly pauses the obsolete deployment workflow with no cloud credentials or remote commands. Android CI, Backend CI, Sonar and installation tests remain enabled. This is an honest suspension of obsolete automation, not a successful Moscow deployment pipeline.

## Not completed
- New 0.5.1 APK publication/install by the owner (track PR829/release separately).
- Old Kazakhstan VM/IP retirement and associated recurring-cost cleanup.
- Audited standard deployment configuration for the Moscow target.
- Automated/independent backup policy and restore test.
- Real phone Telegram login verification and AI Gateway activation.

## Billing
Provider catalog confirmed base Moscow server price 3760 RUB/month vs previous KZ server 4030 RUB/month. IP and backups are separate; exact all-inclusive account bill is not established here. Both VMs currently remain billable, so this is not yet the final single-server running cost. No further VM, disk, resize or model API purchase occurred during final cutover.
