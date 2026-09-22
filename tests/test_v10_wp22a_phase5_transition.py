from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STATUS = ROOT / "knowledge/17_V10_CURRENT_PROGRAM_STATUS.md"
AMENDMENTS_INDEX = ROOT / "docs/master-plan/OMNI_CIO_V10_AMENDMENTS_INDEX.md"
AMENDMENT11 = (
    ROOT
    / "docs"
    / "master-plan"
    / (
        "OMNI_CIO_V10_WP22A_TECHNICAL_CLOSEOUT_AND_"
        "PUBLIC_ACTIVATION_SEPARATION_AMENDMENT.md"
    )
)
PHASE4_EVIDENCE = ROOT / "docs/architecture/V10_WP22A_PHASE4_ACCEPTANCE_EVIDENCE.json"
PHASE4_WORKFLOW = ROOT / ".github/workflows/v10-wp22a-phase4-public-acceptance.yml"
PHASE5_CONTRACT = (
    ROOT
    / "docs"
    / "architecture"
    / "V10_WP22A_PHASE5_PUBLIC_HOSTED_ACCEPTANCE_CONTRACT.json"
)
PHASE5_AUTHORIZATION = (
    ROOT
    / "docs"
    / "architecture"
    / "V10_WP22A_PHASE5_PUBLIC_HOSTED_ACCEPTANCE_AUTHORIZATION.md"
)
PHASE5_EVIDENCE = (
    ROOT
    / "docs"
    / "architecture"
    / "V10_WP22A_PHASE5_TECHNICAL_ACCEPTANCE_EVIDENCE.json"
)
PHASE5_CLOSEOUT_WORKFLOW = (
    ROOT / ".github/workflows/v10-wp22a-phase5-technical-closeout.yml"
)
VISUAL_BRIEF = (
    ROOT
    / "docs"
    / "architecture"
    / "V10_WEB_VISUAL_DESIGN_REFRESH_IMPLEMENTATION_BRIEF.md"
)


def _json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _assert_archived_provider_workflow(workflow: str, refusal_marker: str) -> None:
    assert "ARCHIVE-IN-PLACE" in workflow
    assert "\n  workflow_dispatch:" in workflow
    for trigger in (
        "\n  pull_request:",
        "\n  push:",
        "\n  workflow_run:",
        "\n  schedule:",
        "\n  workflow_call:",
    ):
        assert trigger not in workflow
    assert "if: $" + "{{ false }}" in workflow
    assert refusal_marker in workflow
    assert "no retired V10 provider probe is authorized." in workflow


def test_phase4_acceptance_evidence_is_historical_and_workflow_is_archived() -> None:
    payload = _json(PHASE4_EVIDENCE)

    assert payload["accepted_runtime_main_binding"] == (
        "github.event.pull_request.base.sha"
    )
    assert payload["runtime_parent_record"] == "documented_in_markdown_evidence"
    assert "accepted_runtime_main_sha" not in payload
    assert "runtime_parent_sha" not in payload
    assert payload["public_preview_url"] == ("https://omni-cio-v10-web.onrender.com")
    gate = payload["required_transition_gate"]
    assert gate["exact_pr_base_sha_required"] is True
    assert gate["external_https_probe_required"] is True
    assert gate["ordinary_html_shell_probe_required"] is True
    assert gate["release_sha_match_required"] is True
    assert gate["database_ready_required"] is True
    assert gate["synthetic_preview_required"] is True
    assert gate["cache_no_store_required"] is True
    assert gate["hsts_required"] is True

    workflow = PHASE4_WORKFLOW.read_text(encoding="utf-8")
    _assert_archived_provider_workflow(
        workflow,
        "LEGACY_WP22A_PHASE4_RENDER_ACCEPTANCE_RETIRED_AMENDMENT_18",
    )
    assert "PR_BASE_SHA: ${{ github.event.pull_request.base.sha }}" not in workflow
    assert '--expected-sha "$PR_BASE_SHA"' not in workflow
    assert "accepted_runtime_main_sha" not in workflow
    assert "check_v10_wp22a_phase4_public_acceptance.py" not in workflow


