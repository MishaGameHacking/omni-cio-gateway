from __future__ import annotations

import json
from pathlib import Path
import unittest
from unittest import mock

import scripts.bootstrap_v10_cloudflare_production_database_direct as direct
import scripts.deploy_v10_cloudflare_neon_bootstrap_function as deployer
from scripts.bootstrap_v10_cloudflare_production_database_direct import (
    BootstrapFunctionTarget,
)


_ROOT = Path(__file__).resolve().parents[1]
_WRAPPER = (
    _ROOT
    / "infrastructure/cloudflare/cf_d_neon_bootstrap/provenance_wrapper.mjs"
)
_CONTRACT = (
    _ROOT / "docs/architecture/V10_CLOUDFLARE_RELEASE_ACCEPTANCE_CONTRACT.json"
)
_TARGET = BootstrapFunctionTarget(branch_id="br-example1234", cell="c-6")


class CloudflareNeonFunctionProvenanceIngressTests(unittest.TestCase):
    def test_probe_uses_get_on_canonical_root_with_no_secret_headers(self) -> None:
        digest = "a" * 64
        body = json.dumps(
            {"status": "READY", "source_sha256": digest},
            separators=(",", ":"),
        ).encode("utf-8")
        response = mock.Mock()
        response.status = 200
        response.read.return_value = body
        response.getheader.return_value = "application/json; charset=utf-8"
        connection = mock.Mock()
        connection.getresponse.return_value = response

        with (
            mock.patch.object(
                deployer.http.client,
                "HTTPSConnection",
                return_value=connection,
            ) as connect,
            mock.patch.object(
                deployer,
                "_tls_context",
                return_value=mock.sentinel.tls,
            ),
        ):
            self.assertTrue(deployer._probe_source_provenance(_TARGET, digest))

        connect.assert_called_once_with(
            deployer._bootstrap_hostname(_TARGET),
            443,
            timeout=deployer._HTTP_TIMEOUT,
            context=mock.sentinel.tls,
        )
        connection.request.assert_called_once_with(
            "GET",
            deployer._PROVENANCE_TARGET,
            headers={
                "Accept": "application/json",
                "User-Agent": deployer._USER_AGENT,
            },
        )
        self.assertEqual(deployer._PROVENANCE_PATH, "/")
        self.assertEqual(deployer._PROVENANCE_TARGET, "/")
        connection.close.assert_called_once_with()

    def test_wrapper_reserves_all_get_root_requests_for_read_only_provenance(self) -> None:
        source = _WRAPPER.read_text(encoding="utf-8")
        required = (
            "const SOURCE_PROVENANCE_PATH = '/';",
            "request.method === 'GET'",
            "url.pathname === SOURCE_PROVENANCE_PATH",
            "return provenanceResponse();",
            "return handler.fetch(request);",
        )
        for marker in required:
            self.assertIn(marker, source)
        self.assertNotIn("SOURCE_PROVENANCE_QUERY", source)
        self.assertNotIn("SOURCE_PROVENANCE_HEADER", source)
        self.assertNotIn("SOURCE_PROVENANCE_USER_AGENT", source)
        self.assertNotIn("hasProvenanceDiscriminator", source)
        self.assertNotIn("/__omni-cio/source-provenance", source)
        self.assertNotEqual(deployer._USER_AGENT, direct._DIRECT_USER_AGENT)

    def test_canonical_handler_has_no_legitimate_get_route_to_shadow(self) -> None:
        handler = (
            _ROOT / "infrastructure/cloudflare/cf_d_neon_bootstrap/index.mjs"
        ).read_text(encoding="utf-8")
        self.assertIn(
            "if (request.method !== 'POST') return fail('METHOD_NOT_ALLOWED', 405);",
            handler,
        )

    def test_direct_preflight_accepts_read_only_root_provenance(self) -> None:
        digest = "b" * 64
        body = json.dumps(
            {"status": "READY", "source_sha256": digest},
            separators=(",", ":"),
        ).encode("utf-8")
        response = mock.Mock()
        response.status = 200
        response.read.return_value = body
        connection = mock.Mock()
        connection.getresponse.return_value = response

        with mock.patch.object(
            direct, "_direct_connection", return_value=connection
        ):
            direct._preflight_direct_function(_TARGET)

        connection.request.assert_called_once_with(
            "GET",
            "/",
            body=None,
            headers={
                "Accept": "application/json",
                "User-Agent": direct._DIRECT_USER_AGENT,
            },
        )
        connection.close.assert_called_once_with()

    def test_direct_preflight_rejects_malformed_root_provenance(self) -> None:
        response = mock.Mock()
        response.status = 200
        response.read.return_value = b'{"status":"READY","source_sha256":"bad"}'
        connection = mock.Mock()
        connection.getresponse.return_value = response

        with (
            mock.patch.object(direct, "_direct_connection", return_value=connection),
            self.assertRaisesRegex(
                direct.legacy.BootstrapStopped,
                direct._DIRECT_RESPONSE_INVALID,
            ),
        ):
            direct._preflight_direct_function(_TARGET)

        connection.close.assert_called_once_with()

    def test_release_contract_keeps_canonical_root_provenance_probe(self) -> None:
        contract = json.loads(_CONTRACT.read_text(encoding="utf-8"))
        cutover = contract["cutover"]
        self.assertEqual(
            cutover["production_database_bootstrap_function_provenance_path"],
            deployer._PROVENANCE_PATH,
        )
        self.assertEqual(
            cutover["production_database_bootstrap_function_provenance_method"],
            "GET",
        )
        self.assertEqual(
            cutover["production_database_bootstrap_function_provenance_query"],
            "",
        )
        self.assertIs(
            cutover[
                "production_database_bootstrap_function_provenance_query_primary"
            ],
            False,
        )
        self.assertIs(
            cutover[
                "production_database_bootstrap_function_provenance_root_ingress_required"
            ],
            True,
        )
        self.assertIs(
            cutover[
                "production_database_bootstrap_function_provenance_custom_subpath_allowed"
            ],
            False,
        )


if __name__ == "__main__":
    unittest.main()
