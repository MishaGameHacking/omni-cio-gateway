# Omni-CIO V10 — WP22A IaC Toolchain Decision

Status: **ACTIVE FOR WP22A PHASE A**  
Owning package: **WP22A — External Web Access / OWNER Authentication Security Gate**

## Decision

WP22A validates and later executes its Cloudflare HCL with **OpenTofu 1.12.5**, bootstrapped from the official `opentofu/opentofu` GitHub Release and verified by exact SHA-256 before extraction.

The historical repository filenames `scripts/bootstrap_wp22a_terraform.ps1` and `scripts/validate_wp22a_terraform.ps1` are retained only to avoid an unnecessary contract-path migration. They now return/use `tofu.exe`; they must not download or execute a HashiCorp Terraform binary.

Pinned Windows asset:

- release: `v1.12.5`;
- asset: `tofu_1.12.5_windows_amd64.zip`;
- SHA-256: `465adc4bdf4aa80c650387b7ada2cf750f7908bf1fae7f35b05402c384e79928`.

The Cloudflare provider remains pinned to `5.22.0`. Its source address is deliberately fully qualified as:

`registry.terraform.io/cloudflare/cloudflare`

This prevents OpenTofu's shorthand provider-source default from silently changing the provider origin. The committed `.terraform.lock.hcl` remains authoritative and CI uses `init -lockfile=readonly` so validation cannot rewrite dependency selections.

## Root cause being corrected

The prior exact-head WP22A audit reached the IaC validation step only after Web build/tests, Python static/unit checks and PowerShell parsing had passed. The validator then failed before HCL validation because the protected Lenovo runner could not download the pinned Terraform archive from `releases.hashicorp.com`; the response was a regional trade-controls block.

This was a tool-distribution failure, not a reason to weaken validation or call the lane GREEN. Retrying the same URL, suppressing the failure, skipping provider validation, or moving the authoritative lane to a paid hosted runner would violate the accepted V10 engineering-quality/cost-control contracts.

## Blast radius and prevention

The failure class affects both Phase-A schema validation and any later Phase-B code path that would depend on the same Terraform bootstrap. Therefore the fix is at the shared bootstrap boundary rather than in a single workflow step.

Permanent guards:

- exact OpenTofu version and official GitHub release asset hash are source-controlled;
- the bootstrap rejects hash/version mismatch;
- the old HashiCorp release URL is forbidden by focused tests;
- the Cloudflare provider origin/version and Windows package hash remain source-controlled;
- `init -lockfile=readonly`, `validate`, and provider-address verification remain mandatory;
- exact-head Lenovo CI is the authority for proving the real execution region can obtain and execute the pinned tool/provider path;
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
