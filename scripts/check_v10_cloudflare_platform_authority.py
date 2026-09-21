from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
AMENDMENT = (
    ROOT
    / "docs/master-plan/OMNI_CIO_V10_CLOUDFLARE_PLATFORM_AND_CONTINUOUS_RELEASE_AUTHORITY_AMENDMENT.md"
)
CONTRACT = ROOT / "docs/architecture/V10_CLOUDFLARE_PLATFORM_AUTHORITY_CONTRACT.json"
INDEX = ROOT / "docs/master-plan/OMNI_CIO_V10_AMENDMENTS_INDEX.md"
QUALITY = ROOT / "docs/architecture/V10_ENGINEERING_QUALITY_GATE_CONTRACT.json"
STATUS = ROOT / "knowledge/17_V10_CURRENT_PROGRAM_STATUS.md"
PHASE4_WORKFLOW = ROOT / ".github/workflows/v10-phase4-free-preview-deploy.yml"
ALIGNMENT_WORKFLOW = ROOT / ".github/workflows/v10-hosted-release-alignment.yml"

EXPECTED_SEQUENCE = [
    "CLOUDFLARE-BUILDS-VERIFIER-INTEGRATION",
    "CLOUDFLARE-RUNTIME-COMPATIBILITY",
    "CLOUDFLARE-CANDIDATE-DEPLOYMENT",
    "CLOUDFLARE-PUBLIC-CUTOVER",
]


def _read(path: Path, failures: list[str]) -> str:
    if not path.is_file():
        failures.append(f"missing Cloudflare authority file: {path.relative_to(ROOT)}")
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


def _section(
    payload: dict[str, Any],
    key: str,
    failures: list[str],
) -> dict[str, Any]:
    value = payload.get(key)
    if not isinstance(value, dict):
        failures.append(f"Cloudflare authority contract section must be object: {key}")
        return {}
    return value


def _expect_bool(
    section: dict[str, Any],
    key: str,
    expected: bool,
    label: str,
    failures: list[str],
) -> None:
    if section.get(key) is not expected:
        failures.append(f"{label}.{key} must be {expected!r}")


def _require_markers(
    label: str,
    text: str,
    markers: tuple[str, ...],
    failures: list[str],
) -> None:
    for marker in markers:
        if marker not in text:
            failures.append(f"{label} is missing authority marker: {marker}")


def _validate_provider_and_authority(
    payload: dict[str, Any], failures: list[str]
) -> None:
    authority = _section(payload, "authority", failures)
    provider = _section(payload, "provider_transition", failures)

    if authority.get("github_engineering_authority_rank") != 1:
        failures.append("GitHub engineering authority rank must be 1")
    if authority.get("cloudflare_platform_authority_rank") != 2:
        failures.append("Cloudflare platform authority rank must be 2")
    for key in ("github_is_source_review_provenance_truth",):
        _expect_bool(authority, key, True, "authority", failures)
    for key in (
        "cloudflare_state_may_override_accepted_github_authority",
        "governance_change_performs_provider_mutation",
        "governance_change_performs_production_cutover",
        "governance_change_provisions_secrets",
    ):
        _expect_bool(authority, key, False, "authority", failures)

    if provider.get("new_v10_primary_platform_target") != "CLOUDFLARE_WORKERS_PAID":
        failures.append(
            "new V10 primary platform target must be CLOUDFLARE_WORKERS_PAID"
        )
    _expect_bool(
        provider, "workers_paid_owner_active_baseline", True, "provider", failures
    )
    for key in (
        "cloudru_new_v10_target_selected",
        "render_new_v10_target_selected",
        "render_zero_charge_attestation_required_for_new_v10",
        "render_hosted_release_alignment_required_for_new_v10",
    ):
        _expect_bool(provider, key, False, "provider", failures)
    for key in (
        "historical_wp22a_render_neon_evidence_preserved",
        "protected_v9_render_app_app_baseline_preserved",
    ):
        _expect_bool(provider, key, True, "provider", failures)
    if provider.get("protected_v9_entrypoint") != "app:app":
        failures.append("protected V9 entrypoint must remain app:app")


