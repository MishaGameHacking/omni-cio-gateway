from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = (
    ROOT / "infrastructure" / "preview" / "render-neon-contract.json"
)
APP_PATH = ROOT / "apps" / "api" / "hosted_preview.py"
DEPLOY_PATH = ROOT / "scripts" / "v10_preview_deploy.py"
DOCKERFILE_PATH = ROOT / "Dockerfile.v10-preview"
WORKFLOW_PATH = ROOT / ".github" / "workflows" / "v10-preview-deploy.yml"


def _deploy_module():
    spec = importlib.util.spec_from_file_location("v10_preview_deploy", DEPLOY_PATH)
    if spec is None or spec.loader is None:
        raise AssertionError("preview deploy module unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class HostedPreviewContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
        self.app_source = APP_PATH.read_text(encoding="utf-8")
        self.deploy_source = DEPLOY_PATH.read_text(encoding="utf-8")
        self.dockerfile = DOCKERFILE_PATH.read_text(encoding="utf-8")
        self.workflow = WORKFLOW_PATH.read_text(encoding="utf-8")

    def test_authority_is_zero_cost_and_fail_closed(self) -> None:
        authority = self.contract["authority"]
        self.assertEqual(authority["authorized_recurring_cost"], 0)
        self.assertFalse(authority["paid_overage_allowed"])
        self.assertFalse(authority["public_multi_user_enabled"])
        self.assertFalse(authority["registration_enabled"])
        self.assertFalse(authority["real_trading_enabled"])
        self.assertFalse(authority["trading_methods_enabled"])
        self.assertFalse(authority["wp23_unlocked"])
        self.assertEqual(
            authority["accepted_production_provider_unchanged"],
            "Cloud.ru Evolution",
        )

    def test_render_contract_is_free_docker_frankfurt(self) -> None:
        render = self.contract["render"]
        self.assertEqual(render["service_name"], "omni-cio-v10-preview")
        self.assertEqual(render["runtime"], "docker")
        self.assertEqual(render["plan"], "free")
        self.assertEqual(render["region"], "frankfurt")
        self.assertEqual(render["branch"], "main")
        self.assertEqual(render["health_check_path"], "/healthz")

    def test_neon_contract_requires_postgres_18_frankfurt(self) -> None:
        neon = self.contract["neon"]
        self.assertEqual(neon["postgres_version"], 18)
        self.assertEqual(neon["region_id"], "aws-eu-central-1")
        self.assertTrue(neon["pooled_connection"])
        self.assertTrue(neon["tls_required"])

    def test_preview_is_synthetic_read_only(self) -> None:
        safety = self.contract["preview_safety"]
        self.assertTrue(safety["synthetic_tenant_only"])
        self.assertFalse(safety["mutation_methods_allowed"])
        self.assertFalse(safety["real_broker_credentials_allowed"])
        self.assertFalse(safety["private_tenant_payloads_allowed"])
        self.assertFalse(safety["broker_write_allowed"])
        self.assertFalse(safety["browser_secret_readback_allowed"])
        self.assertEqual(safety["cors_default"], "deny")

    def test_hosted_app_blocks_mutation_and_requires_safe_flags(self) -> None:
        required = (
            "HOSTED_PREVIEW_READ_ONLY",
            "PUBLIC_MULTI_USER_MUST_REMAIN_DISABLED",
            "REAL_TRADING_MUST_REMAIN_DISABLED",
            "secure=True",
            "httponly=True",
            "TrustedHostMiddleware",
            "Cache-Control",
            "Content-Security-Policy",
        )
        for marker in required:
            self.assertIn(marker, self.app_source)
        self.assertNotIn("allow_origins=[\"*\"]", self.app_source)

    def test_hosted_app_uses_factory_without_import_time_database_access(self) -> None:
        self.assertIn("def create_hosted_preview_app()", self.app_source)
        self.assertNotIn("app = create_hosted_preview_app()", self.app_source)
        self.assertIn("--factory", self.dockerfile)

    def test_docker_image_pins_reviewed_toolchains(self) -> None:
        self.assertIn("node:24.18.0-bookworm-slim", self.dockerfile)
        self.assertIn("npm@11.16.0", self.dockerfile)
        self.assertIn("python:3.12.10-slim-bookworm", self.dockerfile)
        self.assertIn("--require-hashes", self.dockerfile)
        self.assertIn("npm ci", self.dockerfile)
        self.assertIn("npm run build", self.dockerfile)

    def test_workflow_never_exposes_secrets_to_pull_requests(self) -> None:
        self.assertNotIn("pull_request:", self.workflow)
        self.assertIn("branches:\n      - main", self.workflow)
        self.assertIn("secrets.NEON_API_KEY", self.workflow)
        self.assertIn("secrets.RENDER_API_KEY", self.workflow)
        self.assertIn("::add-mask::$NEON_API_KEY", self.workflow)
        self.assertIn("::add-mask::$RENDER_API_KEY", self.workflow)
        self.assertIn("cancel-in-progress: false", self.workflow)

    def test_deployer_never_prints_provider_values(self) -> None:
        self.assertIn("::add-mask::{value}", self.deploy_source)
        self.assertIn("::add-mask::{dsn}", self.deploy_source)
        self.assertNotIn("print(dsn)", self.deploy_source)
        self.assertNotIn("print(self._token)", self.deploy_source)
        self.assertIn("PREVIEW_DEPLOYMENT=FAIL", self.deploy_source)

    def test_deployer_flattens_provider_collection_shapes(self) -> None:
        module = _deploy_module()
        direct = module._flatten_items([{"id": "one"}], key="service")
        nested = module._flatten_items(
            [{"service": {"id": "two"}}],
            key="service",
        )
        mapped = module._flatten_items(
            {"services": [{"id": "three"}]},
            key="service",
        )
        self.assertEqual(direct[0]["id"], "one")
        self.assertEqual(nested[0]["id"], "two")
        self.assertEqual(mapped[0]["id"], "three")

    def test_deployer_extracts_only_https_service_url(self) -> None:
        module = _deploy_module()
        service = {
            "serviceDetails": {
                "url": "https://omni-cio-v10-preview.onrender.com/"
            }
        }
        self.assertEqual(
            module._render_service_url(service),
            "https://omni-cio-v10-preview.onrender.com",
        )
        self.assertIsNone(module._render_service_url({"url": "http://invalid"}))

    def test_contract_validation_rejects_runtime_authority_widening(self) -> None:
        module = _deploy_module()
        original = CONTRACT_PATH.read_text(encoding="utf-8")
        payload = json.loads(original)
        payload["authority"]["paid_overage_allowed"] = True
        temporary = CONTRACT_PATH.with_suffix(".invalid.json")
        temporary.write_text(json.dumps(payload), encoding="utf-8")
        old_path = module.CONTRACT_PATH
        module.CONTRACT_PATH = temporary
        try:
            with self.assertRaises(module.PreviewDeployError):
                module._load_contract()
        finally:
            module.CONTRACT_PATH = old_path
            temporary.unlink(missing_ok=True)

    def test_repository_contains_no_provider_secret_values(self) -> None:
        tracked_sources = (
            self.app_source,
            self.deploy_source,
            self.workflow,
            self.dockerfile,
            json.dumps(self.contract),
        )
        forbidden = (
            "postgresql://neondb_owner:",
            "rnd_",
            "napi_",
            "RENDER_API_KEY=",
            "NEON_API_KEY=",
        )
        for source in tracked_sources:
            for marker in forbidden:
                self.assertNotIn(marker, source)


if __name__ == "__main__":
    unittest.main()
