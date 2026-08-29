from __future__ import annotations

import ast
import json
from pathlib import Path
import subprocess
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = (
    ROOT
    / "docs/architecture/V10_CLOUDFLARE_PUBLIC_PRODUCT_INTEGRATED_CONTRACT.json"
)
GUARD = ROOT / "scripts/check_v10_cloudflare_public_product_integrated.py"


class CloudflarePublicProductIntegratedGovernanceTests(unittest.TestCase):
    def test_contract_keeps_ordered_internal_milestones(self) -> None:
        payload = json.loads(CONTRACT.read_text(encoding="utf-8"))
        observed = [
            (
                item["id"],
                item["legacy_stage_id"],
                item["provider_mutation_allowed"],
                item["production_promotion_allowed"],
            )
            for item in payload["milestones"]
        ]
        self.assertEqual(
            observed,
            [
                ("CF-A", "CLOUDFLARE-BUILDS-VERIFIER-INTEGRATION", False, False),
                ("CF-B", "CLOUDFLARE-RUNTIME-COMPATIBILITY", False, False),
                ("CF-C", "CLOUDFLARE-CANDIDATE-DEPLOYMENT", True, False),
                ("CF-D", "CLOUDFLARE-PUBLIC-CUTOVER", True, True),
            ],
        )

    def test_contract_preserves_web_visual_and_money_locks(self) -> None:
        payload = json.loads(CONTRACT.read_text(encoding="utf-8"))
        self.assertFalse(payload["web_visual"]["included_in_this_update"])
        self.assertTrue(payload["web_visual"]["owner_start_required"])
        self.assertEqual(
            payload["web_visual"]["owner_start_command"],
            "START V10 WEB VISUAL SYSTEM UPDATE",
        )
        protected = payload["protected_invariants"]
        self.assertFalse(protected["broker_write"])
        self.assertFalse(protected["trading_methods"])
        self.assertFalse(protected["REAL_TRADING_ENABLED"])
        self.assertEqual(protected["app_entrypoint"], "app:app")

    def test_contract_validator_remains_a_flat_orchestrator(self) -> None:
        tree = ast.parse(GUARD.read_text(encoding="utf-8"))
        function = next(
            node
            for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name == "_validate_contract"
        )
        self.assertTrue(function.body)
        self.assertTrue(all(isinstance(node, ast.Expr) for node in function.body))
        calls = [
            node.value.func.id
            for node in function.body
            if isinstance(node, ast.Expr)
            and isinstance(node.value, ast.Call)
            and isinstance(node.value.func, ast.Name)
        ]
        self.assertEqual(
            calls,
            [
                "_validate_identity",
                "_validate_delivery",
                "_validate_milestones",
                "_validate_cloudflare_first",
                "_validate_cost_security",
                "_validate_web_visual",
                "_validate_protected_invariants",
            ],
        )

    def test_repository_guard_passes(self) -> None:
        completed = subprocess.run(
            [sys.executable, str(GUARD)],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr + completed.stdout)


if __name__ == "__main__":
    unittest.main()
