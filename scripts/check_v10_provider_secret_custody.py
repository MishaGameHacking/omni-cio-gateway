from __future__ import annotations

import json
from pathlib import Path
import re
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CONTRACT_RELATIVE = Path("docs/architecture/V10_PROVIDER_SECRET_CUSTODY_CONTRACT.json")
WORKFLOW_DIRECTORY = Path(".github/workflows")

PROVIDER_WORKFLOW = ".github/workflows/v10-cloudflare-provider-readiness.yml"
CANDIDATE_WORKFLOW = ".github/workflows/v10-cloudflare-candidate-deploy.yml"
PRODUCTION_WORKFLOW = ".github/workflows/v10-cloudflare-production-release.yml"
TIMEWEB_READONLY_WORKFLOW = ".github/workflows/v10-timeweb-postgres-readonly-proof.yml"
TIMEWEB_CREATE_WORKFLOW = ".github/workflows/v10-timeweb-postgres-synthetic-create.yml"
TIMEWEB_NETWORK_WORKFLOW = ".github/workflows/v10-timeweb-postgres-public-ipv4-tls.yml"
TIMEWEB_ALLOCATION_WORKFLOW = ".github/workflows/v10-timeweb-ipv4-allocation.yml"
RETIRED_HOSTED_WORKFLOW = ".github/workflows/v10-hosted-release-alignment.yml"
RETIRED_PREVIEW_WORKFLOW = ".github/workflows/v10-phase4-free-preview-deploy.yml"

CLOUDFLARE_ACCOUNT_ID = "CLOUDFLARE_ACCOUNT_ID"
CLOUDFLARE_API_TOKEN = "CLOUDFLARE_API_TOKEN"
CLOUDFLARE_ZONE_ID = "CLOUDFLARE_ZONE_ID"
CLOUDFLARE_ZONE_NAME = "CLOUDFLARE_ZONE_NAME"
NEON_RUNTIME_BINDING = "NEON_API_KEY"
NEON_FUNCTION_DEPLOY_BINDING = "NEON_FUNCTION_DEPLOY_API_KEY"
NEON_ORG_ID = "NEON_ORG_ID"
NEON_PROJECT_ID = "NEON_PROJECT_ID"
CUSTOM_HOST = "OMNI_V10_CLOUDFLARE_CUSTOM_HOST"
TIMEWEB_CONTROL_PLANE_BINDING = "TIMEWEB_CLOUD_API_TOKEN"
REMOVED_FUNCTION_INVOKE_TOKEN = "NEON_FUNCTION_INVOKE_API_TOKEN"
RETIRED_RENDER_BINDING = "RENDER_API_KEY"

