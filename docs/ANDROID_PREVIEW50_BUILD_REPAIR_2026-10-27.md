# Preview50: actual laptop checks and narrow Windows source-I/O repair

Initial source HEAD b1bfef76159943b48ef8cfa502243877a1799213;
exact tested merge fdc10e23554d164d7de1c3c546ad69c1335d5780;
base main f54912165127bfab42673743cd141d635e20881f.

## Actual first results (not source-only estimates)

Backend CI40552853931/job122361064480 ran on LAPTOP-NPSGA016/WSL.
2161 backend tests +1557 subtests passed. Health/OpenAPI and source compilation
passed. One Starlette/AnyIO dependency warning remains. The overall run FAILED
its strict exact-head Sonar gate; it is not an accepted release.
Evidence artifact12754939674 (backend-laptop-40552853931-1) is retained.
Complete source SHA256: 5a30f8e5f281ac29cd20043db5bab5bb657c26d4206d27ec0d68e70c65c35c08.

Android CI40552853598/job122361107050 ran on LAPTOP-NPSGA016 and failed BEFORE
Gradle in source_identity: source_file_missing. Its checkout prefix plus the
two HomeDisconnectedAppearance PNG names reaches260/261 characters. This is
consistent with Windows MAX_PATH, but the original error did not identify the
path, so the path-length diagnosis remains a hypothesis until the new run.
No new APK, installation, launch or publication was completed by that run.

## Narrow correction

Only local filesystem addressing in source inventory/bounded reads changes:
ordinary absolute local-drive paths use the extended Windows I/O prefix.
Lexical runner/source allowlists, all ancestor reparse/symlink checks, hardlink
rejection, canonical-path checks, bounded reads, file identity before/after read,
Git tree/index matching, actual Git-blob hashes and merge-parent checks remain.
UNC/device/relative/traversal inputs are not newly accepted. No tracked files,
reference images or gates are skipped. Missing-file errors now name the safe
repository-relative file. There are no registry, SDK or machine-policy edits.

Real temporary Git fixtures cover long committed paths, all-file inclusion,
correct SHA256/blob, assume-unchanged tampering, missing long/ordinary files,
read bounds and hardlinks. Windows-only path grammar is tested on Windows.
These NEW tests have not yet executed; the existing owner-host PR CI is the
execution route. Earlier failures and test evidence remain untouched.

Codex implementation request6449568772 received a response asking to connect a
Codex account (6449571786), not an implementation commit. No Codex work or result
is claimed. The source correction was prepared directly through GitHub.

Sonar check122362086528 FAILED, including reliability/security conditions;
50 annotations were available in the existing CI log. No suppression, threshold
change or bypass is performed. Those findings still block publication.

No workflow, cloud/remote transport, credentials, signing, production data,
main, runtime or APK-channel change is part of this correction. The owner
requires an actual APK update; source edits alone are not that result.

References:
https://learn.microsoft.com/en-us/windows/win32/fileio/maximum-file-path-limitation
https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/40552853598
https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/40552853931
