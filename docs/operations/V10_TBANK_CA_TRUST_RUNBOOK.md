# V10 T-Bank package CA trust runbook

Status: **focused Windows dependency trust repair / no product authority change**

## Purpose

The protected Windows CI installs the pinned `t-tech-investments` SDK from the
official T-Bank Python package index. The package index can present a certificate
chain rooted in the Russian Trusted CA. If the Windows machine does not trust the
Russian Trusted Root CA and Russian Trusted Sub CA, pip fails closed with
`SSLCertVerificationError`.

This runbook does not change dependency versions, hashes, broker permissions,
product authentication or Real-money authority.

## Source authority

Use only the certificate download page linked by T-Bank:

`https://www.gosuslugi.ru/crt`

Download these two files locally on the OWNER machine:

- `russian_trusted_root_ca.cer`
- `russian_trusted_sub_ca.cer`

Do not download certificates through a command that disables TLS validation.
Do not paste certificate-store dumps, machine identity or any credential into
GitHub/chat.

## Read-only verification

From a clean checkout, ordinary CI and OWNER can run:

```powershell
powershell.exe -NoLogo -NoProfile -NonInteractive -ExecutionPolicy Bypass -File ".\scripts\check_v10_tbank_ca_trust.ps1" -AsJson
```

A healthy result requires:

- a current `Russian Trusted Root CA` in `Cert:\LocalMachine\Root`;
- a current `Russian Trusted Sub CA`, issued by the root, in
  `Cert:\LocalMachine\CA`;
- a read-only pip TLS probe to the exact configured T-Bank package index to
  succeed with normal certificate and hostname verification.

The check never imports certificates and never disables TLS verification.

## OWNER/Admin preview

The provisioner is verify-by-default. Before mutation, run:

```powershell
powershell.exe -NoLogo -NoProfile -NonInteractive -ExecutionPolicy Bypass -File ".\infrastructure\windows\provision_v10_tbank_ca_trust.ps1" -Verify -AsJson
```

If `ready=true`, no mutation is required.

## OWNER/Admin apply

Only if verification reports `TBANK_CA_TRUST_STORE_NOT_READY`, open PowerShell
**as Administrator** and use the two files downloaded from the official
Gosuslugi page:

```powershell
powershell.exe -NoLogo -NoProfile -NonInteractive -ExecutionPolicy Bypass -File ".\infrastructure\windows\provision_v10_tbank_ca_trust.ps1" -Apply -RootCertificatePath "<local-path>\russian_trusted_root_ca.cer" -SubCertificatePath "<local-path>\russian_trusted_sub_ca.cer" -AsJson
```

The provisioner:

- refuses non-Windows execution;
- requires Administrator for `-Apply`;
- validates the expected CA common names, validity and CA role;
- requires the root to be self-issued and the intermediate issuer to be the
  Russian Trusted Root CA;
- imports the root only into `LocalMachine\Root`;
- imports the intermediate only into `LocalMachine\CA`;
- is idempotent by certificate thumbprint;
- does not download anything and does not weaken TLS.

After apply, rerun the read-only checker above and require
`reason=TBANK_PACKAGE_INDEX_TLS_READY` and `ready=true`.

## CI recovery

The CA trust state is machine state, not source state. Once the exact same
repository SHA has `ready=true`, the Green Checkpoint law permits rerunning only
the failed infrastructure jobs on the same SHA. Do not create a no-op commit.

If the checker remains RED, do not use `--trusted-host`, `--insecure`, disabled
hostname verification, a different public package, or another package index.

## Rollback

If OWNER needs to remove a certificate, use Windows certificate management under
Administrator authority and remove only the exact certificate that OWNER
installed. Do not wildcard-delete certificates from `LocalMachine\Root` or
`LocalMachine\CA`.

After any rollback, the read-only checker must return RED until the required
trust chain is restored.

## Protected invariants

- protected gateway entrypoint remains `app:app`;
- `PUBLIC_MULTI_USER_ENABLED=false`;
- `OMNI_V10_TELEGRAM_LOGIN_ENABLED=false`;
- broker write remains OFF;
- `trading_methods=false`;
- `REAL_TRADING_ENABLED=false`.

## Official references

- T-Bank Dev Portal — installation of Russian Trusted Root/Sub CA:
  `https://developer.tbank.ru/docs/tls-settings`
- Gosuslugi — official certificate download page:
  `https://www.gosuslugi.ru/crt`
