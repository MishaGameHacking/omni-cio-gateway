from __future__ import annotations

import unittest

import scripts.bootstrap_v10_cloudflare_builds as builds
import scripts.run_v10_cloudflare_gated_candidate as candidate


class CloudflareGatedCandidateSourceBranchTests(unittest.TestCase):
    def test_main_branch_adapter_is_scoped_and_restored(self) -> None:
        original = builds._BRANCH
        with candidate._candidate_source_branch("main"):
            self.assertEqual(builds._BRANCH, "main")
        self.assertEqual(builds._BRANCH, original)

    def test_adapter_restores_branch_after_failure(self) -> None:
        original = builds._BRANCH

        def raise_inside_adapter() -> None:
            with candidate._candidate_source_branch("main"):
                raise RuntimeError("synthetic")

        with self.assertRaisesRegex(RuntimeError, "synthetic"):
            raise_inside_adapter()
        self.assertEqual(builds._BRANCH, original)

    def test_only_integrated_branch_and_main_are_allowed(self) -> None:
        self.assertEqual(candidate._source_branch("main"), "main")
        self.assertEqual(
            candidate._source_branch("system/cloudflare-public-product"),
            "system/cloudflare-public-product",
        )
        with self.assertRaisesRegex(
            RuntimeError,
            "CLOUDFLARE_CANDIDATE_SOURCE_BRANCH_INVALID",
        ):
            candidate._source_branch("feature/other")


if __name__ == "__main__":
    unittest.main()
