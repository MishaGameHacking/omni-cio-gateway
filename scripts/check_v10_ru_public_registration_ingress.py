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
README = ROOT / "README.md"
MASTER_CONTEXT = ROOT / "knowledge/00_PROJECT_MASTER_CONTEXT.md"
AGENTS = ROOT / "AGENTS.md"
CONTRIBUTING = ROOT / "CONTRIBUTING.md"
GPT_NEW_CHAT = ROOT / "gpt/NEW_CHAT_PROMPT.md"
GPT_PROJECT = ROOT / "gpt/PROJECT_INSTRUCTIONS.md"
DATA_INVENTORY = ROOT / "docs/legal/V10_TELEGRAM_PUBLIC_USER_DATA_INVENTORY.md"
WP22A_EXECUTION_CONTRACT = ROOT / "docs/architecture/V10_WP22A_EXECUTION_CONTRACT.md"
WP22A_SERVICE_SELECTION = ROOT / "docs/architecture/V10_WP22A_SERVICE_SELECTION.md"
WP22A_IAC_DECISION = ROOT / "docs/architecture/V10_WP22A_IAC_TOOLCHAIN_DECISION.md"
LEDGER = ROOT / "docs/updates/TIMEWEB_PLATFORM_CONSOLIDATION_EXECUTION_LEDGER.md"
WORKFLOW_DIRECTORY = ROOT / ".github/workflows"
ENGINEERING_GOVERNANCE_WORKFLOW = ".github/workflows/v10-engineering-governance.yml"
TIMEWEB_PROOF_WORKFLOW_NAME = (
    ".github/workflows/v10-timeweb-postgres-readonly-proof.yml"
)
AUTHORITATIVE_MERGE_WORKFLOW_NAME = ".github/workflows/self-hosted-windows-smoke.yml"
CLOUDFLARE_PROVIDER_READINESS_WORKFLOW = (
    ".github/workflows/v10-cloudflare-provider-readiness.yml"
)
CLOUDFLARE_CANDIDATE_WORKFLOW = ".github/workflows/v10-cloudflare-candidate-deploy.yml"
CLOUDFLARE_PRODUCTION_WORKFLOW = (
    ".github/workflows/v10-cloudflare-production-release.yml"
)
NEON_EGRESS_WORKFLOW = ".github/workflows/v10-neon-egress-boundary.yml"
WP22A_PHASE4_PUBLIC_ACCEPTANCE_WORKFLOW = (
    ".github/workflows/v10-wp22a-phase4-public-acceptance.yml"
)
RETIRED_CLOUDFLARE_WORKFLOW_NAMES = (
    CLOUDFLARE_PROVIDER_READINESS_WORKFLOW,
    CLOUDFLARE_CANDIDATE_WORKFLOW,
    CLOUDFLARE_PRODUCTION_WORKFLOW,
)
RETIRED_PROVIDER_WORKFLOW_NAMES = RETIRED_CLOUDFLARE_WORKFLOW_NAMES + (
    NEON_EGRESS_WORKFLOW,
    WP22A_PHASE4_PUBLIC_ACCEPTANCE_WORKFLOW,
)
WORKFLOW = ROOT / ENGINEERING_GOVERNANCE_WORKFLOW
TIMEWEB_PROOF_WORKFLOW = ROOT / TIMEWEB_PROOF_WORKFLOW_NAME
AUTHORITATIVE_MERGE_WORKFLOW = ROOT / AUTHORITATIVE_MERGE_WORKFLOW_NAME
RETIRED_CLOUDFLARE_WORKFLOWS = tuple(
    ROOT / relative for relative in RETIRED_CLOUDFLARE_WORKFLOW_NAMES
)
RETIRED_PROVIDER_WORKFLOWS = tuple(
    ROOT / relative for relative in RETIRED_PROVIDER_WORKFLOW_NAMES
)
ACTIVE_WORKFLOW_TRIGGERS = (
    "\n  pull_request:",
    "\n  push:",
    "\n  workflow_run:",
    "\n  workflow_dispatch:",
    "\n  schedule:",
    "\n  workflow_call:",
)
FORBIDDEN_RETIRED_PROVIDER_EXECUTION_MARKERS = (
    "-File scripts\\validate_wp22a_terraform.ps1",
    "-File scripts\\bootstrap_wp22a_cloudflare_provider.ps1",
    "wrangler deploy",
    "wrangler secret",
    "npx wrangler",
    "secrets.CLOUDFLARE_",
    "secrets.NEON_",
    "secrets.RENDER_",
    "secrets.CLOUDRU_",
    "secrets.CLOUD_RU_",
    "secrets.VK_",
    "check_v10_wp22a_phase4_public_acceptance.py",
)

