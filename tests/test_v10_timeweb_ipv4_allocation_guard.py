from __future__ import annotations

import ast
import copy
import json
import io
import contextlib
import tomllib
import unittest

from scripts import check_v10_timeweb_ipv4_allocation as guard


class ProtocolGuardTests(unittest.TestCase):
    def setUp(self) -> None:
        self.data = json.loads(guard.CONTRACT.read_text(encoding="utf-8"))
        self.source = guard.SOURCE.read_text(encoding="utf-8")

    def test_cli_does_not_claim_live_readiness(self) -> None:
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(guard.main(), 0)
        self.assertIn("live allocation remains unaccepted", output.getvalue())
        self.assertNotIn("CERTIFIED_GREEN", output.getvalue())

    def test_missing_contract_section_is_rejected(self) -> None:
        changed = copy.deepcopy(self.data)
        del changed["transition"]
        with self.assertRaises(ValueError):
            guard.validate_contract(changed)

    def test_actual_contract_and_source_pass(self) -> None:
        guard.validate()

    def test_live_adapter_or_readiness_claim_cannot_be_invented(self) -> None:
        for key in self.data["implementation"]:
            if key == "pure_protocol":
                continue
            changed = copy.deepcopy(self.data)
            changed["implementation"][key] = not self.data["implementation"][key]
            with self.subTest(key=key):
                with self.assertRaises(ValueError):
                    guard.validate_contract(changed)

    def test_missing_closed_storage_no_longer_required_is_rejected(self) -> None:
        changed = copy.deepcopy(self.data)
        changed["transition"]["claim_requires_atomic_durable_acknowledgement"] = False
        with self.assertRaises(ValueError):
            guard.validate_contract(changed)

    def test_purchase_delete_network_and_authority_widening_are_rejected(self) -> None:
        for key, value in self.data["protected_invariants"].items():
            if value is not False:
                continue
            changed = copy.deepcopy(self.data)
            changed["protected_invariants"][key] = True
            with self.subTest(key=key):
                with self.assertRaises(ValueError):
                    guard.validate_contract(changed)

    def test_expiry_may_not_reset_attempted_operation(self) -> None:
        changed = copy.deepcopy(self.data)
        changed["transition"]["expiry_releases_attempted_claim"] = True
        with self.assertRaises(ValueError):
            guard.validate_contract(changed)

    def test_boolean_as_count_or_ttl_is_rejected(self) -> None:
        for section, field in (
            ("transition", "metadata_writes_per_claim_max"),
            ("plan", "ttl_seconds"),
            ("plan", "complete_inventory_count"),
        ):
            changed = copy.deepcopy(self.data)
            changed[section][field] = True
            with self.subTest(field=field):
                with self.assertRaises(ValueError):
                    guard.validate_contract(changed)

    def test_no_public_transport_or_parity_pass_marker(self) -> None:
        for marker in (
            "CERTIFIED_GREEN",
            "TIMEWEB_RU_PG_PUBLIC_IPV4_TLS=READY",
            "RU_PG_TIMEWEB_SYNTHETIC_PARITY=PASS",
        ):
            with self.subTest(marker=marker):
                with self.assertRaises(ValueError):
                    guard.validate_source(self.source + "\n# " + marker)

    def test_direct_network_dependency_is_rejected(self) -> None:
        for module in ("socket", "requests", "subprocess", "urllib.request"):
            with self.subTest(module=module):
                with self.assertRaises(ValueError):
                    guard.validate_source(self.source + "\nimport " + module)

    def test_second_metadata_write_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            guard.validate_source(self.source + "\nwrite_comment_once('id', 'value')\n")

    def test_an_unguarded_live_entrypoint_is_rejected(self) -> None:
        changed = self.source + "\nif __name__ == '__main__':\n    apply()\n"
        with self.assertRaises(ValueError):
            guard.validate_source(changed)

    def test_exception_assertions_isolate_the_operation_under_test(self) -> None:
        tests = guard.ROOT / "tests"
        for path in tests.glob("test_v10_timeweb_ipv4_allocation*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if not isinstance(node, ast.With):
                    continue
                contexts = [item.context_expr for item in node.items]
                raises = any(
                    isinstance(value, ast.Call)
                    and isinstance(value.func, ast.Attribute)
                    and value.func.attr in {"assertRaises", "assertRaisesRegex"}
                    for value in contexts
                )
                if raises:
                    calls = [
                        child
                        for statement in node.body
                        for child in ast.walk(statement)
                        if isinstance(child, ast.Call)
                    ]
                    with self.subTest(path=path.name, line=node.lineno):
                        self.assertEqual(len(calls), 1)

    def test_allocation_modules_are_in_canonical_mypy_targets(self) -> None:
        configuration = tomllib.loads(
            (guard.ROOT / "pyproject.toml").read_text(encoding="utf-8")
        )
        targets = set(configuration["tool"]["mypy"]["files"])
        expected = {
            "scripts/timeweb_ipv4_allocation.py",
            "scripts/timeweb_ipv4_allocation_github.py",
            "scripts/timeweb_ipv4_allocation_journal.py",
            "scripts/timeweb_ipv4_allocation_windows.py",
            "scripts/timeweb_ipv4_allocation_provider.py",
            "scripts/run_v10_timeweb_ipv4_allocation.py",
            "scripts/check_v10_timeweb_ipv4_allocation.py",
        }
        self.assertLessEqual(expected, targets)

    def test_m2_workflow_authority_widening_is_rejected(self) -> None:
        changes = (
            ("initialize_provider_access_allowed", True),
            ("summary_private_identifiers_allowed", True),
            ("allocation_success_implies_transport_ready", True),
            ("direct_shell_interpolation_of_dispatch_inputs_allowed", True),
            ("dispatch_inputs_passed_via_environment_only", False),
            ("apply_github_permission", "issues: write"),
            ("non_apply_issue_permission", "issues: read"),
        )
        for key, value in changes:
            changed = copy.deepcopy(self.data)
            changed["operational_workflow"][key] = value
            with self.subTest(key=key):
                with self.assertRaises(ValueError):
                    guard.validate_contract(changed)

    def test_provider_and_workflow_guards_pass_current_source(self) -> None:
        guard._validate_provider()
        guard._validate_runner()
        guard._validate_workflow()

    def test_generic_cost_approval_does_not_replace_owner_allocation(self) -> None:
        changed = copy.deepcopy(self.data)
        changed["approval"]["cost_approval_sufficient"] = True
        with self.assertRaises(ValueError):
            guard.validate_contract(changed)


if __name__ == "__main__":
    unittest.main()
