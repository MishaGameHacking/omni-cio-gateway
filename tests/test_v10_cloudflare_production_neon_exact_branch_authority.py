from __future__ import annotations

from typing import Any
import json
from pathlib import Path
import unittest
from unittest import mock

import scripts.provision_v10_cloudflare_neon_runtime as neon
from scripts import provision_v10_render_neon_preview as neon_base
from scripts.bootstrap_v10_cloudflare_production_database_direct import (
    BootstrapFunctionTarget,
)


_ORG_ID = "org-test"
_PROJECT_ID = "project-frankfurt"
_BRANCH_ID = "br-main-test"
_OTHER_BRANCH_ID = "br-other-test"
_RUNTIME_ROLE = "omni_cio_cloudflare_prod"
_CONTRACT = (
    Path(__file__).resolve().parents[1]
    / "docs/architecture/V10_CLOUDFLARE_RELEASE_ACCEPTANCE_CONTRACT.json"
)


def _exact_branch(**overrides: object) -> dict[str, object]:
    branch: dict[str, object] = {
        "id": _BRANCH_ID,
        "project_id": _PROJECT_ID,
        "name": "main",
        "default": True,
        "current_state": "ready",
    }
    branch.update(overrides)
    return {"branch": branch}


class _ExactBranchApi:
    def __init__(
        self,
        *,
        branch_payload: object | None = None,
        branch_failure: neon_base.ProvisioningStopped | None = None,
    ) -> None:
        self.branch_payload = (
            _exact_branch() if branch_payload is None else branch_payload
        )
        self.branch_failure = branch_failure
        self.calls: list[tuple[str, str]] = []

    def request(self, method: str, path: str, **kwargs: Any) -> object:
        del kwargs
        self.calls.append((method, path))
        expected = f"/projects/{_PROJECT_ID}/branches/{_BRANCH_ID}"
        if method == "GET" and path == expected:
            if self.branch_failure is not None:
                raise self.branch_failure
            return self.branch_payload
        raise AssertionError((method, path))


class _ProjectMetadataVisibleApi(_ExactBranchApi):
    def request(self, method: str, path: str, **kwargs: Any) -> object:
        del kwargs
        self.calls.append((method, path))
        if method == "GET" and path == f"/projects/{_PROJECT_ID}":
            return {
                "project": {
                    "id": _PROJECT_ID,
                    "name": neon_base.NEON_PROJECT_NAME,
                    "org_id": _ORG_ID,
                    "region_id": neon_base.NEON_REGION,
                    "pg_version": 18,
                }
            }
        if method == "GET" and path == f"/organizations/{_ORG_ID}":
            raise neon_base.ProvisioningStopped(
                "NEON_API_KEY_INSUFFICIENT",
                status=403,
            )
        expected = f"/projects/{_PROJECT_ID}/branches/{_BRANCH_ID}"
        if method == "GET" and path == expected:
            if self.branch_failure is not None:
                raise self.branch_failure
            return self.branch_payload
        raise AssertionError((method, path))