_SECRET_REF = re.compile(
    r"""\$\{\{\s*secrets(?:\.([A-Z][A-Z0-9_]*)|\[\s*['"]([A-Z][A-Z0-9_]*)['"]\s*\])\s*\}\}""",
    re.IGNORECASE,
)
_VAR_REF = re.compile(
    r"""\$\{\{\s*vars(?:\.([A-Z][A-Z0-9_]*)|\[\s*['"]([A-Z][A-Z0-9_]*)['"]\s*\])\s*\}\}""",
    re.IGNORECASE,
)
_SECRET_CONTEXT_START = re.compile(r"\$\{\{\s*secrets\b", re.IGNORECASE)
_VAR_CONTEXT_START = re.compile(r"\$\{\{\s*vars\b", re.IGNORECASE)
_EXPECTED_SCHEMA = "omni-cio.v10.provider-secret-custody.v1"
_EXPECTED_STATUS = "ACTIVE_TIMEWEB_PROVIDER_SECRET_CUSTODY"
_EXPECTED_SCOPE = "GITHUB_ACTIONS_PROVIDER_SECRET_REFERENCES"
_EXPECTED_INVENTORY = frozenset(
    {
        CLOUDFLARE_ACCOUNT_ID,
        CLOUDFLARE_API_TOKEN,
        CLOUDFLARE_ZONE_ID,
        CLOUDFLARE_ZONE_NAME,
        NEON_RUNTIME_BINDING,
        NEON_FUNCTION_DEPLOY_BINDING,
        NEON_ORG_ID,
        NEON_PROJECT_ID,
        CUSTOM_HOST,
        TIMEWEB_CONTROL_PLANE_BINDING,
    }
)
_CLOUDFLARE_WORKFLOWS = frozenset(
    {PROVIDER_WORKFLOW, CANDIDATE_WORKFLOW, PRODUCTION_WORKFLOW}
)
_TIMEWEB_WORKFLOWS = frozenset(
    {
        TIMEWEB_READONLY_WORKFLOW,
        TIMEWEB_CREATE_WORKFLOW,
        TIMEWEB_NETWORK_WORKFLOW,
        TIMEWEB_ALLOCATION_WORKFLOW,
    }
)
_ACTIVE_WORKFLOWS = _TIMEWEB_WORKFLOWS
_RETIRED_SECRET_BEARING_WORKFLOWS = _CLOUDFLARE_WORKFLOWS
_EXPECTED_RETIRED = frozenset({RETIRED_HOSTED_WORKFLOW, RETIRED_PREVIEW_WORKFLOW})
_ARCHIVE_MARKER = (
    "ARCHIVE-IN-PLACE: Amendment 18 retired Cloudflare from active V10 authority."
)
_ARCHIVED_DISABLED_JOB_COUNTS = {
    PROVIDER_WORKFLOW: 1,
    CANDIDATE_WORKFLOW: 1,
    PRODUCTION_WORKFLOW: 6,
}
_EXPECTED_FORBIDDEN = frozenset({REMOVED_FUNCTION_INVOKE_TOKEN, RETIRED_RENDER_BINDING})
_ACTIVE_NEON_TUPLE = frozenset({NEON_RUNTIME_BINDING, NEON_ORG_ID, NEON_PROJECT_ID})
_DOMAIN_TUPLE = frozenset({CLOUDFLARE_ZONE_ID, CLOUDFLARE_ZONE_NAME, CUSTOM_HOST})
_RETAINED_FUNCTION_COMPONENTS = frozenset(
    {
        "scripts/deploy_v10_cloudflare_neon_bootstrap_function.py",
        "scripts/neon_function_invocation_credential.py",
    }
)
_EXPECTED_ROLES: dict[str, object] = {
    "current_provider_secret_authority": TIMEWEB_CONTROL_PLANE_BINDING,
    "historical_neon_runtime_management_binding": NEON_RUNTIME_BINDING,
    "legacy_neon_function_deploy_binding": NEON_FUNCTION_DEPLOY_BINDING,
    "legacy_function_transport_active": False,
    "retired_provider_workflow_execution_allowed": False,
    "active_runtime_may_alias_legacy_function_deploy_binding": False,
    "protected_provider_identifiers_may_use_actions_variables": False,
    "active_cloudflare_job_level_provider_binding_injection_allowed": False,
    "timeweb_control_plane_binding": TIMEWEB_CONTROL_PLANE_BINDING,
    "timeweb_binding_environment": "timeweb-synthetic",
    "timeweb_binding_job_level_injection_allowed": False,
    "timeweb_allowed_workflows": [
        TIMEWEB_READONLY_WORKFLOW,
        TIMEWEB_CREATE_WORKFLOW,
        TIMEWEB_NETWORK_WORKFLOW,
        TIMEWEB_ALLOCATION_WORKFLOW,
    ],
}
_EXPECTED_INVARIANTS: dict[str, object] = {
    "gateway_entrypoint": "app:app",
    "PUBLIC_MULTI_USER_ENABLED": False,
    "trading_methods": False,
    "REAL_TRADING_ENABLED": False,
    "broker_write": False,
}


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise RuntimeError("PROVIDER_SECRET_CUSTODY_CONTRACT_INVALID") from exc
    if not isinstance(value, dict):
        raise RuntimeError("PROVIDER_SECRET_CUSTODY_CONTRACT_INVALID")
    return value