def test_phase5_closeout_evidence_maps_accepted_exact_main_chain() -> None:
    evidence = _json(PHASE5_EVIDENCE)

    assert evidence["status"] == (
        "PROPOSED_ACCEPTANCE_EFFECTIVE_ONLY_AFTER_CLOSEOUT_GREEN_MERGE"
    )
    assert evidence["accepted_runtime_main_binding"] == (
        "github.event.pull_request.base.sha"
    )
    implementation = evidence["integrated_implementation"]
    assert implementation["pull_request"] == 391
    assert implementation["exact_head_sha"] == (
        "936f334c4037479d0b2bb99651fa5c8e7dd92b02"
    )
    assert implementation["accepted_main_sha"] == (
        "bb15739acf82ded8eafb6d006cf222fb3988770d"
    )
    assert implementation["draft_green_required"] is True
    assert implementation["fresh_ready_green_required"] is True
    assert implementation["independent_gitar_sonar_required"] is True
    assert implementation["zero_unresolved_blocking_threads_required"] is True

    post_merge = evidence["post_merge_acceptance"]
    assert post_merge["regression_shield_run_id"] == 32958019958
    assert post_merge["regression_shield_conclusion"] == "success"
    assert post_merge["required_regression_jobs_success"] is True
    assert post_merge["all_exact_main_push_workflows_success"] is True

    hosted = evidence["hosted_exact_release"]
    assert hosted["workflow_run_id"] == 32960260373
    assert hosted["workflow_attempt"] == 2
    assert hosted["workflow_conclusion"] == "success"
    assert hosted["exact_main_sha"] == implementation["accepted_main_sha"]
    assert hosted["zero_charge_attestation"] == "PASS_FRESH_NO_PAYMENT_METHOD"
    assert hosted["neon_organization_plan"] == "FREE_VERIFIED"
    assert hosted["database_bootstrap"] == "PASS"
    assert hosted["render_deploy"] == "LIVE_EXACT_SHA"
    assert hosted["external_https_probe"] == "PASS"

    assert all(evidence["technical_exit_gate"].values())
    effect = evidence["closeout_effect_on_green_merge"]
    assert effect["wp22a_technical_gate_complete"] is True
    assert effect["wp22a_complete"] is True
    assert effect["accepted_v10_progress_percent"] == 54
    assert effect["visual_refresh_increment_a_authorized"] is True
    assert effect["wp23_unlocked"] is False

    locks = evidence["locks_preserved"]
    assert locks["public_production_activation_authorized"] is False
    assert locks["public_multi_user_enabled"] is False
    assert locks["cloudru_provider_apply_authorized"] is False
    assert locks["real_user_cutover_authorized"] is False
    assert locks["broker_write_enabled"] is False
    assert locks["trading_methods"] is False
    assert locks["real_trading_enabled"] is False
    assert locks["protected_v9_entrypoint"] == "app:app"


