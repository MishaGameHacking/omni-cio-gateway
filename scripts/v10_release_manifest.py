from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from typing import Any, Callable
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "docs" / "architecture" / "V10_RELEASE_MANIFEST.schema.json"
VERSION_RE = re.compile(r"^v10\.[0-9]+\.[0-9]+(?:-[0-9A-Za-z.-]+)?$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
GIT_SHA_RE = re.compile(r"^[0-9a-f]{40}$")


class ManifestError(ValueError):
    pass


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _resolve_ref(schema_root: dict[str, Any], ref: str) -> dict[str, Any]:
    if not ref.startswith("#/"):
        raise ManifestError(f"unsupported external schema ref: {ref}")
    node: Any = schema_root
    for part in ref[2:].split("/"):
        node = node[part.replace("~1", "/").replace("~0", "~")]
    if not isinstance(node, dict):
        raise ManifestError(f"schema ref does not resolve to an object: {ref}")
    return node


def _type_ok(value: Any, expected: str) -> bool:
    if expected == "object":
        return isinstance(value, dict)
    if expected == "array":
        return isinstance(value, list)
    if expected == "string":
        return isinstance(value, str)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "null":
        return value is None
    return False


def _validate_schema_node(
    value: Any,
    schema: dict[str, Any],
    schema_root: dict[str, Any],
    path: str,
    failures: list[str],
) -> None:
    if "$ref" in schema:
        _validate_schema_node(
            value,
            _resolve_ref(schema_root, str(schema["$ref"])),
            schema_root,
            path,
            failures,
        )
        return

    expected = schema.get("type")
    if expected is not None:
        allowed = [expected] if isinstance(expected, str) else list(expected)
        if not any(_type_ok(value, item) for item in allowed):
            failures.append(
                f"{path}: expected type {allowed}, got {type(value).__name__}"
            )
            return

    if "const" in schema and value != schema["const"]:
        failures.append(f"{path}: expected constant {schema['const']!r}")
    if "enum" in schema and value not in schema["enum"]:
        failures.append(f"{path}: value {value!r} is not in {schema['enum']!r}")

    if isinstance(value, str):
        min_length = schema.get("minLength")
        if isinstance(min_length, int) and len(value) < min_length:
            failures.append(f"{path}: string shorter than {min_length}")
        pattern = schema.get("pattern")
        if isinstance(pattern, str) and re.search(pattern, value) is None:
            failures.append(f"{path}: string does not match pattern {pattern}")
        if schema.get("format") == "date-time":
            try:
                parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
                if parsed.tzinfo is None:
                    raise ValueError("timezone required")
            except ValueError:
                failures.append(f"{path}: invalid RFC3339 date-time")

    if isinstance(value, int) and not isinstance(value, bool):
        minimum = schema.get("minimum")
        if isinstance(minimum, (int, float)) and value < minimum:
            failures.append(f"{path}: integer is below minimum {minimum}")

    if isinstance(value, list):
        min_items = schema.get("minItems")
        if isinstance(min_items, int) and len(value) < min_items:
            failures.append(f"{path}: array has fewer than {min_items} items")
        if schema.get("uniqueItems"):
            normalized = [
                json.dumps(item, sort_keys=True, separators=(",", ":"))
                for item in value
            ]
            if len(normalized) != len(set(normalized)):
                failures.append(f"{path}: array items must be unique")
        item_schema = schema.get("items")
        if isinstance(item_schema, dict):
            for index, item in enumerate(value):
                _validate_schema_node(
                    item,
                    item_schema,
                    schema_root,
                    f"{path}[{index}]",
                    failures,
                )

    if isinstance(value, dict):
        required = schema.get("required", [])
        if isinstance(required, list):
            for key in required:
                if key not in value:
                    failures.append(f"{path}: missing required property {key!r}")
        properties = schema.get("properties", {})
        if isinstance(properties, dict):
            for key, child in value.items():
                child_schema = properties.get(key)
                if isinstance(child_schema, dict):
                    _validate_schema_node(
                        child,
                        child_schema,
                        schema_root,
                        f"{path}.{key}",
                        failures,
                    )
                elif schema.get("additionalProperties") is False:
                    failures.append(f"{path}: unexpected property {key!r}")


def validate_against_schema(
    manifest: dict[str, Any], schema: dict[str, Any]
) -> list[str]:
    failures: list[str] = []
    _validate_schema_node(manifest, schema, schema, "$", failures)
    return failures


def _check_digest_entries(
    entries: list[dict[str, Any]], root: Path, label: str, failures: list[str]
) -> None:
    for entry in entries:
        rel = entry.get("path")
        expected = entry.get("sha256")
        if not isinstance(rel, str) or not isinstance(expected, str):
            continue
        target = root / rel
        if not target.is_file():
            failures.append(f"{label}: referenced file does not exist: {rel}")
            continue
        actual = sha256_file(target)
        if actual != expected:
            failures.append(f"{label}: digest mismatch for {rel}: {actual} != {expected}")


def semantic_failures(
    manifest: dict[str, Any],
    root: Path | None = None,
    expected_git_sha: str | None = None,
) -> list[str]:
    failures: list[str] = []
    release_version = manifest.get("release_version")
    release_tag = manifest.get("release_tag")
    git_sha = manifest.get("git_sha")

    if release_version != release_tag:
        failures.append("release_version and release_tag must be identical")
    if not isinstance(release_tag, str) or VERSION_RE.fullmatch(release_tag) is None:
        failures.append("release_tag must use the v10.* release namespace")
    if expected_git_sha is not None and git_sha != expected_git_sha:
        failures.append(
            f"manifest git_sha {git_sha!r} does not match expected {expected_git_sha!r}"
        )

    build = manifest.get("build", {})
    source_ref = build.get("source_ref") if isinstance(build, dict) else None
    if not isinstance(source_ref, str) or not (
        source_ref == "refs/heads/main" or source_ref.startswith("refs/tags/v10.")
    ):
        failures.append("build.source_ref must be refs/heads/main or refs/tags/v10.*")

    evidence = manifest.get("ci_evidence", {})
    if isinstance(evidence, dict):
        ci_runs: list[tuple[str, Any]] = [
            ("authoritative_gate", evidence.get("authoritative_gate")),
            ("regression_shield", evidence.get("regression_shield")),
        ]
        hosted = evidence.get("hosted_compatibility", [])
        if isinstance(hosted, list):
            ci_runs.extend(
                (f"hosted_compatibility[{index}]", item)
                for index, item in enumerate(hosted)
            )
        for label, run in ci_runs:
            if not isinstance(run, dict):
                continue
            if run.get("conclusion") != "success":
                failures.append(f"ci_evidence.{label} must conclude success")
            if run.get("git_sha") != git_sha:
                failures.append(
                    f"ci_evidence.{label}.git_sha must equal manifest git_sha"
                )

    rollback = manifest.get("rollback", {})
    update = manifest.get("update_delivery")
    if isinstance(update, dict):
        minimum = update.get("minimum_supported_version")
        if not isinstance(minimum, str) or VERSION_RE.fullmatch(minimum) is None:
            failures.append("update_delivery.minimum_supported_version must use v10.*")
        if update.get("rollback_target") not in (None, rollback.get("target")):
            failures.append("update_delivery.rollback_target must match rollback.target")
        if update.get("channel") == "STABLE":
            for field in (
                "signed_metadata_ref",
                "signing_identity_ref",
                "metadata_expires_at_utc",
            ):
                if not update.get(field):
                    failures.append(f"STABLE update_delivery requires {field}")
            if update.get("rollback_compatible") is not True:
                failures.append(
                    "STABLE update_delivery requires rollback_compatible=true"
                )
        artifacts = update.get("artifacts", [])
        if isinstance(artifacts, list):
            for index, artifact in enumerate(artifacts):
                if not isinstance(artifact, dict):
                    continue
                digest = artifact.get("sha256")
                if not isinstance(digest, str) or SHA256_RE.fullmatch(digest) is None:
                    failures.append(
                        f"update_delivery.artifacts[{index}].sha256 invalid"
                    )

    ai = manifest.get("ai")
    if isinstance(ai, dict) and ai.get("enabled") is False:
        for field in (
            "base_model",
            "model_digest_sha256",
            "adapter_digest_sha256",
        ):
            if ai.get(field) not in (None, ""):
                failures.append(f"ai.{field} must be null when AI is disabled for WP4")

    if root is not None:
        dependency_locks = manifest.get("dependency_locks", [])
        sbom = manifest.get("sbom", [])
        if isinstance(dependency_locks, list):
            _check_digest_entries(dependency_locks, root, "dependency_locks", failures)
        if isinstance(sbom, list):
            _check_digest_entries(sbom, root, "sbom", failures)

        if isinstance(rollback, dict):
            instructions = rollback.get("instructions_ref")
            if isinstance(instructions, str) and not (root / instructions).is_file():
                failures.append(
                    f"rollback instructions do not exist: {instructions}"
                )

        contracts = manifest.get("contracts", {})
        if isinstance(contracts, dict):
            for field in (
                "api_schema",
                "db_schema",
                "broker_parser",
                "security_policy",
                "program_plan_revision",
            ):
                ref = contracts.get(field)
                if isinstance(ref, str) and not (root / ref).is_file():
                    failures.append(f"contracts.{field} does not exist: {ref}")

        if isinstance(update, dict):
            artifacts = update.get("artifacts", [])
            if isinstance(artifacts, list):
                for artifact in artifacts:
                    if not isinstance(artifact, dict):
                        continue
                    name = artifact.get("name")
                    expected = artifact.get("sha256")
                    if not isinstance(name, str) or not isinstance(expected, str):
                        continue
                    target = root / name
                    if not target.is_file():
                        failures.append(f"update artifact does not exist: {name}")
                    elif sha256_file(target) != expected:
                        failures.append(f"update artifact digest mismatch: {name}")

    return failures


def validate_manifest(
    manifest_path: Path,
    root: Path = ROOT,
    expected_git_sha: str | None = None,
) -> list[str]:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    failures = validate_against_schema(manifest, schema)
    failures.extend(
        semantic_failures(manifest, root=root, expected_git_sha=expected_git_sha)
    )
    return failures


def _parse_requirement_lock(path: Path) -> list[dict[str, str]]:
    components: dict[str, dict[str, str]] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith(("#", "-", "--")):
            continue
        line = line.split(";", 1)[0].strip()
        match = re.match(r"^([A-Za-z0-9_.-]+)==([^\s\\]+)", line)
        if not match:
            continue
        name, version = match.groups()
        key = name.lower().replace("_", "-")
        components[key] = {
            "type": "library",
            "name": name,
            "version": version,
            "purl": f"pkg:pypi/{name}@{version}",
        }
    return [components[key] for key in sorted(components)]


def _parse_npm_lock(path: Path) -> list[dict[str, str]]:
    lock = json.loads(path.read_text(encoding="utf-8"))
    components: dict[str, dict[str, str]] = {}
    packages = lock.get("packages", {})
    if isinstance(packages, dict):
        for package_path, meta in packages.items():
            if (
                not package_path
                or not package_path.startswith("node_modules/")
                or not isinstance(meta, dict)
            ):
                continue
            name = package_path.split("node_modules/", 1)[1]
            version = meta.get("version")
            if not isinstance(version, str):
                continue
            components[f"{name}@{version}"] = {
                "type": "library",
                "name": name,
                "version": version,
                "purl": f"pkg:npm/{name}@{version}",
            }
    return [components[key] for key in sorted(components)]


def _cyclonedx_serial(release_version: str, name: str) -> str:
    raw = hashlib.sha256((release_version + name).encode()).hexdigest()[:32]
    return (
        f"urn:uuid:{raw[:8]}-{raw[8:12]}-{raw[12:16]}-"
        f"{raw[16:20]}-{raw[20:]}"
    )


def write_cyclonedx(
    path: Path, components: list[dict[str, str]], release_version: str
) -> None:
    payload = {
        "bomFormat": "CycloneDX",
        "specVersion": "1.6",
        "serialNumber": _cyclonedx_serial(release_version, path.name),
        "version": 1,
        "metadata": {
            "component": {
                "type": "application",
                "name": "omni-cio-gateway",
                "version": release_version,
            }
        },
        "components": components,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def _digest_entry(path: Path, root: Path) -> dict[str, str]:
    return {"path": path.relative_to(root).as_posix(), "sha256": sha256_file(path)}


def _git_sha(root: Path) -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )
    sha = result.stdout.strip()
    if GIT_SHA_RE.fullmatch(sha) is None:
        raise ManifestError(f"invalid git SHA from repository: {sha!r}")
    return sha


def build_manifest(args: argparse.Namespace) -> dict[str, Any]:
    root = Path(args.root).resolve()
    git_sha = args.git_sha or _git_sha(root)
    if VERSION_RE.fullmatch(args.release_version) is None:
        raise ManifestError("release_version must use v10.* identity")

    python_sbom = Path(args.python_sbom).resolve()
    frontend_sbom = Path(args.frontend_sbom).resolve()
    source_artifact = Path(args.source_artifact).resolve()
    for path in (python_sbom, frontend_sbom, source_artifact):
        if not path.is_file():
            raise ManifestError(f"required release artifact missing: {path}")

    lock_paths = [root / item for item in args.dependency_lock]
    for path in lock_paths:
        if not path.is_file():
            raise ManifestError(f"dependency lock missing: {path}")

    ci_evidence = json.loads(Path(args.ci_evidence).read_text(encoding="utf-8"))
    manifest: dict[str, Any] = {
        "schema_version": "1",
        "release_version": args.release_version,
        "release_tag": args.release_version,
        "git_sha": git_sha,
        "build": {
            "built_at_utc": args.built_at_utc,
            "workflow_name": args.workflow_name,
            "workflow_run_id": int(args.workflow_run_id),
            "source_ref": args.source_ref,
            "builder_class": "hybrid",
        },
        "toolchain": {
            "python": "3.14.6",
            "node": "24.18.0",
            "npm": "11.16.0",
            "os_compatibility": [
                "windows-latest",
                "ubuntu-latest",
                "self-hosted-windows-x64",
            ],
        },
        "dependency_locks": [_digest_entry(path, root) for path in lock_paths],
        "contracts": {
            "api_schema": None,
            "db_schema": None,
            "broker_parser": None,
            "security_policy": "docs/architecture/V10_SECURITY_BOUNDARIES.md",
            "program_plan_revision": "docs/master-plan/OMNI_CIO_V10_PROGRAM_LOCK.md",
        },
        "sbom": [
            {**_digest_entry(python_sbom, root), "format": "cyclonedx-json"},
            {**_digest_entry(frontend_sbom, root), "format": "cyclonedx-json"},
        ],
        "ai": {
            "enabled": False,
            "provider_runtime": None,
            "base_model": None,
            "model_digest_sha256": None,
            "quantization": None,
            "context_tokens": None,
            "policy_version": "WP4-NOT-INSTALLED",
            "adapter_digest_sha256": None,
            "eval_contract": None,
            "eval_result": None,
        },
        "update_delivery": {
            "channel": args.channel,
            "minimum_supported_version": args.minimum_supported_version,
            "artifacts": [
                {
                    "name": source_artifact.relative_to(root).as_posix(),
                    "sha256": sha256_file(source_artifact),
                    "size_bytes": source_artifact.stat().st_size,
                }
            ],
            "signed_metadata_ref": args.signed_metadata_ref or None,
            "signing_identity_ref": args.signing_identity_ref or None,
            "metadata_expires_at_utc": args.metadata_expires_at_utc or None,
            "database_compatibility": "WP4_NO_V10_DATABASE_RUNTIME",
            "api_compatibility": "WP4_V9_APP_APP_UNCHANGED",
            "model_compatibility": "WP4_AI_NOT_INSTALLED",
            "rollback_compatible": True,
            "rollback_target": args.rollback_target,
        },
        "ci_evidence": ci_evidence,
        "bootstrap": {
            "version": None,
            "compatibility": "WP4_CONTRACT_ONLY_NO_NODE_RUNTIME",
            "recovery_contract_version": None,
        },
        "rollback": {
            "target": args.rollback_target,
            "instructions_ref": "docs/architecture/V10_V9_BASELINE_FREEZE.md",
            "database_constraints": "NOT_APPLICABLE_WP4",
            "ai_rollback": "NOT_APPLICABLE_WP4",
        },
    }
    return manifest


def github_json(url: str, token: str) -> dict[str, Any]:
    request = Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "omni-cio-v10-release-provenance",
        },
    )
    with urlopen(request, timeout=30) as response:  # nosec B310 - fixed GitHub API base
        payload = json.load(response)
    if not isinstance(payload, dict):
        raise ManifestError(f"unexpected GitHub API response for {url}")
    return payload


