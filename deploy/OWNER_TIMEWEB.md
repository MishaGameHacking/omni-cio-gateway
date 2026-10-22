# New single-owner Timeweb installation

The owner authorized server work on 21 October 2026. This replaces the earlier
deployment pause for backend preparation, while preserving authentication and
verified APK delivery. This installer is for an empty Ubuntu 24.04 VM only.
It refuses an existing Analyst installation and never restores old user data.

The installation package includes the broker-only certificate at
`backend/certs/russian_trusted_root_ca.pem`, verified against the same X.509 DER
SHA-256 used by the T-Invest client before any installation commands. Its nested
path must be preserved; a healthy HTTP endpoint alone cannot detect a missing CA.
Public code, the virtual environment and Caddy configuration remain readable by
their service accounts even when the administrator's shell uses `umask 077`.
The configuration directory is owned by `root:caddy` with mode `0750`; both the
bootstrap and runtime Caddyfiles use `root:caddy 0640`. Caddy group lookup and
file publication fail closed. The secret environment file remains root-owned
mode `0600`, and runtime data retains the service's private `UMask=0077`.
The separate systemd drop-in directory is root-owned mode `0700`. The system
manager reads that override; Caddy only reads the group-accessible Caddyfile.
See [systemd unit drop-ins](https://www.freedesktop.org/software/systemd/man/systemd.unit.html).
These packaging and permission boundaries are covered by the installer tests;
they do not prove a live deployment.

Fresh authenticated read-only inventory: [run `39759477768`](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/39759477768),
job `119759775262`, head `a1825d17`, 22 October 2026 at 09:58:16 UTC / 12:58:16 Moscow time,
head `9eb7dcf4`. It returned `servers=[]`, `agents=[]`, `floating_ips=[]`,
`domains_total=0`, `subdomains_total=0`, `unattached_ipv4_count=0`, and
`complete_within_token_visibility=true`. This is visibility granted to this
token, not a whole-account inventory or a billing statement. DNS, ownership
of a hostname, HTTPS and regional capacity have not been verified.
`resource_changes=false`; no server was ordered by this inventory or package.

| Initial candidate | Region IDs | Preset IDs | VM monthly price, excluding IPv4 |
| --- | --- | --- | --- |
| 1 vCPU, 1 GB RAM, 15 GB NVMe | ru-4 / ru-5 | 6767 / 6769 | 350 RUB |
| 1 vCPU, 2 GB RAM, 30 GB NVMe | ru-4 / ru-5 | 6771 / 6773 | 550 RUB |

These are authenticated catalogue observations, not capacity reservations or a
claim of total cost. Start with the 1 GB candidate for one ASGI worker; measure
memory/disk after installation and representative requests before using it for
owner data. Models run remotely. Do not buy Android CI/GPU capacity for backend.
The [official public calculator](https://timeweb.cloud/prices), checked 22 October
2026, lists a public IPv4 at 200 RUB/month and automated backups at 6 RUB per
GB/month. Combined with the authenticated 350 RUB preset, **550 RUB/month covers
only the VM and one IPv4**. The [backup documentation](https://timeweb.cloud/docs/cloud-servers/manage-servers/backup)
charges the disk's capacity for **each retained backup**, including copies left
after automatic creation is disabled. The monthly calculation is
`6 RUB × disk capacity in GB × number of retained copies`.
For the 15 GB disk, retaining exactly one copy costs `6 × 15 × 1 = 90 RUB/month`;
the minimum calculation with that single copy is **640 RUB/month** before AI or
other services. Each further retained 15 GB copy adds another 90 RUB/month.
With the documented retention setting of one copy, the next automatic backup
replaces the previous one. This example does not choose a retention policy or
create any backups, and the amounts are not confirmed by an account order.

Timeweb warns that panel backups do not protect against every failure and cannot
be relied on after deleting the VM; it recommends additional remote copies.
Before connecting real owner data, prepare a separately stored encrypted copy of
the Fernet key and a consistent database backup, and verify restoration from it.
That independent storage and its cost remain to be selected; **640 RUB/month is
not a complete production budget** or proof that recovery has been configured.

The [public IP documentation](https://timeweb.cloud/docs/public-ip) states that
IPv4 billing is hourly and its current price is shown at order. Deleting the VM
leaves the IPv4 on the account; even an unattached address is billed until the
address itself is deleted. Confirm current capacity and the total recurring cost
in the account before order. This guide does not create or delete resources.

## Optional cold S3 backup budget

Checked **22 October 2026**: the [official cold-storage rate](https://timeweb.cloud/blog/digest-november-2025)
is 1 RUB/GB/month. The [minimum billed capacity](https://timeweb.cloud/docs/s3-storage/manage-storage/s3-autoscaling)
is 1 GB even for an empty cold bucket; its autoscaling is always enabled.
[Bucket billing](https://timeweb.cloud/docs/s3-storage/manage-storage/create-bucket) is hourly.
If **all retained encrypted data totals at most 1 GB**, including every [object version](https://timeweb.cloud/docs/s3-storage/supported-features/s3-object-versioning),
the storage floor is 1 RUB/month: **551 RUB/month** for VM + IPv4 + S3,
or **641 RUB/month** with the single 15 GB panel copy retained as well.
These conditional calculations exclude outgoing traffic, AI and other services;
larger backups cost according to stored data, not the VM's full disk capacity.

The [traffic billing documentation](https://timeweb.cloud/docs/s3-storage/tariffication)
charges non-Prime cold storage **1.5 RUB per outgoing GB from the first GB**.
The [service page](https://timeweb.cloud/services/s3-storage) still advertises 100 GB
free; resolve this official conflict before ordering and budget paid downloads.
The outgoing limit is checked hourly, and overshoot is charged; it is not a hard
spending cap. The [official traffic announcement](https://timeweb.cloud/blog/tarifikaciya-iskhodyashchego-trafika-s3)
lists GET/HEAD/OPTIONS/PUT/POST/PATCH/LIST and incoming traffic as free; confirm
current account terms and any unlisted operation charges before ordering.

A private bucket is a separate resource from the VM, allowing a copy to outlive
that VM's deletion. It still shares the Timeweb provider and account: this does
not protect against their common failure, account lockout or account deletion.
S3 scheduling, retention, key recovery and a verified database restore are **not
implemented or configured by this installer**. Before replacing the panel copy,
prove recovery of the consistent SQLite backup and Fernet key without the old VM;
the lower price does not waive backup or restore requirements. No bucket or
backup policy has been selected or ordered; these are not confirmed order totals.

## Free technical domain option

A paid domain is not required. Timeweb offers free technical names in `.twc1.net`,
`.tw1.ru`, `.tw1.su` and `.webtm.ru`; see the official
[technical domain instructions](https://timeweb.cloud/docs/domains/technical-domain).
Choose and create an available name only when the new VM is authorized, then bind
it to the verified new VM and project `2941515`. No name is reserved by this guide.
The panel cannot order SSL for these names, but Timeweb explicitly documents
[server-managed Let's Encrypt for a free technical domain](https://timeweb.cloud/blog/chto-takoe-gitlab-i-komu-on-neobkhodim).
Use the installer's existing Caddy setup; this does not require GitLab or another
paid service. DNS must resolve only to `EXPECTED_PUBLIC_IPV4`, verified through
Timeweb and on the VM's interface. Additional A addresses or any AAAA address
fail the current installer's exact-address check; do not weaken that check.
Validate Caddy's trusted hostname certificate live and confirm external HTTPS
reachability before treating the address as ready. Register the exact origin and
`https://<chosen-name>/auth/telegram/owner-enrollment/callback` in BotFather, and
use that identical callback in `TELEGRAM_ENROLLMENT_REDIRECT_URI`. Availability,
DNS, TLS and Telegram sign-in remain live checks, not results of this guide.

## Configuration still required

The current inventory found `TELEGRAM_CLIENT_SECRET` present and
`TELEGRAM_CLIENT_ID` present in Actions **variables**. It found
`OWNER_TELEGRAM_SUB` and `FERNET_KEY` absent; recovery metadata had zero candidates.
For a fresh empty installation, the missing Fernet key is generated locally as
described below. The missing verified owner subject requires enrollment; the
normal owner-only application cannot start first and discover its own owner.
The new explicit enrollment mode below resolves this cycle without opening
the application. An already verified subject can still be supplied through the
original protected configuration path, never in public code.
Use the exact `sub` claim from the owner's **verified Telegram OIDC ID token**.
It is an opaque, case-sensitive value, distinct from the numeric `id` in the
profile scope. A bot's Client ID, an ordinary account ID, a username, or the
first visitor cannot substitute for it. Do not guess or calculate it.
`OWNER_TELEGRAM_SUB` maps to runtime `ANALYST_OWNER_TELEGRAM_SUB`.
The earlier request for an ordinary numeric Telegram account ID was incorrect.
An administrator must bind the identity obtained through the owner's completed
Telegram sign-in, checking signature, issuer, audience, expiry and the issued
nonce. Do not paste an ID token or client secret into public issues or logs.
Without this verified binding, the application stays closed.
Source: https://core.telegram.org/bots/telegram-login (checked 22 October 2026).

## First owner sign-in — F02 / F20 preparation

The reviewed source now includes `deploy/enroll_owner.py` and the integrated
`--enroll-owner` mode of the fresh installer. It is not a public signup endpoint.
It does not import the application, create a user/session/database or choose the
first visitor as owner. `backend/telegram_oidc.py` contains the shared pure
RS256/issuer/audience/expiry/nonce/subject validator; ordinary browser login
still uses its deployment-pinned JWKS and existing transaction/session boundary.

Live prerequisites are still required: a verified new VM/IP, a controlled hostname
whose DNS identifies that VM, public HTTPS certificate issuance, working direct
TLS connections from that VM to `oauth.telegram.org`, the real BotFather Client
ID and client secret, and an administrator's private interactive SSH terminal.
The owner must sign in interactively using their intended Telegram account.
No live login, BotFather change, VM installation or certificate issuance was
performed by the local tests. A real Client ID, hostname or verified owner `sub`
cannot be invented from the source or a test token.

Register the actual new application origin in BotFather. Also register **exactly**
the actual `BACKEND_PUBLIC_URL` followed by
`/auth/telegram/owner-enrollment/callback` as an allowed HTTPS redirect URI.
Use that exact value in `TELEGRAM_ENROLLMENT_REDIRECT_URI`. This path is distinct
from the existing application's `/auth/telegram/callback`; the installer rejects
a different host, path, scheme, query, fragment or alternate port. No real origin
is supplied in this document because none has been provisioned and verified.

Before installing Caddy or creating any app directories, prepare the new
`/root/analyst-ai-enrollment.json` using the private administrative environment.
It must be a root-owned, mode-0600 regular JSON file with exactly these fields:

- `TELEGRAM_CLIENT_ID` — actual numeric Client ID from BotFather.
- `TELEGRAM_CLIENT_SECRET` — actual secret; never a command-line argument or log.
- `BACKEND_PUBLIC_URL` — the new verified HTTPS origin, without a trailing slash.
- `EXPECTED_PUBLIC_IPV4` — the exact verified new VM address.
- `TELEGRAM_ENROLLMENT_REDIRECT_URI` — the exact registered URI described above.

Do not supply an owner subject in this input. `/root/analyst-ai-owner.json` must
not exist, even as a dangling symlink. Run from the reviewed checkout in a root
interactive terminal with terminal recording disabled. `mesg n` removes other
users' terminal access; the program refuses pipes and shared terminal permissions.

```sh
mesg n
umask 077
python3 deploy/install_owner_backend.py --enroll-owner
python3 deploy/install_owner_backend.py --install --enroll-owner
```

The first command validates configuration and sources only. The second keeps
the original fresh-VM refusal checks, including any existing Caddy configuration
or service drop-in directory. It checks DNS against the verified local interface,
installs dependencies, and temporarily exposes only the exact GET callback
through Caddy to `127.0.0.1:8765`. All other application paths return 404; the
application environment, Fernet key, unit and database are not created yet.
A local TLS probe verifies the hostname certificate and that application routes
remain closed before the sign-in helper is launched.

In the private terminal, the administrator first confirms that the exact redirect
was registered. The helper shows a single-use authorization link only in that
terminal. It issues independent random state, nonce and an S256 PKCE challenge;
the transaction expires in ten minutes. It exchanges the code only at the fixed
Telegram HTTPS token endpoint, fetches only Telegram's fixed HTTPS JWKS endpoint,
and disables redirects and proxy/environment overrides. The callback spends its
matching state before the exchange, including on cancellation or invalid tokens.
No token, authorization code, client secret or provider error body is printed.

Token verification tries at most 64 eligible keys from the trusted JWKS snapshot,
with a fixed RS256 algorithm and RSA public keys of at least 2048 bits. Only after
signature and required-claim validation does it inspect the verified header.
The signed `kid` must identify exactly one eligible entry and match the key that
verified the signature. Duplicate identifiers, mismatched key identifiers,
unsupported critical headers and token-supplied key URLs are rejected. No
unverified header selects a key URL, algorithm or network request. Ordinary login
reads the locally pinned snapshot; updating that trusted snapshot remains necessary
for provider key rotation. Enrollment fetches the fixed provider JWKS before
verification. Synthetic rotation, duplicate and malformed-key tests cover these
boundaries without contacting Telegram.

After verification the listener closes. The terminal shows the verified `sub`
and bounded, escaped profile hints. The administrator must check the intended
account and type `BIND` followed by that exact `sub`; a display name, numeric
profile ID, generic “yes”, empty input, expiration or cancellation cannot bind it.
Only then is the complete owner JSON published atomically as a new mode-0600
file under root's private directory, without replacement or symlink following.
The installer rereads it, checks client/secret/origin/IP against the initial input,
generates the new Fernet key and starts the existing strict owner-only factory.

During this short bootstrap stage, Caddy's **global runtime logger** uses
`output discard`, including `http.log.error`: disabling access logs alone would
not protect callback queries on upstream errors. The Python callback also omits
request/error logs. The runtime Caddy configuration restores ordinary logging
and returns 410 for the enrollment path without forwarding it to Uvicorn.
Sources: [Caddy global logging](https://caddyserver.com/docs/caddyfile/options#log),
[discard output](https://caddyserver.com/docs/caddyfile/directives/log#discard).

Ctrl-C, normal termination and SSH hangup enter controlled cancellation. Failure
after package installation may have started Caddy is covered by cleanup that
disables/stops Caddy and stops a created owner service. A failed cleanup is
reported explicitly. Abrupt process kill or loss of the machine cannot be handled
by a Python cleanup block. Partial installation files are retained, including any
already confirmed owner configuration and generated key; there is no automatic
resume or deletion. Another fresh invocation refuses these paths. An administrator
must inspect and resolve the incomplete installation while preserving any identity,
key or data; removing the refusal checks is not a recovery procedure.

Telegram explicitly documents nonce for its Login SDK; the manual authorization
code example omits it. This implementation sends nonce and requires its exact
signed return, as required by [OpenID Connect Core §3.1.3.7](https://openid.net/specs/openid-connect-core-1_0.html#IDTokenValidation).
Live Telegram code-flow nonce behavior remains an integration gate. A missing
nonce fails closed and must not be “fixed” by removing the check. Ordinary runtime
login must also be tested against the deployed pinned signing-key snapshot.

Local verification on 22 October 2026 passed the full backend suite: 1515 tests /
1481 subtests in 24.94 seconds, plus 816 CI-script tests with four environment
skips. The latter include all 27 network-inventory tests. The only backend
warning was the existing Starlette/AnyIO deprecated alias. Signed synthetic RSA tokens, negative claims,
state/PKCE/replay/expiry/cancellation/manual-binding boundaries, root-private
atomic file publication, symlink refusal and installer ordering are covered by
`test_owner_enrollment.py`, `test_owner_enrollment_install.py` and the preserved
Telegram/owner regression tests. GitHub on `a1825d17` independently passed all
1515 tests / 1481 subtests; Sonar reported one remaining S2612 finding on the
systemd drop-in directory, with the other 26 findings absent. After restricting
that directory to root, all 31 installer tests / 37 subtests passed in 0.24 seconds.
The next head still requires a successful exact-head Backend CI and complete
zero-finding Sonar review. Both generated Caddyfiles were independently
adapted successfully by the official Caddy v2.6.2 binary after checksum verification;
this used no listener, ACME request or service. Their configuration text is unchanged
by the permission repair. Source/test readiness does not
close F02/F20/F23 deployment, owner-login or phone acceptance.

For this fresh database, the installer generates a new Fernet key directly on
the VM. It never prints it or replaces an existing key. Preserve an encrypted
off-server backup of the key and SQLite database before real broker data is
connected. Backup provisioning is not completed by this installer.

After creating and verifying the exact VM ID/project/IP using Timeweb's API,
use a verified SSH host key. Point the new HTTPS hostname to that VM and approve
the new Telegram OIDC origin/redirect in BotFather. Do not reuse the deleted
`176.98.178.81.sslip.io` endpoint as proof of ownership or send credentials to it.

For the original path with an **already verified** owner identity, supply
`/root/analyst-ai-owner.json` on that VM, a root-owned mode-0600 regular JSON file
(not a symlink), with exactly these fields. The integrated enrollment mode instead
creates this file after private confirmation; do not run the two paths in sequence.

- `TELEGRAM_CLIENT_ID`
- `TELEGRAM_CLIENT_SECRET`
- `ANALYST_OWNER_TELEGRAM_SUB`
- `BACKEND_PUBLIC_URL` — new `https://hostname`, no trailing slash
- `EXPECTED_PUBLIC_IPV4` — exact address verified through Timeweb

From the reviewed checkout, validate without installing:

```sh
sudo python3 deploy/install_owner_backend.py
```

Install on the verified new VM:

```sh
sudo python3 deploy/install_owner_backend.py --install
```

The installer verifies DNS and the VM's actual interface, refuses existing app
data, installs packaged Caddy/Python, creates a dedicated unprivileged account,
and uses `owner_app:create_app --factory --workers 1`. Backend binds loopback;
Caddy provides HTTPS. `/health` must succeed and anonymous `/workspace` must
return 401 both on loopback HTTP and on local TLS with the public hostname's certificate verified. The probe only connects to fixed loopback addresses; file configuration cannot redirect it to another host. An independent request from outside the VM must still confirm public reachability, TLS, health and anonymous denial before connecting the APK. Failure stops the new backend and
retains its data/key for inspection. It never reports a stopped install as ready.
Local config tests are not live Timeweb, TLS or Telegram login verification.

## APK connection and remaining acceptance

Set the single `BackendConfig.HOST` only after the new hostname, owner binding,
external health/authentication and Telegram redirect are verified. Backend and
updates share this origin. The current source deliberately blocks connections
before creating a transport while the host is unconfigured; the retired host
cannot be used as a fallback. Keep the strict HTTPS/same-host update checks. Run the full
exact-head Android API37 4 KB/16 KB matrix and Backend/Sonar gates again. Install
and test the signed APK on the owner's phone. The current candidate has no active server; a UI preview alone does not restore
server functions. The pending-installation JVM tests must be updated to validate
the verified configured origin when the deployment is actually ready.

This installer does not publish an APK, change an update channel, create model
charges, restore a database or send trading orders. Old Moscow/Kazakhstan deploy
scripts remain historical and must not be enabled for this fresh installation.