def _string_set(value: object, code: str) -> set[str]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise RuntimeError(code)
    return set(value)


def _workflow_sources(root: Path) -> dict[str, str]:
    workflow_root = root / WORKFLOW_DIRECTORY
    if not workflow_root.is_dir():
        raise RuntimeError("PROVIDER_SECRET_CUSTODY_WORKFLOW_ROOT_MISSING")
    result: dict[str, str] = {}
    for path in sorted(workflow_root.iterdir()):
        if path.suffix not in {".yml", ".yaml"} or not path.is_file():
            continue
        try:
            result[path.relative_to(root).as_posix()] = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            raise RuntimeError("PROVIDER_SECRET_CUSTODY_WORKFLOW_UNREADABLE") from exc
    return result


def _context_refs(
    source: str,
    pattern: re.Pattern[str],
    context_start: re.Pattern[str],
    malformed_code: str,
) -> set[str]:
    matches = list(pattern.finditer(source))
    if len(matches) != len(context_start.findall(source)):
        raise RuntimeError(malformed_code)

    refs: set[str] = set()
    for match in matches:
        name = next((group for group in match.groups() if group is not None), None)
        if name is None:
            raise RuntimeError(malformed_code)
        refs.add(name.upper())
    return refs


def _validate_active_step_scope(source: str) -> None:
    for line in source.splitlines():
        if _SECRET_CONTEXT_START.search(line) is None:
            continue
        leading = line[: len(line) - len(line.lstrip(" "))]
        if "\t" in leading or len(leading) < 8:
            raise RuntimeError("PROVIDER_SECRET_CUSTODY_JOB_SCOPE_TOO_BROAD")


def _validate_inventory(contract: dict[str, Any]) -> None:
    inventory = contract.get("repository_secret_inventory")
    if not isinstance(inventory, dict) or set(inventory) != _EXPECTED_INVENTORY:
        raise RuntimeError("PROVIDER_SECRET_CUSTODY_INVENTORY_MISMATCH")
    for name, metadata in inventory.items():
        _validate_inventory_entry(name, metadata)


_EXPECTED_INVENTORY_METADATA: dict[str, tuple[str, str, str]] = {
    CLOUDFLARE_ACCOUNT_ID: (
        "CLOUDFLARE",
        "PROTECTED_IDENTIFIER",
        "RETIRED_PROVIDER_ARCHIVE_REFERENCE_ONLY",
    ),
    CLOUDFLARE_API_TOKEN: (
        "CLOUDFLARE",
        "CREDENTIAL",
        "RETIRED_PROVIDER_ARCHIVE_REFERENCE_ONLY",
    ),
    CLOUDFLARE_ZONE_ID: (
        "CLOUDFLARE",
        "PROTECTED_IDENTIFIER",
        "RETIRED_PROVIDER_ARCHIVE_REFERENCE_ONLY",
    ),
    CLOUDFLARE_ZONE_NAME: (
        "CLOUDFLARE",
        "PROTECTED_IDENTIFIER",
        "RETIRED_PROVIDER_ARCHIVE_REFERENCE_ONLY",
    ),
    NEON_RUNTIME_BINDING: (
        "NEON",
        "CREDENTIAL",
        "RETIRED_PROVIDER_ARCHIVE_REFERENCE_ONLY",
    ),
    NEON_FUNCTION_DEPLOY_BINDING: (
        "NEON",
        "CREDENTIAL",
        "DORMANT_LEGACY_FUNCTION_DEPLOY",
    ),
    NEON_ORG_ID: (
        "NEON",
        "PROTECTED_IDENTIFIER",
        "RETIRED_PROVIDER_ARCHIVE_REFERENCE_ONLY",
    ),
    NEON_PROJECT_ID: (
        "NEON",
        "PROTECTED_IDENTIFIER",
        "RETIRED_PROVIDER_ARCHIVE_REFERENCE_ONLY",
    ),
    CUSTOM_HOST: (
        "CLOUDFLARE",
        "PROTECTED_IDENTIFIER",
        "RETIRED_PROVIDER_ARCHIVE_REFERENCE_ONLY",
    ),
    TIMEWEB_CONTROL_PLANE_BINDING: (
        "TIMEWEB",
        "CREDENTIAL",
        "RU_PG_B_ENVIRONMENT_SCOPED_CONTROL_PLANE",
    ),
}


