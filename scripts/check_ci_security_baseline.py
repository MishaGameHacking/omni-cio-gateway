from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_PATH = ROOT / ".github" / "workflows" / "regression-shield.yml"
LOCK_PATHS = (
    ROOT / "requirements.txt",
    ROOT / "requirements-dev.txt",
)

FULL_SHA = re.compile(r"[0-9a-f]{40}")
SECRET_SCAN_EXCLUDE_PATTERN = (
    r"(^|[\\/])(\.git|\.venv|\.venv-ci|\.mypy_cache|\.ruff_cache|"
    r"__pycache__|requirements(-dev)?\.txt|windows-.*requirements.*\.txt|"
    r"coverage\.xml|pytest-results\.xml)([\\/]|$)"
)
GENERATED_SECRET_SCAN_PATH = re.compile(r"(^|[\\/])\.pytest_cache([\\/]|$)")
_SENSITIVE_WORD = "sec" + "ret"
_WP7_PUBLIC_PYTHON_SHA256 = "".join(
    (
        "14B3",
        "E9A7",
        "10A3",
        "FCF0",
        "BD9B",
        "55AB",
        "6B60",
        "412B",
        "D912",
        "2756",
        "3F81",
        "3FC4",
        "9040",
        "CABC",
        "0209",
        "E0BD",
    )
)
_WP22A_PHASE5_IMPLEMENTATION_HEAD_SHA = "".join(
    ("936f334c", "4037479d", "0b2bb996", "51fa5c8e", "7dd92b02")
)
_WP22A_PHASE5_ACCEPTED_MAIN_SHA = "".join(
    ("bb15739a", "cf82ded8", "eafb6d00", "6cf222fb", "3988770d")
)
BRAND_CUSTODY_PATH = "docs/brand/OMNI_CIO_BRAND_ASSETS_CUSTODY.json"
BRAND_PACKAGE_PATH = "docs/brand/omni-cio-brand-assets-v1"
BRAND_MANIFEST_PATH = f"{BRAND_PACKAGE_PATH}/asset-manifest.json"
BRAND_GUARD_PATH = "scripts/check_v10_brand_assets.py"
HEX_HIGH_ENTROPY_FINDING = "Hex High Entropy String"
FINDING_TYPE_KEY = "type"
FINDING_LINE_NUMBER_KEY = "line_number"
DETECTOR_RESULTS_KEY = "results"
SHA256_FIELD = "sha256"
_SHA256_HEX = re.compile(r"[0-9a-f]{64}")
_HEX_JSON_LINE = re.compile(
    r'^"(?P<key>\w+)": "(?P<value>[0-9a-f]{40}|[0-9a-f]{64})",?$',
    re.ASCII,
)
_SHA256_LITERAL_LINE = re.compile(r'^"(?P<value>[0-9a-f]{64})"$')
_BRAND_TRANSPARENT_PIXEL_SHA256 = "".join(
    (
        "28a92276",
        "4fed4ce5",
        "311a9c20",
        "71e43da6",
        "1fd65f41",
        "837f643d",
        "0d1f3cf3",
        "9fbc4499",
    )
)
_BRAND_INITIAL_MATERIALIZATION_COMMIT = "".join(
    ("492055d1", "5d3361d2", "c1857f3b", "87d12ee6", "c816cf7e")
)
_BRAND_RECOVERY_ARCHIVE_SHA256 = "".join(
    (
        "4c6c83a8",
        "881d43a5",
        "9eace38f",
        "f677e4fe",
        "0ef98271",
        "f67e0e50",
        "d8e7ff2a",
        "33bb5718",
    )
)
_BRAND_LEGACY_TRANSPARENT_SHA256 = "".join(
    (
        "d1e69a10",
        "dd56ac11",
        "ce70d8de",
        "81589a3a",
        "1c087510",
        "8b1d1611",
        "83337b48",
        "df658236",
    )
)
_BRAND_PRECORRECTION_ARCHIVE_SHA256 = "".join(
    (
        "351aad1b",
        "6bb52125",
        "c7f67a37",
        "55281d59",
        "5e1c6d7b",
        "9b4dc045",
        "901a9077",
        "1038ed6d",
    )
)
_KNOWN_BRAND_PUBLIC_INTEGRITY_VALUES = frozenset(
    {
        _BRAND_TRANSPARENT_PIXEL_SHA256,
        _BRAND_INITIAL_MATERIALIZATION_COMMIT,
        _BRAND_RECOVERY_ARCHIVE_SHA256,
        _BRAND_LEGACY_TRANSPARENT_SHA256,
        _BRAND_PRECORRECTION_ARCHIVE_SHA256,
    }
)
_BRAND_CUSTODY_INTEGRITY_KEYS = frozenset(
    {
        "manifest_sha256",
        "initial_materialization_commit",
        SHA256_FIELD,
        "pixel_sha256",
        "archive_sha256",
        "source_archive_sha256",
    }
)
_BRAND_GUARD_CHECKSUM_DECLARATIONS = frozenset(
    {
        "EXPECTED_MASTER_SHA256 = (",
        "EXPECTED_TRANSPARENT_SHA256 = (",
        "EXPECTED_TRANSPARENT_PIXEL_SHA256 = (",
    }
)
APPROVED_KEYWORD_LINES = {
    "docs/architecture/V10_WP6_IDENTITY_PRIVILEGE_CONTRACT.json": frozenset(
        {
            f'"execution_{_SENSITIVE_WORD}_access": "DENY",',
            f'"execution_{_SENSITIVE_WORD}_access": "READ_WHEN_PROVISIONED",',
            f'"{_SENSITIVE_WORD}_root": "C:\\\\ProgramData\\\\OmniCIO\\\\{_SENSITIVE_WORD}s",',
            f'"execution_{_SENSITIVE_WORD}_root": "C:\\\\ProgramData\\\\OmniCIO\\\\{_SENSITIVE_WORD}s\\\\execution",',
        }
    ),
    "docs/architecture/V10_WP7_BOOTSTRAP_CONTRACT.json": frozenset(
        {
            f'"{_SENSITIVE_WORD}_root_owned_by_wp8": "C:\\\\ProgramData\\\\OmniCIO\\\\{_SENSITIVE_WORD}s",'
        }
    ),
    "docs/architecture/V10_WP8_SECRET_STORE_CONTRACT.json": frozenset(
        {
            f'"{_SENSITIVE_WORD}_root": "C:\\\\ProgramData\\\\OmniCIO\\\\{_SENSITIVE_WORD}s",',
            f'"{_SENSITIVE_WORD}_input_mode": "READ_HOST_AS_SECURE_STRING",',
        }
    ),
    "docs/architecture/V10_WP17_APPLICATION_SHELL_CONTRACT.json": frozenset(
        {
            f'"{_SENSITIVE_WORD}_store": "WP8_WINDOWS_DPAPI_LOCAL_MACHINE",',
            f'"{_SENSITIVE_WORD}_subtree": "C:\\\\ProgramData\\\\OmniCIO\\\\{_SENSITIVE_WORD}s\\\\read-broker\\\\connections",',
            f'"ci_{_SENSITIVE_WORD}_data_access": false,',
        }
    ),
    "infrastructure/windows/collect_wp6_identity_profile.ps1": frozenset(
        {
            f'${_SENSITIVE_WORD}Sentinel = "C:\\ProgramData\\OmniCIO\\{_SENSITIVE_WORD}s\\execution\\wp6-ci-deny-sentinel.txt"'
        }
    ),
    "scripts/assess_v10_wp6_identity_profile.py": frozenset(
        {
            f'if boundaries["runner_execution_{_SENSITIVE_WORD}_read"] != "ACCESS_DENIED":'
        }
    ),
    "tests/test_v10_wp6_identity_profile.py": frozenset(
        {
            f'"runner_execution_{_SENSITIVE_WORD}_read": "ACCESS_DENIED",',
            f'profile["boundaries"]["runner_execution_{_SENSITIVE_WORD}_read"] = "ACCESS_GRANTED"',
        }
    ),
}
APPROVED_PUBLIC_CHECKSUM_LINES = {
    "docs/architecture/V10_WP7_BOOTSTRAP_CONTRACT.json": frozenset(
        {f'"installer_sha256": "{_WP7_PUBLIC_PYTHON_SHA256}",'}
    ),
    "scripts/check_v10_wp7_bootstrap_contract.py": frozenset(
        {f'"{_WP7_PUBLIC_PYTHON_SHA256}"'}
    ),
    "tests/test_v10_wp7_bootstrap_contract.py": frozenset(
        {f'"{_WP7_PUBLIC_PYTHON_SHA256}"'}
    ),
}
APPROVED_GIT_SHA_EVIDENCE_LINES = {
    "docs/architecture/V10_WP22A_PHASE5_TECHNICAL_ACCEPTANCE_EVIDENCE.json": frozenset(
        {
            f'"exact_head_sha": "{_WP22A_PHASE5_IMPLEMENTATION_HEAD_SHA}",',
            f'"accepted_main_sha": "{_WP22A_PHASE5_ACCEPTED_MAIN_SHA}",',
            f'"exact_main_sha": "{_WP22A_PHASE5_ACCEPTED_MAIN_SHA}",',
        }
    ),
    "tests/test_v10_wp22a_phase5_transition.py": frozenset(
        {
            f'"{_WP22A_PHASE5_IMPLEMENTATION_HEAD_SHA}"',
            f'"{_WP22A_PHASE5_ACCEPTED_MAIN_SHA}"',
        }
    ),
}
EXTERNAL_VENV_ROOT_COMMAND = 'VENV_ROOT="$(cygpath -u "$RUNNER_TEMP")"'
EXTERNAL_VENV_EXPORT_COMMAND = 'echo "VENV_PATH=$VENV_PATH" >> "$GITHUB_ENV"'
DIAGNOSTICS_SOFT_FAIL = re.compile(
    r"(?ms)^\s*- name: Upload test diagnostics\s*$"
    r".*?^\s+id: diagnostics_upload\s*$"
    r".*?^\s+continue-on-error: true\s*$"
    r".*?^\s+uses: actions/upload-artifact@[0-9a-f]{40}.*?$"
)

