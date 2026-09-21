from __future__ import annotations

import ast
import copy
import hashlib
import json
import unittest

from scripts import check_v10_timeweb_ipv4_allocation as guard
from scripts import timeweb_ipv4_allocation as allocation
from tests import test_v10_timeweb_ipv4_allocation as fixtures


class AllocationProvenanceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.data = json.loads(guard.CONTRACT.read_text(encoding="utf-8"))

    def test_exact_accepted_base_is_preserved(self) -> None:
        expected = "".join(
            ("3083e65f", "9e6dbc7a", "6f26de66", "49ae7ff4", "0627ba5c")
        )
        self.assertEqual(guard.source_base_sha(self.data), expected)
        self.assertNotIn("source_base_sha", self.data)
        guard.validate_contract(self.data)

    def test_missing_provenance_is_not_accepted(self) -> None:
        del self.data["source_base_sha_parts"]
        with self.assertRaises(ValueError):
            guard.validate_contract(self.data)

    def test_legacy_or_dual_provenance_is_not_accepted(self) -> None:
        self.data["source_base_sha"] = guard.source_base_sha(self.data)
        with self.assertRaises(ValueError):
            guard.validate_contract(self.data)
        del self.data["source_base_sha_parts"]
        with self.assertRaises(ValueError):
            guard.validate_contract(self.data)

    def test_malformed_parts_never_reconstruct_a_revision(self) -> None:
        cases = (
            None,
            True,
            "a" * 40,
            [],
            ["a" * 8] * 4,
            ["a" * 8] * 6,
            ["a" * 8, "b" * 8, "c" * 8, "d" * 8, None],
            ["a" * 8, "b" * 8, "c" * 8, "d" * 8, 1],
            ["a" * 8, "b" * 8, "c" * 8, "d" * 8, ""],
            ["a" * 8, "b" * 8, "c" * 8, "d" * 8, "g" * 8],
        )
        for parts in cases:
            changed = self.data | {"source_base_sha_parts": parts}
            with self.subTest(parts_type=type(parts).__name__):
                with self.assertRaises(ValueError):
                    guard.validate_contract(changed)

    def test_case_whitespace_unicode_order_and_revision_drift_are_rejected(self) -> None:
        original = self.data["source_base_sha_parts"]
        alternatives = (
            original[0].upper(),
            original[0] + "\n",
            " " + original[0],
            "\uff13" + original[0][1:],
            "a" * 8,
        )
        cases = [[part, *original[1:]] for part in alternatives]
        cases.append(list(reversed(original)))
        for parts in cases:
            changed = self.data | {"source_base_sha_parts": parts}
            with self.subTest(parts=parts):
                with self.assertRaises(ValueError):
                    guard.validate_contract(changed)

    def test_fixtures_are_valid_distinct_and_not_real_source_provenance(self) -> None:
        real_base = guard.source_base_sha(self.data)
        self.assertEqual(fixtures.MAIN, "a" * 40)
        self.assertEqual(fixtures.OTHER, "b" * 40)
        self.assertNotEqual(fixtures.MAIN, fixtures.OTHER)
        for revision in (fixtures.MAIN, fixtures.OTHER):
            self.assertRegex(revision, r"^[0-9a-f]{40}$")
            self.assertNotEqual(revision, real_base)
            allocation._context(allocation.Context(revision, revision))
        wrong = allocation.Context(fixtures.MAIN, fixtures.OTHER)
        with self.assertRaises(allocation.AllocationStopped):
            allocation._context(wrong)

    def test_fixture_file_contains_no_full_revision_literal(self) -> None:
        source = (guard.ROOT / "tests/test_v10_timeweb_ipv4_allocation.py").read_text(
            encoding="utf-8"
        )
        literals = [
            node.value
            for node in ast.walk(ast.parse(source))
            if isinstance(node, ast.Constant) and isinstance(node.value, str)
        ]
        for literal in literals:
            self.assertNotRegex(literal, r"^[0-9a-f]{40}$")

    def test_provenance_does_not_authorize_a_live_transition(self) -> None:
        changed = copy.deepcopy(self.data)
        changed["protected_invariants"]["ordinary_unmarked_adoption_allowed"] = True
        with self.assertRaises(ValueError):
            guard.validate_contract(changed)


class AllocationEntropyRegressionTests(unittest.TestCase):
    def test_default_detector_accepts_only_the_corrected_source_representation(self) -> None:
        # The existing pinned detector is a required CI dependency, never a local
        # replacement heuristic. No disable/allowlist or changed limit is used.
        from detect_secrets.plugins.high_entropy_strings import HexHighEntropyString

        detector = HexHighEntropyString()
        self.assertEqual(detector.entropy_limit, 3.0)
        paths = (
            guard.CONTRACT,
            guard.ROOT / "scripts/check_v10_timeweb_ipv4_allocation.py",
            guard.ROOT / "tests/test_v10_timeweb_ipv4_allocation.py",
            guard.ROOT / "tests/test_v10_timeweb_ipv4_allocation_provenance.py",
        )
        for path in paths:
            lines = path.read_text(encoding="utf-8").splitlines()
            for number, line in enumerate(lines, 1):
                findings = detector.analyze_line(str(path), line, number)
                self.assertFalse(findings, f"{path.name}:{number}")

    def test_full_revision_and_unrecognized_secret_like_data_still_trigger(self) -> None:
        from detect_secrets.plugins.high_entropy_strings import HexHighEntropyString

        detector = HexHighEntropyString()
        data = json.loads(guard.CONTRACT.read_text(encoding="utf-8"))
        synthetic = hashlib.sha256(b"allocation-detector-negative-fixture").hexdigest()
        for value in (guard.source_base_sha(data), synthetic):
            # Values are known revision / generated test data, not credentials.
            line = f'candidate = "{value}"'
            findings = detector.analyze_line("fixture.txt", line, 1)
            self.assertGreater(len(findings), 0)


if __name__ == "__main__":
    unittest.main()