def test_status_closes_wp22a_and_preserves_history_before_timeweb_update() -> None:
    text = STATUS.read_text(encoding="utf-8")

    assert "WP0–WP22A COMPLETE" in text
    assert "Block E / WP22A Phase 5 — **ACCEPTED**" in text
    assert "Block E / WP22A overall — **COMPLETE**" in text
    assert "Block E — **COMPLETE (14%)**" in text
    assert "TIMEWEB-PLATFORM-CONSOLIDATION-INTEGRATED" in text
    assert "## Current next package — TIMEWEB-PLATFORM-CONSOLIDATION-INTEGRATED" in text
    assert (
        "Cloudflare Public Product System Update — "
        "**HISTORICAL ACCEPTED COMPLETE / ARCHIVE-IN-PLACE**" in text
    )
    assert "CF-A / CLOUDFLARE-BUILDS-VERIFIER-INTEGRATION" in text
    assert "CF-B / CLOUDFLARE-RUNTIME-COMPATIBILITY" in text
    assert "CF-C / CLOUDFLARE-CANDIDATE-DEPLOYMENT" in text
    assert "CF-D / CLOUDFLARE-PUBLIC-CUTOVER" in text
    assert "### Prepared product package — WEB-VISUAL-INTEGRATED" in text
    assert "START V10 WEB VISUAL SYSTEM UPDATE" in text
    assert "WP23+ remains locked" in text
    assert "Accepted implementation progress is **54%**" in text
    assert "`PUBLIC_MULTI_USER_ENABLED=false`" in text
    assert "current runtime state, not a V10-wide release lock" in text
    assert "current user-facing activation transitions — **BLOCKED_EXTERNAL" in text


def test_phase5_authority_closes_technical_gate_without_widening_locks() -> None:
    payload = _json(PHASE5_CONTRACT)
    authority = payload["authority"]
    provider = payload["provider"]
    broker = payload["broker"]

    assert authority["phase5_authorized"] is True
    assert authority["wp22a_technical_gate_authorized"] is True
    assert authority["wp22a_technical_gate_complete"] is True
    assert authority["public_production_activation_authorized"] is False
    assert authority["wp22a_complete"] is True
    assert authority["wp23_unlocked"] is False
    assert authority["visual_refresh_runtime_authorized"] is True
    assert provider["production_provider"] == "Cloud.ru Evolution"
    assert provider["provider_apply_authorized"] is False
    assert provider["current_authorized_recurring_rub"] == 0
    assert provider["current_authorized_recurring_usd"] == 0
    assert provider["automatic_paid_fallback_allowed"] is False
    assert provider["owner_cost_approval_required_above_current_cap"] is True
    assert broker["broker_write_enabled"] is False
    assert broker["trading_methods"] is False
    assert broker["real_trading_enabled"] is False
    assert broker["public_tinvest_status"] == (
        "FAIL_CLOSED_PENDING_BROKER_TERMS_PERMISSION"
    )


def test_amendment11_separates_technical_closeout_from_public_activation() -> None:
    payload = _json(PHASE5_CONTRACT)
    technical = payload["technical_closeout"]
    production = payload["public_production_activation"]
    legacy_activation = payload["activation"]

    assert payload["schema_version"].endswith(".v3")
    assert technical["hosted_synthetic_acceptance_allowed"] is True
    assert technical["real_provider_secret_required_for_gate"] is False
    assert technical["human_login_protocols"] == ["telegram", "vk_id"]
    assert technical["human_session_bypass_allowed"] is False
    assert technical["provider_double_below_deployed_routing_only"] is True
    assert technical["browser_bound_pre_auth_required"] is True
    assert technical["durable_pre_auth_required"] is True
    assert technical["cross_tenant_negative_tests_required"] is True
    assert technical["recovery_and_rollback_required"] is True

    assert production["production_provider"] == "Cloud.ru Evolution"
    assert production["public_multi_user_enabled"] is False
    assert production["provider_apply_authorized"] is False
    assert production["real_user_cutover_authorized"] is False
    assert production["current_authorized_recurring_rub"] == 0
    assert production["current_authorized_recurring_usd"] == 0
    assert production["automatic_paid_fallback_allowed"] is False
    assert production["production_dns_edge_mutation_authorized"] is False
    assert production["production_provider_secret_provisioning_authorized"] is False
    assert legacy_activation["deprecated_by"] == "public_production_activation"
    assert legacy_activation["activation_requires_focused_phase5_gate"] is False