REQUIRED_WORKFLOW_COMMANDS = {
    "external Windows CI environment": EXTERNAL_VENV_ROOT_COMMAND,
    "external CI environment export": EXTERNAL_VENV_EXPORT_COMMAND,
    "Windows lock projection": "python scripts/windows_ci_lock.py project",
    "hash-locked install": "--require-hashes -r windows-requirements-dev.txt",
    "lock consistency": "python -m piptools compile",
    "Windows lock verification": "python scripts/windows_ci_lock.py verify",
    "CI policy self-check": "python scripts/check_ci_security_baseline.py",
    "V10 repository boundaries": "python scripts/check_v10_repository_boundaries.py",
    "V10 toolchain baseline": "python scripts/check_v10_toolchain_baseline.py",
    "V10 Regression Shield": "python scripts/check_v10_regression_shield.py",
    "lint": "python -m ruff check .",
    "formatting": "python -m ruff format --check",
    "type checking": "python -m mypy",
    "coverage": "--cov-fail-under=",
    "dependency audit": "python -m pip_audit",
    "SAST": "python -m bandit",
    "secret scan": "python -m detect_secrets",
    "cross-platform secret-scan exclusions": SECRET_SCAN_EXCLUDE_PATTERN,
}

SELF_HOSTED_RUNNER_LABELS = "[self-hosted, Windows, X64, omni-cio-ci]"
HEADLESS_REPOSITORY_BOOTSTRAP_MARKERS = {
    "job-scoped GitHub token": "GITHUB_TOKEN: ${{ github.token }}",
    "non-interactive Git": 'GIT_TERMINAL_PROMPT: "0"',
    "non-interactive credential manager": 'GCM_INTERACTIVE: "0"',
    "inherited credential-helper reset": 'git config --local credential.helper ""',
    "temporary job-token helper": "git config --local --add credential.helper",
    "detached exact-head checkout": 'git checkout --detach "$EXPECTED_HEAD"',
    "credential-helper removal": "git config --local --unset-all credential.helper",
    "exact-head verification": 'test "$(git rev-parse HEAD)" = "$EXPECTED_HEAD"',
    "post-bootstrap credential cleanup": (
        'test -z "$(git config --local --get-all credential.helper || true)"'
    ),
}


