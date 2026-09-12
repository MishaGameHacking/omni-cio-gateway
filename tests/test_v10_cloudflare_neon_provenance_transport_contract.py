from __future__ import annotations

import json
from pathlib import Path
import unittest


_ROOT = Path(__file__).resolve().parents[1]
_CONTRACT = _ROOT / "docs/architecture/V10_CLOUDFLARE_RELEASE_ACCEPTANCE_CONTRACT.json"
_RUNNER = _ROOT / "scripts/run_v10_cloudflare_gated_candidate.py"
_WORKER = _ROOT / "cloudflare/src/index.js"
_PROVENANCE = _ROOT / "cloudflare/src/cf-d-neon-function-provenance.js"
_DIRECT_BOOTSTRAP = _ROOT / "scripts/bootstrap_v10_cloudflare_production_database_direct.py"
_CUSTODY_PATH = "/api/internal/v10/cf-d/function-source-provenance-custody"


class CloudflareNeonProvenanceTransportContractTests(unittest.TestCase):
    def test_release_contract_pins_worker_provenance_without_changing_direct_oidc_bootstrap(
        self,
    ) -> None:
        contract = json.loads(_CONTRACT.read_text(encoding="utf-8"))
        candidate = contract["candidate"]
        cutover = contract["cutover"]
        self.assertEqual(
            candidate["staging_function_provenance_custody_path"],
            _CUSTODY_PATH,
        )
        self.assertIs(
            candidate["staging_function_provenance_uses_origin_sync_token"],
            True,
        )
        self.assertIs(candidate["staging_function_provenance_exact_sha_required"], True)
        self.assertIs(
            candidate[
                "staging_function_provenance_provider_identifier_response_allowed"
            ],
            False,
        )
        self.assertIs(
            candidate["staging_function_provenance_available_only_while_sync_token_armed"],
            True,
        )

        self.assertEqual(
            cutover["production_database_bootstrap_function_provenance_transport"],
            "EXACT_SHA_STAGING_WORKER_BOUNDED_EGRESS",
        )
        self.assertIs(
            cutover[
                "production_database_bootstrap_function_runner_direct_provenance_allowed"
            ],
            False,
        )
        self.assertIs(
            cutover[
                "production_database_bootstrap_function_provenance_staging_worker_exact_sha_required"
            ],
            True,
        )
        self.assertIs(
            cutover[
                "production_database_bootstrap_function_provenance_origin_sync_token_required"
            ],
            True,
        )
        self.assertIs(
            cutover[
                "production_database_bootstrap_function_provenance_destination_derived_from_staging_database"
            ],
            True,
        )
        self.assertIs(
            cutover[
                "production_database_bootstrap_function_provenance_provider_identifier_response_allowed"
            ],
            False,
        )
        self.assertEqual(
            cutover["production_database_bootstrap_active_transport"],
            "GITHUB_OIDC_DIRECT_NEON_FUNCTION",
        )
        self.assertIs(
            cutover["production_database_bootstrap_public_staging_relay_active"],
            False,
        )
        self.assertIs(
            contract["fail_closed"]["staging_function_provenance_failure_is_success"],
            False,
        )

    def test_runner_binds_function_convergence_to_staging_provenance_before_token_cleanup(
        self,
    ) -> None:
        source = _RUNNER.read_text(encoding="utf-8")
        token = source.index("with bootstrap_origin_sync_token(api) as sync_token:")
        custody = source.index("bootstrap_origin = fetch_bootstrap_origin_custody(")
        adapter = source.index("with _candidate_provenance_transport(")
        deploy = source.index("deploy_exact_main_bootstrap_function_if_required(api, sha)")
        persist = source.index("persist_bootstrap_origin_custody(api, bootstrap_origin)")
        self.assertLess(token, custody)
        self.assertLess(custody, adapter)
        self.assertLess(adapter, deploy)
        self.assertLess(deploy, persist)
        self.assertIn("probe_exact_source_via_staging", source)

    def test_worker_provenance_is_method_only_and_returns_no_provider_destination(
        self,
    ) -> None:
        source = _PROVENANCE.read_text(encoding="utf-8")
        self.assertIn('method: "GET"', source)
        self.assertIn('headers: { Accept: JSON_MEDIA_TYPE }', source)
        self.assertIn('redirect: "manual"', source)
        self.assertNotIn("Authorization", source)
        self.assertNotIn("X-Omni", source)
        worker = _WORKER.read_text(encoding="utf-8")
        self.assertIn("CF_D_FUNCTION_PROVENANCE_CUSTODY_PATH", worker)
        self.assertIn("handleCfDFunctionProvenanceCustody", worker)

    def test_direct_production_bootstrap_transport_remains_dedicated_oidc(self) -> None:
        source = _DIRECT_BOOTSTRAP.read_text(encoding="utf-8")
        self.assertIn('_DIRECT_OIDC_HEADER = "X-Omni-GitHub-OIDC"', source)
        self.assertIn("_github_oidc_token()", source)
        self.assertNotIn(_CUSTODY_PATH, source)


if __name__ == "__main__":
    unittest.main()
