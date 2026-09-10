from __future__ import annotations

import json
from pathlib import Path
import unittest
from unittest import mock

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
    def test_probe_uses_canonical_root_with_exact_no_secret_header(self) -> None:
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
            "/",
            headers={
                "Accept": "application/json",
                "User-Agent": deployer._USER_AGENT,
                "X-Omni-Source-Provenance": "v1",
            },
        )
        connection.close.assert_called_once_with()

    def test_wrapper_intercepts_only_exact_root_provenance_tuple(self) -> None:
        source = _WRAPPER.read_text(encoding="utf-8")
        required = (
            "const SOURCE_PROVENANCE_PATH = '/';",
            "const SOURCE_PROVENANCE_HEADER = 'x-omni-source-provenance';",
            "const SOURCE_PROVENANCE_HEADER_VALUE = 'v1';",
            "request.method === 'GET'",
            "url.pathname === SOURCE_PROVENANCE_PATH",
            "url.search === ''",
            "request.headers.get(SOURCE_PROVENANCE_HEADER) === "
            "SOURCE_PROVENANCE_HEADER_VALUE",
            "return handler.fetch(request);",
        )
        for marker in required:
            self.assertIn(marker, source)
        self.assertNotIn("/__omni-cio/source-provenance", source)

    def test_release_contract_freezes_canonical_root_ingress(self) -> None:
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
            cutover["production_database_bootstrap_function_provenance_header"],
            deployer._PROVENANCE_HEADER,
        )
        self.assertEqual(
            cutover[
                "production_database_bootstrap_function_provenance_header_value"
            ],
            deployer._PROVENANCE_HEADER_VALUE,
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
