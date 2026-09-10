from __future__ import annotations

import io
import json
from pathlib import Path
from typing import cast
import unittest
from unittest import mock
import zipfile

import scripts.bootstrap_v10_cloudflare_builds as builds
import scripts.deploy_v10_cloudflare_neon_bootstrap_function as deployer
from scripts.bootstrap_v10_cloudflare_production_database_direct import (
    BootstrapFunctionTarget,
)


_ROOT = Path(__file__).resolve().parents[1]
_CANDIDATE_RUNNER = _ROOT / "scripts/run_v10_cloudflare_gated_candidate.py"
_CONTRACT = (
    _ROOT / "docs/architecture/V10_CLOUDFLARE_RELEASE_ACCEPTANCE_CONTRACT.json"
)
_EXPECTED_SHA = "a" * 40
_PROJECT_ID = "billowing-smoke-00000000"
_BRANCH_ID = "br-example1234"
_TARGET = BootstrapFunctionTarget(branch_id=_BRANCH_ID, cell="c-6")
_FUNCTION_URL = (
    f"https://{_BRANCH_ID}-cfdprodbootstrap.compute.c-6.eu-central-1.aws.neon.tech/"
)


def _function_state(
    *,
    current_id: int,
    current_status: str,
    active_id: int,
    active_status: str,
) -> dict[str, object]:
    return {
        "slug": "cfdprodbootstrap",
        "invocation_url": _FUNCTION_URL,
        "current_deployment": {
            "id": current_id,
            "status": current_status,
            "runtime": "nodejs24",
        },
        "active_deployment": {
            "id": active_id,
            "status": active_status,
            "runtime": "nodejs24",
        },
    }


