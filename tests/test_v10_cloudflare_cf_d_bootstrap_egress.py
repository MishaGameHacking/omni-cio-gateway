from __future__ import annotations

import json
import os
from pathlib import Path
import secrets
import ssl
import unittest
from unittest import mock
from urllib.parse import urlencode, urlunsplit

from fastapi import FastAPI
from fastapi.testclient import TestClient

import apps.api.cf_d_database_bootstrap as bootstrap


ROOT = Path(__file__).resolve().parents[1]
WORKER_SOURCE = ROOT / "cloudflare/src/index.js"
EGRESS_SOURCE = ROOT / "cloudflare/src/cf-d-neon-bootstrap-egress.js"
NODE_TEST_SOURCE = ROOT / "apps/web/tests/cloudflare_cf_d_bootstrap_egress.test.mjs"
WEB_PACKAGE = ROOT / "apps/web/package.json"
RELEASE_CONTRACT = ROOT / "docs/architecture/V10_CLOUDFLARE_RELEASE_ACCEPTANCE_CONTRACT.json"
EXPECTED_SHA = "a" * 40
_TEST_VALUE_MARKER = secrets.token_urlsafe(32)
_TEST_AUTHORIZATION = f"Bearer {secrets.token_urlsafe(32)}"


def _dsn(role: str, host: str) -> str:
    return urlunsplit(
        (
            "postgresql",
            f"{role}:{_TEST_VALUE_MARKER}@{host}",
            "/neondb",
            urlencode({"sslmode": "require"}),
            "",
        )
    )


STAGING_DSN = _dsn(
    "omni_cio_cloudflare_staging",
    "ep-example.c-6.eu-central-1.aws.neon.tech",
)
PRODUCTION_DSN = _dsn(
    "omni_cio_cloudflare_prod",
    "ep-example-pooler.c-6.eu-central-1.aws.neon.tech",
)


class _Cursor:
    def fetchone(self) -> tuple[str]:
        return ("br-example1234",)


class _Connection:
    def execute(self, query: str) -> _Cursor:
        if "neon.branch_id" not in query:
            raise AssertionError(query)
        return _Cursor()


class _UnavailableConnection:
    def execute(self, query: str) -> _Cursor:
        if "neon.branch_id" not in query:
            raise AssertionError(query)
        raise RuntimeError("synthetic transient database failure")


class _Response:
    status_code = 200

    def iter_bytes(self, chunk_size: int | None = None):  # type: ignore[no-untyped-def]
        del chunk_size
        payload = {
            "status": "READY",
            "runtime_role": "omni_cio_cloudflare_prod",
            "runtime_dsn": PRODUCTION_DSN,
            "source_sha": EXPECTED_SHA,
        }
        yield json.dumps(payload).encode("utf-8")


class _Stream:
    def __enter__(self) -> _Response:
        return _Response()

    def __exit__(self, exc_type, exc, traceback) -> None:  # type: ignore[no-untyped-def]
        return None


class _Client:
    calls: list[tuple[str, str, dict[str, str], dict[str, str]]] = []
    instances: list[_Client] = []

    def __init__(self, **kwargs: object) -> None:
        self.kwargs = kwargs
        self.instances.append(self)

    def __enter__(self) -> _Client:
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:  # type: ignore[no-untyped-def]
        return None

    def stream(
        self,
        method: str,
        url: str,
        *,
        headers: dict[str, str],
        json: dict[str, str],
    ) -> _Stream:
        self.calls.append((method, url, headers, json))
        return _Stream()


