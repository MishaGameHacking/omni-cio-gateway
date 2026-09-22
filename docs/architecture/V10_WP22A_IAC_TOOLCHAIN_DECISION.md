# Omni-CIO V10 — WP22A IaC Toolchain Decision

> **Amendment 18 CURRENT-AUTHORITY OVERRIDE (2026-09-21): HISTORICAL / SUPERSEDED FOR ACTIVE CI EXECUTION.** This file preserves the earlier OpenTofu/Cloudflare supply-chain proof. Active current/future CI must not download or execute retired Cloudflare provider tooling; only non-mutating static/provenance validation of these archived sources may remain. Current production-platform authority is Timeweb Cloud.


Status: **ACTIVE FOR WP22A PHASE A**  
Owning package: **WP22A — External Web Access / OWNER Authentication Security Gate**

## Decision

WP22A validates and later executes its Cloudflare HCL with **OpenTofu 1.12.5**, bootstrapped from the official `opentofu/opentofu` GitHub Release and verified by exact SHA-256 before extraction.

The historical repository filenames `scripts/bootstrap_wp22a_terraform.ps1` and `scripts/validate_wp22a_terraform.ps1` are retained only to avoid an unnecessary contract-path migration. They now return/use `tofu.exe`; they must not download or execute a HashiCorp Terraform binary.

Pinned OpenTofu Windows asset:

- release: `v1.12.5`;
- asset: `tofu_1.12.5_windows_amd64.zip`;
- SHA-256, grouped for review and to avoid treating a required package digest as an opaque secret candidate: `465adc4b df4aa80c 650387b7 ada2cf75 0f7908bf 1fae7f35 b05402c3 84e79928`.

The Cloudflare provider remains pinned to upstream **5.22.0** with source identity `registry.terraform.io/cloudflare/cloudflare`. The protected Lenovo execution region does not rely on that origin registry at validation time. Instead, `scripts/bootstrap_wp22a_cloudflare_provider.ps1` downloads the official upstream Windows package from the `cloudflare/terraform-provider-cloudflare` GitHub Release, verifies its exact SHA-256, and `scripts/validate_wp22a_terraform.ps1` presents that package to OpenTofu through an explicit `filesystem_mirror`. The direct installation method excludes this exact provider identity, so OpenTofu cannot silently fall back to an origin-registry request.

Pinned Cloudflare provider Windows asset:

- release: `v5.22.0`;
- asset: `terraform-provider-cloudflare_5.22.0_windows_amd64.zip`;
- SHA-256, grouped for review: `ca4bf167 42a7e593 19a482f0 03d32f6f 6abbc5fb f862916c e1a13627 8e6d420d`.

The committed `.terraform.lock.hcl` remains the reviewed provider ZIP trust anchor and CI keeps `init -lockfile=readonly`. For OpenTofu 1.12 compatibility with an installed/unpacked mirror package, the validator derives the corresponding `h1:` content hash only inside an isolated temporary copy of the lock by using `tofu providers lock -fs-mirror=... -platform=windows_amd64`. The source-controlled lock is hash-checked before/after and must not be modified by validation.

## Root causes being corrected

Three environment/toolchain failure classes were observed only after earlier Web build/tests, Python static/unit checks and PowerShell parsing had already passed:

1. the protected Lenovo runner could not download the pinned HashiCorp Terraform archive from `releases.hashicorp.com`; the response was a regional trade-controls block;
2. after switching the CLI to OpenTofu, explicitly using `registry.terraform.io/cloudflare/cloudflare` as an origin registry failed because that host does not expose an OpenTofu provider-registry service;
3. after the exact Cloudflare 5.22.0 Windows ZIP was correctly found and installed from the filesystem mirror, OpenTofu 1.12 `init -lockfile=readonly` warned that it wanted to augment the lock and `validate` rejected the unpacked cached package. The source lock contained only legacy `zh:` ZIP checksums, while the installed package comparison required the matching `h1:` content hash representation. The ZIP version/hash/mirror were correct; lock representation compatibility was incomplete.

A separate PowerShell/native invocation defect was also found and fixed: writing `-chdir=$validateRoot` directly in the native command passed a literal `$validateRoot`. The validator now constructs the fully expanded `-chdir=...` argument before invoking OpenTofu, and a focused regression test forbids the faulty form.

These failures are not reasons to weaken validation or call the lane GREEN. Retrying blocked origins, suppressing failures, skipping provider validation, allowing registry fallback, or removing `-lockfile=readonly` would violate accepted V10 engineering-quality/supply-chain contracts.

## Blast radius and prevention

The failure classes affect both Phase-A schema validation and any later Phase-B code path that depends on the same IaC toolchain. Therefore the correction is at the shared bootstrap/validation boundary rather than in one workflow step.

Permanent guards:

- exact OpenTofu version and official GitHub release asset hash are source-controlled;
- exact upstream Cloudflare provider version and official GitHub release package hash are source-controlled;
- both bootstraps reject hash mismatch;
- the old HashiCorp release URL is forbidden by focused tests;
- OpenTofu receives the upstream Cloudflare package only through the explicit local filesystem mirror for this provider identity;
- direct origin-registry installation is excluded for that identity;
- the committed provider lock retains the reviewed exact Windows ZIP `zh:` trust anchor;
- a mirror/platform-specific `h1:` is derived only in the isolated validation copy via `providers lock -fs-mirror -platform=windows_amd64`;
- the validator checks the source lock SHA before/after and fails if validation mutates source authority;
- a dedicated regression test requires the mirror lock derivation, source-lock immutability check, content-hash check, readonly init and direct-fallback exclusion;
- `fmt`, `init -lockfile=readonly`, `validate`, and provider-address verification remain mandatory;
- exact-head Lenovo CI is the authority for proving the real execution region can obtain and execute the pinned CLI/provider path;
- no real Cloudflare credential is exposed to PR validation.

## Safety invariants

This toolchain correction does not change product authority:

- `app:app` remains unchanged;
- `trading_methods=false`;
- `REAL_TRADING_ENABLED=false`;
- no broker-write or transfer/withdrawal authority is added;
- public multi-user activation remains OFF;
- no Cloudflare mutation is authorized from the dormant Phase-A PR;
- WP23 remains LOCKED until the full WP22A Exit Gate passes.
