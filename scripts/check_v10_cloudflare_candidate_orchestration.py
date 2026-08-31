from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/v10-cloudflare-candidate-deploy.yml"
INSTALLER = ROOT / "scripts/install_v10_cloudflare_delivery_toolchain.py"
QUARANTINE = ROOT / "scripts/quarantine_v10_cloudflare_staging_trigger.py"
GATED_RUNNER = ROOT / "scripts/run_v10_cloudflare_gated_candidate.py"
CONTRACT = (
    ROOT / "docs/architecture/V10_CLOUDFLARE_CONTAINER_DEPLOY_AUTHORITY_CONTRACT.json"
)

_WORKERS_AUTHORITY = "python -m scripts.probe_v10_cloudflare_workers_builds_authority"
_QUARANTINE_COMMAND = "python -m scripts.quarantine_v10_cloudflare_staging_trigger"
_TOOLCHAIN_COMMAND = "python -m scripts.install_v10_cloudflare_delivery_toolchain"
_REGISTRY_AUTHORITY = (
    "python -m scripts.probe_v10_cloudflare_container_registry_authority"
)
_NEON_MUTATION = "- name: Provision isolated Neon staging runtime role"
_WORKER_MUTATION = "- name: Bootstrap isolated staging Worker without local Containers"
_GATED_STEP = (
    "- name: Configure Workers Builds and accept exact staging build (gated exact-SHA)"
)
_GATED_COMMAND = "python -m scripts.run_v10_cloudflare_gated_candidate"
_LIVE_ACCEPTANCE = "- name: Accept live staging Worker and Container"
_EVIDENCE = "- name: Record accepted staging evidence"
_POST_QUARANTINE = "- name: Quarantine staging trigger after candidate attempt"
_CLEANUP = "- name: Clean secrets and self-hosted workspace"


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise RuntimeError(f"CLOUDFLARE_ORCHESTRATION_FILE_UNREADABLE:{path}") from exc


def _load_contract() -> dict[str, Any]:
    try:
        value = json.loads(_read(CONTRACT))
    except ValueError as exc:
        raise RuntimeError("CLOUDFLARE_ORCHESTRATION_CONTRACT_INVALID") from exc
    if not isinstance(value, dict):
        raise RuntimeError("CLOUDFLARE_ORCHESTRATION_CONTRACT_INVALID")
    return value


def _require(source: str, markers: tuple[str, ...], code: str) -> None:
    if any(marker not in source for marker in markers):
        raise RuntimeError(code)


def _forbid(source: str, markers: tuple[str, ...], code: str) -> None:
    if any(marker in source for marker in markers):
        raise RuntimeError(code)


def _code_lines(source: str) -> tuple[str, ...]:
    return tuple(
        line.strip()
        for line in source.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    )


def _require_order(source: str, markers: tuple[str, ...], code: str) -> None:
    indices = tuple(source.find(marker) for marker in markers)
    if any(index < 0 for index in indices) or indices != tuple(sorted(indices)):
        raise RuntimeError(code)


