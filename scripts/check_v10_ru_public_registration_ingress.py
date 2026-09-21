from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "docs/architecture/V10_RU_PUBLIC_REGISTRATION_INGRESS_CONTRACT.json"
AMENDMENT = ROOT / (
    "docs/master-plan/"
    "OMNI_CIO_V10_RU_PUBLIC_REGISTRATION_AND_RUSSIAN_INGRESS_AMENDMENT.md"
)
INDEX = ROOT / "docs/master-plan/OMNI_CIO_V10_AMENDMENTS_INDEX.md"
STATUS = ROOT / "knowledge/17_V10_CURRENT_PROGRAM_STATUS.md"
WORKFLOW = ROOT / ".github/workflows/v10-engineering-governance.yml"

EXPECTED_SERVICES = ["ChatGPT", "GitHub", "Timeweb Cloud", "Telegram Login"]
EXPECTED_RETIRED = ["Cloudflare", "Neon", "Render", "Cloud.ru", "VK ID"]
EXPECTED_MILESTONES = ["TW-A", "TW-B", "TW-C", "TW-D", "TW-E", "TW-F", "TW-G"]


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise RuntimeError(
            f"TIMEWEB_CONSOLIDATION_SOURCE_UNREADABLE:{path.name}"
        ) from exc


def _load() -> dict[str, Any]:
    try:
        payload = json.loads(_read(CONTRACT))
    except json.JSONDecodeError as exc:
        raise RuntimeError("TIMEWEB_CONSOLIDATION_CONTRACT_INVALID") from exc
    if not isinstance(payload, dict):
        raise RuntimeError("TIMEWEB_CONSOLIDATION_CONTRACT_INVALID")
    return payload