def _validate_inventory_entry(name: str, metadata: object) -> None:
    if not isinstance(metadata, dict):
        raise RuntimeError("PROVIDER_SECRET_CUSTODY_INVENTORY_METADATA_INVALID")
    expected = _EXPECTED_INVENTORY_METADATA.get(name)
    if expected is None:
        raise RuntimeError("PROVIDER_SECRET_CUSTODY_INVENTORY_METADATA_INVALID")
    provider, kind, state = expected
    if (
        metadata.get("provider") != provider
        or metadata.get("kind") != kind
        or metadata.get("state") != state
    ):
        raise RuntimeError("PROVIDER_SECRET_CUSTODY_INVENTORY_METADATA_INVALID")

    expected_keys = {"provider", "kind", "state"}
    if name == NEON_FUNCTION_DEPLOY_BINDING:
        expected_keys |= {
            "active_workflow_reference_allowed",
            "retained_source_components",
        }
        if metadata.get("active_workflow_reference_allowed") is not False:
            raise RuntimeError("PROVIDER_SECRET_CUSTODY_FUNCTION_DEPLOY_STATE_INVALID")
        retained = _string_set(
            metadata.get("retained_source_components"),
            "PROVIDER_SECRET_CUSTODY_FUNCTION_DEPLOY_COMPONENTS_INVALID",
        )
        if retained != _RETAINED_FUNCTION_COMPONENTS:
            raise RuntimeError(
                "PROVIDER_SECRET_CUSTODY_FUNCTION_DEPLOY_COMPONENTS_INVALID"
            )
    if set(metadata) != expected_keys:
        raise RuntimeError("PROVIDER_SECRET_CUSTODY_INVENTORY_METADATA_INVALID")


def _validate_workflow_map(
    contract: dict[str, Any], key: str, expected_paths: frozenset[str], code: str
) -> dict[str, set[str]]:
    raw = contract.get(key)
    if not isinstance(raw, dict) or set(raw) != expected_paths:
        raise RuntimeError(code)
    result: dict[str, set[str]] = {}
    for path, names in raw.items():
        expected = _string_set(names, code)
        if not expected <= _EXPECTED_INVENTORY:
            raise RuntimeError("PROVIDER_SECRET_CUSTODY_UNKNOWN_CONTRACT_SECRET")
        result[path] = expected
    return result


def _validate_active_workflows(contract: dict[str, Any]) -> dict[str, set[str]]:
    return _validate_workflow_map(
        contract,
        "active_workflows",
        _ACTIVE_WORKFLOWS,
        "PROVIDER_SECRET_CUSTODY_ACTIVE_WORKFLOWS_MISMATCH",
    )


def _validate_retired_secret_bearing_workflows(
    contract: dict[str, Any],
) -> dict[str, set[str]]:
    return _validate_workflow_map(
        contract,
        "retired_secret_bearing_workflows",
        _RETIRED_SECRET_BEARING_WORKFLOWS,
        "PROVIDER_SECRET_CUSTODY_RETIRED_WORKFLOWS_MISMATCH",
    )

