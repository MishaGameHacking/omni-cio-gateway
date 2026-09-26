# V10 T-Bank package CA trust runbook

Status: **focused Windows dependency trust repair / no product authority change**

## Purpose

Protected Windows CI installs the pinned `t-tech-investments` SDK from the
official T-Bank Python package index. The index can present a TLS chain rooted
in the Russian Trusted Root CA, which is not part of ordinary public CA bundles.

For **pip CI**, repository policy does not require persistent
`LocalMachine` certificate-store mutation. The source-controlled checker
builds an ephemeral PEM bundle from:

1. pip's own vendored certifi bundle, preserving its ordinary public CA roots;
2. the checked-in Russian Trusted Root CA whose DER SHA-256 must equal the
   reviewed contract pin.

The checker then publishes that merged bundle only as `PIP_CERT` for later pip
steps in the same GitHub Actions job and probes the exact official T-Bank index
with certificate and hostname verification enabled. `GITHUB_ENV` propagation is
job-local: a second job that installs the same dependency projection must run
its own CA preflight before its first hash-locked install.

The Windows `LocalMachine` provisioner remains available only for an
environment that explicitly needs system trust outside this pip boundary. It is
not a prerequisite for dependency CI.

This runbook does not change dependency versions, hashes, broker permissions,
product authentication or Real-money authority.

## Source authority and pin

Canonical certificate authority remains the T-Bank instruction pointing to
Gosuslugi:

`https://www.gosuslugi.ru/crt`

The reviewed root is also distributed as PEM at:

`https://gu-st.ru/content/lending/russian_trusted_root_ca_pem.crt`

Repository copy:

`infrastructure/certificates/russian_trusted_root_ca_2022.der`

Accepted DER SHA-256:

`D26D2D0231B7C39F92CC738512BA54103519E4405D68B5BD703E9788CA8ECF31`

The repository stores the public certificate as binary DER so the tracked-content
secret scanner does not need an entropy allowlist for a PEM Base64 body. The
bundle preparer verifies those exact DER bytes, then converts them to PEM only
inside the job-temporary bundle. No secret-scan rule is weakened.

The bundle preparer refuses any root whose DER fingerprint differs from that
pin. A future root rotation is a security boundary and requires fresh official
verification plus code review.

## CI verification

From a clean checkout, run:

```powershell
powershell.exe -NoLogo -NoProfile -NonInteractive -ExecutionPolicy Bypass -File ".\scripts\check_v10_tbank_ca_trust.ps1" -AsJson
```

The checker:

- invokes `scripts/prepare_v10_tbank_pip_ca_bundle.py`;
- verifies the checked-in root against the exact DER SHA-256 pin;
- locates pip's own vendored certifi `cacert.pem`;
- copies that ordinary public CA bundle into a job-temporary file and appends
  the pinned Russian root only if it is not already present;
- publishes only `PIP_CERT=<temporary bundle>` through `GITHUB_ENV`;
- probes the exact T-Bank package index with pip and explicit `--cert`;
- uses the contract-bounded two-attempt new-HTTP-connection retry policy with a
  10-second socket timeout; retries never disable certificate or hostname verification;
- never uses `--trusted-host`, disables hostname checks, disables certificate
  verification or changes the package source;
- never modifies the Windows certificate store;
- never emits the temporary machine path or raw child-process stderr.

Healthy CI output requires:

- `reason=TBANK_PACKAGE_INDEX_TLS_READY`;
- `root_pin_verified=true`;
- `pip_ca_bundle_ready=true`;
- `package_index_tls_ready=true`;
- `machine_trust_store_required=false`;
- `mutations_attempted=false`;
- `ready=true`.

`TBANK_PIP_CA_BUNDLE_FAILED` means the repository bundle source, pin, pip
vendored certifi source or environment publication is unhealthy and must be
repaired as source/toolchain state.

