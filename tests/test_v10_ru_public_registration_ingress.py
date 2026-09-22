from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "docs/architecture/V10_RU_PUBLIC_REGISTRATION_INGRESS_CONTRACT.json"
GUARD = ROOT / "scripts/check_v10_ru_public_registration_ingress.py"
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
WP22A_CLIENTLESS_WORKFLOW = (
    ROOT / ".github/workflows/v10-wp22a-clientless-access-audit.yml"
)
WP22A_PHASE4_PUBLIC_ACCEPTANCE_WORKFLOW = (
    ROOT / ".github/workflows/v10-wp22a-phase4-public-acceptance.yml"
)
WP22A_PHASE5_TECHNICAL_CLOSEOUT_WORKFLOW = (
    ROOT / ".github/workflows/v10-wp22a-phase5-technical-closeout.yml"
)


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

    def test_document_guard_does_not_require_transient_checkpoint_state(self) -> None:
        source = GUARD.read_text(encoding="utf-8")
        document_guard = source.split("def _validate_documents()", 1)[1].split(
            "def main()", 1
        )[0]
        self.assertNotIn('"RED_REPAIR_ONLY"', document_guard)
        self.assertIn('"TW-A-PROVIDER-CONSUMER-INVENTORY"', document_guard)
        self.assertIn('"PR #583"', document_guard)

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
        self.assertFalse(cleanup["historical_artifacts_may_define_current_authority"])
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
        self.assertTrue(execution["branch_execution_ledger_required"])
        self.assertEqual(
            execution["branch_execution_ledger"],
            "docs/updates/TIMEWEB_PLATFORM_CONSOLIDATION_EXECUTION_LEDGER.md",
        )
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

    def test_omnicio_ru_is_confirmed_without_authorizing_cutover(self) -> None:
        payload = _contract()
        timeweb = payload["timeweb"]
        activation = payload["activation"]
        self.assertIsInstance(timeweb, dict)
        self.assertIsInstance(activation, dict)
        assert isinstance(timeweb, dict)
        assert isinstance(activation, dict)
        self.assertEqual(timeweb["canonical_domain_target"], "omnicio.ru")
        self.assertEqual(
            timeweb["canonical_domain_candidates_observed"],
            ["omnicio.ru", "omni-cio.ru"],
        )
        self.assertFalse(timeweb["canonical_domain_owner_confirmation_required"])
        self.assertTrue(timeweb["canonical_domain_owner_confirmed"])
        self.assertFalse(timeweb["dns_cutover_allowed_before_domain_confirmation"])
        self.assertFalse(timeweb["dns_cutover_authorized_by_domain_confirmation_alone"])
        self.assertEqual(
            activation["telegram_canonical_origin"],
            "https://omnicio.ru",
        )
        self.assertEqual(
            activation["telegram_canonical_redirect_uri"],
            "https://omnicio.ru/api/v10/web/auth/telegram/callback",
        )
        self.assertTrue(activation["telegram_canonical_origin_reconfirmation_required"])

    def test_retired_cloudflare_workflows_are_exactly_hard_disabled(self) -> None:
        marker = "if: $" + "{{ false }}"
        expected = {
            ".github/workflows/v10-cloudflare-provider-readiness.yml": 1,
            ".github/workflows/v10-cloudflare-candidate-deploy.yml": 1,
            ".github/workflows/v10-cloudflare-production-release.yml": 6,
            ".github/workflows/v10-neon-egress-boundary.yml": 3,
            ".github/workflows/v10-wp22a-phase4-public-acceptance.yml": 1,
            ".github/workflows/v10-wp22a-phase5-technical-closeout.yml": 1,
        }
        for relative, count in expected.items():
            source = (ROOT / relative).read_text(encoding="utf-8")
            self.assertIn("ARCHIVE-IN-PLACE", source)
            self.assertNotIn("\n  pull_request:", source)
            self.assertNotIn("\n  push:", source)
            self.assertNotIn("\n  workflow_run:", source)
            self.assertNotIn("\n  schedule:", source)
            self.assertNotIn("\n  workflow_call:", source)
            self.assertNotIn("false &&", source)
            self.assertEqual(source.count(marker), count)

    def test_active_ci_graph_is_github_to_timeweb_only(self) -> None:
        ci = _contract()["ci"]
        self.assertIsInstance(ci, dict)
        assert isinstance(ci, dict)
        self.assertEqual(ci["active_service"], "GitHub")
        self.assertEqual(ci["postmerge_upstream_workflow"], "Regression Shield")
        self.assertEqual(
            ci["timeweb_read_only_proof_workflow"],
            ".github/workflows/v10-timeweb-postgres-readonly-proof.yml",
        )
        self.assertEqual(
            ci["retired_cloudflare_workflows"],
            [
                ".github/workflows/v10-cloudflare-provider-readiness.yml",
                ".github/workflows/v10-cloudflare-candidate-deploy.yml",
                ".github/workflows/v10-cloudflare-production-release.yml",
            ],
        )
        self.assertEqual(
            ci["retired_provider_workflows"],
            [
                ".github/workflows/v10-cloudflare-provider-readiness.yml",
                ".github/workflows/v10-cloudflare-candidate-deploy.yml",
                ".github/workflows/v10-cloudflare-production-release.yml",
                ".github/workflows/v10-neon-egress-boundary.yml",
                ".github/workflows/v10-wp22a-phase4-public-acceptance.yml",
                ".github/workflows/v10-wp22a-phase5-technical-closeout.yml",
            ],
        )
        self.assertFalse(ci["retired_provider_live_workflow_auto_trigger_allowed"])
        self.assertFalse(ci["retired_provider_manual_mutation_allowed"])
        self.assertFalse(ci["timeweb_proof_may_depend_on_retired_provider_workflow"])
        self.assertFalse(ci["retired_provider_transitive_execution_allowed"])
        self.assertFalse(ci["sonar_required_final"])
        self.assertFalse(ci["active_external_review_saas_allowed"])
        self.assertEqual(
            ci["github_native_quality_authority"],
            [
                "Regression Shield",
                "V10 authoritative merge gate",
                "V10 Engineering Governance",
            ],
        )

    def test_active_ci_does_not_execute_retired_provider_tooling(self) -> None:
        workflow = WP22A_CLIENTLESS_WORKFLOW.read_text(encoding="utf-8")
        self.assertIn(
            "Verify dormant clientless source contract without provider execution",
            workflow,
        )
        self.assertNotIn(
            "Validate Cloudflare IaC with pinned OpenTofu and provider mirror",
            workflow,
        )
        self.assertNotIn(
            "-File scripts\\validate_wp22a_terraform.ps1",
            workflow,
        )

    def test_historical_phase4_render_probe_is_not_active_ci(self) -> None:
        workflow = WP22A_PHASE4_PUBLIC_ACCEPTANCE_WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("ARCHIVE-IN-PLACE", workflow)
        self.assertIn("if: $" + "{{ false }}", workflow)
        self.assertNotIn("Probe exact public Render preview", workflow)
        self.assertNotIn("check_v10_wp22a_phase4_public_acceptance.py", workflow)
        self.assertNotIn("\n  pull_request:", workflow)

    def test_historical_phase5_render_probe_is_not_active_ci(self) -> None:
        workflow = WP22A_PHASE5_TECHNICAL_CLOSEOUT_WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("ARCHIVE-IN-PLACE", workflow)
        self.assertIn("if: $" + "{{ false }}", workflow)
        self.assertNotIn("Probe exact public hosted technical release", workflow)
        self.assertNotIn("check_v10_wp22a_phase4_public_acceptance.py", workflow)
        self.assertNotIn("\n  pull_request:", workflow)

    def test_retired_provider_execution_guard_covers_future_workflow_forms(
        self,
    ) -> None:
        source = GUARD.read_text(encoding="utf-8")
        for marker in (
            '("*.yml", "*.yaml")',
            '"\\n  workflow_dispatch:"',
            '"\\n  schedule:"',
            '"\\n  workflow_call:"',
            '"secrets.RENDER_"',
            '"secrets.CLOUDRU_"',
            '"secrets.CLOUD_RU_"',
            '"secrets.VK_"',
            '"check_v10_wp22a_phase4_public_acceptance.py"',
            '"python scripts/provision_v10_cloudflare_neon_runtime.py"',
            '"python scripts\\\\provision_v10_render_neon_preview.py"',
            '"python scripts/manage_v10_cloudflare_production.py"',
            '"python scripts/run_v10_cloudflare_gated_production.py"',
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, source)

    def test_historical_wp22a_provider_docs_are_explicitly_superseded(self) -> None:
        for path in (
            WP22A_EXECUTION_CONTRACT,
            WP22A_SERVICE_SELECTION,
            WP22A_IAC_DECISION,
        ):
            with self.subTest(path=path):
                source = path.read_text(encoding="utf-8")
                self.assertIn("Amendment 18", source[:1200])
                self.assertIn("HISTORICAL", source[:1200])

    def test_current_guidance_has_no_retired_provider_authority_drift(
        self,
    ) -> None:
        status = STATUS.read_text(encoding="utf-8")
        for marker in (
            "OWNER-APPROVED PENDING GREEN MERGE",
            "Amendment 14 remains accepted authority:",
            "Current authorized functional implementation package: **NONE**.",
            "The current next prepared product package is `WEB-VISUAL-INTEGRATED`.",
            "Current authorized focused stage: **RU-PG-B",
        ):
            with self.subTest(marker=marker):
                self.assertNotIn(marker, status)

        release_marker = (
            "exact-main post-merge GREEN -> exact Timeweb candidate -> "
            "candidate acceptance -> production promotion"
        )
        for path in (MASTER_CONTEXT, AGENTS, CONTRIBUTING):
            with self.subTest(path=path):
                source = path.read_text(encoding="utf-8")
                self.assertIn(release_marker, source)
                self.assertNotIn(
                    "immutable Cloudflare candidate -> candidate acceptance",
                    source,
                )

    def test_live_guidance_contains_no_actionable_retired_provider_plan(
        self,
    ) -> None:
        stale_markers = (
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
        for path in (README, MASTER_CONTEXT, AGENTS, CONTRIBUTING):
            source = path.read_text(encoding="utf-8")
            for marker in stale_markers:
                with self.subTest(path=path, marker=marker):
                    self.assertNotIn(marker, source)

        status = STATUS.read_text(encoding="utf-8")
        self.assertIn(
            "The formula below is preserved as historical Amendment-14/15 provenance only",
            status,
        )

    def test_recovery_guidance_prefers_timeweb_authority_contracts(self) -> None:
        for path in (GPT_NEW_CHAT, GPT_PROJECT):
            with self.subTest(path=path):
                source = path.read_text(encoding="utf-8")
                self.assertIn(
                    "V10_RU_PUBLIC_REGISTRATION_INGRESS_CONTRACT.json",
                    source,
                )
                self.assertIn(
                    "V10_RU_POSTGRES_TIMEWEB_CONTROL_PLANE_CONTRACT.json",
                    source,
                )
                self.assertIn(
                    "Historical Cloudflare/Neon/Render/VK",
                    source,
                )

    def test_telegram_data_inventory_does_not_freeze_current_main_sha(self) -> None:
        source = DATA_INVENTORY.read_text(encoding="utf-8")
        self.assertIn(
            "Exact accepted-main/current-next authority is always resolved from GitHub",
            source,
        )
        self.assertNotIn("current accepted source behavior on exact base", source)

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