class CloudflareProductionNeonExactBranchAuthorityTests(unittest.TestCase):
    def test_production_uses_custodied_branch_id(self) -> None:
        target = BootstrapFunctionTarget(branch_id=_BRANCH_ID, cell="c-6")
        with mock.patch(
            "scripts.bootstrap_v10_cloudflare_production_database_direct."
            "read_bootstrap_origin_handoff",
            return_value=target,
        ):
            self.assertEqual(
                neon._expected_branch_id_for_environment("production"),
                _BRANCH_ID,
            )
        self.assertIsNone(neon._expected_branch_id_for_environment("staging"))

    def test_exact_authority_never_enumerates_branch_collection(self) -> None:
        api = _ExactBranchApi()
        payload = neon._project_scoped_branch_authority(
            api,
            _ORG_ID,
            _PROJECT_ID,
            _BRANCH_ID,
        )
        self.assertEqual(payload, {"branches": [_exact_branch()["branch"]]})
        self.assertEqual(
            api.calls,
            [("GET", f"/projects/{_PROJECT_ID}/branches/{_BRANCH_ID}")],
        )
        self.assertFalse(
            any(path.endswith("/branches?limit=100") for _, path in api.calls)
        )

    def test_exact_authority_rejects_project_binding_drift(self) -> None:
        api = _ExactBranchApi(
            branch_payload=_exact_branch(project_id="project-other")
        )
        with self.assertRaisesRegex(
            RuntimeError,
            "NEON_BRANCH_PROJECT_BINDING_MISMATCH",
        ):
            neon._project_scoped_branch_authority(
                api,
                _ORG_ID,
                _PROJECT_ID,
                _BRANCH_ID,
            )

    def test_exact_authority_rejects_non_default_or_non_ready_branch(self) -> None:
        cases = (
            (_exact_branch(default=False), "NEON_DEFAULT_BRANCH_MISMATCH"),
            (_exact_branch(current_state="idle"), "NEON_BRANCH_NOT_READY"),
        )
        for payload, code in cases:
            with self.subTest(code=code):
                api = _ExactBranchApi(branch_payload=payload)
                with self.assertRaisesRegex(RuntimeError, code):
                    neon._project_scoped_branch_authority(
                        api,
                        _ORG_ID,
                        _PROJECT_ID,
                        _BRANCH_ID,
                    )

    def test_exact_authority_preserves_403_as_binding_mismatch(self) -> None:
        api = _ExactBranchApi(
            branch_failure=neon_base.ProvisioningStopped(
                "NEON_API_KEY_INSUFFICIENT",
                status=403,
            )
        )
        with self.assertRaisesRegex(
            RuntimeError,
            "NEON_PROJECT_KEY_BINDING_MISMATCH",
        ) as caught:
            neon._project_scoped_branch_authority(
                api,
                _ORG_ID,
                _PROJECT_ID,
                _BRANCH_ID,
            )
        self.assertEqual(caught.exception.status, 403)

    def test_project_scoped_metadata_path_still_converges_to_exact_branch(self) -> None:
        api = _ProjectMetadataVisibleApi()
        scope, project, branches = neon._provider_access_context(
            api,
            _ORG_ID,
            _PROJECT_ID,
            _BRANCH_ID,
        )
        self.assertEqual(scope, "PROJECT_SCOPED")
        self.assertIsNone(project)
        self.assertEqual(branches, {"branches": [_exact_branch()["branch"]]})
        self.assertIn(
            ("GET", f"/projects/{_PROJECT_ID}/branches/{_BRANCH_ID}"),
            api.calls,
        )
        self.assertFalse(
            any(path.endswith("/branches?limit=100") for _, path in api.calls)
        )

    def test_release_contract_freezes_exact_branch_custody(self) -> None:
        contract = json.loads(_CONTRACT.read_text(encoding="utf-8"))
        cutover = contract["cutover"]
        self.assertIs(
            cutover[
                "production_database_bootstrap_project_scoped_exact_"
                "branch_read_required"
            ],
            True,
        )
        self.assertIs(
            cutover["production_database_bootstrap_exact_branch_custody_required"],
            True,
        )
        self.assertEqual(
            cutover["production_database_bootstrap_exact_branch_custody_source"],
            "RESTRICTED_RUNNER_TEMP_TARGET_DESCRIPTOR",
        )
        self.assertIs(
            cutover[
                "production_database_bootstrap_exact_branch_project_binding_required"
            ],
            True,
        )
        self.assertIs(
            cutover[
                "production_database_bootstrap_exact_branch_default_ready_required"
            ],
            True,
        )
        self.assertIs(
            cutover[
                "production_database_bootstrap_branch_collection_allowed_"
                "when_exact_custody_available"
            ],
            False,
        )
        self.assertIs(
            cutover[
                "production_database_bootstrap_staging_collection_fallback_retained"
            ],
            True,
        )

    def test_target_rejects_branch_different_from_custody(self) -> None:
        api = mock.Mock()
        payload = {
            "branches": [
                {
                    "id": _OTHER_BRANCH_ID,
                    "name": "main",
                    "default": True,
                }
            ]
        }
        with self.assertRaisesRegex(
            RuntimeError,
            "NEON_BRANCH_CUSTODY_MISMATCH",
        ):
            neon._project_scoped_target(
                api,
                _PROJECT_ID,
                _RUNTIME_ROLE,
                payload,
                _BRANCH_ID,
            )
        api.request.assert_not_called()


if __name__ == "__main__":
    unittest.main()