def _validate_named_set(
    contract: dict[str, Any],
    key: str,
    expected: frozenset[str],
    code: str,
) -> set[str]:
    actual = _string_set(contract.get(key), code)
    if actual != expected:
        raise RuntimeError(code)
    return actual


def _validate_contract_shape(
    contract: dict[str, Any],
) -> tuple[dict[str, set[str]], dict[str, set[str]], set[str], set[str]]:
    if contract.get("schema") != _EXPECTED_SCHEMA:
        raise RuntimeError("PROVIDER_SECRET_CUSTODY_SCHEMA_MISMATCH")
    if contract.get("status") != _EXPECTED_STATUS:
        raise RuntimeError("PROVIDER_SECRET_CUSTODY_STATUS_MISMATCH")
    if contract.get("scope") != _EXPECTED_SCOPE:
        raise RuntimeError("PROVIDER_SECRET_CUSTODY_SCOPE_MISMATCH")
    if contract.get("values_recorded") is not False:
        raise RuntimeError("PROVIDER_SECRET_CUSTODY_VALUES_MUST_NOT_BE_RECORDED")

    _validate_inventory(contract)
    expected_by_workflow = _validate_active_workflows(contract)
    retired_secret_bearing = _validate_retired_secret_bearing_workflows(contract)
    forbidden = _validate_named_set(
        contract,
        "forbidden_workflow_secret_names",
        _EXPECTED_FORBIDDEN,
        "PROVIDER_SECRET_CUSTODY_FORBIDDEN_SET_INVALID",
    )
    retired = _validate_named_set(
        contract,
        "retired_secret_free_workflows",
        _EXPECTED_RETIRED,
        "PROVIDER_SECRET_CUSTODY_RETIRED_WORKFLOW_SET_INVALID",
    )
    if contract.get("role_separation") != _EXPECTED_ROLES:
        raise RuntimeError("PROVIDER_SECRET_CUSTODY_ROLE_SEPARATION_INVALID")
    if contract.get("protected_invariants") != _EXPECTED_INVARIANTS:
        raise RuntimeError("PROVIDER_SECRET_CUSTODY_PROTECTED_INVARIANTS_INVALID")
    return expected_by_workflow, retired_secret_bearing, forbidden, retired


def _scan_workflow_refs(
    workflows: dict[str, str], forbidden: set[str]
) -> dict[str, set[str]]:
    all_refs: dict[str, set[str]] = {}
    protected_variables = _EXPECTED_INVENTORY | forbidden
    for path, source in workflows.items():
        refs = _context_refs(
            source,
            _SECRET_REF,
            _SECRET_CONTEXT_START,
            "PROVIDER_SECRET_CUSTODY_SECRET_CONTEXT_UNPARSED",
        )
        variables = _context_refs(
            source,
            _VAR_REF,
            _VAR_CONTEXT_START,
            "PROVIDER_SECRET_CUSTODY_VARIABLE_CONTEXT_UNPARSED",
        )
        all_refs[path] = refs
        if refs & forbidden:
            raise RuntimeError("PROVIDER_SECRET_CUSTODY_DEPRECATED_SECRET_REFERENCED")
        if refs - _EXPECTED_INVENTORY:
            raise RuntimeError("PROVIDER_SECRET_CUSTODY_UNREVIEWED_SECRET_REFERENCED")
        if variables & protected_variables:
            raise RuntimeError("PROVIDER_SECRET_CUSTODY_VARIABLE_FALLBACK_FORBIDDEN")
    return all_refs


def _validate_active_bindings(
    workflows: dict[str, str],
    all_refs: dict[str, set[str]],
    expected_by_workflow: dict[str, set[str]],
) -> None:
    for path, expected in expected_by_workflow.items():
        if all_refs[path] != expected:
            raise RuntimeError("PROVIDER_SECRET_CUSTODY_ACTIVE_BINDINGS_MISMATCH")
        _validate_active_step_scope(workflows[path])


