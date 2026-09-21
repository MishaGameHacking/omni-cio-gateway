from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "docs/architecture/V10_RU_PUBLIC_REGISTRATION_INGRESS_CONTRACT.json"
GUARD = ROOT / "scripts/check_v10_ru_public_registration_ingress.py"


def _contract() -> dict[str, object]:
    return json.loads(CONTRACT.read_text(encoding="utf-8"))


class RuPublicRegistrationIngressTests(unittest.TestCase):
    def test_guard_passes_current_repository(self) -> None:
        completed = subprocess.run(
            [sys.executable, str(GUARD)],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert completed.returncode == 0, completed.stderr or completed.stdout
        assert "Russia public-registration ingress authority passed" in completed.stdout

    def test_provider_set_is_exact_and_has_no_legacy_active_platform(self) -> None:
        providers = _contract()["providers"]
        assert isinstance(providers, dict)
        assert providers["exact_public_launch_set"] == [
            "GitHub",
            "Cloudflare",
            "Timeweb Cloud",
        ]
        assert providers["render_active_v10_allowed"] is False
        assert providers["cloud_ru_active_v10_allowed"] is False

    def test_cloudflare_is_not_sole_russia_ingress_authority(self) -> None:
        reachability = _contract()["cloudflare_russia_reachability"]
        assert isinstance(reachability, dict)
        assert (
            reachability["cloudflare_only_public_ingress_accepted_for_russia_launch"]
            is False
        )
        assert (
            reachability["representative_russian_network_no_vpn_evidence_required"]
            is True
        )

    def test_timeweb_app_candidate_is_exact_sha_and_not_auto_deployed(self) -> None:
        app = _contract()["timeweb_app_platform_candidate"]
        assert isinstance(app, dict)
        assert app["explicit_accepted_main_commit_required"] is True
        assert app["production_autodeploy_allowed"] is False
        assert app["runtime_secrets_in_repository_allowed"] is False
        assert app["live_public_deploy_authorized_by_contract"] is False

    def test_neon_cannot_be_deleted_before_timeweb_cutover(self) -> None:
        database = _contract()["database_end_state"]
        assert isinstance(database, dict)
        assert database["final_production_provider"] == (
            "Timeweb Cloud Managed PostgreSQL 18"
        )
        assert database["migration_sequence"] == [
            "RU-PG-B",
            "RU-PG-C",
            "RU-PG-D",
            "RU-PG-E",
        ]
        assert database["neon_active_production_retirement_stage"] == "RU-PG-E"
        assert database["neon_delete_before_ru_pg_d_allowed"] is False
        assert database["real_russian_user_data_before_ru_pg_d_allowed"] is False

    def test_single_giant_pr_is_forbidden_at_material_boundaries(self) -> None:
        execution = _contract()["execution"]
        assert isinstance(execution, dict)
        assert execution["umbrella_program_issue"] == 580
        assert execution["one_unbounded_pr_for_all_stages_allowed"] is False
        assert "RU-PG-D_PRODUCTION_DATABASE_CUTOVER" in (
            execution["mandatory_split_boundaries"]
        )
        assert "PUBLIC_USER_ACTIVATION" in execution["mandatory_split_boundaries"]

    def test_public_activation_and_real_money_remain_off(self) -> None:
        activation = _contract()["activation"]
        protected = _contract()["protected_invariants"]
        assert isinstance(activation, dict)
        assert isinstance(protected, dict)
        assert activation["public_registration_allowed_by_contract"] is False
        assert activation["telegram_first_allowed_after_owning_gates"] is True
        for key in (
            "PUBLIC_MULTI_USER_ENABLED",
            "OMNI_V10_TELEGRAM_LOGIN_ENABLED",
            "OMNI_V10_VK_ID_LOGIN_ENABLED",
            "broker_write",
            "trading_methods",
            "REAL_TRADING_ENABLED",
        ):
            assert protected[key] is False
        assert protected["protected_v9_entrypoint"] == "app:app"


if __name__ == "__main__":
    unittest.main()
