from __future__ import annotations

import unittest
from unittest import mock

import scripts.bootstrap_v10_cloudflare_builds as builds
import scripts.deploy_v10_cloudflare_neon_bootstrap_function as deployer
from scripts.bootstrap_v10_cloudflare_production_database_direct import (
    BootstrapFunctionTarget,
)


_PROJECT_ID = "billowing-smoke-00000000"
_BRANCH_ID = "br-example1234"
_TARGET = BootstrapFunctionTarget(branch_id=_BRANCH_ID, cell="c-6")
_EXPECTED_PATH = f"/api/v2/projects/{_PROJECT_ID}/branches/{_BRANCH_ID}"


class CloudflareNeonExactBranchAuthorityTests(unittest.TestCase):
    def test_exact_branch_uses_custodied_resource_not_branch_collection(self) -> None:
        payload = {
            "branch": {
                "id": _BRANCH_ID,
                "project_id": _PROJECT_ID,
                "name": "main",
                "default": True,
                "current_state": "ready",
            }
        }
        with mock.patch.object(deployer, "_get", return_value=payload) as get:
            branch_id = deployer._exact_branch(
                "synthetic-provider-fixture",
                _PROJECT_ID,
                _TARGET,
            )

        self.assertEqual(branch_id, _BRANCH_ID)
        get.assert_called_once_with(
            _EXPECTED_PATH,
            "synthetic-provider-fixture",
            "CLOUDFLARE_CF_D_NEON_FUNCTION_DEPLOY_BRANCH_RESPONSE_INVALID",
        )
        self.assertNotIn("?", get.call_args.args[0])

    def test_exact_branch_rejects_cross_project_response(self) -> None:
        payload = {
            "branch": {
                "id": _BRANCH_ID,
                "project_id": "different-project-00000000",
                "default": True,
                "current_state": "ready",
            }
        }
        with (
            mock.patch.object(deployer, "_get", return_value=payload),
            self.assertRaisesRegex(
                builds.BootstrapStopped,
                "CLOUDFLARE_CF_D_NEON_FUNCTION_DEPLOY_DEFAULT_BRANCH_MISMATCH",
            ),
        ):
            deployer._exact_branch(
                "synthetic-provider-fixture",
                _PROJECT_ID,
                _TARGET,
            )

    def test_exact_branch_rejects_non_default_or_unready_response(self) -> None:
        cases = (
            {
                "id": _BRANCH_ID,
                "project_id": _PROJECT_ID,
                "default": False,
                "current_state": "ready",
            },
            {
                "id": _BRANCH_ID,
                "project_id": _PROJECT_ID,
                "default": True,
                "current_state": "init",
            },
            {
                "id": "br-other1234",
                "project_id": _PROJECT_ID,
                "default": True,
                "current_state": "ready",
            },
        )
        for branch in cases:
            with self.subTest(branch=branch):
                with (
                    mock.patch.object(
                        deployer,
                        "_get",
                        return_value={"branch": branch},
                    ),
                    self.assertRaisesRegex(
                        builds.BootstrapStopped,
                        "CLOUDFLARE_CF_D_NEON_FUNCTION_DEPLOY_DEFAULT_BRANCH_MISMATCH",
                    ),
                ):
                    deployer._exact_branch(
                        "synthetic-provider-fixture",
                        _PROJECT_ID,
                        _TARGET,
                    )

    def test_exact_branch_rejects_malformed_exact_resource_payload(self) -> None:
        for payload in ({}, {"branch": []}, {"branches": "not-a-list"}):
            with self.subTest(payload=payload):
                with (
                    mock.patch.object(deployer, "_get", return_value=payload),
                    self.assertRaisesRegex(
                        builds.BootstrapStopped,
                        "CLOUDFLARE_CF_D_NEON_FUNCTION_DEPLOY_BRANCH_RESPONSE_INVALID",
                    ),
                ):
                    deployer._exact_branch(
                        "synthetic-provider-fixture",
                        _PROJECT_ID,
                        _TARGET,
                    )


if __name__ == "__main__":
    unittest.main()
