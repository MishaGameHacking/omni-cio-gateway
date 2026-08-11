from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
BASELINE_PATH = ROOT / "docs" / "architecture" / "V10_TOOLCHAIN_BASELINE.json"
WEB_ROOT = ROOT / "apps" / "web"
FORBIDDEN_DIRECT_VERSION_PREFIXES = ("^", "~", ">", "<", "=", "*", "latest")
REQUIRED_SCRIPTS = (
    "preview",
    "typecheck",
    "lint",
    "test",
    "build",
    "e2e",
    "e2e:browser",
)


def _load_json(path: Path, failures: list[str]) -> dict[str, Any]:
    if not path.is_file():
        failures.append(f"missing required JSON file: {path}")
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        failures.append(f"invalid JSON in {path}: {exc}")
        return {}
    if not isinstance(value, dict):
        failures.append(f"JSON root must be an object: {path}")
        return {}
    return value


def _require_exact_direct_version(
    package_name: str, version: Any, failures: list[str]
) -> None:
    if not isinstance(version, str) or not version:
        failures.append(f"Web direct dependency has invalid version: {package_name}")
        return
    lowered = version.lower()
    if lowered == "latest" or version.startswith(
        FORBIDDEN_DIRECT_VERSION_PREFIXES[:-1]
    ):
        failures.append(
            f"Web direct dependency must use exact version: {package_name}={version}"
        )
    if any(
        marker in lowered
        for marker in ("git+", "github:", "file:", "http://", "https://")
    ):
        failures.append(
            f"Web direct dependency uses unreviewed source: {package_name}={version}"
        )


def validate_web(root: Path, baseline: dict[str, Any], failures: list[str]) -> None:
    web = root / "apps" / "web"
    package_path = web / "package.json"
    lock_path = web / "package-lock.json"
    package = _load_json(package_path, failures)
    lock = _load_json(lock_path, failures)
    if not package or not lock:
        return

    frontend = baseline.get("frontend")
    if not isinstance(frontend, dict):
        failures.append("toolchain baseline is missing frontend object")
        return

    scripts = package.get("scripts")
    if not isinstance(scripts, dict):
        failures.append("apps/web/package.json scripts must be an object")
        scripts = {}
    for name in REQUIRED_SCRIPTS:
        value = scripts.get(name)
        if not isinstance(value, str) or not value.strip():
            failures.append(f"apps/web requires deterministic `{name}` script")

    expected = {
        ("dependencies", "react"): "react",
        ("dependencies", "react-dom"): "react_dom",
        ("devDependencies", "vite"): "vite",
        ("devDependencies", "@vitejs/plugin-react"): "vite_plugin_react",
        ("devDependencies", "typescript"): "typescript",
        ("devDependencies", "@types/node"): "types_node",
        ("devDependencies", "@types/react"): "types_react",
        ("devDependencies", "@types/react-dom"): "types_react_dom",
        ("devDependencies", "@playwright/test"): "playwright_test",
    }
    for (group, package_name), baseline_name in expected.items():
        group_value = package.get(group)
        actual = (
            group_value.get(package_name) if isinstance(group_value, dict) else None
        )
        baseline_value = frontend.get(baseline_name)
        if actual != baseline_value:
            failures.append(
                f"apps/web package.json {group}.{package_name}={actual!r} "
                f"!= baseline {baseline_value!r}"
            )

    for group in ("dependencies", "devDependencies"):
        group_value = package.get(group)
        if not isinstance(group_value, dict):
            failures.append(f"apps/web package.json {group} must be an object")
            continue
        for package_name, version in sorted(group_value.items()):
            _require_exact_direct_version(package_name, version, failures)

    engines = package.get("engines")
    if not isinstance(engines, dict):
        failures.append("apps/web package.json engines must be an object")
    else:
        if engines.get("node") != frontend.get("node"):
            failures.append("apps/web Node engine does not match V10 baseline")
        if engines.get("npm") != frontend.get("npm"):
            failures.append("apps/web npm engine does not match V10 baseline")
    if package.get("packageManager") != f"npm@{frontend.get('npm')}":
        failures.append("apps/web packageManager does not match V10 baseline")

    if lock.get("lockfileVersion") != frontend.get("lockfile_version"):
        failures.append("apps/web package-lock lockfileVersion does not match baseline")
    packages = lock.get("packages")
    if not isinstance(packages, dict):
        failures.append("apps/web package-lock packages must be an object")
        return
    root_entry = packages.get("")
    if not isinstance(root_entry, dict):
        failures.append("apps/web package-lock is missing root package entry")
        return
    for group in ("dependencies", "devDependencies", "engines"):
        if root_entry.get(group) != package.get(group):
            failures.append(f"apps/web package-lock root {group} != package.json")

    allowed_registry = baseline.get("registry_policy", {}).get("npm")
    licenses = baseline.get("allowed_frontend_licenses")
    if not isinstance(allowed_registry, str) or not allowed_registry.startswith(
        "https://"
    ):
        failures.append("V10 npm registry policy must be an HTTPS URL")
        allowed_registry = ""
    allowed_licenses = set(licenses) if isinstance(licenses, list) else set()
    if not allowed_licenses or not all(
        isinstance(item, str) for item in allowed_licenses
    ):
        failures.append("allowed_frontend_licenses must be a non-empty string array")
        allowed_licenses = set()

    for path, metadata in sorted(packages.items()):
        if not path.startswith("node_modules/"):
            continue
        if not isinstance(metadata, dict):
            failures.append(f"invalid apps/web lock metadata for {path}")
            continue
        resolved = metadata.get("resolved")
        if (
            isinstance(resolved, str)
            and allowed_registry
            and not resolved.startswith(allowed_registry)
        ):
            failures.append(f"unapproved Web npm source for {path}: {resolved}")
        license_name = metadata.get("license")
        if not isinstance(license_name, str) or not license_name:
            failures.append(f"apps/web lock dependency has no license: {path}")
        elif allowed_licenses and license_name not in allowed_licenses:
            failures.append(
                f"apps/web lock dependency has unapproved license {license_name}: {path}"
            )

    required_paths = (
        web / "playwright.config.ts",
        web / "scripts" / "lint.mjs",
        web / "scripts" / "run-e2e.mjs",
    )
    for path in required_paths:
        if not path.is_file():
            failures.append(f"apps/web is missing required test/build contract: {path}")
    if not list((web / "e2e").glob("*.spec.ts")) and not list(
        (web / "e2e").glob("*.spec.tsx")
    ):
        failures.append("apps/web requires Playwright browser specs")


def main() -> int:
    failures: list[str] = []
    baseline = _load_json(BASELINE_PATH, failures)
    if baseline:
        validate_web(ROOT, baseline, failures)
    if failures:
        print("V10 Web baseline check failed:", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1
    print("V10 Web baseline check passed.")
    print("Web root: apps/web")
    print("Lock: package-lock v3 / exact direct pins / approved registry+licenses")
    print("Browser evidence: exact Playwright Test pin + bounded harness")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
