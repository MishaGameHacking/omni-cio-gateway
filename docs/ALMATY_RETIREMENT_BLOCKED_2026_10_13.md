# Old-server retirement — not executed

The owner confirmed at 2026-10-13 08:08:58 UTC that the updated app launches and explicitly requested removal of the old server, keeping Russian servers only.

## Outcome of this attempt
- GitHub reads reconfirmed the recorded cutover: Moscow target 9334503, IP 176.98.178.81, and old Almaty source 9326369, IP 94.198.220.228.
- The main branch's obsolete deployment workflow remains explicitly paused; this attempt did not change it.
- A narrowly scoped retirement script and read-only probes were prepared. Twenty-one offline tests passed locally. These are not evidence of a live cloud check or deletion.
- The tool blocked creation of the execution controller `.github/scripts/retire_almaty.sh` before any retirement workflow or cloud call was launched.
- No alternate route was used to execute the blocked operation. Both newly added, unexecuted scripts were removed from the branch afterwards (commits 4b328be4762dd87746758f079a6e8a726d784fcd and 84db55023b01119fac23b3c0e237cb8abd1aea16).
- NO cloud VM/IP deletion, SSH-key issuance, target change, backup order, or security-setting change occurred during this attempt. No deletion is scheduled.

## Owner panel operation, with existing permission/confirmation intact
The migrated source to retire is `analyst-ai-backend`, VM 9326369, Almaty / ALA-1, IPv4 94.198.220.228. Retain Moscow VM 9334503 (`analyst-ai-ru-stage-9326369`), IPv4 176.98.178.81 and its recovery material.

Use the normal Timeweb delete-server operation and select removal of the old public IP if available. Complete provider-required confirmation inside Timeweb/Telegram; do not paste verification codes, tokens or passwords into chat. If the old IP is retained, verify it is unbound and remove only 94.198.220.228 from public IP inventory.

Last earlier provider backup evidence: backup 106582657 of Moscow disk 26060189 was confirmed done by workflow 38364293430. This attempt did not refresh that live status or perform a restore test.

Actual source absence, IP removal, retained Moscow health and an all-Russian final server inventory still require live verification. Do not claim billing cleanup or retirement is complete from this document.
