# V10 Engineering Failure Learning Ledger — FL166

## Scope

Reusable defect class: protected Windows CI cannot establish TLS trust to the
official T-Bank Python package index.

The defect was reproduced on TW-B PR #584 exact head
`ecaab689f872d2547af1f26e43e744fd53e575f6` in WP20 Research Dossier Audit
#2288 / run `35770674981`, job `106891291518`.

This focused repair is a dependency/security machine-boundary split from TW-B.
It does not authorize TW-C, Timeweb provider mutation, Telegram public
activation, broker write or Real-money execution.

## Failure evidence

The dependency install repeatedly reached
`https://opensource.tbank.ru/api/v4/projects/238/packages/pypi/simple/` and
failed with Windows `SSLCertVerificationError` reporting an untrusted root.
After the TLS failures pip emitted `No matching distribution found for
t-tech-investments==1.49.3`.

The selected dependency version and hashes were unchanged. The same failure
class appeared across multiple Windows jobs because the canonical lock carries
the official T-Bank package index as an additional resolver source.

## Root cause

The persistent self-hosted Windows runner did not have a usable Russian Trusted
Root CA + Russian Trusted Sub CA trust chain for the package-index TLS path.

T-Bank documents that its affected TLS endpoints require these two MinDigital
certificates and that Windows services use the LocalMachine Root and
Intermediate CA stores. The repository previously assumed this machine
precondition but did not model, verify or recover it.

The global extra-index configuration amplifies the visible blast radius because
pip can query the additional index while resolving unrelated public packages.
That is not a reason to disable certificate validation or substitute an
unrelated public SDK package.

## Blast radius

Without a permanent machine-trust boundary:

- authoritative Self-Hosted Windows CI can stop before static quality/tests;
- WP13–WP22A audits that install the canonical lock can fail at the same
  dependency step;
- repeated pip retries obscure one common trust failure as many package lookup
  failures;
- blind reruns cannot repair persistent machine trust;
- disabling TLS or changing package source would create a supply-chain security
  regression.

## Correction

1. Add a machine-readable T-Bank CA trust contract.
2. Add an OWNER/Admin-only, local-file provisioner that never downloads
   certificates and never disables TLS. Pin the long-lived root by DER SHA-256,
   and require every supplied/current intermediate to cryptographically chain
   to that pinned root.
3. Add a read-only verifier that first proves the LocalMachine CA presence and
   then uses pip itself for a bounded package-index TLS probe.
4. Run that verifier before the authoritative dependency installation so the
   failure is immediate and classified.
5. Add regression tests forbidding TLS bypasses and proving the verifier remains
   before dependency installation.
6. Document exact OWNER recovery and same-SHA CI rerun semantics.

## Security and authority invariants preserved

- no real credential, broker token, GitHub token or machine identifier is
  written to source/evidence;
- CI runner receives no certificate-store mutation authority;
- OWNER/Admin mutation is explicit and idempotent;
- matching certificate names alone are insufficient mutation authority: the
  root fingerprint is pinned and the intermediate chain is verified;
- dependency versions/hashes and T-Bank package-source authority are unchanged;
- certificate and hostname verification remain enabled;
- `PUBLIC_MULTI_USER_ENABLED=false`;
- `OMNI_V10_TELEGRAM_LOGIN_ENABLED=false`;
- broker write remains OFF;
- `trading_methods=false`;
- `REAL_TRADING_ENABLED=false`.

## Replacement-head source defect and guard gap

Security-hardening head `483d1933143f8fa0417d3b6f684dfc01696703e7`
introduced a malformed `provision_v10_tbank_ca_trust.ps1`: the intended pinned
root implementation was concatenated with the previous provisioner body and the
root-fingerprint policy regex was truncated. Self-Hosted Windows CI #3135 failed
at the new trust preflight before any dependency install or machine mutation.

Root cause: the replacement content was assembled by unsafe text composition and
the generic Fast PR lane did not parse this new PowerShell boundary. Python
compile/Ruff/governance could therefore pass while the PowerShell source was
syntactically invalid.

Systemic correction:

- replace the provisioner with one canonical implementation;
- validate root fingerprint and intermediate chain fully before the first
  certificate-store mutation;
