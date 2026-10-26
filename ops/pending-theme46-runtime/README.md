# Theme46: exact three-file runtime deployment preparation

State: administrative source prepared for review. The generator, remote payload,
application and tests have **not** been executed here. No bound workflow is
rendered until actual successful46 evidence and its source backup exist. Nothing
has been pushed or deployed.

## Authorized scope

The owner asked to remake every element's light and dark colors. Root approved a
narrow update of the three active owned HTML surfaces on runtime9417611:

| Runtime path | Observed old SHA256 | Reviewed46 SHA256 |
|---|---|---|
| `/opt/analyst-ai/backend/app.py` | `6a44c9fbe9cd06a91c890961db9708accf7f4a9096987fae5b490113933ad455` | `a402ec6346c3ef5673484e11e2d60640245e1dc1be9ea1f9bec7263a2427ed4b` |
| `/opt/analyst-ai/backend/telegram_browser_app.py` | `be7d2b0b122740bd02d8fecf0148db9c6569f0cf3b1c255b79eb4bf020bca5ff` | `6be30431dfe9c6330479e15d1932a9b9bd05352b531ff145558759c6d2696750` |
| `/opt/analyst-ai/backend/owner_app.py` | `4162966c03c3793d6cb9903a690842600fcc241dff1a402ae253e3fc0b285419` | `4b0456f25f82fdfd8e4bc1fbe46c231c855650a4105716589bea611c36e227c3` |

Exact source preparation is the23-file assets manifest `a320b29b…`; this
deployment includes only its three backend production files. It does not deploy
the unserved legacy HTML help file, Android resources, dependencies or a whole
backend tree. The source and routing observations are original read-only
receipts `599df7ca…` and `ba03f612…` respectively.

Actual observed owner entrypoint is `owner_app:create_app --factory`, one worker,
lifespan on, loopback8080. The separately owned update factory remains8081.
Active Caddy routes GET/HEAD update-policy/APK to8081, retired enrollment callback
to410, and the remaining owned host to8080. Current unit and Caddy hashes are
checked again before and after deployment; source changes outside these exact
three files cause a closed failure. The3 unchanged update-source identities are
also checked. No environment values or complete configuration text leave the
process.

## Required future inputs

`prepare-deployment.py` accepts `--request`, `--request-sha256`, `--output`, all
under `context/`. The output must be a new child of this directory. The request
is a JSON object with exactly these fields:

- `schema`:1; `candidate_version_code`:46; `candidate_version_name`:"0.13.8-preview".
- Actual `source_backup_commit` and `source_sha256`.
- `build_report`, `build_controller`, `build_export_receipt`, `source_inventory`,
  `reviewed_manifest`, `prepared_build`: each an exact `{ "path": ..., "sha256": ... }`
  reference to an original or prepared evidence file under `context/`.

The generator requires full Windows check/build PASS, all required command
phases exit0, canonical laptop/lease/root, stopped worker and successful cleanup,
unchanged source and complete-source digests, the reviewed45→46 identity bump,
and exact equality of every applied patch to the full original46 inventory.
The three web files and the real six-test HTML/security source must match the
reviewed assets bytes. Future union schema follows the existing Windows
reviewed-files/manifest-summary contract; if root changes that contract, update
this generator explicitly and review the change.

The generated hosted job checks the current exact GitHub build attempt and all
five completed jobs via the read-only Actions API. It checks out the explicit
source46 backup using the pinned checkout action and verifies the entire code
tree against the Windows inventory, including committed Git blob identities.
Documentation may differ in the source checkpoint; code may not. Neither
application modules nor tests run on the hosted job.

Before any runtime source change, the remote payload hashes the entire exact
retained Windows ZIP, validates its envelope, original report/controller and
original source-final bytes, and validates the archive/source-inventory mapping.
It reads the original Linux test report and JUnit XML from that archive. All six
real `OwnedWebThemeTests` must be present, unique and neither failed nor skipped.
The tested source of those tests is pinned too. Source bytes come from the
verified ZIP, never from an unreviewed workspace or a reconstructed inventory.

## Replacement, recovery and idempotence

An exclusive nonblocking `flock` lives under the root-only
`/opt/analyst-ai/.theme46-web-deployment` directory. A per-source directory holds
immutable original bytes, original uid/gid/modes and an atomically replaced,
fsynced transaction journal. The source directory and every parent must be
canonical, root-owned and not group/world writable; each file must be regular,
single-link and stable across the read.

The owner service briefly stops before replacing the three files, preventing a
new process from importing a mixture of versions. Replacement uses staged files
on the same filesystem, `os.replace`, preserved original owner/group/mode and
directory fsync. Only `analyst-ai-owner.service` receives stop/start. No daemon
reload is issued. Updates service PID, source hashes, unit/config hashes and
public policy must remain unchanged. A normal owner restart still runs the
existing startup lifecycle: the deployer does not open/change the database or
environment files, and does **not** claim that normal startup has zero database
effects.

Failure after preparation restores all three original files, starts the owner
service and checks its health. Restoration checks the exact owner unit and
owned source identities independently of Caddy/update availability: a failed
proxy check cannot prevent restoring the original files. A still-unavailable
public route is reported separately as restored source with unverified public
health, and the workflow remains failed. SIGTERM/SIGINT/SIGHUP enter restoration and
cannot interrupt it a second time. A process or machine loss can still interrupt
the operation; a subsequent invocation admits mixed old/new files only when the
exact matching journal and original backups exist, then restores before retry.
Unknown file content is never overwritten. Failed restoration remains an
explicit failure requiring review. A committed exact46 transaction verifies
current files and routes without a needless new service restart.

The remote task's bounded failure JSON is captured and retained, then explicitly
fails the hosted job. A zero SSH transport exit is never a deployment success
condition. The action has a20-minute outer budget, a600-second remote transport
bound, individual45-second owner stop/start bounds, and finite file/HTTP limits.
This is a light administrative deployment; no emulator or Windows lease is used.

## What is actually verified live

- `GET /health`: exact200 `{"status":"ok"}`, also loopback owner health.
- `GET /auth/telegram/callback?error=theme_verification`: exact200; preserved
  security headers and fixed error handoff; exact reviewed static CSS bytes,
  including both light and dark role sets. AST admission verifies this error
  branch returns before database work. The HTTP body stays in memory.
- `GET /auth/telegram/owner-enrollment/callback`: remains410.
- `GET /client/update-policy?package_name=ru.omnicio.app.debug`: remains the same
  public policy during the operation. Policy identity and version are retained;
  no credentials, complete response body or user identity is exported.

HTTPS connects to the pinned83.217.195.29 with verified TLS/SNI for
`analyst-ai-2941515.twc1.net`, with no redirects or proxy fallback. The hosted job
independently repeats the public checks after the remote receipt.

`/auth/telegram/start` is deliberately not requested: its normal route creates a
login transaction. No login, nonce, owner-denial session or user identity is
manufactured. Login and owner403 rendering/security rely on the six actual
Windows backend tests and exact deployed bytes; no live login/403 or browser
pixel verification is claimed. No help route, Caddy change, orders/model calls,
APK publication/installation or physical-phone/full-Android acceptance is part
of this operation.

The generated target is `.github/workflows/theme46-web-runtime-deployment.yml`
on the existing administrative branch. It shares the existing publication
concurrency group so policy publication does not race this verification, retains
only bounded JSON receipts for3days with the proven pinned artifact action, and
reuses the byte-identical9417611 temporary-key transport with its finally cleanup.

Required next step: root's independent static review, actual46 receipts and
source backup, generator rendering/review, then the separately authorized
administrative application. This directory currently contains preparation only.
