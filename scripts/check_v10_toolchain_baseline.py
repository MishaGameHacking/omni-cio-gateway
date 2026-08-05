from __future__ import annotations

import json
from pathlib import Path
import re
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
BASELINE_PATH = ROOT / "docs" / "architecture" / "V10_TOOLCHAIN_BASELINE.json"
PACKAGE_ROOT = ROOT / "tests" / "toolchain" / "frontend"
PACKAGE_JSON_PATH = PACKAGE_ROOT / "package.json"
PACKAGE_LOCK_PATH = PACKAGE_ROOT / "package-lock.json"
REQUIREMENTS_IN = ROOT / "requirements.in"

EXACT_REQUIREMENT = re.compile(
    r"^(?P<name>[A-Za-z0-9_.-]+)(?:\[[^\]]+\])?==(?P<version>[^;\s]+)"
)
FORBIDDEN_DIRECT_VERSION_PREFIXES = ("^", "~", ">", "<", "=", "*", "latest")


def _load_json(path: Path, failures: list[str]) -> dict[str, Any]:
    if not path.is_file():
        failures.append(f"missing required JSON file: {path.relative_to(ROOT)}")
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        failures.append(f"invalid JSON in {path.relative_to(ROOT)}: {exc}")
        return {}
    if not isinstance(value, dict):
        failures.append(f"JSON root must be an object: {path.relative_to(ROOT)}")
        return {}
    return value