class CfDBootstrapEgressTests(unittest.TestCase):
    def setUp(self) -> None:
        _Client.calls.clear()
        _Client.instances.clear()

    def test_staging_proxy_has_no_provider_destination_authority(self) -> None:
        app = FastAPI()
        with mock.patch.object(bootstrap.httpx, "Client", _Client):
            bootstrap.install_cf_d_database_bootstrap_route(
                app,
                connection=_Connection(),
                runtime_dsn=STAGING_DSN,
                release_sha=EXPECTED_SHA,
                runtime_role="omni_cio_cloudflare_staging",
            )
            response = TestClient(app).post(
                bootstrap._BOOTSTRAP_PATH,
                headers={
                    "Authorization": _TEST_AUTHORIZATION,
                    "X-Omni-Expected-Sha": EXPECTED_SHA,
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(_Client.calls), 1)
        self.assertEqual(len(_Client.instances), 1)
        method, url, headers, payload = _Client.calls[0]
        self.assertEqual(method, "POST")
        self.assertEqual(url, "https://cf-d-neon-bootstrap.internal/")
        self.assertEqual(payload, {"expected_sha": EXPECTED_SHA})
        self.assertEqual(headers["Authorization"], _TEST_AUTHORIZATION)
        self.assertNotIn("X-Omni-Neon-Bootstrap-Target", headers)
        self.assertEqual(set(headers), {"Authorization", "Accept", "Content-Type"})
        self.assertIsInstance(_Client.instances[0].kwargs["verify"], ssl.SSLContext)
        self.assertFalse(bool(_Client.instances[0].kwargs["trust_env"]))

    def test_transient_branch_context_failure_is_request_scoped_not_startup_fatal(self) -> None:
        app = FastAPI()
        bootstrap.install_cf_d_database_bootstrap_route(
            app,
            connection=_UnavailableConnection(),
            runtime_dsn=STAGING_DSN,
            release_sha=EXPECTED_SHA,
            runtime_role="omni_cio_cloudflare_staging",
        )

        response = TestClient(app).post(
            bootstrap._BOOTSTRAP_PATH,
            headers={
                "Authorization": _TEST_AUTHORIZATION,
                "X-Omni-Expected-Sha": EXPECTED_SHA,
            },
        )

        self.assertEqual(response.status_code, 502)
        self.assertEqual(
            response.json()["detail"],
            "CLOUDFLARE_CF_D_STAGING_PROVIDER_CONTEXT_UNAVAILABLE",
        )
        self.assertEqual(_Client.calls, [])

    def test_cloudflare_runtime_requires_ephemeral_container_ca(self) -> None:
        app = FastAPI()
        with (
            mock.patch.dict(
                os.environ,
                {"OMNI_V10_CLOUDFLARE_RUNTIME": "1"},
                clear=False,
            ),
            mock.patch.object(
                bootstrap,
                "_CLOUDFLARE_CONTAINER_CA_FILE",
                "/definitely/missing/cloudflare-container-ca.crt",
            ),
        ):
            bootstrap.install_cf_d_database_bootstrap_route(
                app,
                connection=_Connection(),
                runtime_dsn=STAGING_DSN,
                release_sha=EXPECTED_SHA,
                runtime_role="omni_cio_cloudflare_staging",
            )
            response = TestClient(app).post(
                bootstrap._BOOTSTRAP_PATH,
                headers={
                    "Authorization": _TEST_AUTHORIZATION,
                    "X-Omni-Expected-Sha": EXPECTED_SHA,
                },
            )

        self.assertEqual(response.status_code, 502)
        self.assertEqual(
            response.json()["detail"],
            "CLOUDFLARE_CF_D_EGRESS_TLS_UNAVAILABLE",
        )

    def test_worker_exports_container_proxy_and_uses_guarded_bootstrap_executor(self) -> None:
        worker = WORKER_SOURCE.read_text(encoding="utf-8")
        required = (
            'export { ContainerProxy } from "@cloudflare/containers";',
            'from "./cf-d-neon-bootstrap-egress.js"',
            "CF_D_NEON_BOOTSTRAP_EGRESS_HOST",
            "fetchCfDNeonBootstrap",
            "Backend.outboundByHost",
            "SOURCE_SHA",
            "env",
            "interceptHttps = true",
            "return await fetchCfDNeonBootstrap(request, env, SOURCE_SHA)",
        )
        for marker in required:
            with self.subTest(marker=marker):
                self.assertIn(marker, worker)
        self.assertNotIn("return fetch(providerRequest)", worker)

    def test_egress_policy_uses_secret_bound_function_origin_and_runtime_database_binding(self) -> None:
        source = EGRESS_SOURCE.read_text(encoding="utf-8")
        required = (
            'RUNTIME_DSN_BINDING = "OMNI_V10_POSTGRES_DSN"',
            'BOOTSTRAP_ORIGIN_BINDING = "OMNI_V10_CF_D_NEON_BOOTSTRAP_ORIGIN"',
            'EXPECTED_STAGING_ROLE = "omni_cio_cloudflare_staging"',
            "current_setting('neon.branch_id', true)",
            "Neon-Connection-String",
            "Neon-Raw-Text-Output",
            "Neon-Array-Mode",
            "DATABASE_SQL_URL_PATTERN",
            "FUNCTION_URL_PATTERN",
            "DESTINATION_POLICIES",
            "trustedDestinationUrl",
            "trustedBootstrapContext",
            "fetchRuntimeBranchLookup",
            "fetchTrustedBootstrapRequest",
            "CLOUDFLARE_CF_D_BOOTSTRAP_ORIGIN_INVALID",
            "CLOUDFLARE_CF_D_BOOTSTRAP_ORIGIN_MISMATCH",
            "CLOUDFLARE_CF_D_NEON_DESTINATION_REJECTED",
            "CLOUDFLARE_CF_D_NEON_BRANCH_RESPONSE_TOO_LARGE",
            "MAX_BRANCH_LOOKUP_RESPONSE_BYTES",
            "MAX_TRUSTED_REQUEST_BODY_BYTES",
            "eu-central-1\\.aws\\.neon\\.tech",
            'request.headers.has(LEGACY_TARGET_HEADER)',
            'request.method !== "POST"',
            'virtualUrl.protocol !== "https:"',
            'url.protocol !== "https:"',
            'url.port !== ""',
            'url.search !== ""',
            'url.hash !== ""',
            'redirect: "manual"',
        )
        for marker in required:
            with self.subTest(marker=marker):
                self.assertIn(marker, source)
        self.assertNotIn('redirect: "error"', source)

        for marker in (
            "NEON_API_KEY",
            "NEON_PROJECT_ID",
            "NEON_ORG_ID",
            "process.env",
            "console.log",
            "export async function fetchCfDTrustedNeonRequest",
        ):
            with self.subTest(marker=marker):
                self.assertNotIn(marker, source)

    def test_release_contract_tracks_staging_bootstrap_origin_binding_fail_closed(self) -> None:
        contract = json.loads(RELEASE_CONTRACT.read_text(encoding="utf-8"))
        self.assertEqual(
            contract["candidate"]["staging_bootstrap_origin_binding"],
            "OMNI_V10_CF_D_NEON_BOOTSTRAP_ORIGIN",
        )
        self.assertFalse(
            contract["fail_closed"]["missing_staging_bootstrap_origin_is_success"]
        )

    def test_executable_node_regression_is_wired_into_product_web_test_command(self) -> None:
        node_test = NODE_TEST_SOURCE.read_text(encoding="utf-8")
        package = json.loads(WEB_PACKAGE.read_text(encoding="utf-8"))
        test_command = package["scripts"]["test"]
        self.assertIn("node --test", test_command)
        self.assertIn("tests/*.test.mjs", test_command)
        for marker in (
            "fetchCfDNeonBootstrap",
            "prepareCfDNeonBootstrapRequest",
            "secret-bound same-branch Neon Function",
            "cannot select an external target",
            "non-staging or non-Frankfurt runtime database bindings",
            "secret-bound Function origin matching database cell and branch",
            "oversized or malformed branch metadata",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, node_test)

    def test_bridge_does_not_disable_or_broaden_unrelated_container_network_policy(self) -> None:
        worker = WORKER_SOURCE.read_text(encoding="utf-8")
        egress = EGRESS_SOURCE.read_text(encoding="utf-8")
        self.assertNotIn("enableInternet = false", worker)
        self.assertNotIn("enableInternet = false", egress)
        self.assertNotIn("Authorization: Bearer", worker)
        self.assertNotIn("Authorization: Bearer", egress)


if __name__ == "__main__":
    unittest.main()
