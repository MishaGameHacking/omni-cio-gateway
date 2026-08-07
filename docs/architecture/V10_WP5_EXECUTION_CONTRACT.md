# Omni-CIO V10 — WP5 Execution Contract

Status: **IMPLEMENTATION CANDIDATE — acceptance requires focused PR, factual Lenovo evidence and WP5 Exit Gate**  
Work package: **WP5 — Hardware/OS Audit и эксплуатационный профиль**  
Accepted base at start: `546885e78c07ccb4ff85cec6c9d0d5dee62ffa07`

## 1. Purpose

Establish a factual, privacy-safe operating profile for the existing OWNER Lenovo node before any V10 node runtime installation. WP5 measures hardware/OS/security/power/network/time/thermal facts and defines conservative operating guardrails. It does not create a new runtime architecture.

## 2. Reuse decisions

- existing Lenovo GitHub self-hosted runner: `REUSE_AS_IS` as the remote evidence collection path;
- existing Windows/Python CI bootstrap: `REUSE_AS_IS`;
- existing V9 `app:app` production/recovery runtime: `REUSE_AS_IS` and untouched;
- repository `infrastructure/windows/` ownership: `REUSE_AS_IS` from WP1 architecture authority;
- no V9 financial component is rewritten, moved or retired in WP5.

## 3. Allowed changes

WP5 may add only:

- passive Windows hardware/OS/security/network/time/power/thermal collectors;
- a sanitized `OWNER_NODE_PROFILE` schema, validator and factual snapshot;
- conservative resource/thermal/disk/time/network thresholds;
- controlled stability-test tooling and runbooks;
- CI evidence collection scoped to WP5;
- tests proving privacy/fail-closed behavior.

## 4. Explicit non-goals

WP5 must not install or configure:

- Ollama, Qwen or Cortex;
- V10 Web/API runtime;
- Telegram Bot or Mini App runtime;
- broker HTML runtime;
- Portfolio Guardian or Watchtower V10 runtime;
- Block C service identities/secret store/bootstrap owned by WP6–WP8;
- billing/license/update runtime;
- Personal Real Execution changes.

No broker credentials or real portfolio data are needed for WP5.

## 5. Privacy contract

The repository-safe profile must never contain:

- hardware serial numbers, device UUIDs or other stable device identifiers;
- MAC addresses, IP addresses, SSIDs or public/private network addresses;
- Windows username, hostname/computer name or user-profile paths;
- BitLocker recovery password/key protector material;
- broker/Telegram/API tokens or secret values;
- account identifiers or private portfolio data.

Collectors may record only the minimum operational facts needed for the WP5 Exit Gate. The validator rejects forbidden key names and common identifier-shaped values.

## 6. Factual profile contract

`docs/architecture/V10_OWNER_NODE_PROFILE.schema.json` defines the repository-safe shape. The canonical thresholds are in `infrastructure/windows/wp5_node_thresholds.json`.

The profile covers:

- CPU model/core/thread count;
- RAM capacity;
- GPU vendor/model/VRAM/driver and available temperature telemetry;
- system-volume capacity/free space and physical-disk health without disk identity;
- Windows product/version/build/architecture and last boot time;
- BitLocker state without key material;
- Windows Firewall profile state and wildcard-listener count without addresses/ports/process names;
- Windows Time service/source class and measured offset against the fixed audit target `time.windows.com`;
- wired-link availability/speed without interface identity;
- battery/AC/power-scheme and normalized Lenovo conservation/power-loss settings where queryable;
- passive thermal sensor data;
- mandatory disk/reboot/network-reconnect/sustained-load checks.

## 7. Fail-closed rules

WP5 Exit Gate remains blocked when any material fact is unknown or unsafe, including:

