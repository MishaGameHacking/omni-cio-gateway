# Moscow recovery backup receipt — 13 October 2026

Actions run 38364293430 / job 115185604157 (head 13f0a93243c15d2d68fe6059f96bb8293fecca75) completed successfully.

At 07:41:53 UTC the API returned the new backup ID. At 07:42:45 UTC a separate GET confirmed status `done`:
- Moscow VM: 9334503, ru-3 / msk-1, 2 CPU / 2048 MB RAM / 40960 MB NVMe.
- Verified system disk ID: 26060189.
- Provider backup ID: 106582657.
- Comment: Analyst AI final Moscow migration recovery 2026-10-13.
- Exactly one backup created; no new VM, disk, address or tariff change.
- Ten offline scope/identity checks passed before cloud access.
- No server stopped, deleted, restored or overwritten by this backup operation.
- One-time workflow removed after success; automatic daily backup scheduling is NOT configured.

The backup covers the existing Moscow disk, which contains the private final migration recovery archive. Actual restore from this provider backup has NOT been tested on the live production server. Successful creation is not a complete disaster-recovery exercise.

Timeweb's published price is 6 RUB per GB of provisioned disk per stored backup; for this 40 GB disk the estimate is 240 RUB per month while retained, separate from VM/IP costs. This is a documented-price estimate, not verification of the account's full invoice. The official documentation warns that provider backups do not cover every hardware/software failure or deletion of the backed-up server and recommends additional remote copies. Therefore this backup is not described as an independently guaranteed disaster-recovery solution.

Old Kazakhstan VM 9326369 remains the compatibility proxy for installed 0.5.0 clients and is not deleted by this operation. Remove it and its old IP only after updated client readiness and required provider confirmation are resolved.