- add a Windows PowerShell parser step to Fast PR for both CA trust scripts;
- add regression assertions that the provisioner has one implementation and the
  parser guard remains source-controlled.

This source defect must be repaired before any OWNER/Admin certificate action.
The machine trust state is not a valid explanation for a parser failure.

## Child-process diagnostic isolation gap

Replacement head `ade50693ccbe921033c82bf6a996e805f5a427db` repaired the
PowerShell source itself, but Self-Hosted Windows CI #3137 exposed a second
repository-side defect in the read-only checker. The checker invoked a child
`powershell.exe` directly while `$ErrorActionPreference=Stop`; child stderr was
promoted to a terminating `NativeCommandError` before the checker could inspect
the bounded exit code or emit its sanitized JSON state.

This is a diagnostic-boundary defect, not evidence that the OWNER machine trust
store is the only remaining blocker.

Systemic correction:

- execute both the provisioner verification and pip TLS probe through
  `Start-Process`;
- redirect child stdout/stderr into separate temporary files;
- parse only the expected provisioner JSON and never emit raw child stderr,
  machine paths or certificate-store dumps;
- require the child exit/state pair to be internally consistent;
- classify launch/shape/unexpected-exit failures as
  `TBANK_CA_TRUST_VERIFIER_FAILED`;
- delete temporary files in `finally` and remain fail-closed.

Only after this exact diagnostic boundary is verified may
`TBANK_CA_TRUST_STORE_NOT_READY` be treated as an OWNER/Admin machine-state
blocker.

## StrictMode collection normalization

Post-#3137 source review identified an additional deterministic Windows
PowerShell hazard in the provisioner: `Get-TrustedCandidates` emits pipeline
output, so a 0/1/N result must not be consumed as an assumed array under
`Set-StrictMode -Version 3.0`. The root-candidate caller now wraps the
producer in `@(...)`, matching the already-safe intermediate-candidate path.
This guarantees a real zero-length collection before `.Count` is evaluated
when the Russian Trusted Root CA is absent.

The correction is fail-closed and does not change certificate acceptance,
mutation authority or TLS behavior.

## Fast parser transport / ExecutionPolicy defect

Exact head `8b064b2e351a7bfc9fc97cd58617ce036c689b8d` proved the CA
checker itself now classifies the real machine state as
`TBANK_CA_TRUST_STORE_NOT_READY`, but Fast PR #3048 failed before parsing either
trust script. GitHub Actions `shell: powershell` materialized the workflow body
as a temporary `.ps1`; the runner's effective execution policy rejected that
temporary script with `PSSecurityException / UnauthorizedAccess`.

This is a verifier-transport defect, not a syntax defect in the two trust
scripts and not a reason to weaken the runner's machine execution policy.

Systemic correction:

- keep the read-only PowerShell AST parser and the same two source targets;
- execute the parser from the existing `cmd` workflow shell via an explicit
  `powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -Command`
  process-local invocation, matching accepted Windows verifier patterns;
- do not call `Set-ExecutionPolicy`, do not mutate LocalMachine/CurrentUser
  policy and do not grant new runner authority;
- add regression coverage that the Fast PR parser block remains `shell: cmd`,
  uses explicit process-local `-ExecutionPolicy Bypass`, and cannot regress
  back to `shell: powershell`.

Microsoft documents that execution policy can be supplied for one PowerShell
session without persisting a machine/user policy change. The runner's
Restricted/managed policy therefore remains intact outside this bounded parser
process.

## Project-wide dependency-consumer closure

Exact head `dd5c845c3a8512aeb26ea41be921e9f4213e93b4` proved the
authoritative checker now emits bounded machine state:
`TBANK_CA_TRUST_STORE_NOT_READY`, verifier exit 71, checker exit 72. The same
exact-head WP18, WP22, WP22A Phase 2 and WP22A clientless logs independently
reproduced the same Windows `SSLCertVerificationError` while resolving through
the official T-Bank package index.

Repository inventory found 14 active self-hosted Windows workflows that both
run on the `omni-cio-ci` runner and consume `windows-requirements-dev.txt`.
Previously only the authoritative merge gate failed fast; the other consumers
entered pip resolution and emitted long retry storms that obscured one machine
trust defect as many package failures.