class CloudflareNeonFunctionDeploymentTests(unittest.TestCase):
    def test_archive_is_deterministic_single_root_entry(self) -> None:
        source = b"export default { fetch() {} }; oidcTokenFromRequest"
        source_path = mock.Mock()
        source_path.is_symlink.return_value = False
        source_path.is_file.return_value = True
        source_path.read_bytes.return_value = source
        with mock.patch.object(deployer, "_SOURCE", source_path):
            first = deployer._archive()
            second = deployer._archive()
        self.assertEqual(first, second)
        with zipfile.ZipFile(io.BytesIO(first), "r") as archive:
            self.assertEqual(archive.namelist(), ["index.mjs"])
            self.assertEqual(
                archive.getinfo("index.mjs").date_time,
                (1980, 1, 1, 0, 0, 0),
            )
            self.assertEqual(archive.read("index.mjs"), source)

    def test_target_branch_requires_exact_default_handoff_branch(self) -> None:
        payload = {
            "branches": [
                {"id": _BRANCH_ID, "default": True, "current_state": "ready"}
            ]
        }
        with mock.patch.object(deployer, "_get", return_value=payload):
            self.assertEqual(
                deployer._exact_branch("token", _PROJECT_ID, _TARGET),
                _BRANCH_ID,
            )

        wrong = {
            "branches": [
                {
                    "id": "br-other1234",
                    "default": True,
                    "current_state": "ready",
                }
            ]
        }
        with mock.patch.object(deployer, "_get", return_value=wrong):
            with self.assertRaisesRegex(
                builds.BootstrapStopped,
                "CLOUDFLARE_CF_D_NEON_FUNCTION_DEPLOY_DEFAULT_BRANCH_MISMATCH",
            ):
                deployer._exact_branch("token", _PROJECT_ID, _TARGET)

    def test_function_binding_requires_exact_origin_and_completed_state(self) -> None:
        function = _function_state(
            current_id=6,
            current_status="completed",
            active_id=6,
            active_status="completed",
        )
        self.assertEqual(deployer._preexisting(function, _TARGET), "6")
        function["invocation_url"] = "https://example.invalid/"
        with self.assertRaisesRegex(
            builds.BootstrapStopped,
            "CLOUDFLARE_CF_D_NEON_FUNCTION_DEPLOY_FUNCTION_ORIGIN_MISMATCH",
        ):
            deployer._preexisting(function, _TARGET)

    def test_deploy_returns_identity_without_secret_in_body(self) -> None:
        response = json.dumps(
            {"id": 7, "status": "pending", "runtime": "nodejs24"}
        ).encode("utf-8")
        observed: dict[str, object] = {}

        def request(
            method: str,
            path: str,
            token: str,
            *,
            body: bytes | None = None,
            content_type: str | None = None,
        ) -> tuple[int, bytes]:
            observed.update(
                method=method,
                path=path,
                token=token,
                body=body,
                content_type=content_type,
            )
            return 201, response

        with (
            mock.patch.object(deployer, "_request", side_effect=request),
            mock.patch.object(
                deployer,
                "_archive",
                return_value=b"PK synthetic",
            ),
        ):
            deployment_id = deployer._deploy(
                "synthetic-secret-token",
                _PROJECT_ID,
                _BRANCH_ID,
                _EXPECTED_SHA,
            )
        self.assertEqual(deployment_id, "7")
        self.assertEqual(observed["method"], "POST")
        self.assertTrue(
            str(observed["path"]).endswith(
                "/functions/cfdprodbootstrap/deployments"
            )
        )
        self.assertIn("multipart/form-data", str(observed["content_type"]))
        self.assertNotIn(
            b"synthetic-secret-token",
            cast(bytes, observed["body"]),
        )

    def test_wait_accepts_only_returned_deployment_and_rejects_race(self) -> None:
        sequence = [
            _function_state(
                current_id=7,
                current_status="building",
                active_id=6,
                active_status="completed",
            ),
            _function_state(
                current_id=7,
                current_status="completed",
                active_id=7,
                active_status="completed",
            ),
        ]
        with (
            mock.patch.object(deployer, "_function", side_effect=sequence),
            mock.patch.object(deployer.time, "sleep"),
            mock.patch.object(
                deployer.time,
                "monotonic",
                side_effect=[0.0, 1.0, 2.0],
            ),
        ):
            deployer._wait("token", _PROJECT_ID, _BRANCH_ID, "6", "7")

        race = _function_state(
            current_id=8,
            current_status="building",
            active_id=6,
            active_status="completed",
        )
        with mock.patch.object(deployer, "_function", return_value=race):
            with self.assertRaisesRegex(
                builds.BootstrapStopped,
                "CLOUDFLARE_CF_D_NEON_FUNCTION_DEPLOY_RACE",
            ):
                deployer._wait("token", _PROJECT_ID, _BRANCH_ID, "6", "7")

    def test_runtime_secret_reuse_suppresses_function_redeployment(self) -> None:
        api = cast(builds.CloudflareApi, object())
        with (
            mock.patch(
                "scripts.manage_v10_cloudflare_production._runtime_secret_present",
                return_value=True,
            ),
            mock.patch.object(
                deployer,
                "deploy_exact_main_bootstrap_function",
            ) as deploy,
        ):
            self.assertFalse(
                deployer.deploy_exact_main_bootstrap_function_if_required(
                    api,
                    _EXPECTED_SHA,
                )
            )
            deploy.assert_not_called()

    def test_exact_main_candidate_deploys_after_origin_custody(self) -> None:
        source = _CANDIDATE_RUNNER.read_text(encoding="utf-8")
        persist = source.index(
            "persist_bootstrap_origin_custody(api, bootstrap_origin)"
        )
        deploy = source.index(
            "deploy_exact_main_bootstrap_function_if_required(api, sha)"
        )
        self.assertLess(persist, deploy)
        self.assertIn('if branch == "main":', source[persist:deploy])

    def test_release_contract_requires_function_deploy_before_oidc(self) -> None:
        contract = json.loads(_CONTRACT.read_text(encoding="utf-8"))
        cutover = contract["cutover"]
        self.assertIs(
            cutover[
                "production_database_bootstrap_function_exact_main_deploy_required"
            ],
            True,
        )
        self.assertEqual(
            cutover["production_database_bootstrap_function_source"],
            "infrastructure/cloudflare/cf_d_neon_bootstrap/index.mjs",
        )
        self.assertEqual(
            cutover["production_database_bootstrap_function_runtime"],
            "nodejs24",
        )
        self.assertEqual(
            cutover[
                "production_database_bootstrap_function_existing_slug_required"
            ],
            "cfdprodbootstrap",
        )
        self.assertIs(
            cutover[
                "production_database_bootstrap_function_create_if_missing_allowed"
            ],
            False,
        )
        self.assertIs(
            cutover[
                "production_database_bootstrap_function_deploy_if_runtime_secret_missing_only"
            ],
            True,
        )
        self.assertIs(
            cutover[
                "production_database_bootstrap_function_active_deployment_match_required"
            ],
            True,
        )
        self.assertIs(
            cutover[
                "production_database_bootstrap_function_deploy_before_oidc_mint_required"
            ],
            True,
        )
        self.assertIs(
            cutover[
                "production_database_bootstrap_function_provider_identifier_logging_allowed"
            ],
            False,
        )


if __name__ == "__main__":
    unittest.main()