def _verify_run(
    repository: str,
    run_id: int,
    expected_sha: str,
    expected_workflow: str,
    token: str,
    required_job: str | None = None,
    fetcher: Callable[[str, str], dict[str, Any]] = github_json,
) -> dict[str, Any]:
    base = f"https://api.github.com/repos/{repository}/actions/runs/{run_id}"
    run = fetcher(base, token)
    if run.get("name") != expected_workflow:
        raise ManifestError(
            f"run {run_id} workflow mismatch: {run.get('name')!r} != "
            f"{expected_workflow!r}"
        )
    if run.get("head_sha") != expected_sha:
        raise ManifestError(f"run {run_id} head_sha does not match release SHA")
    if run.get("conclusion") != "success":
        raise ManifestError(f"run {run_id} conclusion is not success")
    if required_job is not None:
        jobs = fetcher(base + "/jobs?per_page=100", token)
        rows = jobs.get("jobs", [])
        matched = [
            row
            for row in rows
            if isinstance(row, dict)
            and row.get("name") == required_job
            and row.get("conclusion") == "success"
        ]
        if not matched:
            raise ManifestError(
                f"run {run_id} is missing successful required job {required_job!r}"
            )
    return {
        "workflow": expected_workflow,
        "run_id": run_id,
        "conclusion": "success",
        "git_sha": expected_sha,
    }