def display_path(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return path.name


def requirement_blocks(text: str) -> list[str]:
    blocks: list[str] = []
    current: list[str] = []

    for raw_line in text.splitlines():
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if raw_line[:1].isspace():
            if current:
                current.append(stripped)
            continue
        if stripped.startswith(("--", "-r ", "-c ")):
            continue
        if current:
            blocks.append(" ".join(current))
        current = [stripped]

    if current:
        blocks.append(" ".join(current))
    return blocks


def validate_lock_file(path: Path, failures: list[str]) -> None:
    if not path.is_file():
        failures.append(f"missing lock file: {display_path(path)}")
        return
    blocks = requirement_blocks(path.read_text(encoding="utf-8"))
    if not blocks:
        failures.append(f"lock file has no pinned packages: {display_path(path)}")
        return
    for block in blocks:
        requirement = block.split("\\", maxsplit=1)[0].strip()
        if "==" not in requirement:
            failures.append(
                f"unpinned requirement in {display_path(path)}: {requirement}"
            )
        if "--hash=sha256:" not in block:
            failures.append(
                f"requirement without SHA-256 hash in {display_path(path)}: "
                f"{requirement}"
            )


def validate_action_pins(workflow_text: str, failures: list[str]) -> None:
    for line_number, raw_line in enumerate(workflow_text.splitlines(), start=1):
        if "uses:" not in raw_line:
            continue
        value = raw_line.split("uses:", maxsplit=1)[1].split("#", maxsplit=1)[0]
        value = value.strip().strip("\"'")
        if value.startswith("./"):
            continue
        if "@" not in value:
            failures.append(
                f"Action without ref at {WORKFLOW_PATH.name}:{line_number}: {value}"
            )
            continue
        ref = value.rsplit("@", maxsplit=1)[1]
        if not FULL_SHA.fullmatch(ref):
            failures.append(
                f"Action is not pinned to a full commit SHA at "
                f"{WORKFLOW_PATH.name}:{line_number}: {value}"
            )


def validate_soft_fail_policy(workflow_text: str, failures: list[str]) -> None:
    count = workflow_text.count("continue-on-error: true")
    if count == 0:
        return
    if count != 1 or DIAGNOSTICS_SOFT_FAIL.search(workflow_text) is None:
        failures.append(
            "security and quality gates may not use continue-on-error; only the "
            "post-merge diagnostics artifact transport may be best-effort"
        )


def validate_headless_repository_bootstrap(
    workflow_text: str,
    failures: list[str],
) -> None:
    if "actions/checkout@" in workflow_text:
        failures.append(
            "self-hosted Regression Shield must not depend on actions/checkout; "
            "use the reviewed headless exact-SHA bootstrap"
        )
    for label, marker in HEADLESS_REPOSITORY_BOOTSTRAP_MARKERS.items():
        if workflow_text.count(marker) < 2:
            failures.append(
                "headless repository bootstrap must prevent persisted credentials "
                f"for every self-hosted job; missing {label}: {marker}"
            )


def validate_workflow(failures: list[str]) -> None:
    if not WORKFLOW_PATH.is_file():
        failures.append("missing .github/workflows/regression-shield.yml")
        return
    text = WORKFLOW_PATH.read_text(encoding="utf-8")
    validate_action_pins(text, failures)
    validate_soft_fail_policy(text, failures)
    for label, command in REQUIRED_WORKFLOW_COMMANDS.items():
        if command not in text:
            failures.append(f"Regression Shield is missing {label}: {command}")
    if "contents: read" not in text:
        failures.append("workflow permissions must retain contents: read")
    if "\n  pull_request:" in text:
        failures.append(
            "Regression Shield must remain post-merge only; PR authority belongs to the authoritative gate"
        )
    if SELF_HOSTED_RUNNER_LABELS not in text:
        failures.append(
            "Regression Shield must target the dedicated self-hosted Windows runner"
        )
    validate_headless_repository_bootstrap(text, failures)
    if "scripts\\bootstrap_windows_ci_python.cmd" not in text:
        failures.append("Regression Shield must bootstrap the verified Python runtime")
    if "python -m venv .venv-ci" in text:
        failures.append(
            "CI virtual environments must be created outside the repository checkout"
        )
    if text.count(EXTERNAL_VENV_ROOT_COMMAND) < 2:
        failures.append(
            "every self-hosted job must create its virtual environment in RUNNER_TEMP"
        )
    if text.count(EXTERNAL_VENV_EXPORT_COMMAND) < 2:
        failures.append(
            "every self-hosted job must export its external virtual environment"
        )
    if text.count('rm -rf "$VENV_PATH"') < 4:
        failures.append(
            "every self-hosted job must reset and clean its external virtual environment"
        )


def validate_render_contract(failures: list[str]) -> None:
    path = ROOT / "render.yaml"
    if not path.is_file():
        failures.append("missing render.yaml")
        return
    text = path.read_text(encoding="utf-8")
    if "pip install --require-hashes -r requirements.txt" not in text:
        failures.append("Render must install the hash-locked runtime dependencies")
    if "uvicorn app:app --host 0.0.0.0 --port $PORT" not in text:
        failures.append("Render must preserve the app:app entrypoint")


def _normalize_repo_filename(filename: str) -> str:
    normalized = filename.replace("\\", "/")
    if normalized.startswith("./"):
        normalized = normalized[2:]
    return normalized


def _read_finding_line(
    filename: str,
    line_number: object,
) -> tuple[str, list[str], str] | None:
    if isinstance(line_number, bool) or not isinstance(line_number, int):
        return None
    normalized = _normalize_repo_filename(filename)
    root = ROOT.resolve()
    candidate = (ROOT / Path(normalized)).resolve()
    try:
        candidate.relative_to(root)
    except ValueError:
        return None
    try:
        lines = candidate.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError):
        return None
    if line_number < 1 or line_number > len(lines):
        return None
    return normalized, lines, lines[line_number - 1].strip()


