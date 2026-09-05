from __future__ import annotations

import json
from pathlib import Path
import unittest
from unittest import mock
from urllib.parse import urlencode, urlunsplit

from fastapi import FastAPI
from fastapi.testclient import TestClient

import apps.api.cf_d_database_bootstrap as bootstrap


ROOT = Path(__file__).resolve().parents[1]
WORKER_SOURCE = ROOT / "cloudflare/src/index.js"
EXPECTED_SHA = "a" * 40
_TEST_CREDENTIAL = "synthetic-egress-credential"


def _dsn(role: str, host: str) -> str:
    return urlunsplit(
        (
            "postgresql",
            f"{role}:{_TEST_CREDENTIAL}@{host}",
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

    def __init__(self, **kwargs: object) -> None:
        self.kwargs = kwargs

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

    def test_staging_proxy_uses_worker_virtual_egress_host(self) -> None:
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
                    "Authorization": "Bearer synthetic.jwt.token",
                    "X-Omni-Expected-Sha": EXPECTED_SHA,
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(_Client.calls), 1)
        method, url, headers, payload = _Client.calls[0]
        self.assertEqual(method, "POST")
        self.assertEqual(url, "http://cf-d-neon-bootstrap.internal/")
        self.assertEqual(payload, {"expected_sha": EXPECTED_SHA})
        self.assertEqual(headers["Authorization"], "Bearer synthetic.jwt.token")
        self.assertEqual(
            headers["X-Omni-Neon-Bootstrap-Target"],
            "https://br-example1234-cfdprodbootstrap.compute."
            "c-6.eu-central-1.aws.neon.tech/",
        )

    def test_worker_exports_container_proxy_and_strict_target_bridge(self) -> None:
        source = WORKER_SOURCE.read_text(encoding="utf-8")
        required = (
            "ContainerProxy",
            "export { ContainerProxy };",
            'CF_D_NEON_BOOTSTRAP_EGRESS_HOST = "cf-d-neon-bootstrap.internal"',
            'CF_D_NEON_BOOTSTRAP_TARGET_HEADER = "x-omni-neon-bootstrap-target"',
            "Backend.outboundByHost",
            "validatedCfDNeonBootstrapTarget",
            "cfdprodbootstrap\\.compute\\.c-[a-z0-9]+\\.eu-central-1\\.aws\\.neon\\.tech",
            'headers.delete(CF_D_NEON_BOOTSTRAP_TARGET_HEADER)',
            'headers.delete("host")',
            'redirect: "manual"',
        )
        for marker in required:
            with self.subTest(marker=marker):
                self.assertIn(marker, source)

        forbidden = (
            "NEON_API_KEY",
            "NEON_PROJECT_ID",
            "NEON_ORG_ID",
            "console.log",
        )
        for marker in forbidden:
            with self.subTest(marker=marker):
                self.assertNotIn(marker, source)

    def test_worker_target_bridge_remains_narrow_and_non_secret(self) -> None:
        source = WORKER_SOURCE.read_text(encoding="utf-8")
        self.assertIn('target.protocol !== "https:"', source)
        self.assertIn('target.pathname !== "/"', source)
        self.assertIn('request.method !== "POST"', source)
        self.assertNotIn("enableInternet = false", source)
        self.assertNotIn("Authorization: Bearer", source)


if __name__ == "__main__":
    unittest.main()
