from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from scripts import v10_ci_router
from scripts import v10_release_manifest as release


SHA = "a" * 40
DIGEST = "b" * 64


def valid_manifest() -> dict[str, object]:
    return {
        "schema_version": "1",
        "release_version": "v10.0.0-rc.1",
        "release_tag": "v10.0.0-rc.1",
        "git_sha": SHA,
        "build": {
            "built_at_utc": "2026-08-07T12:00:00+00:00",
            "workflow_name": "V10 Release Provenance",
            "workflow_run_id": 123,
            "source_ref": "refs/heads/main",
            "builder_class": "hybrid",
        },
        "toolchain": {
            "python": "3.14.6",
            "node": "24.18.0",
            "npm": "11.16.0",
            "os_compatibility": ["windows-latest"],
        },
        "dependency_locks": [{"path": "requirements.txt", "sha256": DIGEST}],
        "contracts": {
            "api_schema": None,
            "db_schema": None,
            "broker_parser": None,
            "security_policy": "docs/architecture/V10_SECURITY_BOUNDARIES.md",
            "program_plan_revision": "docs/master-plan/OMNI_CIO_V10_PROGRAM_LOCK.md",
        },
        "sbom": [
            {
                "path": "dist/python.cdx.json",
                "sha256": DIGEST,
                "format": "cyclonedx-json",
            }
        ],
        "ai": {
            "enabled": False,
            "provider_runtime": None,
            "base_model": None,
            "model_digest_sha256": None,
            "quantization": None,
            "context_tokens": None,
            "policy_version": "WP4-NOT-INSTALLED",
            "adapter_digest_sha256": None,
            "eval_contract": None,
            "eval_result": None,
        },
        "update_delivery": {
            "channel": "INTERNAL",
            "minimum_supported_version": "v10.0.0",
            "artifacts": [
                {"name": "dist/source.zip", "sha256": DIGEST, "size_bytes": 1}
            ],
            "signed_metadata_ref": None,
            "signing_identity_ref": None,
            "metadata_expires_at_utc": None,
            "database_compatibility": "WP4_NO_V10_DATABASE_RUNTIME",
            "api_compatibility": "WP4_V9_APP_APP_UNCHANGED",
            "model_compatibility": "WP4_AI_NOT_INSTALLED",
            "rollback_compatible": True,
            "rollback_target": "v9.0.0@app:app",
        },
        "ci_evidence": {
            "authoritative_gate": {
                "workflow": "Self-Hosted Windows CI",
                "run_id": 1,
                "conclusion": "success",
                "git_sha": SHA,
            },
            "hosted_compatibility": [
                {
                    "workflow": "V10 Toolchain Compatibility",
                    "run_id": 2,
                    "conclusion": "success",
                    "git_sha": SHA,
                }
            ],
            "regression_shield": {
                "workflow": "Regression Shield",
                "run_id": 3,
                "conclusion": "success",
                "git_sha": SHA,
            },
        },
        "bootstrap": {
            "version": None,
            "compatibility": "WP4_CONTRACT_ONLY_NO_NODE_RUNTIME",
            "recovery_contract_version": None,
        },
        "rollback": {
            "target": "v9.0.0@app:app",
            "instructions_ref": "docs/architecture/V10_V9_BASELINE_FREEZE.md",
            "database_constraints": "NOT_APPLICABLE_WP4",
            "ai_rollback": "NOT_APPLICABLE_WP4",
        },
    }


class V10CiRouterTests(unittest.TestCase):
    def test_docs_only_skips_hosted_windows(self) -> None:
        result = v10_ci_router.classify(["docs/architecture/example.md"])
        self.assertTrue(result["docs_only"])
        self.assertFalse(result["hosted_windows_python"])
        self.assertFalse(result["hosted_windows_frontend"])

    def test_frontend_routes_frontend_windows(self) -> None:
        result = v10_ci_router.classify(["apps/web/src/App.tsx"])
        self.assertTrue(result["hosted_windows_frontend"])
        self.assertTrue(result["fast_frontend"])
        self.assertFalse(result["hosted_windows_python"])

    def test_reconciliation_routes_broker_parser_data(self) -> None:
        for path in (
            "omni_cio/reconciliation/__init__.py",
            "omni_cio/reconciliation/_parts/01.pyfrag",
        ):
            with self.subTest(path=path):
                result = v10_ci_router.classify([path])
                self.assertIn("broker_parser_data", result["categories"])
                self.assertTrue(result["hosted_windows_python"])

    def test_release_authority_routes_full_clean_room(self) -> None:
        result = v10_ci_router.classify(
            [".github/workflows/v10-release-provenance.yml"]
        )
        self.assertTrue(result["hosted_windows_python"])
        self.assertTrue(result["hosted_windows_frontend"])
        self.assertTrue(result["release_matrix"])

    def test_unknown_path_fails_closed(self) -> None:
        result = v10_ci_router.classify(["new-root/unknown.bin"])
        self.assertIn("release_security_authority", result["categories"])
        self.assertTrue(result["hosted_windows_python"])