Systemic correction:

- declare the complete consumer set in the CA trust contract;
- require every consumer to run the same read-only CA checker before its first
  hash-locked pip install;
- discover consumers independently in regression tests from workflow source and
  require exact equality with the declared contract set, so a future hidden
  consumer fails closed;
- require exactly one checker invocation per consumer and prove it occurs before
  `--require-hashes -r windows-requirements-dev.txt`;
- keep certificate-store mutation OWNER/Admin-only and keep dependency
  versions, hashes and T-Bank package-source authority unchanged.

This turns a shared machine prerequisite into a shared explicit producer guard
without granting CI any additional trust-store mutation authority.

## Fast parser cmd-quoting defect

Exact head `e4d1fa70b869780738c882ba5abf61743b3e2742` proved the
project-wide dependency-consumer fail-fast wiring, but Fast PR #3050 failed in
the parser transport itself. The multi-line PowerShell program embedded in
`cmd -> powershell.exe -Command` was split by the workflow transport: PowerShell
received an unterminated `foreach` block and subsequent lines such as
`$errors=$null` were interpreted by `cmd.exe`.

Root cause: a non-trivial PowerShell program was encoded inline across YAML,
GitHub Actions and cmd.exe quoting boundaries. Process-local
`-ExecutionPolicy Bypass` was correct; the multi-layer quoting strategy was
not deterministic.

Systemic correction:

- move the AST parser into checked-in
  `scripts/check_v10_tbank_ca_trust_syntax.ps1`;
- keep its target set bounded to the read-only checker and OWNER/Admin
  provisioner;
- invoke it from Fast PR with one
  `powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File`
  command;
- regression-test the dedicated script, its exact targets, no mutation/network
  behavior, and the Fast workflow's use of `-File` rather than inline
  `-Command`;
- keep machine/user execution policy unchanged.

The dedicated script is itself parsed by PowerShell when executed, so a syntax
defect in the parser guard also fails the same Fast step.

## Exact-head project failure convergence and pip trust correction

Exact head `15be56561f4a439e39db16626fc8c633ddb8676c` completed Fast PR
#3052, Engineering Governance #1937 and Toolchain Compatibility #3086
successfully. Every remaining failing Windows audit (WP13, WP14, both WP15
lanes, WP17, WP18, WP19, WP20, WP21, WP22, WP22A clientless, WP22A Phase 2 and
the authoritative merge gate) failed only at the shared T-Bank CA preflight;
their hash-locked pip install and all later steps were skipped.

This proves the 13 visible RED checks are one shared dependency trust producer,
not 13 independent application defects.

Further root-cause review found that the original repair over-bound pip CI to
persistent Windows `LocalMachine` trust. T-Bank documents that Python clients
can require their own CA bundle, and pip officially supports a PEM trust bundle
through `--cert` / `PIP_CERT`. Persistent machine-store mutation is therefore
not required to preserve TLS verification for package CI.

Systemic correction:

- check in the public Russian Trusted Root CA as auditable source data;
- verify its DER SHA-256 against the existing reviewed root pin before every
  bundle assembly;
- copy pip's own vendored certifi bundle and add the pinned Russian root only if
  absent, preserving ordinary public CA trust;
- publish the merged job-temporary bundle only as `PIP_CERT`;
- make the checker probe the exact official T-Bank index with explicit
  `--cert`, certificate verification and hostname verification still enabled;
- keep all 14 Windows dependency consumers behind the same preflight;
- keep `LocalMachine` mutation outside CI and OWNER/Administrator-only for an
  explicit non-pip system-trust requirement;
- add Fast PR source execution and regression coverage for bundle assembly,
  pin integrity, no-network assembly and no TLS bypass.

The public root trust anchor is scoped to pip processes that receive
`PIP_CERT`, which is narrower than installing it for the entire Windows
machine. Dependency versions, hashes and the official T-Bank package source are
unchanged.

## Acceptance

This repair is not GREEN merely because the source exists. The exact repair head
must pass source/governance checks, build and verify the pinned ephemeral pip CA
bundle, reach the official T-Bank package index with TLS verification enabled,
then pass every applicable GitHub-native check. The squash-merged exact new main
must pass post-merge Regression Shield.