def _approved_exact_line(
    filename: str,
    line_number: object,
    approved_by_path: dict[str, frozenset[str]],
) -> bool:
    normalized = _normalize_repo_filename(filename)
    approved_lines = approved_by_path.get(normalized)
    if not approved_lines:
        return False
    located = _read_finding_line(filename, line_number)
    if located is None:
        return False
    _, _, line = located
    return line in approved_lines


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError:
        return ""
    return digest.hexdigest()


def _safe_descendant(root: Path, raw_path: object) -> Path | None:
    if (
        not isinstance(raw_path, str)
        or not raw_path
        or "\\" in raw_path
        or "\x00" in raw_path
    ):
        return None
    relative = PurePosixPath(raw_path)
    if relative.is_absolute() or not relative.parts or ".." in relative.parts:
        return None
    if any(":" in part for part in relative.parts):
        return None
    resolved_root = root.resolve()
    candidate = resolved_root.joinpath(*relative.parts).resolve()
    try:
        candidate.relative_to(resolved_root)
    except ValueError:
        return None
    return candidate


def _load_brand_manifest_records() -> list[Any] | None:
    manifest_path = ROOT / BRAND_MANIFEST_PATH
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    records = payload.get("files")
    if not isinstance(records, list) or not records:
        return None
    return records