def _validate_release_law(payload: dict[str, Any], failures: list[str]) -> None:
    release = _section(payload, "continuous_release", failures)
    for key in (
        "accepted_main_sha_is_product_candidate_source",
        "exact_main_post_merge_success_required",
        "immutable_candidate_before_promotion",
        "recheck_current_main_before_promotion",
        "production_must_converge_to_latest_accepted_promotable_main",
        "failed_new_main_keeps_last_known_good",
        "out_of_sync_state_must_be_visible",
        "public_release_id_generated_without_source_version_bump_commit",
    ):
        _expect_bool(release, key, True, "continuous_release", failures)
    for key in (
        "merge_immediately_deploys_production",
        "superseded_candidate_may_be_promoted",
        "rollback_rewrites_github_authority",
    ):
        _expect_bool(release, key, False, "continuous_release", failures)
    if release.get("public_release_id_format") != "YYYY.MM.DD.N":
        failures.append("public release ID format must remain YYYY.MM.DD.N")
    if release.get("allowed_out_of_sync_states") != [
        "UPDATE_PENDING",
        "DEPLOYMENT_BLOCKED",
        "OUT_OF_SYNC",
    ]:
        failures.append("continuous release out-of-sync state vocabulary changed")


def _validate_runtime_database_security(
    payload: dict[str, Any], failures: list[str]
) -> None:
    product = _section(payload, "product", failures)
    runtime = _section(payload, "web_runtime", failures)
    database = _section(payload, "database", failures)
    security = _section(payload, "security", failures)

    _expect_bool(product, "one_canonical_public_web", True, "product", failures)
    _expect_bool(
        product, "second_user_facing_product_allowed", False, "product", failures
    )
    _expect_bool(product, "cloudflare_is_product_identity", False, "product", failures)
    _expect_bool(
        product, "public_multi_user_enabled_current", False, "product", failures
    )
    _expect_bool(
        product,
        "cloudflare_deployment_alone_activates_real_users",
        False,
        "product",
        failures,
    )
    if product.get("human_product_identity_providers") != ["telegram", "vk_id"]:
        failures.append(
            "human product identity providers must remain Telegram and VK ID"
        )

    _expect_bool(
        runtime,
        "existing_react_vite_web_is_canonical_source",
        True,
        "web_runtime",
        failures,
    )
    _expect_bool(
        runtime,
        "existing_backend_assumed_compatible_without_test",
        False,
        "web_runtime",
        failures,
    )
    _expect_bool(
        runtime,
        "python_worker_dependency_compatibility_required",
        True,
        "web_runtime",
        failures,
    )
    _expect_bool(
        runtime,
        "rewrite_only_to_claim_cloudflare_adoption_allowed",
        False,
        "web_runtime",
        failures,
    )

    if database.get("accepted_postgresql_major") != 18:
        failures.append("accepted PostgreSQL major must remain 18")
    _expect_bool(
        database, "neon_postgresql_authority_preserved", True, "database", failures
    )
    _expect_bool(
        database,
        "d1_replaces_financial_tenant_truth_by_default",
        False,
        "database",
        failures,
    )
    _expect_bool(
        database,
        "hyperdrive_postgresql18_assumed_supported",
        False,
        "database",
        failures,
    )
    _expect_bool(
        database,
        "hyperdrive_pg18_compatibility_test_required",
        True,
        "database",
        failures,
    )
    _expect_bool(database, "tenant_scope_and_rls_required", True, "database", failures)

    _expect_bool(
        security,
        "cloudflare_security_is_additive_outer_layer",
        True,
        "security",
        failures,
    )
    _expect_bool(
        security,
        "access_replaces_product_authentication",
        False,
        "security",
        failures,
    )
    _expect_bool(
        security,
        "server_side_authorization_required_after_edge",
        True,
        "security",
        failures,
    )
    _expect_bool(
        security,
        "tenant_rls_required_after_edge",
        True,
        "security",
        failures,
    )
    _expect_bool(
        security,
        "secret_values_in_source_pr_ci_screenshot_release_manifest_allowed",
        False,
        "security",
        failures,
    )