EXPECTED_SERVICES = ["ChatGPT", "GitHub", "Timeweb Cloud", "Telegram Login"]
EXPECTED_RETIRED = ["Cloudflare", "Neon", "Render", "Cloud.ru", "VK ID"]
EXPECTED_MILESTONES = ["TW-A", "TW-B", "TW-C", "TW-D", "TW-E", "TW-F", "TW-G"]
STALE_CURRENT_AUTHORITY_MARKERS = (
    "OWNER-APPROVED PENDING GREEN MERGE",
    "Amendment 14 remains accepted authority:",
    "Current authorized functional implementation package: **NONE**.",
    "The current next prepared product package is `WEB-VISUAL-INTEGRATED`.",
    "Current authorized focused stage: **RU-PG-B",
)
STALE_PROVIDER_GUIDANCE_MARKERS = (
    "Cloudflare Workers Paid is the selected managed application/edge/build platform",
    "current GitHub/Lenovo CI routing remains authoritative until `CF-A",
    "Cloudflare services may be adopted when an owning milestone proves the need",
    "Cloudflare Workers Paid is platform rank 2 and selected new-V10",
    "Cloudflare Workers Paid is new-V10 application/edge/build platform rank 2",
    "selected managed target: `CLOUDFLARE_WORKERS_PAID`",
    "Do not create Cloudflare tokens/secrets, candidate mutation",
    "Integrated Cloudflare sequence:",
    "immutable Cloudflare candidate -> candidate acceptance",
    "`PUBLIC_MULTI_USER_ENABLED=false` remains the public activation kill switch until CF-D",
)
CURRENT_RELEASE_MARKER = (
    "exact-main post-merge GREEN -> exact Timeweb candidate -> "
    "candidate acceptance -> production promotion"
)


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
    _require(
        ci.get("postmerge_upstream_workflow") == "Regression Shield",
        "TIMEWEB_CONSOLIDATION_CI_GRAPH_INVALID",
    )
    _require(
        ci.get("timeweb_read_only_proof_workflow") == TIMEWEB_PROOF_WORKFLOW_NAME,
        "TIMEWEB_CONSOLIDATION_CI_GRAPH_INVALID",
    )
    _require(
        ci.get("retired_cloudflare_workflows")
        == list(RETIRED_CLOUDFLARE_WORKFLOW_NAMES),
        "TIMEWEB_CONSOLIDATION_CI_GRAPH_INVALID",
    )
    _require(
        ci.get("retired_provider_workflows") == list(RETIRED_PROVIDER_WORKFLOW_NAMES),
        "TIMEWEB_CONSOLIDATION_CI_GRAPH_INVALID",
    )
    for key in (
        "retired_provider_live_workflow_auto_trigger_allowed",
        "retired_provider_manual_mutation_allowed",
        "timeweb_proof_may_depend_on_retired_provider_workflow",
        "retired_provider_transitive_execution_allowed",
        "sonar_required_final",
        "active_external_review_saas_allowed",
    ):
        _require(ci.get(key) is False, "TIMEWEB_CONSOLIDATION_CI_GRAPH_INVALID")
    _require(
        ci.get("github_native_quality_authority")
        == [
            "Regression Shield",
            "V10 authoritative merge gate",
            "V10 Engineering Governance",
        ],
        "TIMEWEB_CONSOLIDATION_CI_GRAPH_INVALID",
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
    _require(
        execution.get("branch_execution_ledger")
        == "docs/updates/TIMEWEB_PLATFORM_CONSOLIDATION_EXECUTION_LEDGER.md",
        "TIMEWEB_CONSOLIDATION_LEDGER_INVALID",
    )
    _require(
        execution.get("branch_execution_ledger_required") is True,
        "TIMEWEB_CONSOLIDATION_LEDGER_INVALID",
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


def _workflow_paths() -> tuple[Path, ...]:
    paths = {
        path
        for pattern in ("*.yml", "*.yaml")
        for path in WORKFLOW_DIRECTORY.glob(pattern)
    }
    return tuple(sorted(paths))


def _validate_no_retired_provider_execution_from_active_workflows() -> None:
    retired = {path.resolve() for path in RETIRED_PROVIDER_WORKFLOWS}
    for path in _workflow_paths():
        if path.resolve() in retired:
            continue
        source = _read(path)
        if not any(trigger in source for trigger in ACTIVE_WORKFLOW_TRIGGERS):
            continue
        for marker in FORBIDDEN_RETIRED_PROVIDER_EXECUTION_MARKERS:
            _require(
                marker not in source,
                "TIMEWEB_CONSOLIDATION_ACTIVE_WORKFLOW_RETIRED_PROVIDER_EXECUTION",
            )


def _validate_active_workflow_graph() -> None:
    manual_disable_marker = "if: $" + "{{ false }}"
    expected_disabled_jobs = (1, 1, 6, 3, 1)
    for path, expected_count in zip(
        RETIRED_PROVIDER_WORKFLOWS,
        expected_disabled_jobs,
        strict=True,
    ):
        retired = _read(path)
        _require(
            "ARCHIVE-IN-PLACE" in retired,
            "TIMEWEB_CONSOLIDATION_RETIRED_WORKFLOW_NOT_ARCHIVED",
        )
        for trigger in (
            "\n  pull_request:",
            "\n  push:",
            "\n  workflow_run:",
            "\n  schedule:",
            "\n  workflow_call:",
        ):
            _require(
                trigger not in retired,
                "TIMEWEB_CONSOLIDATION_RETIRED_WORKFLOW_AUTO_TRIGGER",
            )
        _require(
            retired.count(manual_disable_marker) == expected_count,
            "TIMEWEB_CONSOLIDATION_RETIRED_WORKFLOW_MUTATION_ENABLED",
        )
        _require(
            "false &&" not in retired,
            "TIMEWEB_CONSOLIDATION_RETIRED_WORKFLOW_AMBIGUOUS_DISABLE",
        )

    for active_workflow in (WORKFLOW, AUTHORITATIVE_MERGE_WORKFLOW):
        active_source = _read(active_workflow)
        _require(
            "run: python scripts/check_v10_pr_external_review_gate.py"
            not in active_source,
            "TIMEWEB_CONSOLIDATION_EXTERNAL_REVIEW_SAAS_ACTIVE",
        )
        _require(
            "Verify exact-head Sonar review gate" not in active_source
            and "Fail fast on exact-head Sonar findings" not in active_source,
            "TIMEWEB_CONSOLIDATION_EXTERNAL_REVIEW_SAAS_ACTIVE",
        )

    _validate_no_retired_provider_execution_from_active_workflows()

    timeweb = _read(TIMEWEB_PROOF_WORKFLOW)
    for required in (
        "workflow_run:",
        "- Regression Shield",
        "github.event.workflow_run.conclusion == 'success'",
        "github.event.workflow_run.event == 'push'",
        "github.event.workflow_run.head_branch == 'main'",
    ):
        _require(required in timeweb, "TIMEWEB_CONSOLIDATION_TIMEWEB_GRAPH_DRIFT")
    for forbidden in (
        "- V10 Cloudflare Production Release",
        "secrets.CLOUDFLARE_API_TOKEN",
        "secrets.CLOUDFLARE_ACCOUNT_ID",
        "secrets.NEON_API_KEY",
        "secrets.NEON_ORG_ID",
        "secrets.NEON_PROJECT_ID",
    ):
        _require(
            forbidden not in timeweb,
            "TIMEWEB_CONSOLIDATION_TIMEWEB_GRAPH_RETIRED_DEPENDENCY",
        )


def _validate_current_guidance() -> None:
    for historical_path in (
        WP22A_EXECUTION_CONTRACT,
        WP22A_SERVICE_SELECTION,
        WP22A_IAC_DECISION,
    ):
        historical = _read(historical_path)
        _require(
            "Amendment 18" in historical and "HISTORICAL" in historical[:1200],
            "TIMEWEB_CONSOLIDATION_STALE_WP22A_PROVIDER_GUIDANCE",
        )

    status = _read(STATUS)
    for marker in STALE_CURRENT_AUTHORITY_MARKERS:
        _require(
            marker not in status,
            "TIMEWEB_CONSOLIDATION_STALE_CURRENT_STATUS",
        )
    for marker in (
        "Amendment 18 is accepted on protected `main` through PR #581",
        "current authorized System Update — **TIMEWEB-PLATFORM-CONSOLIDATION-INTEGRATED**",
        "## Current next package — TIMEWEB-PLATFORM-CONSOLIDATION-INTEGRATED",
    ):
        _require(marker in status, "TIMEWEB_CONSOLIDATION_STATUS_DRIFT")
    _require(
        "The formula below is preserved as historical Amendment-14/15 provenance only"
        in status,
        "TIMEWEB_CONSOLIDATION_HISTORICAL_RELEASE_CONTEXT_MISSING",
    )

    for path in (MASTER_CONTEXT, AGENTS, CONTRIBUTING):
        source = _read(path)
        _require(
            CURRENT_RELEASE_MARKER in source,
            "TIMEWEB_CONSOLIDATION_RELEASE_GUIDANCE_DRIFT",
        )

    for path in (README, MASTER_CONTEXT, AGENTS, CONTRIBUTING):
        source = _read(path)
        for marker in STALE_PROVIDER_GUIDANCE_MARKERS:
            _require(
                marker not in source,
                "TIMEWEB_CONSOLIDATION_STALE_PROVIDER_GUIDANCE",
            )

    for path in (GPT_NEW_CHAT, GPT_PROJECT):
        source = _read(path)
        for marker in (
            "V10_RU_PUBLIC_REGISTRATION_INGRESS_CONTRACT.json",
            "V10_RU_POSTGRES_TIMEWEB_CONTROL_PLANE_CONTRACT.json",
            "Historical Cloudflare/Neon/Render/VK",
        ):
            _require(
                marker in source,
                "TIMEWEB_CONSOLIDATION_RECOVERY_GUIDANCE_DRIFT",
            )

    inventory = _read(DATA_INVENTORY)
    _require(
        "Exact accepted-main/current-next authority is always resolved from GitHub"
        in inventory,
        "TIMEWEB_CONSOLIDATION_DATA_INVENTORY_AUTHORITY_DRIFT",
    )
    _require(
        "current accepted source behavior on exact base" not in inventory,
        "TIMEWEB_CONSOLIDATION_DATA_INVENTORY_AUTHORITY_DRIFT",
    )


def _validate_documents() -> None:
    amendment = _read(AMENDMENT)
    ledger = _read(LEDGER)
    for marker in (
        "BRANCH-LOCAL EXECUTION STATE — NOT ACCEPTED MAIN AUTHORITY",
        "TIMEWEB-PLATFORM-CONSOLIDATION-INTEGRATED",
        "system/timeweb-platform-consolidation",
        "TW-A-CI-AUTHORITY-GRAPH-REPAIR",
        "PR #582",
        "TW-A-PROVIDER-CONSUMER-INVENTORY",
        "PR #583",
        "RED_REPAIR_ONLY",
        "PUBLIC_MULTI_USER_ENABLED=false",
        "trading_methods=false",
        "REAL_TRADING_ENABLED=false",
    ):
        _require(marker in ledger, "TIMEWEB_CONSOLIDATION_LEDGER_DRIFT")
    for marker in (
        "Timeweb-Only Platform Consolidation & Telegram-Only Login Authority",
        "TIMEWEB-PLATFORM-CONSOLIDATION-INTEGRATED",
        "ChatGPT",
        "GitHub",
        "Timeweb Cloud",
        "Telegram Login",
        "VK ID — RETIRED",
        "Cloudflare — OWNER reports its external account/resources/domain zone/secrets",
        "Neon — OWNER reports its project/organization/API keys/account",
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
        _validate_active_workflow_graph()
        _validate_current_guidance()
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