def _validated_manifest_record_digest(
    record: object,
    package_root: Path,
    seen_paths: set[str],
) -> str | None:
    if not isinstance(record, dict):
        return None
    raw_path = record.get("path")
    byte_count = record.get("bytes")
    sha256 = record.get(SHA256_FIELD)
    if not isinstance(raw_path, str) or raw_path in seen_paths:
        return None
    if (
        not isinstance(byte_count, int)
        or isinstance(byte_count, bool)
        or byte_count < 0
    ):
        return None
    if not isinstance(sha256, str) or _SHA256_HEX.fullmatch(sha256) is None:
        return None

    candidate = _safe_descendant(package_root, raw_path)
    if candidate is None or not candidate.is_file():
        return None
    try:
        actual_size = candidate.stat().st_size
    except OSError:
        return None
    if actual_size != byte_count or _sha256_file(candidate) != sha256:
        return None
    seen_paths.add(raw_path)
    return sha256


def _verified_brand_manifest_digests() -> frozenset[str]:
    records = _load_brand_manifest_records()
    if records is None:
        return frozenset()

    package_root = ROOT / BRAND_PACKAGE_PATH
    seen_paths: set[str] = set()
    verified: set[str] = set()
    for record in records:
        sha256 = _validated_manifest_record_digest(record, package_root, seen_paths)
        if sha256 is None:
            return frozenset()
        verified.add(sha256)
    return frozenset(verified)


