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
PHASE4_EVIDENCE = (
    ROOT / "docs/architecture/V10_WP22A_PHASE4_ACCEPTANCE_EVIDENCE.json"
)
PHASE4_WORKFLOW = (
    ROOT / ".github/workflows/v10-wp22a-phase4-public-acceptance.yml"
)
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
VISUAL_BRIEF = (
    ROOT
    / "docs"
    / "architecture"
    / "V10_WEB_VISUAL_DESIGN_REFRESH_IMPLEMENTATION_BRIEF.md"
)


def _json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def test_phase4_acceptance_is_bound_to_exact_current_main_and_public_gate() -> None:
    payload = _json(PHASE4_EVIDENCE)

    assert payload["accepted_runtime_main_binding"] == (
        "github.event.pull_request.base.sha"
    )
    assert payload["runtime_parent_record"] == "documented_in_markdown_evidence"
    assert "accepted_runtime_main_sha" not in payload
    assert "runtime_parent_sha" not in payload
    assert payload["public_preview_url"] == (
        "https://omni-cio-v10-web.onrender.com"
    )
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
    assert "PR_BASE_SHA: ${{ github.event.pull_request.base.sha }}" in workflow
    assert '--expected-sha "$PR_BASE_SHA"' in workflow
    assert "accepted_runtime_main_sha" not in workflow


def test_status_proposes_phase4_acceptance_and_phase5_as_current() -> None:
    text = STATUS.read_text(encoding="utf-8")

    assert (
        "PHASE 3 ACCEPTED / PHASE 4 ACCEPTED / "
        "PHASE 5 TECHNICAL CLOSEOUT AUTHORIZED / "
        "PUBLIC PRODUCTION ACTIVATION LOCKED" in text
    )
    assert "Block E / WP22A Phase 4 — **ACCEPTED**" in text
    assert (
        "Block E / WP22A Phase 5 — "
        "**INTEGRATED TECHNICAL CLOSEOUT AUTHORIZED CURRENT INCREMENT**"
        in text
    )
    assert (
        "## Current next package — WP22A Phase 5 — Integrated technical closeout"
        in text
    )
    assert "WP23+ remains locked" in text
    assert "Accepted implementation progress is **40%**" in text


def test_phase5_authority_preserves_cost_and_execution_locks() -> None:
    payload = _json(PHASE5_CONTRACT)
    authority = payload["authority"]
    provider = payload["provider"]
    broker = payload["broker"]

    assert authority["phase5_authorized"] is True
    assert authority["wp22a_technical_gate_authorized"] is True
    assert authority["wp22a_technical_gate_complete"] is False
    assert authority["public_production_activation_authorized"] is False
    assert authority["wp22a_complete"] is False
    assert authority["wp23_unlocked"] is False
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

    assert payload["schema_version"].endswith(".v2")
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


def test_amendment11_is_discoverable_and_keeps_next_gates_locked() -> None:
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
        "provider doubles may be injected only below deployed routing"
        in authorization
    )
    assert "PUBLIC PRODUCTION ACTIVATION LOCKED" in status
    assert "Accepted implementation progress is **40%**" in status


def test_phase5_product_identity_is_user_tenant_session_not_provider_authority() -> None:
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


def test_visual_refresh_remains_planning_only_during_phase5_transition() -> None:
    payload = _json(PHASE5_CONTRACT)
    visual = payload["visual_refresh"]
    authorization = PHASE5_AUTHORIZATION.read_text(encoding="utf-8")
    brief = VISUAL_BRIEF.read_text(encoding="utf-8")

    assert visual["owner_approved_direction"] is True
    assert visual["implementation_authorized_by_this_contract"] is False
    assert visual["second_frontend_allowed"] is False
    assert "planning-only" in authorization
    assert "NOT CURRENT-WP AUTHORITY BY ITSELF" in brief
