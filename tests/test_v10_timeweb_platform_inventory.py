from __future__ import annotations

import unittest

from scripts import check_v10_timeweb_platform_inventory as inventory


class TimewebPlatformInventoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.payload = inventory._load()

    def test_complete_inventory_guard_passes_current_tree(self) -> None:
        self.assertEqual(inventory.main(), 0)

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

    def test_hidden_shared_runtime_consumer_requires_timeweb_replacement(self) -> None:
        self.assertEqual(
            inventory._classify_path("apps/api/hosted_preview.py", self.payload),
            "TIMEWEB_REPLACE",
        )
        self.assertEqual(
            inventory._classify_path("apps/api/cf_d_database_bootstrap.py", self.payload),
            "TIMEWEB_REPLACE",
        )

    def test_vk_runtime_is_retired_but_protected_v9_render_is_kept(self) -> None:
        self.assertEqual(
            inventory._classify_path("omni_cio/web/vk_id_oauth_v1.py", self.payload),
            "RETIRE_NOW_AFTER_AUTHORITY",
        )
        self.assertEqual(inventory._classify_path("render.yaml", self.payload), "KEEP")


if __name__ == "__main__":
    unittest.main()