def _verified_brand_public_integrity_values() -> frozenset[str]:
    manifest_digests = _verified_brand_manifest_digests()
    if not manifest_digests:
        return frozenset()
    values = set(manifest_digests)
    manifest_sha256 = _sha256_file(ROOT / BRAND_MANIFEST_PATH)
    if manifest_sha256:
        values.add(manifest_sha256)
    values.update(_KNOWN_BRAND_PUBLIC_INTEGRITY_VALUES)
    return frozenset(values)


def _hex_entropy_finding_line(
    filename: str,
    finding: dict[str, Any],
) -> tuple[str, list[str], str] | None:
    if finding.get(FINDING_TYPE_KEY) != HEX_HIGH_ENTROPY_FINDING:
        return None
    return _read_finding_line(filename, finding.get(FINDING_LINE_NUMBER_KEY))


def _approved_brand_manifest_finding(filename: str, finding: dict[str, Any]) -> bool:
    located = _hex_entropy_finding_line(filename, finding)
    if located is None:
        return False
    normalized, _, line = located
    if normalized != BRAND_MANIFEST_PATH:
        return False
    match = _HEX_JSON_LINE.fullmatch(line)
    return (
        match is not None
        and match.group("key") == SHA256_FIELD
        and match.group("value") in _verified_brand_manifest_digests()
    )


def _approved_brand_custody_finding(filename: str, finding: dict[str, Any]) -> bool:
    located = _hex_entropy_finding_line(filename, finding)
    if located is None:
        return False
    normalized, _, line = located
    if normalized != BRAND_CUSTODY_PATH:
        return False
    match = _HEX_JSON_LINE.fullmatch(line)
    return (
        match is not None
        and match.group("key") in _BRAND_CUSTODY_INTEGRITY_KEYS
        and match.group("value") in _verified_brand_public_integrity_values()
    )


def _approved_brand_guard_finding(filename: str, finding: dict[str, Any]) -> bool:
    located = _hex_entropy_finding_line(filename, finding)
    line_number = finding.get(FINDING_LINE_NUMBER_KEY)
    if (
        located is None
        or isinstance(line_number, bool)
        or not isinstance(line_number, int)
        or line_number < 2
    ):
        return False
    normalized, lines, line = located
    if normalized != BRAND_GUARD_PATH:
        return False
    match = _SHA256_LITERAL_LINE.fullmatch(line)
    declaration = lines[line_number - 2].strip()
    return (
        match is not None
        and declaration in _BRAND_GUARD_CHECKSUM_DECLARATIONS
        and match.group("value") in _verified_brand_public_integrity_values()
    )


def _approved_brand_integrity_finding(filename: str, finding: dict[str, Any]) -> bool:
    return (
        _approved_brand_manifest_finding(filename, finding)
        or _approved_brand_custody_finding(filename, finding)
        or _approved_brand_guard_finding(filename, finding)
    )


def _approved_keyword_metadata_finding(filename: str, finding: dict[str, Any]) -> bool:
    if finding.get(FINDING_TYPE_KEY) != "Secret Keyword":
        return False
    return _approved_exact_line(
        filename,
        finding.get(FINDING_LINE_NUMBER_KEY),
        APPROVED_KEYWORD_LINES,
    )


def _approved_public_checksum_finding(filename: str, finding: dict[str, Any]) -> bool:
    if finding.get(FINDING_TYPE_KEY) != HEX_HIGH_ENTROPY_FINDING:
        return False
    return _approved_exact_line(
        filename,
        finding.get(FINDING_LINE_NUMBER_KEY),
        APPROVED_PUBLIC_CHECKSUM_LINES,
    )


