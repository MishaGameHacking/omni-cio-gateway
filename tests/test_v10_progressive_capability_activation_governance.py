from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/check_v10_progressive_capability_activation_governance.py"
CONTRACT = (
    ROOT / "docs/architecture/V10_PROGRESSIVE_CAPABILITY_ACTIVATION_CONTRACT.json"
)
LEDGER = ROOT / "docs/operations/V10_CAPABILITY_ACTIVATION_LEDGER.json"
STANDARD = ROOT / "docs/operations/V10_LIVE_USER_OPERABILITY_ACCEPTANCE_STANDARD.md"
ISSUE_TEMPLATE = ROOT / ".github/ISSUE_TEMPLATE/v10_capability_activation.yml"


def _json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


class ProgressiveCapabilityActivationGovernanceTests(unittest.TestCase):
    def test_current_repository_satisfies_progressive_activation_governance(
        self,
    ) -> None:
        completed = subprocess.run(
            [sys.executable, str(SCRIPT)],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert completed.returncode == 0, completed.stderr or completed.stdout
        assert "Capability states: IMPLEMENTED / LIVE_OPERABLE" in completed.stdout
        assert (
            "TRADE credential connection is not submit authority"
            in completed.stdout
        )
        assert (
            "Product implementation: PAUSED until exact OWNER START"
            in completed.stdout
        )

    def test_capability_state_set_is_exact(self) -> None:
        expected = [
            "IMPLEMENTED",
            "LIVE_OPERABLE",
            "BLOCKED_EXTERNAL",
            "REAL_MONEY_AUTHORIZED",
        ]
        contract = _json(CONTRACT)
        ledger = _json(LEDGER)
        assert contract["capability_states"] == expected
        assert ledger["allowed_states"] == expected
        semantics = contract["state_semantics"]
        assert isinstance(semantics, dict)
        assert semantics["unlisted_capability"] == (
            "NOT_ACCEPTED_IMPLEMENTED_AND_NO_AUTHORITY"
        )

    def test_independent_read_and_trade_connection_do_not_grant_submit(self) -> None:
        broker = _json(CONTRACT)["broker_credentials"]
        assert isinstance(broker, dict)
        assert broker["read_can_be_live_operable_before_real_execution"] is True
        assert (
            broker["trade_credential_provisioning_can_be_live_operable_before_submit"]
            is True
        )
        assert broker["trade_credential_connected_is_real_money_authorized"] is False
        assert broker["execution_account_rule"] == (
            "VERIFIED_READ_ACCOUNTS_INTERSECTION_VERIFIED_TRADE_ACCOUNTS"
        )
        assert broker["user_supplied_token_waives_broker_terms"] is False

    def test_current_external_capabilities_remain_truthfully_blocked(self) -> None:
        ledger = _json(LEDGER)
        items = ledger["capabilities"]
        assert isinstance(items, list)
        by_id = {
            item["capability_id"]: item
            for item in items
            if isinstance(item, dict)
            and isinstance(item.get("capability_id"), str)
        }
        for capability_id in (
            "product_authentication_telegram_vk",
            "public_multi_user_tenant_access",
            "t_invest_read_public_connector",
        ):
            assert by_id[capability_id]["state"] == "BLOCKED_EXTERNAL"
            blockers = by_id[capability_id]["external_blockers"]
            assert isinstance(blockers, list)
            assert blockers
        assert all(
            item.get("state") != "REAL_MONEY_AUTHORIZED"
            for item in by_id.values()
        )

    def test_real_money_requires_execution_safeguards(self) -> None:
        real_money = _json(CONTRACT)["real_money"]
        assert isinstance(real_money, dict)
        assert real_money["credential_connection_is_authorization"] is False
        required = set(real_money["required_before_authorization"])
        assert {
            "SANDBOX_OR_SHADOW_EVIDENCE",
            "IMMUTABLE_PLAN_APPROVAL",
            "DRIFT_STOP_AND_REPLAN",
            "AMBIGUOUS_SUBMIT_RECONCILIATION",
            "BROKER_RECONCILIATION",
            "EMERGENCY_KILL_SWITCHES",
        }.issubset(required)
        assert real_money["REAL_TRADING_ENABLED_current_default"] is False
        assert real_money["trading_methods_current_default"] is False
        assert real_money["transfer_withdrawal_authority_expanded"] is False
        assert real_money["margin_leverage_authority_expanded"] is False
        assert real_money["uncovered_short_authority_expanded"] is False

    def test_user_facing_definition_of_done_includes_live_operability_and_isolation(
        self,
    ) -> None:
        dod = _json(CONTRACT)["user_facing_definition_of_done"]
        assert isinstance(dod, dict)
        for key in (
            "canonical_web_deployment_required_for_live_operable",
            "ordinary_user_path_required",
            "real_user_operability_evidence_required",
            "multi_user_isolation_evidence_required_when_applicable",
            "deterministic_cross_tenant_negative_tests_required_when_applicable",
            "rollback_recovery_required",
            "capability_ledger_transition_required",
        ):
            assert dod[key] is True
        standard = STANDARD.read_text(encoding="utf-8")
        assert "real-user operability" in standard
        assert "Multi-user isolation acceptance" in standard

    def test_dashboard_is_working_state_not_progress_authority(self) -> None:
        ledgers = _json(CONTRACT)["ledgers"]
        assert isinstance(ledgers, dict)
        assert ledgers["capability_ledger_is_program_progress_authority"] is False
        assert ledgers["dashboard_is_program_progress_authority"] is False
        banner = "CAPABILITY ACTIVATION WORKING STATE — NOT V10 PROGRESS AUTHORITY"
        assert ledgers["working_state_banner"] == banner
        assert banner in ISSUE_TEMPLATE.read_text(encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
