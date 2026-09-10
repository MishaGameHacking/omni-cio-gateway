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
_ORG_ID = "org-example1234"
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


def _required_env(name: str) -> str:
    return {
        "NEON_API_KEY": "synthetic-secret-token",
        "NEON_PROJECT_ID": _PROJECT_ID,
        "NEON_ORG_ID": _ORG_ID,
    }[name]


class CloudflareNeonFunctionDeploymentTests(unittest.TestCase):
    def test_archive_is_deterministic_and_binds_wrapper_plus_handler(self) -> None:
        handler = b"export default { fetch() {} }; oidcTokenFromRequest"
        wrapper = (
            b"import handler from './handler.mjs';\n"
            b"const digest = '__OMNI_CIO_CF_D_SOURCE_BUNDLE_SHA256__';\n"
        )
        handler_path = mock.Mock()
        handler_path.is_symlink.return_value = False
        handler_path.is_file.return_value = True
        handler_path.read_bytes.return_value = handler
        wrapper_path = mock.Mock()
        wrapper_path.is_symlink.return_value = False
        wrapper_path.is_file.return_value = True
        wrapper_path.read_bytes.return_value = wrapper
        with (
            mock.patch.object(deployer, "_SOURCE", handler_path),
            mock.patch.object(deployer, "_WRAPPER_SOURCE", wrapper_path),
        ):
            first, first_digest = deployer._deployment_bundle()
            second, second_digest = deployer._deployment_bundle()
        self.assertEqual(first, second)
        self.assertEqual(first_digest, second_digest)
        self.assertRegex(first_digest, r"^[0-9a-f]{64}$")
        with zipfile.ZipFile(io.BytesIO(first), "r") as archive:
            self.assertEqual(archive.namelist(), ["index.mjs", "handler.mjs"])
            for name in archive.namelist():
                self.assertEqual(
                    archive.getinfo(name).date_time,
                    (1980, 1, 1, 0, 0, 0),
                )
            rendered = archive.read("index.mjs")
            self.assertIn(first_digest.encode("ascii"), rendered)
            self.assertNotIn(deployer._WRAPPER_DIGEST_PLACEHOLDER, rendered)
            self.assertEqual(archive.read("handler.mjs"), handler)

    def test_provenance_accepts_exact_digest_and_marks_legacy_handler_stale(self) -> None:
        digest = "b" * 64
        exact = json.dumps(
            {"status": "READY", "source_sha256": digest},
            separators=(",", ":"),
        ).encode("utf-8")
        self.assertTrue(
            deployer._provenance_response(200, "application/json", exact, digest)
        )
        stale = json.dumps(
            {"status": "READY", "source_sha256": "c" * 64},
            separators=(",", ":"),
        ).encode("utf-8")
        self.assertFalse(
            deployer._provenance_response(200, "application/json", stale, digest)
        )
        legacy = b'{"status":"BLOCKED","code":"METHOD_NOT_ALLOWED"}'
        self.assertFalse(
            deployer._provenance_response(405, "application/json", legacy, digest)
        )

    def test_provenance_rejects_untrusted_or_malformed_response(self) -> None:
        digest = "d" * 64
        for status, content_type, body in (
            (200, "text/html", b"<html>provider</html>"),
            (200, "application/json", b'{"status":"READY"}'),
            (403, "application/json", b'{"provider":"blocked"}'),
        ):
            with self.assertRaisesRegex(
                builds.BootstrapStopped,
                "CLOUDFLARE_CF_D_NEON_FUNCTION_PROVENANCE_INVALID",
            ):
                deployer._provenance_response(
                    status,
                    content_type,
                    body,
                    digest,
                )

    def test_exact_source_reuse_requires_stable_read_state_but_no_write(self) -> None:
        archive = b"PK synthetic"
        digest = "e" * 64
        function = _function_state(
            current_id=6,
            current_status="completed",
            active_id=6,
            active_status="completed",
        )
        with (
            mock.patch.object(
                deployer,
                "_assert_exact_head",
                return_value=_EXPECTED_SHA,
            ),
            mock.patch.object(
                deployer,
                "read_bootstrap_origin_handoff",
                return_value=_TARGET,
            ),
            mock.patch.object(
                deployer,
                "_deployment_bundle",
                return_value=(archive, digest),
            ),
            mock.patch.object(builds, "_required_env", side_effect=_required_env),
            mock.patch.object(deployer, "_validate_project"),
            mock.patch.object(deployer, "_exact_branch", return_value=_BRANCH_ID),
            mock.patch.object(deployer, "_function", return_value=function) as function_read,
            mock.patch.object(
                deployer,
                "_probe_source_provenance",
                return_value=True,
            ),
            mock.patch.object(deployer, "_deploy") as deploy,
        ):
            self.assertFalse(
                deployer.deploy_exact_main_bootstrap_function(_EXPECTED_SHA)
            )
        self.assertEqual(function_read.call_count, 2)
        deploy.assert_not_called()

    def test_exact_source_reuse_rejects_deployment_race(self) -> None:
        archive = b"PK synthetic"
        digest = "f" * 64
        sequence = [
            _function_state(
                current_id=6,
                current_status="completed",
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
            mock.patch.object(
                deployer,
                "_assert_exact_head",
                return_value=_EXPECTED_SHA,
            ),
            mock.patch.object(
                deployer,
                "read_bootstrap_origin_handoff",
                return_value=_TARGET,
            ),
            mock.patch.object(
                deployer,
                "_deployment_bundle",
                return_value=(archive, digest),
            ),
            mock.patch.object(builds, "_required_env", side_effect=_required_env),
            mock.patch.object(deployer, "_validate_project"),
            mock.patch.object(deployer, "_exact_branch", return_value=_BRANCH_ID),
            mock.patch.object(deployer, "_function", side_effect=sequence),
            mock.patch.object(
                deployer,
                "_probe_source_provenance",
                return_value=True,
            ),
            mock.patch.object(deployer, "_deploy") as deploy,
        ):
            with self.assertRaisesRegex(
                builds.BootstrapStopped,
                "CLOUDFLARE_CF_D_NEON_FUNCTION_DEPLOY_RACE",
            ):
                deployer.deploy_exact_main_bootstrap_function(_EXPECTED_SHA)
        deploy.assert_not_called()

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

        with mock.patch.object(deployer, "_request", side_effect=request):
            deployment_id = deployer._deploy(
                "synthetic-secret-token",
                _PROJECT_ID,
                _BRANCH_ID,
                _EXPECTED_SHA,
                b"PK synthetic",
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

    def test_deploy_403_is_explicit_function_write_authority_failure(self) -> None:
        with mock.patch.object(
            deployer,
            "_request",
            return_value=(403, b'{"provider":"redacted"}'),
        ):
            with self.assertRaisesRegex(
                builds.BootstrapStopped,
                "CLOUDFLARE_CF_D_NEON_FUNCTION_DEPLOY_API_KEY_INSUFFICIENT",
            ):
                deployer._deploy(
                    "synthetic-secret-token",
                    _PROJECT_ID,
                    _BRANCH_ID,
                    _EXPECTED_SHA,
                    b"PK synthetic",
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

    def test_release_contract_requires_provenance_before_conditional_deploy(self) -> None:
        contract = json.loads(_CONTRACT.read_text(encoding="utf-8"))
        cutover = contract["cutover"]
        self.assertIs(
            cutover[
                "production_database_bootstrap_function_exact_main_deploy_required"
            ],
            False,
        )
        self.assertIs(
            cutover[
                "production_database_bootstrap_function_exact_source_provenance_required"
            ],
            True,
        )
        self.assertEqual(
            cutover["production_database_bootstrap_function_source"],
            "infrastructure/cloudflare/cf_d_neon_bootstrap/index.mjs",
        )
        self.assertEqual(
            cutover["production_database_bootstrap_function_provenance_wrapper"],
            "infrastructure/cloudflare/cf_d_neon_bootstrap/provenance_wrapper.mjs",
        )
        self.assertEqual(
            cutover["production_database_bootstrap_function_provenance_path"],
            deployer._PROVENANCE_PATH,
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
                "production_database_bootstrap_function_write_only_on_source_drift"
            ],
            True,
        )
        self.assertIs(
            cutover[
                "production_database_bootstrap_function_exact_source_reuse_without_api_write_allowed"
            ],
            True,
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