def _validate_retired_workflows(
    all_refs: dict[str, set[str]], retired: set[str]
) -> None:
    for path in retired:
        if all_refs[path]:
            raise RuntimeError(
                "PROVIDER_SECRET_CUSTODY_RETIRED_WORKFLOW_SECRET_REFERENCE"
            )


def _validate_archived_provider_workflow(path: str, source: str) -> None:
    if _ARCHIVE_MARKER not in source:
        raise RuntimeError("PROVIDER_SECRET_CUSTODY_RETIRED_WORKFLOW_ARCHIVE_MISSING")
    if "on:\n  workflow_dispatch:" not in source:
        raise RuntimeError("PROVIDER_SECRET_CUSTODY_RETIRED_WORKFLOW_DISPATCH_MISSING")
    if "on:\n  push:" in source or "on:\n  workflow_run:" in source:
        raise RuntimeError("PROVIDER_SECRET_CUSTODY_RETIRED_WORKFLOW_TRIGGER_PRESENT")
    if source.count("if: ${{ false }}") != _ARCHIVED_DISABLED_JOB_COUNTS[path]:
        raise RuntimeError("PROVIDER_SECRET_CUSTODY_RETIRED_WORKFLOW_NOT_HARD_DISABLED")


def _validate_retired_secret_bearing_bindings(
    workflows: dict[str, str],
    all_refs: dict[str, set[str]],
    expected_by_workflow: dict[str, set[str]],
) -> None:
    for path, expected in expected_by_workflow.items():
        if all_refs[path] != expected:
            raise RuntimeError("PROVIDER_SECRET_CUSTODY_RETIRED_BINDINGS_MISMATCH")
        _validate_active_step_scope(workflows[path])
        _validate_archived_provider_workflow(path, workflows[path])


def _validate_role_consumers(all_refs: dict[str, set[str]]) -> None:
    if any(NEON_FUNCTION_DEPLOY_BINDING in refs for refs in all_refs.values()):
        raise RuntimeError("PROVIDER_SECRET_CUSTODY_DORMANT_FUNCTION_KEY_EXPOSED")
    retired_provider_bindings = (
        _ACTIVE_NEON_TUPLE
        | _DOMAIN_TUPLE
        | {CLOUDFLARE_ACCOUNT_ID, CLOUDFLARE_API_TOKEN}
    )
    for path, refs in all_refs.items():
        if (
            path not in _RETIRED_SECRET_BEARING_WORKFLOWS
            and refs & retired_provider_bindings
        ):
            raise RuntimeError(
                "PROVIDER_SECRET_CUSTODY_RETIRED_PROVIDER_BINDING_OUTSIDE_ARCHIVE"
            )
    for path in _TIMEWEB_WORKFLOWS:
        if all_refs[path] != {TIMEWEB_CONTROL_PLANE_BINDING}:
            raise RuntimeError("PROVIDER_SECRET_CUSTODY_TIMEWEB_SCOPE_INVALID")


def validate(root: Path = ROOT) -> None:
    contract = _load_json(root / CONTRACT_RELATIVE)
    expected_by_workflow, retired_secret_bearing, forbidden, retired = (
        _validate_contract_shape(contract)
    )
    workflows = _workflow_sources(root)
    required = set(expected_by_workflow) | set(retired_secret_bearing) | retired
    if required - set(workflows):
        raise RuntimeError("PROVIDER_SECRET_CUSTODY_REQUIRED_WORKFLOW_MISSING")

    all_refs = _scan_workflow_refs(workflows, forbidden)
    _validate_active_bindings(workflows, all_refs, expected_by_workflow)
    _validate_retired_secret_bearing_bindings(
        workflows, all_refs, retired_secret_bearing
    )
    _validate_retired_workflows(all_refs, retired)
    _validate_role_consumers(all_refs)


def main() -> int:
    try:
        validate()
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print("V10 provider secret custody contract passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
