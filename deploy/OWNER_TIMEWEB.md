# New single-owner Timeweb installation

The owner authorized server work on 21 October 2026. This replaces the earlier
deployment pause for backend preparation, while preserving authentication and
verified APK delivery. This installer is for an empty Ubuntu 24.04 VM only.
It refuses an existing Analyst installation and never restores old user data.

Fresh Timeweb inventory: run `39636306165`; catalogue/configuration inventory:
run `39249141914`, latest job `119349484440`. Project `2941515` is visible and
contains no visible servers. No server has been ordered by this new installation.

| Initial candidate | Region IDs | Preset IDs | VM monthly price, excluding IPv4 |
| --- | --- | --- | --- |
| 1 vCPU, 1 GB RAM, 15 GB NVMe | ru-4 / ru-5 | 6767 / 6769 | 350 RUB |
| 1 vCPU, 2 GB RAM, 30 GB NVMe | ru-4 / ru-5 | 6771 / 6773 | 550 RUB |

These are authenticated catalogue observations, not capacity reservations or a
claim of total cost. Start with the 1 GB candidate for one ASGI worker; measure
memory/disk after installation and representative requests before using it for
owner data. Models run remotely. Do not buy Android CI/GPU capacity for backend.
Confirm current capacity, IPv4 price and the total recurring cost before order.

## Configuration still required

The inventory found `TELEGRAM_CLIENT_SECRET` present. A direct check of repository
settings also found `TELEGRAM_CLIENT_ID` in Actions **variables**; the old inventory
incorrectly read it from secrets. The workflow now reads `vars.TELEGRAM_CLIENT_ID`.
Only `OWNER_TELEGRAM_SUB` is missing. Configure it through GitHub's protected secret
settings or the server's private configuration, never in public code.
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
Source: https://core.telegram.org/bots/telegram-login (checked 21 October 2026).

For this fresh database, the installer generates a new Fernet key directly on
the VM. It never prints it or replaces an existing key. Preserve an encrypted
off-server backup of the key and SQLite database before real broker data is
connected. Backup provisioning is not completed by this installer.

After creating and verifying the exact VM ID/project/IP using Timeweb's API,
use a verified SSH host key. Point the new HTTPS hostname to that VM and approve
the new Telegram OIDC origin/redirect in BotFather. Do not reuse the deleted
`176.98.178.81.sslip.io` endpoint as proof of ownership or send credentials to it.

On that VM, supply `/root/analyst-ai-owner.json`, a root-owned mode-0600 regular JSON file (not a symlink), with exactly these fields:

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

Update both `BackendConfig.BASE_URL` and `UpdateProtocol.HOST` only after the new
hostname is verified. Keep the strict HTTPS/same-host update checks. Run the full
exact-head Android API37 4 KB/16 KB matrix and Backend/Sonar gates again. Install
and test the signed APK on the owner's phone. The current candidate still points
at the retired address; a UI preview alone does not restore server functions.

This installer does not publish an APK, change an update channel, create model
charges, restore a database or send trading orders. Old Moscow/Kazakhstan deploy
scripts remain historical and must not be enabled for this fresh installation.