def test_amendment11_is_discoverable_and_keeps_next_gates_locked() -> None:
    payload = _json(PHASE5_CONTRACT)
    amendment = AMENDMENT11.read_text(encoding="utf-8")
    index = AMENDMENTS_INDEX.read_text(encoding="utf-8")
    authorization = PHASE5_AUTHORIZATION.read_text(encoding="utf-8")
    status = STATUS.read_text(encoding="utf-8")

    assert AMENDMENT11.name in index
    for marker in (
        "exactly Telegram Login and VK ID",
        "`PUBLIC_MULTI_USER_ENABLED=false`",
        "`provider_apply_authorized=false`",
        "`trading_methods=false`",
        "`REAL_TRADING_ENABLED=false`",
        "WP23 remains locked",
        "Protected V9 `app:app` rollback",
    ):
        assert marker in amendment

    assert "no deployed `preview-login`" in authorization
    assert (
        "provider doubles may be injected only below deployed routing" in authorization
    )
    assert "Amendment 13 — progressive capability activation" in status
    assert "current runtime state, not a V10-wide release lock" in status
    assert "BLOCKED_EXTERNAL" in status
    assert "Accepted implementation progress is **54%**" in status
    assert payload["provider"]["production_provider"] == "Cloud.ru Evolution"


def test_phase5_product_identity_is_user_tenant_session_not_provider_authority() -> (
    None
):
    payload = _json(PHASE5_CONTRACT)
    product = payload["product_path"]
    session = payload["session"]
    tenant = payload["tenant"]

    assert product["normal_browser_required"] is True
    assert product["owner_home_availability_dependency_allowed"] is False
    assert product["external_identity_providers"] == ["telegram", "vk_id"]
    assert product["provider_identity_is_product_identity"] is False
    assert product["owner_special_product_role_allowed"] is False
    assert session["server_side_required"] is True
    assert session["browser_web_storage_tokens_allowed"] is False
    assert session["logout_required"] is True
    assert session["revoke_all_required"] is True
    assert tenant["server_resolved_scope_required"] is True
    assert tenant["client_supplied_tenant_authority_allowed"] is False
    assert tenant["cross_tenant_negative_tests_required"] is True


def test_visual_refresh_increment_a_was_explicitly_authorized_by_phase5() -> None:
    payload = _json(PHASE5_CONTRACT)
    visual = payload["visual_refresh"]
    brief = VISUAL_BRIEF.read_text(encoding="utf-8")

    assert visual["owner_approved_direction"] is True
    assert visual["implementation_authorized_by_this_contract"] is True
    assert visual["current_increment"] == "A_DESIGN_SYSTEM_FOUNDATION"
    assert visual["product_semantic_changes_allowed"] is False
    assert visual["second_frontend_allowed"] is False
    assert "### Increment A — Design-system foundation" in brief
    assert "- `tokens.css`;" in brief
    assert "- `base.css`;" in brief
    assert "- no product-semantic changes." in brief


def test_closeout_workflow_is_archived_after_timeweb_supersession() -> None:
    workflow = PHASE5_CLOSEOUT_WORKFLOW.read_text(encoding="utf-8")

    _assert_archived_provider_workflow(
        workflow,
        "LEGACY_WP22A_PHASE5_RENDER_CLOSEOUT_RETIRED_AMENDMENT_18",
    )
    assert "permissions:\n  contents: read" in workflow
    for marker in (
        "actions: read",
        "PR_BASE_SHA: ${{ github.event.pull_request.base.sha }}",
        "EXPECTED_MAIN_SHA: ${{ github.event.pull_request.base.sha }}",
        "python scripts/check_v10_exact_main_regression.py",
        "python scripts/check_v10_public_product_plan.py",
        "python -m pytest -q tests/test_v10_wp22a_phase5_transition.py",
        '--expected-sha "$PR_BASE_SHA"',
        "check_v10_wp22a_phase4_public_acceptance.py",
        "RENDER_API_KEY",
        "NEON_API_KEY",
    ):
        assert marker not in workflow