def _normalized(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def _requirements_pins(failures: list[str]) -> dict[str, str]:
    pins: dict[str, str] = {}
    if not REQUIREMENTS_IN.is_file():
        failures.append("missing requirements.in")
        return pins
    for line_number, raw in enumerate(
        REQUIREMENTS_IN.read_text(encoding="utf-8").splitlines(), start=1
    ):
        line = raw.strip()
        if not line or line.startswith("#") or line.startswith(("--", "-r ", "-c ")):
            continue
        match = EXACT_REQUIREMENT.match(line)
        if match is None:
            failures.append(
                f"requirements.in:{line_number} must use an exact == direct pin: {line}"
            )
            continue
        pins[_normalized(match.group("name"))] = match.group("version")
    return pins


def validate_python_baseline(baseline: dict[str, Any], failures: list[str]) -> None:
    backend = baseline.get("backend")
    if not isinstance(backend, dict):
        failures.append("toolchain baseline is missing backend object")
        return
    if backend.get("python") != "3.14.6":
        failures.append("selected V10 Python baseline must be exactly 3.14.6")

    pins = _requirements_pins(failures)
    expected = {
        "fastapi": backend.get("fastapi"),
        "uvicorn": backend.get("uvicorn"),
        "httpx": backend.get("httpx"),
        "t-tech-investments": backend.get("t_tech_investments"),
    }
    for name, version in expected.items():
        if not isinstance(version, str) or not version:
            failures.append(f"toolchain baseline is missing backend version: {name}")
            continue
        if pins.get(name) != version:
            failures.append(
                f"requirements.in {name} pin {pins.get(name)!r} != V10 baseline {version!r}"
            )


def _require_exact_direct_version(
    package_name: str, version: Any, failures: list[str]
) -> None:
    if not isinstance(version, str) or not version:
        failures.append(
            f"frontend direct dependency has invalid version: {package_name}"
        )
        return
    if version.lower() == "latest" or version.startswith(
        FORBIDDEN_DIRECT_VERSION_PREFIXES[:-1]
    ):
        failures.append(
            f"frontend direct dependency must use exact version: {package_name}={version}"
        )
    if any(
        token in version
        for token in ("git+", "github:", "file:", "http://", "https://")
    ):
        failures.append(
            f"frontend direct dependency uses unreviewed source: {package_name}={version}"
        )


def validate_frontend_baseline(baseline: dict[str, Any], failures: list[str]) -> None:
    frontend = baseline.get("frontend")
    if not isinstance(frontend, dict):
        failures.append("toolchain baseline is missing frontend object")
        return

    package = _load_json(PACKAGE_JSON_PATH, failures)
    lock = _load_json(PACKAGE_LOCK_PATH, failures)
    if not package or not lock:
        return

    expected_fields = {
        ("dependencies", "react"): "react",
        ("dependencies", "react-dom"): "react_dom",
        ("devDependencies", "vite"): "vite",
        ("devDependencies", "@vitejs/plugin-react"): "vite_plugin_react",
        ("devDependencies", "typescript"): "typescript",
        ("devDependencies", "@types/node"): "types_node",
        ("devDependencies", "@types/react"): "types_react",
        ("devDependencies", "@types/react-dom"): "types_react_dom",
    }
    for (group, package_name), baseline_name in expected_fields.items():
        group_value = package.get(group)
        actual = (
            group_value.get(package_name) if isinstance(group_value, dict) else None
        )
        expected = frontend.get(baseline_name)
        if actual != expected:
            failures.append(
                f"package.json {group}.{package_name}={actual!r} != baseline {expected!r}"
            )

    for group in ("dependencies", "devDependencies"):
        group_value = package.get(group, {})
        if not isinstance(group_value, dict):
            failures.append(f"package.json {group} must be an object")
            continue
        for package_name, version in sorted(group_value.items()):
            _require_exact_direct_version(package_name, version, failures)

    engines = package.get("engines")
    if not isinstance(engines, dict):
        failures.append("package.json engines must be an object")
    else:
        if engines.get("node") != frontend.get("node"):
            failures.append("package.json Node engine does not match V10 baseline")
        if engines.get("npm") != frontend.get("npm"):
            failures.append("package.json npm engine does not match V10 baseline")
    if package.get("packageManager") != f"npm@{frontend.get('npm')}":
        failures.append("package.json packageManager does not match V10 baseline")

    if lock.get("lockfileVersion") != frontend.get("lockfile_version"):
        failures.append("package-lock.json lockfileVersion does not match V10 baseline")
    lock_packages = lock.get("packages")
    if not isinstance(lock_packages, dict):
        failures.append("package-lock.json packages must be an object")
        return
    root_entry = lock_packages.get("")
    if not isinstance(root_entry, dict):
        failures.append("package-lock.json is missing root package entry")
        return
    for group in ("dependencies", "devDependencies", "engines"):
        if root_entry.get(group) != package.get(group):
            failures.append(f"package-lock root {group} does not match package.json")

    allowed_registry = baseline.get("registry_policy", {}).get("npm")
    allowed_licenses = baseline.get("allowed_frontend_licenses")
    if not isinstance(allowed_registry, str) or not allowed_registry.startswith(
        "https://"
    ):
        failures.append("V10 npm registry policy must be an HTTPS URL")
        allowed_registry = ""
    if not isinstance(allowed_licenses, list) or not all(
        isinstance(item, str) for item in allowed_licenses
    ):
        failures.append("allowed_frontend_licenses must be a string array")
        allowed_license_set: set[str] = set()
    else:
        allowed_license_set = set(allowed_licenses)

    for path, metadata in sorted(lock_packages.items()):
        if not path.startswith("node_modules/"):
            continue
        if not isinstance(metadata, dict):
            failures.append(f"invalid package-lock metadata for {path}")
            continue
        resolved = metadata.get("resolved")
        if (
            isinstance(resolved, str)
            and allowed_registry
            and not resolved.startswith(allowed_registry)
        ):
            failures.append(f"unapproved npm registry/source for {path}: {resolved}")
        license_name = metadata.get("license")
        if not isinstance(license_name, str) or not license_name:
            failures.append(f"package-lock dependency has no license metadata: {path}")
        elif allowed_license_set and license_name not in allowed_license_set:
            failures.append(
                f"package-lock dependency has unapproved license {license_name}: {path}"
            )


def validate_database_baseline(baseline: dict[str, Any], failures: list[str]) -> None:
    database = baseline.get("database")
    if not isinstance(database, dict):
        failures.append("toolchain baseline is missing database object")
        return
    if database.get("postgresql_major") != 18:
        failures.append("V10 PostgreSQL major baseline must be 18")
    if database.get("tested_patch") != "18.4":
        failures.append("V10 PostgreSQL tested patch baseline must be 18.4")


def main() -> int:
    failures: list[str] = []
    baseline = _load_json(BASELINE_PATH, failures)
    if baseline:
        validate_python_baseline(baseline, failures)
        validate_frontend_baseline(baseline, failures)
        validate_database_baseline(baseline, failures)

    if failures:
        print("V10 toolchain baseline check failed:", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1

    print("V10 toolchain baseline check passed.")
    print("Python: 3.14.6")
    print("Node.js/npm: 24.18.0 / 11.16.0")
    print("Frontend lock: exact direct versions + package-lock v3")
    print("PostgreSQL: 18 / tested patch 18.4")
    print("Frontend registry/license policy: verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