`TBANK_PACKAGE_INDEX_SECURE_PROBE_NOT_READY` means the verified bundle was
built but the bounded verified package-index probe still could not complete. This
classification intentionally does not claim that every nonzero pip probe is a
certificate-chain failure: a temporary connection/provider failure can produce the
same nonzero process result. Do not bypass TLS.

## Why this is not a TLS bypass

pip officially supports `--cert <path>` and the corresponding `PIP_CERT`
environment variable for a PEM CA bundle. The repository bundle retains pip's
vendored certifi roots and adds one reviewed root trust anchor. Normal TLS chain
validation and hostname verification remain enabled.

This is narrower than installing the Russian root into the whole Windows
machine: the added trust applies only to pip processes receiving `PIP_CERT`.

## Optional OWNER/Admin system trust

Some non-pip Windows applications can require `LocalMachine` trust. Only for
that separate need, OWNER may use the existing provisioner.

Preview, read-only:

```powershell
powershell.exe -NoLogo -NoProfile -NonInteractive -ExecutionPolicy Bypass -File ".\infrastructure\windows\provision_v10_tbank_ca_trust.ps1" -Verify -AsJson
```

If system trust is explicitly required and preview is not ready, download these
two files from the official Gosuslugi certificate page:

- `russian_trusted_root_ca.cer`;
- `russian_trusted_sub_ca.cer`.

Then open PowerShell **as Administrator** and run:

```powershell
powershell.exe -NoLogo -NoProfile -NonInteractive -ExecutionPolicy Bypass -File ".\infrastructure\windows\provision_v10_tbank_ca_trust.ps1" -Apply -RootCertificatePath "<local-path>\russian_trusted_root_ca.cer" -SubCertificatePath "<local-path>\russian_trusted_sub_ca.cer" -AsJson
```

The provisioner remains fail-closed: it validates the pinned root and
intermediate chain before the first mutation, imports only into the expected
`LocalMachine\Root` / `LocalMachine\CA` stores, is idempotent and never
downloads certificates or weakens TLS.

CI does not receive this mutation authority.

## CI recovery and rerun

The ephemeral bundle is source/toolchain state, not persistent machine state.
GitHub Runner's job-temporary directory owns the generated file. No no-op commit
or administrator action is required when the source boundary is healthy.

After a source correction, verify the new exact head. If the checker returns
`TBANK_PACKAGE_INDEX_TLS_READY`, allow the same job to continue through its
normal hash-locked installs and later gates. Every independent Windows job that
installs `windows-requirements-dev.txt` must run its own checker first; a
successful preflight in another job is not transferable evidence.

If the checker remains RED, do not use `--trusted-host`, `--insecure`,
disabled hostname verification, a different public package, another package
index or a weakened dependency lock.

## Rollback

The CI bundle has no persistent machine mutation. Rollback is removal of the
source change; GitHub Runner job-temp cleanup removes generated bundle files.

If OWNER separately installed system certificates using the optional provisioner,
rollback that system change only under Administrator authority and only for the
exact certificates OWNER installed. Never wildcard-delete
`LocalMachine\Root` or `LocalMachine\CA`.

## Protected invariants

- protected gateway entrypoint remains `app:app`;
- `PUBLIC_MULTI_USER_ENABLED=false`;
- `OMNI_V10_TELEGRAM_LOGIN_ENABLED=false`;
- broker write remains OFF;
- `trading_methods=false`;
- `REAL_TRADING_ENABLED=false`.

## Official references

- T-Bank Dev Portal — Russian Trusted CA configuration:
  `https://developer.tbank.ru/docs/tls-settings`
- T-Invest network guidance:
  `https://developer.tbank.ru/invest/intro/developer/network`
- Gosuslugi certificate page:
  `https://www.gosuslugi.ru/crt`
- pip HTTPS certificate verification:
  `https://pip.pypa.io/en/stable/topics/https-certificates/`
