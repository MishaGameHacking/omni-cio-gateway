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
        detector = inventory._validate_contract(self.payload)
        provider_named = tuple(path for path in files if detector.search(path))
        self.assertEqual(
            len(provider_named),
            self.payload["expected_provider_named_file_count"],
        )
        self.assertNotIn("minimum_provider_named_file_count", self.payload)

    def test_repository_discovery_does_not_spawn_processes(self) -> None:
        source = (ROOT / "scripts/check_v10_timeweb_platform_inventory.py").read_text(
            encoding="utf-8"
        )
        self.assertNotIn("import subprocess", source)
        self.assertNotIn("subprocess.", source)

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

    def test_hidden_shared_runtime_consumers_require_timeweb_replacement(self) -> None:
        for path in (
            "apps/api/hosted_preview.py",
            "apps/api/cf_d_database_bootstrap.py",
            "omni_cio/persistence/hosted_postgres_runtime_v1.py",
            "omni_cio/web/identity_v1.py",
            "omni_cio/web/provider_start_adapter_v1.py",
        ):
            with self.subTest(path=path):
                self.assertEqual(
                    inventory._classify_path(path, self.payload),
                    "TIMEWEB_REPLACE",
                )

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

    def test_vk_runtime_is_retired_but_protected_v9_render_is_kept(self) -> None:
        self.assertEqual(
            inventory._classify_path("omni_cio/web/vk_id_oauth_v1.py", self.payload),
            "RETIRE_NOW_AFTER_AUTHORITY",
        )
        self.assertEqual(inventory._classify_path("render.yaml", self.payload), "KEEP")


if __name__ == "__main__":
    unittest.main()