def _validate_builds_reference_values_and_flags(
    payload: dict[str, Any], failures: list[str]
) -> None:
    builds = _section(payload, "workers_builds", failures)
    expected_numbers = {
        "included_build_minutes_per_month_reference": 6000,
        "concurrent_builds_per_account_reference": 6,
        "build_timeout_minutes_reference": 20,
        "vcpu_per_build_reference": 4,
        "memory_gb_per_build_reference": 8,
        "disk_gb_per_build_reference": 20,
    }
    for key, expected in expected_numbers.items():
        if builds.get(key) != expected:
            failures.append(f"workers_builds.{key} must be {expected}")
    for key in (
        "reference_values_must_be_revalidated_before_material_mutation",
        "included_paid_plan_capacity_authorized_for_omni_cio",
        "dedicated_builds_verifier_integration_required",
        "portable_checks_target_cloudflare_builds",
        "work_conserving_safe_parallelism_target",
    ):
        _expect_bool(builds, key, True, "workers_builds", failures)
    for key in (
        "automatic_paid_overage_beyond_authorized_baseline_allowed",
        "higher_paid_plan_without_fresh_owner_approval_allowed",
        "repository_ci_routing_changes_on_amendment_acceptance",
        "quota_or_outage_may_be_reported_as_success",
    ):
        _expect_bool(builds, key, False, "workers_builds", failures)


def _validate_implementation_sequence(
    payload: dict[str, Any], failures: list[str]
) -> None:
    sequence = payload.get("implementation_sequence")
    if not isinstance(sequence, list):
        failures.append("implementation_sequence must be a list")
        return
    observed = [item.get("id") for item in sequence if isinstance(item, dict)]
    if observed != EXPECTED_SEQUENCE:
        failures.append(
            "Cloudflare implementation sequence must remain "
            + " -> ".join(EXPECTED_SEQUENCE)
        )
    if len(sequence) != len(EXPECTED_SEQUENCE):
        failures.append(
            "Cloudflare implementation sequence must have exactly four stages"
        )

    if len(sequence) >= 2:
        for item in sequence[:2]:
            if not isinstance(item, dict):
                continue
            if item.get("provider_mutation") is not False:
                failures.append(
                    "first two Cloudflare stages must not mutate provider state"
                )
            if item.get("production_deploy") is not False:
                failures.append(
                    "first two Cloudflare stages must not deploy production"
                )


def _validate_builds_and_sequence(payload: dict[str, Any], failures: list[str]) -> None:
    _validate_builds_reference_values_and_flags(payload, failures)
    _validate_implementation_sequence(payload, failures)


def _validate_protected_invariants(
    payload: dict[str, Any], failures: list[str]
) -> None:
    protected = _section(payload, "protected_invariants", failures)
    for key in (
        "public_multi_user_enabled",
        "broker_write_enabled",
        "trading_methods",
        "real_trading_enabled",
        "transfer_withdrawal_authority",
        "margin_leverage_authority",
        "uncovered_short_authority",
        "wp23_unlocked",
        "web_visual_integrated_executed_inside_authority_change",
    ):
        _expect_bool(protected, key, False, "protected_invariants", failures)


def validate_contract(payload: dict[str, Any], failures: list[str]) -> None:
    if payload.get("schema") != "omni-cio.v10.cloudflare-platform-authority.v1":
        failures.append("Cloudflare platform authority schema mismatch")
    _validate_provider_and_authority(payload, failures)
    _validate_release_law(payload, failures)
    _validate_runtime_database_security(payload, failures)
    _validate_builds_and_sequence(payload, failures)
    _validate_protected_invariants(payload, failures)


