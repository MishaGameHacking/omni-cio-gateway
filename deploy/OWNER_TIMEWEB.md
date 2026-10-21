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
The owner subject is the owner's numeric verified Telegram identity, not a
username and not the first visitor. `OWNER_TELEGRAM_SUB` maps to the runtime name
`ANALYST_OWNER_TELEGRAM_SUB`.

For this fresh database, the installer generates a new Fernet key directly on
the VM. It never prints it or replaces an existing key. Preserve an encrypted
off-server backup of the key and SQLite database before real broker data is
connected. Backup provisioning is not completed by this installer.

After creating and verifying the exact VM ID/project/IP using Timeweb's API,
use a verified SSH host key. Point the new HTTPS hostname to that VM and approve
the new Telegram OIDC origin/redirect in BotFather. Do not reuse the deleted
`176.98.178.81.sslip.io` endpoint as proof of ownership or send credentials to it.

On that VM, supply a root-owned mode-0600 JSON file with exactly these fields:

- `TELEGRAM_CLIENT_ID`
- `TELEGRAM_CLIENT_SECRET`
- `ANALYST_OWNER_TELEGRAM_SUB`
- `BACKEND_PUBLIC_URL` — new `https://hostname`, no trailing slash
- `EXPECTED_PUBLIC_IPV4` — exact address verified through Timeweb

From the reviewed checkout, validate without installing:

```sh
sudo python3 deploy/install_owner_backend.py --config /root/owner-backend.json
```

Install on the verified new VM:

```sh
sudo python3 deploy/install_owner_backend.py --config /root/owner-backend.json --install
```

The installer verifies DNS and the VM's actual interface, refuses existing app
data, installs packaged Caddy/Python, creates a dedicated unprivileged account,
and uses `owner_app:create_app --factory --workers 1`. Backend binds loopback;
Caddy provides HTTPS. `/health` must succeed and anonymous `/workspace` must
return 401 both locally and through HTTPS. Failure stops the new backend and
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
