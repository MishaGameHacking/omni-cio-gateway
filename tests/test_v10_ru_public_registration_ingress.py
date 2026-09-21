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


class TimewebPlatformConsolidationTests(unittest.TestCase):
    def test_guard_passes_current_repository(self) -> None:
        completed = subprocess.run(
            [sys.executable, str(GUARD)],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr or completed.stdout)
        self.assertIn(
            "Timeweb-only platform consolidation authority passed",
            completed.stdout,
        )

    def test_active_service_set_is_exact(self) -> None:
        payload = _contract()
        self.assertEqual(
            payload["active_general_service_set"],
            ["ChatGPT", "GitHub", "Timeweb Cloud", "Telegram Login"],
        )
        self.assertEqual(
            payload["retired_active_services"],
            ["Cloudflare", "Neon", "Render", "Cloud.ru", "VK ID"],
        )

    def test_timeweb_is_only_production_platform_and_pg18(self) -> None:
        payload = _contract()
        service = payload["service_model"]
        timeweb = payload["timeweb"]
        database = payload["database"]
        self.assertIsInstance(service, dict)
        self.assertIsInstance(timeweb, dict)
        self.assertIsInstance(database, dict)
        assert isinstance(service, dict)
        assert isinstance(timeweb, dict)
        assert isinstance(database, dict)
        self.assertEqual(service["production_platform"], "Timeweb Cloud")
        self.assertEqual(timeweb["managed_postgresql_major"], 18)
        self.assertEqual(
            database["final_provider"],
            "Timeweb Cloud Managed PostgreSQL 18",
        )

    def test_vk_and_session_bypasses_are_retired(self) -> None:
        auth = _contract()["auth"]
        self.assertIsInstance(auth, dict)
        assert isinstance(auth, dict)
        self.assertEqual(auth["human_identity_providers"], ["telegram"])
        self.assertFalse(auth["vk_id_active_allowed"])
        self.assertFalse(auth["owner_admin_demo_preview_session_bypass_allowed"])

    def test_neon_cannot_be_deleted_before_cutover(self) -> None:
        database = _contract()["database"]
        self.assertIsInstance(database, dict)
        assert isinstance(database, dict)
        self.assertFalse(database["neon_new_feature_work_allowed"])
        self.assertFalse(database["neon_delete_before_timeweb_cutover_allowed"])

    def test_legacy_provider_files_are_archive_in_place(self) -> None:
        cleanup = _contract()["cleanup"]
        self.assertIsInstance(cleanup, dict)
        assert isinstance(cleanup, dict)
        self.assertTrue(cleanup["retired_provider_files_may_remain_archive_in_place"])
        self.assertFalse(cleanup["mass_repository_deletion_required"])
        self.assertFalse(
            cleanup["historical_artifacts_may_define_current_authority"]
        )
        self.assertFalse(
            cleanup["new_feature_dependencies_on_retired_providers_allowed"]
        )
        self.assertFalse(cleanup["git_history_rewrite_for_cleanup_allowed"])
        self.assertFalse(cleanup["provider_physical_media_erasure_claim_allowed"])

    def test_one_branch_default_preserves_split_boundaries(self) -> None:
        execution = _contract()["execution"]
        self.assertIsInstance(execution, dict)
        assert isinstance(execution, dict)
        self.assertTrue(execution["source_one_branch_default"])
        self.assertEqual(
            execution["milestones"],
            ["TW-A", "TW-B", "TW-C", "TW-D", "TW-E", "TW-F", "TW-G"],
        )
        self.assertIn(
            "PRODUCTION_DATABASE_CUTOVER",
            execution["mandatory_split_boundaries"],
        )
        self.assertIn(
            "EXTERNAL_PROVIDER_DECOMMISSION",
            execution["mandatory_split_boundaries"],
        )

    def test_external_legacy_provider_rollback_is_unavailable(self) -> None:
        decommission = _contract()["external_decommission"]
        self.assertIsInstance(decommission, dict)
        assert isinstance(decommission, dict)
        self.assertTrue(decommission["owner_supplied_visual_evidence"])
        self.assertFalse(decommission["cloudflare_rollback_available"])
        self.assertFalse(decommission["neon_rollback_available"])
        self.assertFalse(
            decommission["provider_side_physical_erasure_independently_verified"]
        )

    def test_domain_mismatch_blocks_dns_and_telegram_cutover(self) -> None:
        payload = _contract()
        timeweb = payload["timeweb"]
        activation = payload["activation"]
        self.assertIsInstance(timeweb, dict)
        self.assertIsInstance(activation, dict)
        assert isinstance(timeweb, dict)
        assert isinstance(activation, dict)
        self.assertIsNone(timeweb["canonical_domain_target"])
        self.assertEqual(
            timeweb["canonical_domain_candidates_observed"],
            ["omnicio.ru", "omni-cio.ru"],
        )
        self.assertTrue(timeweb["canonical_domain_owner_confirmation_required"])
        self.assertFalse(timeweb["dns_cutover_allowed_before_domain_confirmation"])
        self.assertTrue(activation["telegram_canonical_origin_reconfirmation_required"])

    def test_public_and_real_money_flags_remain_fail_closed(self) -> None:
        protected = _contract()["protected_invariants"]
        self.assertIsInstance(protected, dict)
        assert isinstance(protected, dict)
        for key in (
            "PUBLIC_MULTI_USER_ENABLED",
            "OMNI_V10_TELEGRAM_LOGIN_ENABLED",
            "broker_write",
            "trading_methods",
            "REAL_TRADING_ENABLED",
        ):
            self.assertFalse(protected[key])


if __name__ == "__main__":
    unittest.main()
