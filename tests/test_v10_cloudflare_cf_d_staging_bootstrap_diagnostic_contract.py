from __future__ import annotations

import json
from pathlib import Path
import unittest

from omni_cio.contracts.v1.cloudflare_cf_d_bootstrap_failures import (
    STAGING_OUTER_FAILURE_PREFIX,
    STAGING_OUTER_FAILURE_STATUS_BY_DETAIL,
    STAGING_UNCLASSIFIED_HTTP_PREFIX,
    STAGING_UNCLASSIFIED_HTTP_STATUSES,
)


_ROOT = Path(__file__).resolve().parents[1]
_CONTRACT = (
    _ROOT
    / "docs/architecture/V10_CLOUDFLARE_CF_D_STAGING_BOOTSTRAP_DIAGNOSTIC_CONTRACT.json"
)


class CloudflareCfDStagingBootstrapDiagnosticContractTests(unittest.TestCase):
    def test_machine_contract_matches_source_controlled_taxonomy(self) -> None:
        contract = json.loads(_CONTRACT.read_text(encoding="utf-8"))

        self.assertEqual(contract["outer_failure_prefix"], STAGING_OUTER_FAILURE_PREFIX)
        self.assertEqual(
            contract["outer_failure_status_by_detail"],
            dict(STAGING_OUTER_FAILURE_STATUS_BY_DETAIL),
        )
        self.assertEqual(
            contract["unclassified_http_prefix"],
            STAGING_UNCLASSIFIED_HTTP_PREFIX,
        )
        self.assertEqual(
            contract["unclassified_http_statuses"],
            sorted(STAGING_UNCLASSIFIED_HTTP_STATUSES),
        )
        self.assertIs(contract["raw_error_reflection_allowed"], False)
        self.assertIs(contract["response_headers_reflection_allowed"], False)
        self.assertIs(contract["provider_identifier_reflection_allowed"], False)
        self.assertIs(contract["unknown_failure_retryable"], False)
        self.assertIs(contract["unsupported_unknown_status_remains_generic"], True)
        self.assertIs(contract["redirect_classification_preserved"], True)
        self.assertIs(contract["transport_classification_preserved"], True)
        self.assertIs(
            contract["existing_endpoint_specific_failure_taxonomy_preserved"],
            True,
        )


if __name__ == "__main__":
    unittest.main()
