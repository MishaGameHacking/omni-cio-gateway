from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PHASE4_WORKFLOW = ROOT / ".github/workflows/v10-phase4-free-preview-deploy.yml"
ALIGNMENT_WORKFLOW = ROOT / ".github/workflows/v10-hosted-release-alignment.yml"
CLOUDFLARE_AMENDMENT = (
    ROOT
    / "docs/master-plan/OMNI_CIO_V10_CLOUDFLARE_PLATFORM_AND_CONTINUOUS_RELEASE_AUTHORITY_AMENDMENT.md"
)
CLOUDFLARE_CONTRACT = (
    ROOT / "docs/architecture/V10_CLOUDFLARE_PLATFORM_AUTHORITY_CONTRACT.json"
)


def _read(path: Path, failures: list[str]) -> str:
    if not path.is_file():
        failures.append(f"missing hosted-release governance file: {path.relative_to(ROOT)}")
        return ""
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        failures.append(f"cannot read {path.relative_to(ROOT)}: {exc}")
        return ""


def _load_json(path: Path, failures: list[str]) -> dict[str, Any] | None:
    text = _read(path, failures)
    if not text:
        return None
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        failures.append(f"invalid JSON in {path.relative_to(ROOT)}: {exc}")
        return None
    if not isinstance(payload, dict):
        failures.append(f"JSON root must be object: {path.relative_to(ROOT)}")
        return None
    return payload


def _require_markers(
    label: str,
    text: str,
    markers: tuple[str, ...],
    failures: list[str],
) -> None:
    for marker in markers:
        if marker not in text:
            failures.append(f"{label} is missing governance marker: {marker}")


def _forbid_markers(
    label: str,
    text: str,
    markers: tuple[str, ...],
    failures: list[str],
) -> None:
    for marker in markers:
        if marker in text:
            failures.append(f"{label} contains forbidden active-provider marker: {marker}")


def _validate_manual_only_retired_workflow(
    *,
    label: str,
    text: str,
    retirement_marker: str,
    failure_code: str,
    failures: list[str],
) -> None:
    _require_markers(
        label,
        text,
        (
            "workflow_dispatch:",
            "contents: read",
            "runs-on: [self-hosted, Windows, X64, omni-cio-ci]",
            retirement_marker,
            failure_code,
        ),
        failures,
    )
    _forbid_markers(
        label,
        text,
        (
            "workflow_run:",
            "schedule:",
            "RENDER_API_KEY",
            "NEON_API_KEY",
            "RENDER_ZERO_CHARGE_ATTESTATION",
            "NEON_ORG_ID",
            "check_v10_zero_cost_provider_boundary.py",
            "provision_v10_phase4_free_preview.py",
            "check_v10_hosted_release_alignment.py",
            "onrender.com",
        ),
        failures,
    )


def validate_sources(
    *,
    phase4_workflow: str,
    alignment_workflow: str,
    cloudflare_amendment: str,
    cloudflare_contract: dict[str, Any] | None,
    failures: list[str],
) -> None:
    _validate_manual_only_retired_workflow(
        label="historical Phase-4 Render workflow",
        text=phase4_workflow,
        retirement_marker="LEGACY_RENDER_PHASE4_RETIRED_AMENDMENT_14",
        failure_code="exit /b 78",
        failures=failures,
    )
    _validate_manual_only_retired_workflow(
        label="historical Render alignment workflow",
        text=alignment_workflow,
        retirement_marker="LEGACY_RENDER_ALIGNMENT_RETIRED_AMENDMENT_14",
        failure_code="exit /b 79",
        failures=failures,
    )

    _require_markers(
        "Cloudflare authority amendment",
        cloudflare_amendment,
        (
            "Render.com is no longer an active new-V10 deployment",
            "Historical contracts, runbooks and acceptance evidence may retain",
            "protected V9 Render production/recovery baseline remains protected",
            "CLOUDFLARE-BUILDS-VERIFIER-INTEGRATION",
        ),
        failures,
    )

    if cloudflare_contract is None:
        return
    provider = cloudflare_contract.get("provider_transition")
    if not isinstance(provider, dict):
        failures.append("Cloudflare authority contract provider_transition must be an object")
        return
    if provider.get("render_new_v10_target_selected") is not False:
        failures.append("Render must remain disabled as a new V10 target")
    if provider.get("render_zero_charge_attestation_required_for_new_v10") is not False:
        failures.append("Render zero-charge attestation must not gate new V10")
    if provider.get("render_hosted_release_alignment_required_for_new_v10") is not False:
        failures.append("Render hosted alignment must not gate new V10")
    if provider.get("historical_wp22a_render_neon_evidence_preserved") is not True:
        failures.append("historical WP22A Render/Neon evidence must stay preserved")
    if provider.get("protected_v9_render_app_app_baseline_preserved") is not True:
        failures.append("protected V9 Render app:app baseline must stay preserved")


def main() -> int:
    failures: list[str] = []
    phase4_workflow = _read(PHASE4_WORKFLOW, failures)
    alignment_workflow = _read(ALIGNMENT_WORKFLOW, failures)
    amendment = _read(CLOUDFLARE_AMENDMENT, failures)
    contract = _load_json(CLOUDFLARE_CONTRACT, failures)

    validate_sources(
        phase4_workflow=phase4_workflow,
        alignment_workflow=alignment_workflow,
        cloudflare_amendment=amendment,
        cloudflare_contract=contract,
        failures=failures,
    )

    if failures:
        print("V10 hosted-release alignment governance check failed:", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1

    print("V10 hosted-release alignment governance check passed.")
    print("Legacy Render Phase-4 deployment: manual-only and fail-closed")
    print("Legacy Render hosted alignment: manual-only and fail-closed")
    print("New V10 release authority: Cloudflare sequence owned by Amendment 14")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
