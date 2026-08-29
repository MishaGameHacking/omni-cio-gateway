from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "package.json"
PACKAGE_LOCK = ROOT / "package-lock.json"
NPMRC = ROOT / ".npmrc"

_EXPECTED_ENGINES = {"node": "24.18.0", "npm": "10.9.2"}
_EXPECTED_PACKAGE_MANAGER = "npm@10.9.2"
_EXPECTED_DEPENDENCIES = {"@cloudflare/containers": "0.3.7"}
_EXPECTED_DEV_DEPENDENCIES = {"wrangler": "4.127.1"}
_FORBIDDEN_LIFECYCLE_SCRIPTS = {
    "preinstall",
    "install",
    "postinstall",
    "prepare",
    "prepublish",
    "prepublishOnly",
}


def _load_object(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"CLOUDFLARE_NODE_SUPPLY_CHAIN_{label}_UNREADABLE") from exc
    if not isinstance(value, dict):
        raise RuntimeError(f"CLOUDFLARE_NODE_SUPPLY_CHAIN_{label}_INVALID")
    return value


def _object(value: object, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise RuntimeError(f"CLOUDFLARE_NODE_SUPPLY_CHAIN_{label}_INVALID")
    return value


def _read_npmrc() -> tuple[str, ...]:
    try:
        lines = NPMRC.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError) as exc:
        raise RuntimeError("CLOUDFLARE_NODE_SUPPLY_CHAIN_NPMRC_UNREADABLE") from exc
    return tuple(line.strip() for line in lines if line.strip())


def validate() -> None:
    package = _load_object(PACKAGE, "PACKAGE")
    if package.get("name") != "omni-cio-v10-cloudflare-delivery":
        raise RuntimeError("CLOUDFLARE_NODE_SUPPLY_CHAIN_PACKAGE_NAME_INVALID")
    if package.get("engines") != _EXPECTED_ENGINES:
        raise RuntimeError("CLOUDFLARE_NODE_SUPPLY_CHAIN_TOOLCHAIN_INVALID")
    if package.get("packageManager") != _EXPECTED_PACKAGE_MANAGER:
        raise RuntimeError("CLOUDFLARE_NODE_SUPPLY_CHAIN_PACKAGE_MANAGER_INVALID")
    if package.get("dependencies") != _EXPECTED_DEPENDENCIES:
        raise RuntimeError("CLOUDFLARE_NODE_SUPPLY_CHAIN_DEPENDENCIES_INVALID")
    if package.get("devDependencies") != _EXPECTED_DEV_DEPENDENCIES:
        raise RuntimeError("CLOUDFLARE_NODE_SUPPLY_CHAIN_DEV_DEPENDENCIES_INVALID")

    scripts = _object(package.get("scripts"), "SCRIPTS")
    forbidden = sorted(_FORBIDDEN_LIFECYCLE_SCRIPTS.intersection(scripts))
    if forbidden:
        raise RuntimeError(
            "CLOUDFLARE_NODE_SUPPLY_CHAIN_LIFECYCLE_SCRIPTS_FORBIDDEN:"
            + ",".join(forbidden)
        )

    if _read_npmrc() != ("ignore-scripts=true",):
        raise RuntimeError("CLOUDFLARE_NODE_SUPPLY_CHAIN_NPMRC_INVALID")

    lock = _load_object(PACKAGE_LOCK, "PACKAGE_LOCK")
    if lock.get("lockfileVersion") != 3 or lock.get("requires") is not True:
        raise RuntimeError("CLOUDFLARE_NODE_SUPPLY_CHAIN_LOCKFILE_VERSION_INVALID")
    if lock.get("name") != package.get("name") or lock.get("version") != package.get(
        "version"
    ):
        raise RuntimeError("CLOUDFLARE_NODE_SUPPLY_CHAIN_LOCK_IDENTITY_INVALID")

    packages = _object(lock.get("packages"), "LOCK_PACKAGES")
    root = _object(packages.get(""), "LOCK_ROOT")
    expected_root = {
        "name": package.get("name"),
        "version": package.get("version"),
        "dependencies": _EXPECTED_DEPENDENCIES,
        "devDependencies": _EXPECTED_DEV_DEPENDENCIES,
        "engines": _EXPECTED_ENGINES,
    }
    for key, expected in expected_root.items():
        if root.get(key) != expected:
            raise RuntimeError(
                f"CLOUDFLARE_NODE_SUPPLY_CHAIN_LOCK_ROOT_{key.upper()}_INVALID"
            )

    containers = _object(
        packages.get("node_modules/@cloudflare/containers"),
        "LOCK_CONTAINERS",
    )
    if containers.get("version") != "0.3.7":
        raise RuntimeError("CLOUDFLARE_NODE_SUPPLY_CHAIN_LOCK_CONTAINERS_INVALID")

    wrangler = _object(packages.get("node_modules/wrangler"), "LOCK_WRANGLER")
    if wrangler.get("version") != "4.127.1":
        raise RuntimeError("CLOUDFLARE_NODE_SUPPLY_CHAIN_LOCK_WRANGLER_INVALID")


def main() -> int:
    try:
        validate()
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print("V10 Cloudflare Node supply-chain contract passed.")
    print("Cloudflare build toolchain: Node 24.18.0 / npm 10.9.2")
    print("Root dependency lock: package-lock v3, exact package versions")
    print("Dependency lifecycle scripts: DISABLED by source-controlled .npmrc")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
