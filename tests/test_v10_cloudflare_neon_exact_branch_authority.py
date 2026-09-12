from __future__ import annotations

from pathlib import Path
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


class CloudflareNeonExactBranchAuthorityTests(unittest.TestCase):
    def test_exact_branch_reads_custodied_resource_not_collection(self) -> None:
        observed: dict[str, str] = {}

        def get(path: str, token: str, code: str) -> dict[str, object]:
            observed.update(path=path, token=token, code=code)
            return {
                "branch": {
                    "id": _BRANCH_ID,
                    "project_id": _PROJECT_ID,
                    "default": True,
                    "current_state": "ready",
                }
            }

        with mock.patch.object(deployer, "_get", side_effect=get):
            self.assertEqual(
                deployer._exact_branch("synthetic-provider-fixture", _PROJECT_ID, _TARGET),
                _BRANCH_ID,
            )

        self.assertEqual(
            observed["path"],
            f"{deployer._API_PREFIX}/projects/{_PROJECT_ID}/branches/{_BRANCH_ID}",
        )
        self.assertNotIn("?limit=", observed["path"])
        self.assertEqual(observed["token"], "synthetic-provider-fixture")
        self.assertEqual(
            observed["code"],
            "CLOUDFLARE_CF_D_NEON_FUNCTION_DEPLOY_BRANCH_RESPONSE_INVALID",
        )

    def test_exact_branch_rejects_provider_project_mismatch(self) -> None:
        payload = {
            "branch": {
                "id": _BRANCH_ID,
                "project_id": "billowing-smoke-other0000",
                "default": True,
                "current_state": "ready",
            }
        }
        with mock.patch.object(deployer, "_get", return_value=payload):
            with self.assertRaisesRegex(
                builds.BootstrapStopped,
                "CLOUDFLARE_CF_D_NEON_FUNCTION_DEPLOY_DEFAULT_BRANCH_MISMATCH",
            ):
                deployer._exact_branch("synthetic-provider-fixture", _PROJECT_ID, _TARGET)

    def test_exact_branch_rejects_non_default_or_non_ready(self) -> None:
        for default, state in ((False, "ready"), (True, "suspended")):
            payload = {
                "branch": {
                    "id": _BRANCH_ID,
                    "project_id": _PROJECT_ID,
                    "default": default,
                    "current_state": state,
                }
            }
            with mock.patch.object(deployer, "_get", return_value=payload):
                with self.assertRaisesRegex(
                    builds.BootstrapStopped,
                    "CLOUDFLARE_CF_D_NEON_FUNCTION_DEPLOY_DEFAULT_BRANCH_MISMATCH",
                ):
                    deployer._exact_branch(
                        "synthetic-provider-fixture", _PROJECT_ID, _TARGET
                    )

    def test_function_convergence_source_has_no_broad_branch_collection_read(self) -> None:
        source = Path(deployer.__file__).read_text(encoding="utf-8")
        self.assertNotIn("/branches?limit=100", source)


if __name__ == "__main__":
    unittest.main()