def _validate_repository_markers(
    amendment: str, index: str, status: str, failures: list[str]
) -> None:
    _require_markers(
        "Amendment 14",
        amendment,
        (
            "GitHub is authority rank 1",
            "Cloudflare Workers Paid is platform rank 2",
            "Render.com is no longer an active new-V10 deployment",
            "Continuous exact-main public release law",
            "CLOUDFLARE-BUILDS-VERIFIER-INTEGRATION",
            "CLOUDFLARE-PUBLIC-CUTOVER",
        ),
        failures,
    )
    _require_markers(
        "Amendments Index",
        index,
        (
            "Cloudflare Platform & Continuous Release Authority",
            AMENDMENT.name,
            "V10_CLOUDFLARE_PLATFORM_AUTHORITY_CONTRACT.json",
        ),
        failures,
    )
    _require_markers(
        "current V10 status",
        status,
        (
            "CLOUDFLARE-BUILDS-VERIFIER-INTEGRATION",
            "Cloudflare Workers Paid",
            "PUBLIC_MULTI_USER_ENABLED=false",
            "Render/Neon historical technical evidence",
            "TIMEWEB-PLATFORM-CONSOLIDATION-INTEGRATED",
            "Amendment 18 — Timeweb-only platform consolidation",
        ),
        failures,
    )


def _validate_retired_workflow_guards(
    phase4: str, alignment: str, failures: list[str]
) -> None:
    _require_markers(
        "retired Phase-4 workflow",
        phase4,
        (
            "workflow_dispatch:",
            "LEGACY_RENDER_PHASE4_RETIRED_AMENDMENT_14",
            "exit /b 78",
        ),
        failures,
    )
    _require_markers(
        "retired hosted-alignment workflow",
        alignment,
        (
            "workflow_dispatch:",
            "LEGACY_RENDER_ALIGNMENT_RETIRED_AMENDMENT_14",
            "exit /b 79",
        ),
        failures,
    )
    for label, text in (
        ("retired Phase-4 workflow", phase4),
        ("retired hosted-alignment workflow", alignment),
    ):
        for forbidden in (
            "workflow_run:",
            "schedule:",
            "RENDER_API_KEY",
            "NEON_API_KEY",
        ):
            if forbidden in text:
                failures.append(f"{label} reactivated forbidden marker: {forbidden}")


def _validate_quality_contract_overlay(
    quality: dict[str, Any] | None, failures: list[str]
) -> None:
    if quality is None:
        return
    runtime = quality.get("runtime_hosting")
    if not isinstance(runtime, dict):
        failures.append("engineering quality runtime_hosting must be an object")
        return
    if runtime.get("cloudflare_workers_paid_selected") is not True:
        failures.append("engineering quality contract must select Workers Paid")
    if runtime.get("cloudru_new_v10_runtime_target_selected") is not False:
        failures.append("engineering quality contract must retire Cloud.ru for new V10")
    if runtime.get("render_com_new_v10_release_acceptance_allowed") is not False:
        failures.append(
            "engineering quality contract must retire Render release acceptance"
        )


def validate_repository(failures: list[str]) -> None:
    amendment = _read(AMENDMENT, failures)
    index = _read(INDEX, failures)
    status = _read(STATUS, failures)
    quality = _load_json(QUALITY, failures)
    contract = _load_json(CONTRACT, failures)
    phase4 = _read(PHASE4_WORKFLOW, failures)
    alignment = _read(ALIGNMENT_WORKFLOW, failures)

    _validate_repository_markers(amendment, index, status, failures)
    _validate_retired_workflow_guards(phase4, alignment, failures)
    _validate_quality_contract_overlay(quality, failures)

    if contract is not None:
        validate_contract(contract, failures)


def main() -> int:
    failures: list[str] = []
    validate_repository(failures)

    if failures:
        print("V10 Cloudflare platform authority check failed:", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1

    print("V10 Cloudflare platform authority check passed.")
    print(
        "Historical authority evidence: GitHub rank 1; "
        "Cloudflare Workers Paid platform rank 2 before Amendment 18"
    )
    print("Legacy Render new-V10 deployment/alignment: retired and fail-closed")
    print("Continuous release: exact-main candidate -> acceptance -> promotion")
    print("Paid overage: forbidden without fresh OWNER approval")
    print(
        "Current next stage is governed by Amendment 18: "
        "TIMEWEB-PLATFORM-CONSOLIDATION-INTEGRATED"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