def _validate_workflow() -> None:
    workflow = _read(WORKFLOW)
    if workflow.count(_QUARANTINE_COMMAND) != 2:
        raise RuntimeError("CLOUDFLARE_ORCHESTRATION_QUARANTINE_COUNT_INVALID")
    if workflow.count(_GATED_COMMAND) != 1:
        raise RuntimeError("CLOUDFLARE_ORCHESTRATION_GATED_RUNNER_COUNT_INVALID")
    _require_order(
        workflow,
        (
            _WORKERS_AUTHORITY,
            "- name: Quarantine stale automatic staging trigger",
            _TOOLCHAIN_COMMAND,
            _REGISTRY_AUTHORITY,
            _NEON_MUTATION,
            _WORKER_MUTATION,
            _GATED_STEP,
            _GATED_COMMAND,
            _LIVE_ACCEPTANCE,
            _EVIDENCE,
            _POST_QUARANTINE,
            _CLEANUP,
        ),
        "CLOUDFLARE_ORCHESTRATION_GATE_ORDER_INVALID",
    )
    post_index = workflow.find(_POST_QUARANTINE)
    cleanup_index = workflow.find(_CLEANUP)
    post_section = workflow[post_index:cleanup_index]
    _require(
        post_section,
        ("if: always()", _QUARANTINE_COMMAND),
        "CLOUDFLARE_ORCHESTRATION_POST_QUARANTINE_INVALID",
    )
    _forbid(
        workflow,
        ("continue-on-error", "python -m scripts.bootstrap_v10_cloudflare_builds"),
        "CLOUDFLARE_ORCHESTRATION_BYPASS_FORBIDDEN",
    )
    active_lines = _code_lines(workflow)
    if any(line.startswith("npm ci ") for line in active_lines):
        raise RuntimeError("CLOUDFLARE_ORCHESTRATION_SYSTEM_NPM_ROOT_INSTALL_FORBIDDEN")
    if not any(_TOOLCHAIN_COMMAND in line for line in active_lines):
        raise RuntimeError("CLOUDFLARE_ORCHESTRATION_PINNED_TOOLCHAIN_MISSING")


def _validate_installer() -> None:
    source = _read(INSTALLER)
    _require(
        source,
        (
            '_NPM_VERSION = "10.9.2"',
            '_FRONTEND_NPM_VERSION = "11.16.0"',
            '_WRANGLER_VERSION = "4.127.1"',
            "https://registry.npmjs.org/npm/-/npm-10.9.2.tgz",
            "_NPM_TARBALL_SHA512 = bytes(",
            "len(_NPM_TARBALL_SHA512) != hashlib.sha512().digest_size",
            "hashlib.sha512(payload).digest()",
            "hmac.compare_digest(actual, _NPM_TARBALL_SHA512)",
            "_RejectRedirects",
            "_MAX_TARBALL_BYTES",
            "_MAX_UNPACKED_BYTES",
            "_MAX_ARCHIVE_MEMBERS",
            "_MAX_MEMBER_NAME_CHARS",
            '"\\\\" in name',
            '".." in candidate.parts',
            '"ci"',
            '"--ignore-scripts"',
            '"--no-audit"',
            '"--no-fund"',
            'node_modules" / "npm" / "bin" / "npm-cli.js"',
            'node_modules" / "wrangler" / "bin" / "wrangler.js"',
        ),
        "CLOUDFLARE_ORCHESTRATION_PINNED_TOOLCHAIN_INVALID",
    )
    _forbid(
        source,
        (
            "shell=True",
            "npm install -g",
            "npx ",
            "check_hostname = False",
            "_NPM_TARBALL_INTEGRITY",
            "import base64",
            "base64.b64decode",
        ),
        "CLOUDFLARE_ORCHESTRATION_PINNED_TOOLCHAIN_UNSAFE",
    )


def _validate_quarantine() -> None:
    source = _read(QUARANTINE)
    _require(
        source,
        (
            '"git", "rev-parse", "HEAD"',
            "_GITHUB_OWNER_ID",
            "_GITHUB_OWNER",
            "_GITHUB_REPO_ID",
            "_GITHUB_REPO",
            '"DELETE"',
            'f"/accounts/{api.account_id}/builds/triggers/{trigger_uuid}"',
            'f"/accounts/{api.account_id}/builds/builds/{build_uuid}/cancel"',
            "remove_staging_triggers",
            "_cancel_staging_builds",
            "CLOUDFLARE_STAGING_AUTOBUILD=QUARANTINED",
            "CLOUDFLARE_STAGING_TRIGGER_REPO_AUTHORITY_DRIFT",
            "CLOUDFLARE_STAGING_BUILD_CANCEL_RACE",
        ),
        "CLOUDFLARE_ORCHESTRATION_QUARANTINE_INVALID",
    )
    _forbid(
        source,
        ("shell=True", "capture_output=True", "stdout=subprocess.PIPE"),
        "CLOUDFLARE_ORCHESTRATION_QUARANTINE_OUTPUT_UNSAFE",
    )


