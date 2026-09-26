from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/check_v10_progressive_capability_activation.py"
CONTRACT = (
    ROOT / "docs/architecture/V10_PROGRESSIVE_CAPABILITY_ACTIVATION_CONTRACT.json"
)
LEDGER = ROOT / "docs/updates/V10_CAPABILITY_ACTIVATION_LEDGER_TEMPLATE.md"
ISSUE_TEMPLATE = ROOT / ".github/ISSUE_TEMPLATE/v10_capability_activation.yml"
STATUS = ROOT / "knowledge/17_V10_CURRENT_PROGRAM_STATUS.md"

EXPECTED_STATES = [
    "IMPLEMENTED",
    "LIVE_OPERABLE",
    "BLOCKED_EXTERNAL",
    "REAL_MONEY_AUTHORIZED",
]


def _contract() -> dict[str, object]:
    return json.loads(CONTRACT.read_text(encoding="utf-8"))


class ProgressiveCapabilityActivationTests(unittest.TestCase):
    def test_current_repository_satisfies_progressive_activation_law(self) -> None:
        completed = subprocess.run(
            [sys.executable, str(SCRIPT)],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert completed.returncode == 0, completed.stderr or completed.stdout
        assert "one canonical Web" in completed.stdout
        assert "REAL_MONEY_AUTHORIZED" in completed.stdout

    def test_activation_state_enum_is_exact(self) -> None:
        payload = _contract()
        assert payload["activation_states"] == EXPECTED_STATES

    def test_current_live_capabilities_remain_blocked_external(self) -> None:
        payload = _contract()
        capabilities = {
            item["id"]: item
            for item in payload["current_capabilities"]
            if isinstance(item, dict)
        }
        assert set(capabilities) == {
            "telegram_login",
            "public_multi_user_tenant_access",
            "tinvest_read",
        }
        assert all(
            item["implementation_complete"] is True
            and item["state"] == "BLOCKED_EXTERNAL"
            and item["blockers"]
            for item in capabilities.values()
        )
        assert (
            capabilities["public_multi_user_tenant_access"]["runtime_flag"]
            == "PUBLIC_MULTI_USER_ENABLED=false"
        )
        assert capabilities["tinvest_read"]["external_gate"] == (
            "FAIL_CLOSED_PENDING_BROKER_TERMS_PERMISSION"
        )

    def test_read_is_independent_but_trade_connection_is_not_submit(self) -> None:
        broker = _contract()["broker"]
        assert isinstance(broker, dict)
        assert broker["read_independent_from_real_execution"] is True
        assert broker["read_live_operability_must_not_wait_real_execution"] is True
        assert broker["trade_credential_connected_does_not_authorize_submit"] is True
        assert broker["trade_credential_never_fallback_for_reads"] is True
        assert broker["executable_accounts_formula"] == (
            "VERIFIED_READ_ACCOUNTS ∩ VERIFIED_TRADE_ACCOUNTS"
        )
        assert broker["mismatched_account_identity_fails_closed"] is True
        assert broker["trading_methods_is_global_master_switch"] is False
        assert broker["read_only_contours_require_trading_methods_false"] is True
        assert broker["real_execution_surface_uses_real_trading_methods"] is True
        assert (
            broker["timeweb_hosted_runtime_may_import_v9_real_trading_gateway"] is False
        )
        assert (
            broker["timeweb_hosted_runtime_may_consume_global_tinvest_trading_token"]
            is False
        )
        assert (
            broker["v10_real_execution_requires_tenant_scoped_trade_credential"] is True
        )
        assert (
            broker["v10_real_execution_requires_authenticated_server_session"] is True
        )
        assert broker["v10_real_execution_is_mandatory_split_boundary"] is True

    def test_real_submit_requires_full_real_money_gate(self) -> None:
        broker = _contract()["broker"]
        assert isinstance(broker, dict)
        assert broker["sandbox_shadow_before_real"] is True
        assert broker["real_submit_requires_state"] == "REAL_MONEY_AUTHORIZED"
        for key in (
            "real_submit_requires_immutable_plan",
            "real_submit_requires_user_approval",
            "real_submit_requires_drift_preflight",
            "real_submit_requires_ambiguous_submit_reconciliation",
            "real_submit_requires_kill_switches",
            "real_submit_requires_broker_terms_permission",
            "submitted_is_not_filled_without_broker_evidence",
        ):
            assert broker[key] is True
        for key in (
            "transfer_withdrawal_authority",
            "margin_leverage_authority",
            "uncovered_short_authority",
        ):
            assert broker[key] is False

    def test_governance_does_not_activate_current_runtime(self) -> None:
        payload = _contract()
        authority = payload["authority"]
        runtime = payload["current_runtime_defaults"]
        assert isinstance(authority, dict)
        assert isinstance(runtime, dict)
        assert authority["product_progress_effect"] == "NONE"
        assert authority["runtime_mutation_effect"] == "NONE"
        assert authority["product_implementation_paused_after_acceptance"] is False
        assert (
            authority["current_system_update"]
            == "TIMEWEB-PLATFORM-CONSOLIDATION-INTEGRATED"
        )
        assert authority["owner_start_command"] is None
        assert authority["amendment_18_current_overlay"] is True
        assert authority["web_visual_paused"] is True
        assert authority["wp23_plus_locked"] is True
        assert runtime["app_entrypoint"] == "app:app"
        assert runtime["PUBLIC_MULTI_USER_ENABLED"] is False
        assert runtime["OMNI_V10_TELEGRAM_LOGIN_ENABLED"] is False
        assert runtime["trading_methods"] is False
        assert runtime["broker_write"] is False
        assert runtime["REAL_TRADING_ENABLED"] is False
        assert runtime["public_tinvest_state"] == (
            "FAIL_CLOSED_PENDING_BROKER_TERMS_PERMISSION"
        )

    def test_live_user_definition_of_done_preserves_isolation(self) -> None:
        dod = _contract()["real_user_definition_of_done"]
        model = _contract()["product_model"]
        assert isinstance(dod, dict)
        assert isinstance(model, dict)
        for key in (
            "automated_verification_required",
            "canonical_deployed_web_required_when_live_provable",
            "real_supported_user_interaction_required_when_live_provable",
            "multi_user_isolation_negatives_required_where_applicable",
            "monitoring_required",
            "rollback_or_recovery_required",
            "sanitized_evidence_only",
        ):
            assert dod[key] is True
        assert model["one_canonical_web"] is True
        assert model["separate_user_facing_staging_required"] is False
        assert model["second_product_or_auth_bypass_allowed"] is False

    def test_activation_ledgers_are_non_authoritative_working_state(self) -> None:
        ledgers = _contract()["working_ledgers"]
        assert isinstance(ledgers, dict)
        banner = "WORKING CAPABILITY ACTIVATION STATE — NOT ACCEPTED MAIN AUTHORITY"
        assert ledgers["working_state_banner"] == banner
        assert ledgers["current_status_authority_remains"] == (
            "knowledge/17_V10_CURRENT_PROGRAM_STATUS.md"
        )
        assert banner in LEDGER.read_text(encoding="utf-8")
        assert banner in ISSUE_TEMPLATE.read_text(encoding="utf-8")

        status = STATUS.read_text(encoding="utf-8")
        for marker in (
            "TIMEWEB-PLATFORM-CONSOLIDATION-INTEGRATED",
            "Telegram Login = sole selected human product login provider",
            "Amendment 13 — progressive capability activation",
            "current runtime state, not a V10-wide release lock",
        ):
            assert marker in status


if __name__ == "__main__":
    unittest.main()
