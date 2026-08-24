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
    / "OMNI_CIO_V10_WP22A_TECHNICAL_CLOSEOUT_AND_PUBLIC_ACTIVATION_SEPARATION_AMENDMENT.md"
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
    assert "PR_BASE_REF: ${{ github.event.pull_request.base.ref }}" in workflow
    assert '--expected-sha "$PR_BASE_SHA"' in workflow
    assert "accepted_runtime_main_sha" not in workflow


def test_historical_phase4_live_probe_is_not_coupled_to_phase5_status_changes() -> None:
    workflow = PHASE4_WORKFLOW.read_text(encoding="utf-8")

    for path in (
        "docs/architecture/V10_WP22A_PHASE5_PUBLIC_HOSTED_ACCEPTANCE_AUTHORIZATION.md",
        "docs/architecture/V10_WP22A_PHASE5_PUBLIC_HOSTED_ACCEPTANCE_CONTRACT.json",
        "knowledge/17_V10_CURRENT_PROGRAM_STATUS.md",
        "tests/test_v10_wp22a_phase5_transition.py",
    ):
        assert f'- "{path}"' not in workflow

    assert "Route historical Phase 4 live probe by changed authority surface" in workflow
    assert "PHASE4_LIVE_PROBE_REQUIRED" in workflow
    assert (
        "PHASE4_PUBLIC_ACCEPTANCE_ROUTING=PASS "
        "reason=historical_phase4_runtime_authority_unchanged"
    ) in workflow
    assert "if: env.PHASE4_LIVE_PROBE_REQUIRED == 'true'" in workflow
    assert "docs/architecture/V10_WP22A_PHASE4_ACCEPTANCE_EVIDENCE.json" in workflow
    assert "docs/architecture/V10_WP22A_PHASE4_ACCEPTANCE_EVIDENCE.md" in workflow
    assert "scripts/check_v10_wp22a_phase4_public_acceptance.py" in workflow


def test_status_keeps_phase5_current_and_wp23_locked() -> None:
    text = STATUS.read_text(encoding="utf-8")

    assert (
        "PHASE 3 ACCEPTED / PHASE 4 ACCEPTED / PHASE 5 AUTHORIZED" in text
    )
    assert "Block E / WP22A Phase 4 — **ACCEPTED**" in text
    assert "Block E / WP22A Phase 5 — **AUTHORIZED CURRENT INCREMENT**" in text
    assert (
        "## Current next package — WP22A Phase 5 — Public-hosted acceptance"
        in text
    )
    assert "WP23+ remains locked" in text
    assert "Accepted implementation progress is **40%**" in text
    assert "one integrated WP22A Phase-5 technical-closeout implementation" in text
    assert "`PUBLIC_MULTI_USER_ENABLED=false`" in text


def test_amendment11_is_registered_as_sequencing_only() -> None:
    index = AMENDMENTS_INDEX.read_text(encoding="utf-8")
    amendment = AMENDMENT11.read_text(encoding="utf-8")

    assert "### 11. WP22A Technical Closeout / Public Activation Separation" in index
    assert AMENDMENT11.name in index
    assert "sequencing only" in index
    assert "The only supported human product-login protocols are:" in amendment
    assert "Telegram Login" in amendment
    assert "VK ID" in amendment
    assert "No third human login path exists." in amendment
    assert "PUBLIC_MULTI_USER_ENABLED=true" in amendment
    assert "later independent fail-closed gate" in amendment
    assert "does not by itself mark Phase 5 accepted" in amendment
    assert "does not unlock WP23" in amendment


def test_phase5_authority_preserves_cost_and_execution_locks() -> None:
    payload = _json(PHASE5_CONTRACT)
    authority = payload["authority"]
    provider = payload["provider"]
    activation = payload["public_production_activation"]
    broker = payload["broker"]

    assert payload["schema_version"] == (
        "v10.wp22a.phase5.public-hosted-acceptance.v2"
    )
    assert payload["status"] == (
        "WP22A_TECHNICAL_CLOSEOUT_AUTHORIZED_PUBLIC_ACTIVATION_LOCKED"
    )
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
    assert activation["public_multi_user_enabled"] is False
    assert activation["provider_apply_authorized"] is False
    assert activation["real_user_cutover_authorized"] is False
    assert activation["current_authorized_recurring_rub"] == 0
    assert activation["current_authorized_recurring_usd"] == 0
    assert activation["automatic_paid_fallback_allowed"] is False
    assert broker["broker_write_enabled"] is False
    assert broker["trading_methods"] is False
    assert broker["real_trading_enabled"] is False
    assert broker["public_tinvest_status"] == (
        "FAIL_CLOSED_PENDING_BROKER_TERMS_PERMISSION"
    )


def test_phase5_technical_closeout_forbids_human_session_bypass() -> None:
    payload = _json(PHASE5_CONTRACT)
    technical = payload["technical_closeout"]
    product = payload["product_path"]
    access = payload["initial_user_access"]

    assert technical["hosted_synthetic_acceptance_allowed"] is True
    assert technical["real_provider_secret_required_for_gate"] is False
    assert technical["human_login_protocols"] == ["telegram", "vk_id"]
    assert technical["human_session_bypass_allowed"] is False
    assert technical[
        "deterministic_provider_double_may_mint_human_product_session"
    ] is False
    assert technical["browser_bound_pre_auth_required"] is True
    assert technical["durable_pre_auth_required"] is True
    assert technical["one_time_atomic_pre_auth_consume_required"] is True
    assert technical[
        "provider_mixup_replay_browser_swap_negative_tests_required"
    ] is True
    assert product["human_product_login_protocols_only"] is True
    assert product["human_session_bypass_allowed"] is False
    assert access["authentication_required"] is True
    assert access["anonymous_demo_product_session_allowed"] is False


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