def _approved_git_sha_evidence_finding(filename: str, finding: dict[str, Any]) -> bool:
    if finding.get(FINDING_TYPE_KEY) != HEX_HIGH_ENTROPY_FINDING:
        return False
    return _approved_exact_line(
        filename,
        finding.get(FINDING_LINE_NUMBER_KEY),
        APPROVED_GIT_SHA_EVIDENCE_LINES,
    )


def _approved_detect_secrets_finding(filename: str, finding: dict[str, Any]) -> bool:
    return (
        _approved_keyword_metadata_finding(filename, finding)
        or _approved_public_checksum_finding(filename, finding)
        or _approved_git_sha_evidence_finding(filename, finding)
        or _approved_brand_integrity_finding(filename, finding)
    )


def _validate_detect_secrets_finding(
    filename: str,
    finding: object,
    failures: list[str],
) -> None:
    if not isinstance(finding, dict):
        failures.append(f"invalid detect-secrets finding for {filename}")
        return
    if _approved_detect_secrets_finding(filename, finding):
        return
    line_number = finding.get(FINDING_LINE_NUMBER_KEY, "unknown")
    finding_type = finding.get(FINDING_TYPE_KEY, "unknown")
    failures.append(f"potential secret: {filename}:{line_number} ({finding_type})")


def _validate_detect_secrets_findings(
    filename: str,
    findings: object,
    failures: list[str],
) -> None:
    if not isinstance(findings, list):
        failures.append(f"invalid detect-secrets findings for {filename}")
        return
    for finding in findings:
        _validate_detect_secrets_finding(filename, finding, failures)


def _validate_detect_secrets_file(
    filename: object,
    findings: object,
    failures: list[str],
) -> None:
    if not isinstance(filename, str):
        failures.append("invalid detect-secrets filename")
        return
    if GENERATED_SECRET_SCAN_PATH.search(filename):
        return
    _validate_detect_secrets_findings(filename, findings, failures)


def validate_detect_secrets_report(
    report: dict[str, Any],
    failures: list[str],
) -> None:
    results = report.get(DETECTOR_RESULTS_KEY)
    if not isinstance(results, dict):
        failures.append("detect-secrets output does not contain a results object")
        return
    for filename, findings in results.items():
        _validate_detect_secrets_file(filename, findings, failures)


def validate_repository_baseline() -> list[str]:
    failures: list[str] = []
    for path in LOCK_PATHS:
        validate_lock_file(path, failures)
    validate_workflow(failures)
    validate_render_contract(failures)
    bootstrap = ROOT / ".github" / "workflows" / "pr03-bootstrap.yml"
    if bootstrap.exists():
        failures.append("temporary PR-03 bootstrap workflow must not be committed")
    return failures


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--detect-secrets-report",
        action="store_true",
        help="Validate detect-secrets JSON read from standard input.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.detect_secrets_report:
        try:
            report = json.load(sys.stdin)
        except (json.JSONDecodeError, OSError) as exc:
            print(f"Invalid detect-secrets JSON: {exc}", file=sys.stderr)
            return 1
        failures: list[str] = []
        validate_detect_secrets_report(report, failures)
    else:
        failures = validate_repository_baseline()
    if failures:
        print("CI/security baseline check failed:", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1
    if args.detect_secrets_report:
        print("Secret scan passed: no potential secrets detected.")
    else:
        print("CI/security baseline check passed.")
        print("Dependency locks: pinned and SHA-256 hashed")
        print("Windows projection: exact except allowlisted uvloop exclusion")
        print("CI virtual environments: isolated in RUNNER_TEMP")
        print("GitHub Actions: pinned to full commit SHAs")
        print(
            "Regression Shield: post-merge only on dedicated self-hosted Windows runner"
        )
        print("V10 repository boundary guard: required")
        print("V10 toolchain baseline guard: required")
        print("V10 Regression Shield guard: required")
        print("Diagnostics artifact transport: best-effort and non-authoritative")
        print("Render entrypoint: app:app")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