- system-volume full-disk encryption not proven and protected;
- recovery-key custody not explicitly confirmed as separate from the node;
- Windows Time not running, offset unknown, or absolute drift above the sensitive-operation threshold;
- low disk space or unhealthy physical disk;
- required Windows Firewall profile disabled or inbound baseline unsafe;
- wired network unavailable;
- restart-after-power-loss or battery-conservation behavior not verified where applicable;
- reboot/network-reconnect/30–60 minute controlled CPU/GPU load checks not passed.

Clock drift and unknown time are represented as a deterministic sensitive-operation gate. This is a WP5 safety fact only; it does not grant any broker-write authority.

## 8. Conservative initial thresholds

The WP5 thresholds are intentionally conservative engineering defaults, not manufacturer specifications:

- clock warning at 500 ms absolute offset; sensitive operations blocked at 2,000 ms or unknown time;
- system disk warning below 20% or 50 GiB free; block below 10% or 20 GiB;
- memory warning at 85%; block starting new heavy work at 95%;
- GPU warning at 80 °C and controlled-load abort at 87 °C;
- ACPI zone warning at 85 °C and load abort at 95 °C;
- any lower manufacturer limit takes precedence;
- controlled load duration: minimum 30 min, target 45 min, maximum 60 min.

A later measured/manufacturer-backed adjustment requires a reviewed WP-owned change; thresholds are not silently tuned to make an Exit Gate pass.

## 9. Normal-path tests

- passive collector emits the expected safe schema;
- exact hardware/OS values come from the Lenovo, not assumptions in documentation;
- BitLocker command output is reduced to non-secret protection facts only;
- Windows Time offset is converted into PASS/BLOCK_DRIFT/BLOCK_UNKNOWN_TIME consistently;
- low-space and disk-health rules are deterministic;
- firewall/wired/power facts are deterministic where queryable;
- a fully safe synthetic profile computes `PASS`;
- an initial passive profile with physical tests not yet run remains structurally valid but computes `BLOCKED`.

## 10. Negative tests

- injected serial/MAC/IP/username path/recovery-key field is rejected;
- inconsistent recorded Exit Gate state is rejected;
- BitLocker off/unverified blocks;
- stopped Windows Time blocks even when a numeric offset happens to be available;
- >2 s clock drift blocks;
- low disk blocks;
- disabled firewall or missing wired network blocks;
- missing reboot/network/load evidence blocks;
- no test or documentation may convert an unknown hardware fact into an assumed PASS.

## 11. OWNER participation boundary

Automation must exhaust passive/read-only evidence first. OWNER participation is requested only for an indivisible physical/admin action, for example:

- confirming BitLocker recovery-key custody without disclosing the key;
- reboot/power-loss behavior that cannot be proven remotely without interrupting the machine;
- a controlled 30–60 minute load test if a safe GPU workload generator is unavailable through the accepted local toolchain;
- firmware-only power-loss/battery-conservation settings that Windows cannot read reliably.

OWNER is never asked to paste secrets or recovery-key material into chat/GitHub.

## 12. Binary Exit Gate

WP5 is COMPLETE only when all are true:

- focused WP5 PR is based on accepted current `main`;
- passive collector and validator tests are green;
- factual sanitized `OWNER_NODE_PROFILE` is captured from the Lenovo;
- CPU/RAM/GPU/VRAM/storage/Windows/NVIDIA-driver facts are known;
- disk health/free-space checks pass;
- full-disk encryption and separate recovery-key custody are proven without storing the key;
- Windows Time/UTC/drift guard passes;
- firewall/wired-network baseline passes and no V10 public listener exists;
- battery/AC/restart-after-power-loss facts are acceptable;
- 30–60 minute controlled CPU/GPU load completes without threshold abort or thermal shutdown;
- reboot and network reconnect checks pass;
- exact-head Fast/hosted/authoritative CI is green;
- V9 `app:app` and money-authority invariants are unchanged;
- squash merge lands on `main`;
- post-merge Regression Shield is successful.

Only then may canonical status mark WP5 complete and unlock WP6.