class V10ReleaseManifestTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.schema = json.loads(release.SCHEMA_PATH.read_text(encoding="utf-8"))

    def test_schema_accepts_complete_shape(self) -> None:
        self.assertEqual(
            release.validate_against_schema(valid_manifest(), self.schema),
            [],
        )

    def test_schema_rejects_incomplete_provenance(self) -> None:
        manifest = valid_manifest()
        del manifest["ci_evidence"]
        failures = release.validate_against_schema(manifest, self.schema)
        self.assertTrue(any("ci_evidence" in item for item in failures), failures)

    def test_semantics_reject_ci_sha_drift(self) -> None:
        manifest = valid_manifest()
        manifest["ci_evidence"]["authoritative_gate"]["git_sha"] = "c" * 40  # type: ignore[index]
        failures = release.semantic_failures(manifest)
        self.assertTrue(
            any("authoritative_gate.git_sha" in item for item in failures), failures
        )

    def test_semantics_reject_failed_ci(self) -> None:
        manifest = valid_manifest()
        manifest["ci_evidence"]["regression_shield"]["conclusion"] = "failure"  # type: ignore[index]
        failures = release.semantic_failures(manifest)
        self.assertTrue(
            any("regression_shield must conclude success" in item for item in failures)
        )

    def test_semantics_require_signing_for_stable(self) -> None:
        manifest = valid_manifest()
        manifest["update_delivery"]["channel"] = "STABLE"  # type: ignore[index]
        failures = release.semantic_failures(manifest)
        self.assertTrue(any("signed_metadata_ref" in item for item in failures))
        self.assertTrue(any("signing_identity_ref" in item for item in failures))
        self.assertTrue(any("metadata_expires_at_utc" in item for item in failures))

    def test_digest_verification_fails_closed(self) -> None:
        manifest = valid_manifest()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "requirements.txt").write_text("x", encoding="utf-8")
            (root / "dist").mkdir()
            (root / "dist/python.cdx.json").write_text("{}", encoding="utf-8")
            (root / "dist/source.zip").write_bytes(b"x")
            (root / "docs/architecture").mkdir(parents=True)
            (root / "docs/master-plan").mkdir(parents=True)
            (root / "docs/architecture/V10_SECURITY_BOUNDARIES.md").write_text(
                "x", encoding="utf-8"
            )
            (root / "docs/master-plan/OMNI_CIO_V10_PROGRAM_LOCK.md").write_text(
                "x", encoding="utf-8"
            )
            (root / "docs/architecture/V10_V9_BASELINE_FREEZE.md").write_text(
                "x", encoding="utf-8"
            )
            failures = release.semantic_failures(manifest, root=root)
        self.assertTrue(any("digest mismatch" in item for item in failures), failures)

    def test_authoritative_ci_verifier_requires_job(self) -> None:
        def fake_fetch(url: str, token: str) -> dict[str, object]:
            self.assertEqual(token, "token")
            if "/jobs?" in url:
                return {
                    "jobs": [
                        {
                            "name": "V10 authoritative merge gate",
                            "conclusion": "success",
                        }
                    ]
                }
            return {
                "name": "Self-Hosted Windows CI",
                "head_sha": SHA,
                "conclusion": "success",
            }

        evidence = release._verify_run(
            "owner/repo",
            42,
            SHA,
            "Self-Hosted Windows CI",
            "token",
            required_job="V10 authoritative merge gate",
            fetcher=fake_fetch,
        )
        self.assertEqual(evidence["run_id"], 42)


class V10ReleaseWorkflowContractTests(unittest.TestCase):
    def test_release_workflow_is_candidate_only_and_read_only(self) -> None:
        text = (
            release.ROOT / ".github/workflows/v10-release-provenance.yml"
        ).read_text(encoding="utf-8")
        self.assertIn("workflow_dispatch:", text)
        self.assertIn("contents: read", text)
        self.assertIn("actions: read", text)
        self.assertNotIn("contents: write", text)
        self.assertIn("persist-credentials: false", text)
        self.assertIn("Reject non-main release candidates", text)
        self.assertIn("Fail closed on incomplete or damaged provenance", text)
        self.assertIn("retention-days: 3", text)
        self.assertNotIn("softprops/action-gh-release", text)
        self.assertNotIn("gh release create", text)

    def test_hosted_workflows_use_internal_path_router_not_trigger_filters(
        self,
    ) -> None:
        for relative in (
            ".github/workflows/v10-pr-fast-checks.yml",
            ".github/workflows/v10-toolchain-compat.yml",
        ):
            text = (release.ROOT / relative).read_text(encoding="utf-8")
            self.assertIn("scripts/v10_ci_router.py", text)
            self.assertNotIn("\n    paths:", text)
            self.assertNotIn("\n    paths-ignore:", text)


if __name__ == "__main__":
    unittest.main()
