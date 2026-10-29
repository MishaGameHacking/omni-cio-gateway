# Candidate 55 publication preparation

This is a staged administrative patch. It has not published an APK or changed the
current channel. Existing version 54 remains the baseline: 29,775,147 bytes,
SHA-256 fae5dcfd6658bfc221aba7f3f4630f53f6deebefebb634dbebc04b9db1c47499,
package ru.omnicio.app.debug, signing certificate
bbce9534fd4cfee8f3bdcaf51a31cce384a4f303f090c8cae9ec558227d59eb1.

The source workflow is the previous workspace-shell-delivery.yml at administrative
commit c6fcbef253ee48f7474d550cc341420b79f415ec. Its actual version 54 publication
tools were pinned to 49e457d56330faa85853ed890c2a0ed1ef1b84ae; this patch derives
the separately named owner55 tools from that tested revision. Existing version 54
publication files are not edited.

First push only the new tools, their tests, checker and owner55-shell-tools.yml.
Run the synthetic suite on LAPTOP-NPSGA016 in its existing leased WSL environment.
Do not treat these synthetic tests as native acceptance or phone verification.

Only after the final owner-system.yml run succeeds for both verify and verify-client,
the same exact source passes Sonar, the backend is deployed successfully, and the
actual screenshots are reviewed, fill the owner55-shell-delivery.yml PIN fields.
EXPECTED_PUBLICATION_TOOLS_SHA and its run must identify the exact tested tools.
The visual artifact SHA must be explicitly repeated in REVIEWED_VISUAL_ARTIFACT_SHA256
after inspection; automated rendering alone does not claim visual approval.

The publication gate binds the current source branch, exact successful run attempts,
client archive digest, APK digest/signature evidence, visual archive and each required
screenshot's content, and the deployed backend receipt. The public verification keeps
the existing no-redirect HTTPS check, downloads the complete APK, compares its byte
count and SHA-256, and rereads the update policy to detect change during download.

The immutable update channel accepts only the known version 54 baseline or an
idempotent retry of the same version 55 bytes. Publication uses the existing server
and bounded SSH transport. It neither enables trading nor modifies owner credentials,
token configuration or backend code. Prior APK bytes remain available. Rollback of
the application or authentication is not performed by these tools.