def _validate_gated_runner() -> None:
    source = _read(GATED_RUNNER)
    _require(
        source,
        (
            '"git", "rev-parse", "HEAD"',
            "CLOUDFLARE_GATED_TRIGGER_PREEXISTED",
            '_GATED_AUTOBUILD_SENTINEL_BRANCH = "__omni_cf_c_manual_only__"',
            'desired["branch_includes"] = [_GATED_AUTOBUILD_SENTINEL_BRANCH]',
            'body={"branch": builds._BRANCH, "commit_hash": expected_sha}',
            "CLOUDFLARE_BUILD_SOURCE=GATED_MANUAL_EXACT_SHA",
            "CLOUDFLARE_GATED_TRIGGER=ARMED_UNTIL_BUILD_TERMINAL",
            "quarantine_staging_autobuild",
            "CLOUDFLARE_GATED_CANDIDATE_CLEANUP_FAILED",
            'builds._wait_build(api, build_uuid, sha)',
            'builds._write_output("staging_url", url)',
            'builds._write_output("cloudflare_build_uuid", build_uuid)',
        ),
        "CLOUDFLARE_ORCHESTRATION_GATED_RUNNER_INVALID",
    )
    _forbid(
        source,
        (
            "_start_or_reuse_build",
            "_find_exact_build",
            "CLOUDFLARE_BUILD_SOURCE=AUTO",
            "remove_staging_triggers",
            "CLOUDFLARE_GATED_TRIGGER=RETIRED",
            "continue-on-error",
        ),
        "CLOUDFLARE_ORCHESTRATION_AUTOBUILD_REUSE_FORBIDDEN",
    )
    _require_order(
        source,
        (
            "build_uuid = _start_exact_manual_build(",
            "CLOUDFLARE_GATED_TRIGGER=ARMED_UNTIL_BUILD_TERMINAL",
            "builds._wait_build(api, build_uuid, sha)",
            "quarantine_staging_autobuild(api, expected_sha=sha, verify_head=False)",
        ),
        "CLOUDFLARE_ORCHESTRATION_ACTIVE_TRIGGER_LIFETIME_INVALID",
    )


def _object(value: object, code: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise RuntimeError(code)
    return value


def _validate_contract() -> None:
    contract = _load_contract()
    if contract.get("milestone") != "CF-C":
        raise RuntimeError("CLOUDFLARE_ORCHESTRATION_MILESTONE_INVALID")
    quarantine = _object(
        contract.get("staging_autobuild_quarantine"),
        "CLOUDFLARE_ORCHESTRATION_QUARANTINE_CONTRACT_MISSING",
    )
    expected = {
        "risk_reducing_provider_deactivation_allowed_before_registry_probe": True,
        "persistent_branch_push_trigger_allowed_during_cf_c": False,
        "preexisting_nonterminal_staging_builds_must_be_cancelled": True,
        "preexisting_build_may_be_accepted_as_exact_sha_candidate": False,
        "candidate_build_start_mode": "MANUAL_EXACT_SHA_AFTER_AUTHORITY_GATES",
        "trigger_must_be_removed_after_candidate_attempt": True,
        "gated_trigger_branch_filter_must_not_match_integrated_branch": True,
        "gated_trigger_must_be_deleted_immediately_after_manual_build_start": False,
        "gated_trigger_must_remain_until_candidate_build_terminal": True,
    }
    if any(quarantine.get(key) != value for key, value in expected.items()):
        raise RuntimeError("CLOUDFLARE_ORCHESTRATION_QUARANTINE_CONTRACT_INVALID")


def validate() -> None:
    _validate_workflow()
    _validate_installer()
    _validate_quarantine()
    _validate_gated_runner()
    _validate_contract()


def main() -> int:
    try:
        validate()
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print("V10 Cloudflare CF-C orchestration contract passed.")
    print("Staging push auto-build: QUARANTINED")
    print("Candidate build: MANUAL EXACT-SHA AFTER AUTHORITY GATES")
    print("Gated trigger lifetime: UNTIL CANDIDATE BUILD TERMINAL")
    print("Root provider npm: INTEGRITY-PINNED 10.9.2")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