def build_ci_evidence(args: argparse.Namespace) -> dict[str, Any]:
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        raise ManifestError("GITHUB_TOKEN is required for CI evidence verification")
    authoritative = _verify_run(
        args.repository,
        int(args.authoritative_run_id),
        args.git_sha,
        "Self-Hosted Windows CI",
        token,
        required_job="V10 authoritative merge gate",
    )
    regression = _verify_run(
        args.repository,
        int(args.regression_run_id),
        args.git_sha,
        "Regression Shield",
        token,
    )
    hosted = _verify_run(
        args.repository,
        int(args.hosted_run_id),
        args.git_sha,
        "V10 Toolchain Compatibility",
        token,
    )
    return {
        "authoritative_gate": authoritative,
        "hosted_compatibility": [hosted],
        "regression_shield": regression,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Omni-CIO V10 release provenance")
    sub = parser.add_subparsers(dest="command", required=True)

    validate = sub.add_parser("validate")
    validate.add_argument("manifest")
    validate.add_argument("--root", default=str(ROOT))
    validate.add_argument("--expected-git-sha")

    sbom = sub.add_parser("generate-sbom")
    sbom.add_argument("--release-version", required=True)
    sbom.add_argument("--python-lock", required=True)
    sbom.add_argument("--npm-lock", required=True)
    sbom.add_argument("--python-output", required=True)
    sbom.add_argument("--frontend-output", required=True)

    ci = sub.add_parser("verify-ci")
    ci.add_argument("--repository", required=True)
    ci.add_argument("--git-sha", required=True)
    ci.add_argument("--authoritative-run-id", required=True)
    ci.add_argument("--regression-run-id", required=True)
    ci.add_argument("--hosted-run-id", required=True)
    ci.add_argument("--output", required=True)

    generate = sub.add_parser("generate")
    generate.add_argument("--root", default=str(ROOT))
    generate.add_argument("--release-version", required=True)
    generate.add_argument("--git-sha")
    generate.add_argument("--built-at-utc", required=True)
    generate.add_argument("--workflow-name", required=True)
    generate.add_argument("--workflow-run-id", required=True)
    generate.add_argument("--source-ref", required=True)
    generate.add_argument("--dependency-lock", action="append", required=True)
    generate.add_argument("--python-sbom", required=True)
    generate.add_argument("--frontend-sbom", required=True)
    generate.add_argument("--source-artifact", required=True)
    generate.add_argument("--ci-evidence", required=True)
    generate.add_argument("--rollback-target", required=True)
    generate.add_argument(
        "--channel", choices=["INTERNAL", "STAGING", "STABLE"], required=True
    )
    generate.add_argument("--minimum-supported-version", required=True)
    generate.add_argument("--signed-metadata-ref")
    generate.add_argument("--signing-identity-ref")
    generate.add_argument("--metadata-expires-at-utc")
    generate.add_argument("--output", required=True)

    args = parser.parse_args(argv)
    try:
        if args.command == "validate":
            failures = validate_manifest(
                Path(args.manifest),
                root=Path(args.root).resolve(),
                expected_git_sha=args.expected_git_sha,
            )
            if failures:
                for failure in failures:
                    print(f"- {failure}", file=sys.stderr)
                return 1
            print("V10 release manifest validation passed.")
            return 0

        if args.command == "generate-sbom":
            if VERSION_RE.fullmatch(args.release_version) is None:
                raise ManifestError("release-version must use v10.*")
            write_cyclonedx(
                Path(args.python_output),
                _parse_requirement_lock(Path(args.python_lock)),
                args.release_version,
            )
            write_cyclonedx(
                Path(args.frontend_output),
                _parse_npm_lock(Path(args.npm_lock)),
                args.release_version,
            )
            return 0

        if args.command == "verify-ci":
            if GIT_SHA_RE.fullmatch(args.git_sha) is None:
                raise ManifestError("git-sha must be a 40-character lowercase SHA")
            evidence = build_ci_evidence(args)
            output = Path(args.output)
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(
                json.dumps(evidence, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            return 0

        if args.command == "generate":
            manifest = build_manifest(args)
            output = Path(args.output)
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(
                json.dumps(manifest, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            failures = validate_manifest(
                output,
                root=Path(args.root).resolve(),
                expected_git_sha=manifest["git_sha"],
            )
            if failures:
                output.unlink(missing_ok=True)
                raise ManifestError("; ".join(failures))
            return 0
    except (
        OSError,
        json.JSONDecodeError,
        KeyError,
        ManifestError,
        subprocess.CalledProcessError,
    ) as exc:
        print(f"V10 release provenance failed: {exc}", file=sys.stderr)
        return 1
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
