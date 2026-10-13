# Moscow migration status — 13 October 2026

This is a factual progress record, not a declaration of completed cutover.

## Scope and authorization
The owner requested Russian hosting, transfer of all Analyst AI application data, and deletion of the old server after safe migration. Software provisioning protection PR828 was merged into main as 2a4a85d0d920b2bc91c9869df957a74e3c57686c after all applicable checks passed. Normal deploy does not order new servers or IPs.

## Actual resources
- Source: server 9326369, analyst-ai-backend, kz-1 / ala-1, 2 CPU / 2048 MB RAM / 40960 MB NVMe, Ubuntu 24.04, public address 94.198.220.228. The source remains operational and has NOT been deleted or stopped.
- Target: server 9334503, analyst-ai-ru-stage-9326369, ru-3 / msk-1 (Moscow, Russia), 2 CPU / 2048 MB RAM / 40960 MB NVMe, Ubuntu 24.04.
- Target public IPv4: 176.98.178.81. Exactly one IPv4 was ordered for this target. No additional staging VM was created.
- Provider catalog at creation: current KZ server preset 3795 costs 4030 RUB/month; selected Moscow Ultra preset 6871 costs 3760 RUB/month. This is a 270 RUB/month reduction for the server component only, not a confirmed all-inclusive invoice. IP, backup services and temporary overlap are separate costs.
- Verified cheaper basic candidates were rejected by the provider (no_free_node, location_not_available or preset_not_found). The accepted Moscow Ultra uses the same CPU/RAM/disk quantities, not increased capacity.

Creation evidence: Actions run 38357951795 / job 115165132980, head d93971e1831f73214959e70b9f9f169c233b67ac. Logs report RUSSIAN_VM_CREATED id9334503 and RUSSIAN_VM_READY msk-1, status on.

## Completed initial application transfer
Actions run 38359203974 / job 115169124088, head cd0b53d7cc1ddfce3a6fa0f7da0504658a93e46f completed successfully at 06:54:18 UTC.

The source application snapshot timestamp is 2026-10-13T06:53:19.931985+00:00. Persistent application files under /var/lib/analyst-ai, backend code, the original environment including FERNET_KEY, the service unit and Caddy configuration were copied to a root-only archive. SQLite databases were copied with SQLite's backup API, not by copying a live database without its transaction state.

The archive was transferred using authenticated SSH connections (scp -3); it was not published as a repository file, CI artifact, or chat attachment. Detailed manifests and configuration remain private on the VMs. The source application continued operating.

Completed checks recorded by the job:
- SHA-256 of the transported archive and every restored application file matched.
- SQLite PRAGMA integrity_check returned ok.
- Table row counts matched the consistent source snapshot, including preserved user/session data.
- Original FERNET_KEY matched and every stored encrypted broker token decrypted successfully. Token values were not printed.
- Only BACKEND_PUBLIC_URL and ANALYSIS_SCHEDULER_ENABLED were changed in target environment; the staging scheduler is disabled.
- Target local backend health and public HTTPS health passed.
- Public target /me returned 503, as intended for isolation. Other user-facing routes remain closed; this is NOT a public production switch.
- The old public health endpoint still passed.
- Temporary migration SSH key 813387 was removed from both VMs and the account. Runner private key and state files were cleaned.

The initial private archive remains under /root/analyst-migration-38359203974 on the source and target. This is a migration recovery copy, not an enabled recurring provider backup service.

## Remaining gates — do not delete the source yet
1. Register https://176.98.178.81.sslip.io/auth/telegram/callback in the owner's BotFather Login Widget Allowed URLs / Redirect URIs, keeping the old URI during the transition. The connected cloud/GitHub tools do not administer that Telegram setting. It is not confirmed as registered.
2. Finish and validate the Android endpoint update. Published 0.5.0 still embeds https://94.198.220.228.sslip.io. A separate preparation branch infra/moscow-endpoint-051 changes only the endpoint/version and is not a published replacement.
3. Immediately before cutover, pause writes, create a fresh final snapshot and synchronize changes made after the initial copy. The 06:53 snapshot is NOT guaranteed current after source activity continues.
4. Pin normal production deployment to the verified Russian target (server ID and region), open its user routes, enable exactly one scheduler, verify authentication and portfolio access, and coordinate client switching without concurrent writable databases.
5. Only after the new path and recoverability are verified, retire and delete server 9326369. Handle its old IP and backup resources deliberately; do not delete the sole good recovery copy or leave unintended ongoing charges. Any provider-required deletion confirmation must be completed, not disabled.

Final state of this record: initial copy and isolated restore VERIFIED; final synchronization NOT done; traffic NOT switched; new client APK NOT published; old server NOT deleted. Both VMs are temporarily billable. No token permissions or secret values were weakened or exposed.
