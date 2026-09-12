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
    if name == "NEON_PROJECT_ID":
        return _PROJECT_ID
    if name == "NEON_ORG_ID":
        return _ORG_ID
    raise KeyError(name)


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

    def test_provenance_accepts_exact_digest_and_marks_legacy_handler_stale(
        self,
    ) -> None:
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
                deployer._provenance_response(status, content_type, body, digest)

    def test_exact_source_reuse_is_credential_free(self) -> None:
        archive = b"PK synthetic"
        digest = "e" * 64
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
            mock.patch.object(
                deployer,
                "_probe_source_provenance",
                return_value=True,
            ),
            mock.patch.object(deployer, "_deploy_api_key") as project_key,
            mock.patch.object(deployer, "_validate_project") as validate_project,
            mock.patch.object(deployer, "_exact_branch") as exact_branch,
            mock.patch.object(deployer, "_function") as function_read,
            mock.patch.object(deployer, "_deploy") as deploy,
        ):
            self.assertFalse(
                deployer.deploy_exact_main_bootstrap_function(_EXPECTED_SHA)
            )
        project_key.assert_not_called()
        validate_project.assert_not_called()
        exact_branch.assert_not_called()
        function_read.assert_not_called()
        deploy.assert_not_called()

    def test_source_drift_loads_exact_project_authority_then_rechecks_before_post(
        self,
    ) -> None:
        archive = b"PK synthetic"
        digest = "f" * 64
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
            mock.patch.object(
                deployer,
                "_probe_source_provenance",
                side_effect=[False, True],
            ),
            mock.patch.object(
                deployer,
                "_deploy_api_key",
                return_value="synthetic-deploy-fixture",
            ) as project_key,
            mock.patch.object(builds, "_required_env", side_effect=_required_env),
            mock.patch.object(deployer, "_validate_project") as validate_project,
            mock.patch.object(deployer, "_exact_branch", return_value=_BRANCH_ID),
            mock.patch.object(deployer, "_function", return_value=function),
            mock.patch.object(deployer, "_deploy") as deploy,
        ):
            self.assertFalse(
                deployer.deploy_exact_main_bootstrap_function(_EXPECTED_SHA)
            )
        project_key.assert_called_once_with()
        validate_project.assert_called_once_with(
            "synthetic-deploy-fixture",
            _PROJECT_ID,
            _ORG_ID,
        )
        deploy.assert_not_called()

    def test_concurrent_exact_source_with_changed_deployment_rejects_race(self) -> None:
        archive = b"PK synthetic"
        digest = "a" * 64
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
            mock.patch.object(
                deployer,
                "_probe_source_provenance",
                side_effect=[False, True],
            ),
            mock.patch.object(
                deployer,
                "_deploy_api_key",
                return_value="synthetic-deploy-fixture",
            ),
            mock.patch.object(builds, "_required_env", side_effect=_required_env),
            mock.patch.object(deployer, "_validate_project"),
            mock.patch.object(deployer, "_exact_branch", return_value=_BRANCH_ID),
            mock.patch.object(deployer, "_function", side_effect=sequence),
            mock.patch.object(deployer, "_deploy") as deploy,
        ):
            with self.assertRaisesRegex(
                builds.BootstrapStopped,
                "CLOUDFLARE_CF_D_NEON_FUNCTION_DEPLOY_RACE",
            ):
                deployer.deploy_exact_main_bootstrap_function(_EXPECTED_SHA)
        deploy.assert_not_called()

    def test_post_deploy_provenance_rechecks_active_deployment_identity(self) -> None:
        archive = b"PK synthetic"
        digest = "a" * 64
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
            mock.patch.object(
                deployer,
                "_deploy_api_key",
                return_value="synthetic-deploy-fixture",
            ),
            mock.patch.object(builds, "_required_env", side_effect=_required_env),
            mock.patch.object(deployer, "_validate_project"),
            mock.patch.object(deployer, "_exact_branch", return_value=_BRANCH_ID),
            mock.patch.object(deployer, "_function", return_value={}),
            mock.patch.object(deployer, "_preexisting", side_effect=["6", "8"]),
            mock.patch.object(
                deployer,
                "_probe_source_provenance",
                side_effect=[False, False, True],
            ),
            mock.patch.object(deployer, "_deploy", return_value="7") as deploy,
            mock.patch.object(deployer, "_wait") as wait,
        ):
            with self.assertRaisesRegex(
                builds.BootstrapStopped,
                "CLOUDFLARE_CF_D_NEON_FUNCTION_DEPLOY_RACE",
            ):
                deployer.deploy_exact_main_bootstrap_function(_EXPECTED_SHA)
        deploy.assert_called_once_with(
            "synthetic-deploy-fixture",
            _PROJECT_ID,
            _BRANCH_ID,
            _EXPECTED_SHA,
            archive,
        )
        wait.assert_called_once_with(
            "synthetic-deploy-fixture",
            _PROJECT_ID,
            _BRANCH_ID,
            "6",
            "7",
        )

    def test_target_branch_requires_exact_default_handoff_branch(self) -> None:
        payload = {
            "branch": {
                "id": _BRANCH_ID,
                "project_id": _PROJECT_ID,
                "default": True,
                "current_state": "ready",
            }
        }
        with mock.patch.object(deployer, "_get", return_value=payload):
            self.assertEqual(
                deployer._exact_branch("token", _PROJECT_ID, _TARGET),
                _BRANCH_ID,
            )

        wrong = {
            "branch": {
                "id": "br-other1234",
                "project_id": _PROJECT_ID,
                "default": True,
                "current_state": "ready",
            }
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
                "synthetic-provider-fixture",
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
            b"synthetic-provider-fixture",
            cast(bytes, observed["body"]),
        )

    def test_management_403_is_explicit_project_authority_failure(self) -> None:
        with mock.patch.object(
            deployer,
            "_request",
            return_value=(403, b'{"provider":"redacted"}'),
        ):
            with self.assertRaisesRegex(
                builds.BootstrapStopped,
                "CLOUDFLARE_CF_D_NEON_FUNCTION_DEPLOY_PROJECT_API_KEY_INSUFFICIENT",
            ):
                deployer._deploy(
                    "synthetic-provider-fixture",
                    _PROJECT_ID,
                    _BRANCH_ID,
                    _EXPECTED_SHA,
                    b"PK synthetic",
                )

    def test_project_authority_is_required_only_after_source_drift(self) -> None:
        with mock.patch.dict(
            deployer.os.environ,
            {deployer._DEPLOY_API_KEY_ENV: ""},
            clear=False,
        ):
            with self.assertRaisesRegex(
                builds.BootstrapStopped,
                "CLOUDFLARE_CF_D_NEON_FUNCTION_DEPLOY_PROJECT_API_KEY_REQUIRED",
            ):
                deployer._deploy_api_key()

    def test_project_authority_is_masked_before_use(self) -> None:
        with (
            mock.patch.dict(
                deployer.os.environ,
                {deployer._DEPLOY_API_KEY_ENV: "synthetic-deploy-fixture"},
                clear=False,
            ),
            mock.patch.object(builds, "_mask") as mask,
        ):
            self.assertEqual(
                deployer._deploy_api_key(),
                "synthetic-deploy-fixture",
            )
        mask.assert_called_once_with("synthetic-deploy-fixture")

    def test_legacy_neon_read_credential_is_metadata_only(
        self,
    ) -> None:
        source = Path(deployer.__file__).read_text(encoding="utf-8")
        self.assertEqual(source.count("_READ_API_KEY_ENV"), 1)
        self.assertNotIn("def _read_api_key", source)

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

    def test_release_contract_requires_provenance_before_project_management(
        self,
    ) -> None:
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
                (
                    "production_database_bootstrap_function_exact_source_"
                    "provenance_required"
                )
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
                (
                    "production_database_bootstrap_function_exact_source_reuse_"
                    "without_api_write_allowed"
                )
            ],
            True,
        )
        self.assertIs(
            cutover[
                (
                    "production_database_bootstrap_function_provenance_before_"
                    "management_api_required"
                )
            ],
            True,
        )
        self.assertIs(
            cutover[
                (
                    "production_database_bootstrap_function_exact_source_reuse_"
                    "without_management_api_required"
                )
            ],
            False,
        )
        self.assertIs(
            cutover[
                "production_database_bootstrap_function_unauthenticated_provenance_attempt_required"
            ],
            True,
        )
        self.assertIs(
            cutover[
                "production_database_bootstrap_function_unauthenticated_403_is_provenance_success"
            ],
            False,
        )
        self.assertIs(
            cutover[
                "production_database_bootstrap_function_unauthenticated_403_requires_scoped_invoke_retry"
            ],
            True,
        )
        self.assertEqual(
            cutover["production_database_bootstrap_function_invoke_credential_scope"],
            "functions:invoke",
        )
        self.assertIs(
            cutover["production_database_bootstrap_function_invoke_credential_ephemeral"],
            True,
        )
        self.assertIs(
            cutover[
                "production_database_bootstrap_function_invoke_credential_persistence_allowed"
            ],
            False,
        )
        self.assertIs(
            cutover[
                "production_database_bootstrap_function_invoke_credential_revoke_after_use_required"
            ],
            True,
        )
        self.assertIs(
            cutover[
                "production_database_bootstrap_function_invoke_credential_broader_scopes_allowed"
            ],
            False,
        )
        self.assertIs(
            cutover[
                (
                    "production_database_bootstrap_function_active_deployment_"
                    "match_required"
                )
            ],
            True,
        )
        self.assertIs(
            cutover[
                (
                    "production_database_bootstrap_function_deploy_before_oidc_"
                    "mint_required"
                )
            ],
            True,
        )
        self.assertIs(
            cutover[
                (
                    "production_database_bootstrap_function_provider_identifier_"
                    "logging_allowed"
                )
            ],
            False,
        )
        self.assertEqual(
            cutover[
                "production_database_bootstrap_function_read_api_key_binding"
            ],
            deployer._READ_API_KEY_ENV,
        )
        self.assertIs(
            cutover[
                (
                    "production_database_bootstrap_function_read_api_key_binding_"
                    "active"
                )
            ],
            False,
        )
        self.assertEqual(
            cutover[
                "production_database_bootstrap_function_deploy_api_key_binding"
            ],
            deployer._DEPLOY_API_KEY_ENV,
        )
        self.assertIs(
            cutover[
                (
                    "production_database_bootstrap_function_read_write_authority_"
                    "separation_required"
                )
            ],
            False,
        )
        self.assertIs(
            cutover[
                (
                    "production_database_bootstrap_function_deploy_api_key_required_"
                    "only_on_source_drift"
                )
            ],
            False,
        )
        self.assertIs(
            cutover[
                (
                    "production_database_bootstrap_function_deploy_api_key_used_for_"
                    "read_polling_allowed"
                )
            ],
            True,
        )


if __name__ == "__main__":
    unittest.main()
