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
_EXPECTED_DEV_DEPENDENCIES = {"npm": "11.16.0", "wrangler": "4.127.1"}
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
    except (OSError, ValueError) as exc:
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


def _require_equal(actual: object, expected: object, code: str) -> None:
    if actual != expected:
        raise RuntimeError(code)


def _validate_package(package: dict[str, Any]) -> None:
    expected = (
        (
            "name",
            "omni-cio-v10-cloudflare-delivery",
            "CLOUDFLARE_NODE_SUPPLY_CHAIN_PACKAGE_NAME_INVALID",
        ),
        (
            "engines",
            _EXPECTED_ENGINES,
            "CLOUDFLARE_NODE_SUPPLY_CHAIN_TOOLCHAIN_INVALID",
        ),
        (
            "packageManager",
            _EXPECTED_PACKAGE_MANAGER,
            "CLOUDFLARE_NODE_SUPPLY_CHAIN_PACKAGE_MANAGER_INVALID",
        ),
        (
            "dependencies",
            _EXPECTED_DEPENDENCIES,
            "CLOUDFLARE_NODE_SUPPLY_CHAIN_DEPENDENCIES_INVALID",
        ),
        (
            "devDependencies",
            _EXPECTED_DEV_DEPENDENCIES,
            "CLOUDFLARE_NODE_SUPPLY_CHAIN_DEV_DEPENDENCIES_INVALID",
        ),
    )
    for key, value, code in expected:
        _require_equal(package.get(key), value, code)

    scripts = _object(package.get("scripts"), "SCRIPTS")
    forbidden = sorted(_FORBIDDEN_LIFECYCLE_SCRIPTS.intersection(scripts))
    if forbidden:
        raise RuntimeError(
            "CLOUDFLARE_NODE_SUPPLY_CHAIN_LIFECYCLE_SCRIPTS_FORBIDDEN:"
            + ",".join(forbidden)
        )
    _require_equal(
        _read_npmrc(),
        ("ignore-scripts=true",),
        "CLOUDFLARE_NODE_SUPPLY_CHAIN_NPMRC_INVALID",
    )


def _validate_lock_identity(lock: dict[str, Any], package: dict[str, Any]) -> None:
    if (lock.get("lockfileVersion"), lock.get("requires")) != (3, True):
        raise RuntimeError("CLOUDFLARE_NODE_SUPPLY_CHAIN_LOCKFILE_VERSION_INVALID")
    if (lock.get("name"), lock.get("version")) != (
        package.get("name"),
        package.get("version"),
    ):
        raise RuntimeError("CLOUDFLARE_NODE_SUPPLY_CHAIN_LOCK_IDENTITY_INVALID")


def _validate_lock_root(packages: dict[str, Any], package: dict[str, Any]) -> None:
    root = _object(packages.get(""), "LOCK_ROOT")
    expected = {
        "name": package.get("name"),
        "version": package.get("version"),
        "dependencies": _EXPECTED_DEPENDENCIES,
        "devDependencies": _EXPECTED_DEV_DEPENDENCIES,
        "engines": _EXPECTED_ENGINES,
    }
    for key, value in expected.items():
        _require_equal(
            root.get(key),
            value,
            f"CLOUDFLARE_NODE_SUPPLY_CHAIN_LOCK_ROOT_{key.upper()}_INVALID",
        )


def _validate_locked_versions(packages: dict[str, Any]) -> None:
    locked = (
        (
            "node_modules/@cloudflare/containers",
            "LOCK_CONTAINERS",
            "0.3.7",
            "CLOUDFLARE_NODE_SUPPLY_CHAIN_LOCK_CONTAINERS_INVALID",
        ),
        (
            "node_modules/npm",
            "LOCK_NPM_BOOTSTRAP",
            "11.16.0",
            "CLOUDFLARE_NODE_SUPPLY_CHAIN_LOCK_NPM_BOOTSTRAP_INVALID",
        ),
        (
            "node_modules/wrangler",
            "LOCK_WRANGLER",
            "4.127.1",
            "CLOUDFLARE_NODE_SUPPLY_CHAIN_LOCK_WRANGLER_INVALID",
        ),
    )
    for path, label, version, code in locked:
        package = _object(packages.get(path), label)
        _require_equal(package.get("version"), version, code)


def validate() -> None:
    package = _load_object(PACKAGE, "PACKAGE")
    _validate_package(package)
    lock = _load_object(PACKAGE_LOCK, "PACKAGE_LOCK")
    _validate_lock_identity(lock, package)
    packages = _object(lock.get("packages"), "LOCK_PACKAGES")
    _validate_lock_root(packages, package)
    _validate_locked_versions(packages)


def main() -> int:
    try:
        validate()
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print("V10 Cloudflare Node supply-chain contract passed.")
    print("Cloudflare provider package manager: Node 24.18.0 / npm 10.9.2")
    print("Frontend bootstrap npm: 11.16.0, exact lock entry required")
    print("Root dependency lock: package-lock v3, exact package versions")
    print("Dependency lifecycle scripts: DISABLED by source-controlled .npmrc")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
