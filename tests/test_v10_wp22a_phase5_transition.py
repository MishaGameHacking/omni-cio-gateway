from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STATUS = ROOT / "knowledge/17_V10_CURRENT_PROGRAM_STATUS.md"
PHASE4_EVIDENCE = (
    ROOT / "docs/architecture/V10_WP22A_PHASE4_ACCEPTANCE_EVIDENCE.json"
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

    assert payload["accepted_runtime_main_sha"] == (
        "4b8b0ce71e33c5e7b723e2f748a6fcf334bf6481"
    )
    assert payload["runtime_parent_sha"] == (
        "235ebfd386d46b74fb2428085ac233aa4494d696"
    )
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


def test_status_proposes_phase4_acceptance_and_phase5_as_current() -> None:
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


def test_phase5_authority_preserves_cost_and_execution_locks() -> None:
    payload = _json(PHASE5_CONTRACT)
    authority = payload["authority"]
    provider = payload["provider"]
    broker = payload["broker"]

    assert authority["phase5_authorized"] is True
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
