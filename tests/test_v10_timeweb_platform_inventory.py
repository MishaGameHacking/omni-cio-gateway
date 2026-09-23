from __future__ import annotations

from pathlib import Path
import unittest

from scripts import check_v10_timeweb_platform_inventory as inventory


ROOT = Path(__file__).resolve().parents[1]


class TimewebPlatformInventoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.payload = inventory._load()

    def test_complete_inventory_guard_passes_current_tree(self) -> None:
        self.assertEqual(inventory.main(), 0)

    def test_provider_named_inventory_uses_exact_cardinality(self) -> None:
        files = inventory._repository_files()
        keywords = inventory._validate_contract(self.payload)
        provider_named = tuple(
            path for path in files if inventory._provider_named_path(path, keywords)
        )
        self.assertEqual(
            len(provider_named),
            self.payload["expected_provider_named_file_count"],
        )
        self.assertNotIn("minimum_provider_named_file_count", self.payload)

    def test_contract_uses_only_non_regex_match_primitives(self) -> None:
        source = (ROOT / "scripts/check_v10_timeweb_platform_inventory.py").read_text(
            encoding="utf-8"
        )
        self.assertNotIn("import re", source)
        self.assertNotIn("re.compile", source)
        self.assertNotIn("re.search", source)
        self.assertNotIn("provider_path_detector_regex", self.payload)
        self.assertNotIn("accepted_base_sha", self.payload)
        for rule in self.payload["path_rules"]:
            self.assertNotIn("regex", rule)
            self.assertIn("match", rule)

    def test_repository_discovery_does_not_spawn_processes(self) -> None:
        source = (ROOT / "scripts/check_v10_timeweb_platform_inventory.py").read_text(
            encoding="utf-8"
        )
        self.assertNotIn("import subprocess", source)
        self.assertNotIn("subprocess.", source)

    def test_repository_integrity_reads_every_discovered_file(self) -> None:
        files = inventory._repository_files()
        stats = inventory._validate_repository_integrity(files)

        self.assertEqual(stats["files"], len(files))
        self.assertEqual(
            stats["text_files"] + stats["binary_files"],
            len(files),
        )
        self.assertGreater(stats["python_files"], 900)
        self.assertGreater(stats["json_files"], 70)
        self.assertGreater(stats["bytes"], 1_000_000)

    def test_repository_integrity_rejects_conflict_and_syntax_drift(self) -> None:
        for marker in ("<<<<<<< HEAD", "=======", ">>>>>>> branch"):
            with self.subTest(marker=marker):
                self.assertTrue(inventory._has_conflict_marker(marker))
        with self.assertRaisesRegex(
            RuntimeError,
            "TIMEWEB_INVENTORY_REPOSITORY_SYNTAX_INVALID",
        ):
            inventory._validate_structured_repository_text(
                "scripts/broken.py",
                "def broken(:\n",
            )
        with self.assertRaisesRegex(
            RuntimeError,
            "TIMEWEB_INVENTORY_REPOSITORY_SYNTAX_INVALID",
        ):
            inventory._validate_structured_repository_text(
                "docs/hostile.xml",
                '<!DOCTYPE root [<!ENTITY xxe SYSTEM "file:///etc/passwd">]>'
                "<root>&xxe;</root>",
            )

    def test_current_timeweb_workflow_is_keep(self) -> None:
        self.assertEqual(
            inventory._classify_path(
                ".github/workflows/v10-timeweb-postgres-readonly-proof.yml",
                self.payload,
            ),
            "KEEP",
        )

    def test_retired_cloudflare_runtime_is_history(self) -> None:
        self.assertEqual(
            inventory._classify_path("apps/api/cloudflare_runtime.py", self.payload),
            "HISTORY",
        )

    def test_tw_b_current_source_runtime_surfaces_are_keep(self) -> None:
        for path in (
            "Dockerfile",
            "apps/api/hosted_app.py",
            "apps/api/hosted_database_runtime.py",
            "apps/api/hosted_runtime.py",
            "apps/api/telegram_auth.py",
            "apps/web/vite.config.ts",
            "infrastructure/postgres/hosted-postgres-runtime.sql",
            "omni_cio/persistence/hosted_postgres_runtime_v1.py",
            "omni_cio/persistence/hosted_synthetic_scope_v1.py",
            "omni_cio/web/browser_security_v1.py",
            "omni_cio/web/identity_v1.py",
            "omni_cio/web/telegram_auth_routes_v1.py",
            "omni_cio/web/telegram_auth_services_v1.py",
            "scripts/check_v10_ru_postgres_data_residency_migration.py",
            "scripts/postgres_runtime_primitives.py",
            "scripts/provider_runtime_primitives.py",
            "scripts/provision_v10_timeweb_postgres_synthetic.py",
        ):
            with self.subTest(path=path):
                self.assertEqual(
                    inventory._classify_path(path, self.payload),
                    "KEEP",
                )

    def test_keep_runtime_cannot_import_historical_hosted_preview(self) -> None:
        rehearsal = (
            ROOT / "scripts/rehearse_v10_wp22a_phase4_runtime_role.py"
        ).read_text(encoding="utf-8")
        self.assertIn(
            "from apps.api.hosted_preview import",
            inventory._RETIRED_EXECUTION_MARKERS,
        )
        self.assertNotIn("from apps.api.hosted_preview import", rehearsal)
        self.assertIn(
            "from omni_cio.persistence.hosted_synthetic_scope_v1 import",
            rehearsal,
        )

    def test_detached_provider_wrappers_are_history(self) -> None:
        for path in (
            "apps/api/hosted_preview.py",
            "apps/api/cf_d_database_bootstrap.py",
            "apps/api/wp22a_phase5_auth.py",
            "omni_cio/web/provider_auth_routes_v1.py",
            "omni_cio/web/provider_start_adapter_v1.py",
            "scripts/provision_v10_cloudflare_neon_runtime.py",
            "scripts/provision_v10_render_neon_preview.py",
            "infrastructure/cloudru/wp22a/hosted-postgres-runtime.sql",
            "wrangler.jsonc",
        ):
            with self.subTest(path=path):
                self.assertEqual(
                    inventory._classify_path(path, self.payload),
                    "HISTORY",
                )

    def test_historical_cloudflare_guard_cannot_own_current_web_provenance(
        self,
    ) -> None:
        path = "scripts/check_v10_cloudflare_runtime_compatibility.py"
        source = (ROOT / path).read_text(encoding="utf-8")
        self.assertEqual(
            inventory._classify_path(path, self.payload),
            "HISTORY",
        )
        self.assertNotIn('WEB_CONFIG = ROOT / "apps/web/vite.config.ts"', source)
        self.assertNotIn("_validate_web_config()", source)
        self.assertIn('"source_sha_precedence"', source)
        self.assertIn('"RENDER_GIT_COMMIT"', source)

    def test_dormant_provider_history_does_not_become_current_authority(self) -> None:
        for path in (
            ".github/workflows/v10-wp22a-phase4-public-acceptance.yml",
            ".github/workflows/v10-wp22a-phase5-technical-closeout.yml",
            "apps/api/wp22a_remote.py",
            "omni_cio/web/external_access_v1.py",
        ):
            with self.subTest(path=path):
                self.assertEqual(
                    inventory._classify_path(path, self.payload),
                    "HISTORY",
                )

    def test_content_only_retired_consumers_are_inventory_bound(self) -> None:
        files = inventory._repository_files()
        inventory._validate_content_consumers(self.payload, files)

    def test_current_keep_sources_reject_retired_live_endpoint_dependency(self) -> None:
        self.assertIn(
            "https://cloudflare.com/cdn-cgi/trace",
            inventory._RETIRED_EXECUTION_MARKERS_CASEFOLD,
        )
        self.assertTrue(
            inventory._contains_retired_execution_marker(
                'TRACE_URL = "https://cloudflare.com/cdn-cgi/trace"'
            )
        )
        discoverer = (ROOT / "scripts/discover_v10_ru_pg_verifier_ipv4.py").read_text(
            encoding="utf-8"
        )
        self.assertFalse(inventory._contains_retired_execution_marker(discoverer))

    def test_current_database_authority_cannot_reassert_retired_neon(self) -> None:
        self.assertTrue(
            inventory._contains_stale_current_database_authority_marker(
                '"current_neon_production_authority_preserved": true'
            )
        )
        self.assertTrue(
            inventory._contains_stale_current_database_authority_marker(
                "Neon production authority remains unchanged"
            )
        )
        for relative in inventory._CURRENT_DATABASE_AUTHORITY_SOURCES:
            with self.subTest(path=relative):
                source = (ROOT / relative).read_text(encoding="utf-8")
                self.assertFalse(
                    inventory._contains_stale_current_database_authority_marker(source)
                )

    def test_security_verifier_marker_data_is_exactly_exempt(self) -> None:
        self.assertEqual(
            inventory._STATIC_EVIDENCE_PATHS,
            frozenset(
                {
                    "scripts/check_v10_ru_public_registration_ingress.py",
                    "scripts/check_v10_timeweb_platform_inventory.py",
                }
            ),
        )
        for path in inventory._STATIC_EVIDENCE_PATHS:
            with self.subTest(path=path):
                self.assertFalse(inventory._should_scan_content(path))
        self.assertEqual(
            inventory._classify_path(
                "scripts/check_v10_ru_public_registration_ingress.py",
                self.payload,
            ),
            "KEEP",
        )

    def test_workflows_use_execution_guard_not_source_consumer_scan(self) -> None:
        self.assertFalse(
            inventory._should_scan_content(
                ".github/workflows/v10-engineering-governance.yml"
            )
        )
        self.assertFalse(
            inventory._should_scan_content(
                ".github/workflows/v10-wp22a-clientless-access-audit.yml"
            )
        )
        self.assertTrue(inventory._should_scan_content("apps/api/hosted_preview.py"))
        self.assertEqual(
            inventory._classify_path(
                ".github/workflows/v10-wp22a-clientless-access-audit.yml",
                self.payload,
            ),
            "KEEP",
        )

    def test_matcher_inputs_are_bounded(self) -> None:
        too_many_values = [
            f"marker-{index}" for index in range(inventory._MAX_MATCH_VALUES + 1)
        ]
        with self.assertRaisesRegex(RuntimeError, "TIMEWEB_INVENTORY_RULE_INVALID"):
            inventory._rule_matches(
                "scripts/example.py",
                {"match": {"contains_any": too_many_values}},
            )
        with self.assertRaisesRegex(RuntimeError, "TIMEWEB_INVENTORY_RULE_INVALID"):
            inventory._rule_matches(
                "scripts/example.py",
                {"match": {"contains": "x" * (inventory._MAX_MATCH_TEXT_LENGTH + 1)}},
            )
        too_many_keywords = [
            f"provider{index}" for index in range(inventory._MAX_PROVIDER_KEYWORDS + 1)
        ]
        with self.assertRaisesRegex(
            RuntimeError,
            "TIMEWEB_INVENTORY_PROVIDER_KEYWORDS_INVALID",
        ):
            inventory._provider_keywords({"provider_path_keywords": too_many_keywords})

    def test_current_contract_stays_within_verifier_bounds(self) -> None:
        self.assertLessEqual(
            len(self.payload["provider_path_keywords"]),
            inventory._MAX_PROVIDER_KEYWORDS,
        )
        self.assertLessEqual(len(self.payload["path_rules"]), inventory._MAX_PATH_RULES)
        self.assertLessEqual(
            len(self.payload["explicit_paths"]),
            inventory._MAX_EXPLICIT_PATHS,
        )

    def test_safe_matcher_rejects_empty_or_unknown_rule_shapes(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "TIMEWEB_INVENTORY_RULE_INVALID"):
            inventory._rule_matches("anything.py", {"match": {}})
        with self.assertRaisesRegex(RuntimeError, "TIMEWEB_INVENTORY_RULE_INVALID"):
            inventory._rule_matches(
                "anything.py",
                {"match": {"prefix": "scripts/", "regex": ".*"}},
            )

    def test_vk_runtime_is_retired_but_protected_v9_render_is_kept(self) -> None:
        self.assertEqual(
            inventory._classify_path("omni_cio/web/vk_id_oauth_v1.py", self.payload),
            "RETIRE_NOW_AFTER_AUTHORITY",
        )
        self.assertEqual(inventory._classify_path("render.yaml", self.payload), "KEEP")


if __name__ == "__main__":
    unittest.main()