def _mapping(value: object, code: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise RuntimeError(code)
    return value


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise RuntimeError(code)


def _validate_service_model(payload: dict[str, Any]) -> None:
    _require(
        payload.get("schema") == "omni-cio.v10.timeweb-only-platform-consolidation.v1",
        "TIMEWEB_CONSOLIDATION_SCHEMA_INVALID",
    )
    _require(
        payload.get("amendment_number") == 18,
        "TIMEWEB_CONSOLIDATION_AUTHORITY_INVALID",
    )
    _require(
        payload.get("owning_issue") == 580,
        "TIMEWEB_CONSOLIDATION_DASHBOARD_INVALID",
    )
    _require(
        payload.get("active_general_service_set") == EXPECTED_SERVICES,
        "TIMEWEB_CONSOLIDATION_SERVICE_SET_INVALID",
    )
    _require(
        payload.get("retired_active_services") == EXPECTED_RETIRED,
        "TIMEWEB_CONSOLIDATION_RETIRED_SET_INVALID",
    )
    _require(
        payload.get("provider_reentry_requires_fresh_owner_amendment") is True,
        "TIMEWEB_CONSOLIDATION_PROVIDER_REENTRY_INVALID",
    )


def _validate_product_timeweb_auth(payload: dict[str, Any]) -> None:
    product = _mapping(
        payload.get("product"),
        "TIMEWEB_CONSOLIDATION_PRODUCT_INVALID",
    )
    for key in (
        "one_canonical_web",
        "provider_neutral_core_required",
        "server_side_session_authority",
    ):
        _require(product.get(key) is True, "TIMEWEB_CONSOLIDATION_PRODUCT_INVALID")
    for key in ("second_product_allowed", "browser_selects_tenant"):
        _require(product.get(key) is False, "TIMEWEB_CONSOLIDATION_PRODUCT_INVALID")

    timeweb = _mapping(
        payload.get("timeweb"),
        "TIMEWEB_CONSOLIDATION_TIMEWEB_INVALID",
    )
    _require(
        timeweb.get("app_platform_selected") is True,
        "TIMEWEB_CONSOLIDATION_TIMEWEB_INVALID",
    )
    _require(
        timeweb.get("managed_postgresql_major") == 18,
        "TIMEWEB_CONSOLIDATION_PG_MAJOR_INVALID",
    )
    for key in (
        "exact_accepted_main_commit_required",
        "technical_candidate_before_canonical_dns",
        "backups_required_before_production_cutover",
        "restore_proof_required",
        "representative_russia_no_vpn_evidence_required",
    ):
        _require(timeweb.get(key) is True, "TIMEWEB_CONSOLIDATION_TIMEWEB_INVALID")
    for key in (
        "production_autodeploy_may_bypass_github_acceptance",
        "runtime_secrets_in_git_allowed",
        "private_networking_assumed_without_provider_evidence",
    ):
        _require(timeweb.get(key) is False, "TIMEWEB_CONSOLIDATION_TIMEWEB_INVALID")

    auth = _mapping(payload.get("auth"), "TIMEWEB_CONSOLIDATION_AUTH_INVALID")
    _require(
        auth.get("human_identity_providers") == ["telegram"],
        "TIMEWEB_CONSOLIDATION_AUTH_INVALID",
    )
    _require(
        auth.get("vk_id_active_allowed") is False,
        "TIMEWEB_CONSOLIDATION_VK_RETIRED",
    )
    _require(
        auth.get("owner_admin_demo_preview_session_bypass_allowed") is False,
        "TIMEWEB_CONSOLIDATION_AUTH_BYPASS_FORBIDDEN",
    )


def _validate_database_ci_execution(payload: dict[str, Any]) -> None:
    database = _mapping(
        payload.get("database"),
        "TIMEWEB_CONSOLIDATION_DATABASE_INVALID",
    )
    _require(
        database.get("final_provider") == "Timeweb Cloud Managed PostgreSQL 18",
        "TIMEWEB_CONSOLIDATION_DATABASE_PROVIDER_INVALID",
    )
    _require(
        database.get("neon_new_feature_work_allowed") is False,
        "TIMEWEB_CONSOLIDATION_NEON_RETIRED",
    )
    _require(
        database.get("neon_delete_before_timeweb_cutover_allowed") is False,
        "TIMEWEB_CONSOLIDATION_EARLY_DB_DELETE_FORBIDDEN",
    )
    for key in (
        "migrations_required",
        "rls_force_rls_required",
        "cross_tenant_negative_required",
        "least_privilege_runtime_role_required",
        "migrated_data_verification_required",
    ):
        _require(database.get(key) is True, "TIMEWEB_CONSOLIDATION_DATABASE_INVALID")

    ci = _mapping(payload.get("ci"), "TIMEWEB_CONSOLIDATION_CI_INVALID")
    _require(ci.get("active_service") == "GitHub", "TIMEWEB_CONSOLIDATION_CI_INVALID")
    _require(
        ci.get("quality_weakening_for_saas_retirement_allowed") is False,
        "TIMEWEB_CONSOLIDATION_CI_WEAKENING_FORBIDDEN",
    )
    _require(
        ci.get("external_saas_required_final") is False,
        "TIMEWEB_CONSOLIDATION_CI_INVALID",
    )

    execution = _mapping(
        payload.get("execution"),
        "TIMEWEB_CONSOLIDATION_EXECUTION_INVALID",
    )
    _require(
        execution.get("update_id") == "TIMEWEB-PLATFORM-CONSOLIDATION-INTEGRATED",
        "TIMEWEB_CONSOLIDATION_UPDATE_ID_INVALID",
    )
    _require(
        execution.get("default_branch") == "system/timeweb-platform-consolidation",
        "TIMEWEB_CONSOLIDATION_BRANCH_INVALID",
    )
    _require(
        execution.get("milestones") == EXPECTED_MILESTONES,
        "TIMEWEB_CONSOLIDATION_MILESTONE_ORDER_INVALID",
    )
    _require(
        execution.get("source_one_branch_default") is True,
        "TIMEWEB_CONSOLIDATION_BRANCH_INVALID",
    )


def _validate_external_decommission(payload: dict[str, Any]) -> None:
    decommission = _mapping(
        payload.get("external_decommission"),
        "TIMEWEB_CONSOLIDATION_DECOMMISSION_INVALID",
    )
    for key in (
        "owner_supplied_visual_evidence",
        "cloudflare_external_resources_and_account_reported_deleted",
        "neon_project_organization_keys_and_account_reported_deleted",
        "repository_history_and_archived_files_preserved",
    ):
        _require(
            decommission.get(key) is True,
            "TIMEWEB_CONSOLIDATION_DECOMMISSION_INVALID",
        )
    for key in (
        "cloudflare_rollback_available",
        "neon_rollback_available",
        "provider_side_physical_erasure_independently_verified",
    ):
        _require(
            decommission.get(key) is False,
            "TIMEWEB_CONSOLIDATION_DECOMMISSION_INVALID",
        )

    timeweb = _mapping(
        payload.get("timeweb"),
        "TIMEWEB_CONSOLIDATION_TIMEWEB_INVALID",
    )
    _require(
        timeweb.get("canonical_domain_target") == "omnicio.ru",
        "TIMEWEB_CONSOLIDATION_CANONICAL_DOMAIN_INVALID",
    )
    _require(
        timeweb.get("canonical_domain_candidates_observed")
        == ["omnicio.ru", "omni-cio.ru"],
        "TIMEWEB_CONSOLIDATION_DOMAIN_EVIDENCE_INVALID",
    )
    _require(
        timeweb.get("canonical_domain_owner_confirmation_required") is False,
        "TIMEWEB_CONSOLIDATION_DOMAIN_CONFIRMATION_STATE_INVALID",
    )
    _require(
        timeweb.get("canonical_domain_owner_confirmed") is True,
        "TIMEWEB_CONSOLIDATION_DOMAIN_CONFIRMATION_MISSING",
    )
    _require(
        timeweb.get("dns_cutover_allowed_before_domain_confirmation") is False,
        "TIMEWEB_CONSOLIDATION_PREMATURE_DNS_CUTOVER",
    )
    _require(
        timeweb.get("dns_cutover_authorized_by_domain_confirmation_alone") is False,
        "TIMEWEB_CONSOLIDATION_DOMAIN_ONLY_CUTOVER_FORBIDDEN",
    )


def _validate_cleanup_activation(payload: dict[str, Any]) -> None:
    cleanup = _mapping(
        payload.get("cleanup"),
        "TIMEWEB_CONSOLIDATION_CLEANUP_INVALID",
    )
    for key in (
        "retired_provider_files_may_remain_archive_in_place",
        "future_historical_file_removal_requires_separate_owner_authority",
    ):
        _require(cleanup.get(key) is True, "TIMEWEB_CONSOLIDATION_CLEANUP_INVALID")
    for key in (
        "mass_repository_deletion_required",
        "historical_artifacts_may_define_current_authority",
        "new_feature_dependencies_on_retired_providers_allowed",
        "retired_live_workflow_actions_allowed_after_cutover",
        "retired_required_merge_checks_allowed_after_equivalent_github_proof",
        "provider_credentials_remain_active_after_decommission",
        "vk_id_deployed_product_composition_allowed_after_tw_g",
        "git_history_rewrite_for_cleanup_allowed",
        "provider_physical_media_erasure_claim_allowed",
    ):
        _require(cleanup.get(key) is False, "TIMEWEB_CONSOLIDATION_CLEANUP_INVALID")

    activation = _mapping(
        payload.get("activation"),
        "TIMEWEB_CONSOLIDATION_ACTIVATION_INVALID",
    )
    _require(
        activation.get("public_registration_enabled_by_governance_alone") is False,
        "TIMEWEB_CONSOLIDATION_PREMATURE_ACTIVATION",
    )
    _require(
        activation.get("telegram_first_and_only_human_login") is True,
        "TIMEWEB_CONSOLIDATION_TELEGRAM_ONLY_INVALID",
    )

    protected = _mapping(
        payload.get("protected_invariants"),
        "TIMEWEB_CONSOLIDATION_INVARIANTS_INVALID",
    )
    for key in (
        "PUBLIC_MULTI_USER_ENABLED",
        "OMNI_V10_TELEGRAM_LOGIN_ENABLED",
        "broker_write",
        "trading_methods",
        "REAL_TRADING_ENABLED",
    ):
        _require(
            protected.get(key) is False,
            "TIMEWEB_CONSOLIDATION_INVARIANTS_INVALID",
        )


def _validate_documents() -> None:
    amendment = _read(AMENDMENT)
    for marker in (
        "Timeweb-Only Platform Consolidation & Telegram-Only Login Authority",
        "TIMEWEB-PLATFORM-CONSOLIDATION-INTEGRATED",
        "ChatGPT",
        "GitHub",
        "Timeweb Cloud",
        "Telegram Login",
        "VK ID — RETIRED",
        "Cloudflare — RETIRE",
        "Neon — RETIRE",
    ):
        _require(marker in amendment, "TIMEWEB_CONSOLIDATION_AMENDMENT_DRIFT")

    index = _read(INDEX)
    _require(
        "### 18. Timeweb-Only Platform Consolidation & Telegram-Only Login Authority"
        in index,
        "TIMEWEB_CONSOLIDATION_INDEX_MISSING",
    )
    status = _read(STATUS)
    for marker in (
        "TIMEWEB-PLATFORM-CONSOLIDATION-INTEGRATED",
        "ChatGPT + GitHub + Timeweb Cloud + Telegram Login",
        "Cloudflare, Neon, Render, Cloud.ru and VK ID",
    ):
        _require(marker in status, "TIMEWEB_CONSOLIDATION_STATUS_DRIFT")

    workflow = _read(WORKFLOW)
    _require(
        "python scripts/check_v10_ru_public_registration_ingress.py" in workflow,
        "TIMEWEB_CONSOLIDATION_GOVERNANCE_WORKFLOW_MISSING",
    )
    _require(
        "tests.test_v10_ru_public_registration_ingress" in workflow,
        "TIMEWEB_CONSOLIDATION_GOVERNANCE_TEST_MISSING",
    )


def main() -> int:
    try:
        payload = _load()
        _validate_service_model(payload)
        _validate_product_timeweb_auth(payload)
        _validate_database_ci_execution(payload)
        _validate_external_decommission(payload)
        _validate_cleanup_activation(payload)
        _validate_documents()
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(
        "V10 Timeweb-only platform consolidation authority passed: "
        "ChatGPT + GitHub + Timeweb + Telegram Login target is fail-closed."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
