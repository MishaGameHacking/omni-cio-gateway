"""Unit tests for the evidence parser, not emulator installation results."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest

MODULE = Path(__file__).resolve().parents[1] / "installation_report.py"
spec = importlib.util.spec_from_file_location("installation_report", MODULE)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def report(*groups):
    return [{"test": name, "success": True} for group in groups for name in sorted(group)]


class InstallationReportTests(unittest.TestCase):
    def validate(self, rows, upgrade=False, profile=False):
        module.validate_results(rows, upgrade_required=upgrade, profile_required=profile)

    def test_clean_install_report(self):
        self.validate(report(module.BASE_TESTS))

    def test_required_upgrade_report(self):
        self.validate(report(module.BASE_TESTS, module.UPGRADE_TESTS), upgrade=True)

    def test_upgrade_requires_post_install_launch(self):
        self.assertIn("upgrade_bootstrap_launch", module.UPGRADE_TESTS)
        rows = report(module.BASE_TESTS, module.UPGRADE_TESTS)
        rows = [row for row in rows if row["test"] != "upgrade_bootstrap_launch"]
        with self.assertRaises(ValueError):
            self.validate(rows, upgrade=True)

    def test_required_profile_report(self):
        self.validate(report(module.BASE_TESTS, module.PROFILE_TESTS), profile=True)

    def test_upgrade_and_profile_report(self):
        self.validate(report(module.BASE_TESTS, module.UPGRADE_TESTS, module.PROFILE_TESTS), True, True)

    def test_each_required_check_is_mandatory(self):
        rows = report(module.BASE_TESTS, module.UPGRADE_TESTS, module.PROFILE_TESTS)
        for removed in rows:
            with self.subTest(missing=removed["test"]):
                remaining = [row for row in rows if row != removed]
                with self.assertRaises(ValueError):
                    self.validate(remaining, True, True)

    def test_empty_report_is_not_success(self):
        with self.assertRaises(ValueError):
            self.validate([])

    def test_non_list_is_rejected(self):
        with self.assertRaises(ValueError):
            self.validate({"success": True})

    def test_non_mapping_item_is_rejected(self):
        rows = report(module.BASE_TESTS) + ["profile_ui"]
        with self.assertRaises(ValueError):
            self.validate(rows)

    def test_false_result_is_rejected(self):
        rows = report(module.BASE_TESTS)
        rows[0]["success"] = False
        with self.assertRaises(ValueError):
            self.validate(rows)

    def test_truthy_result_is_not_explicit_success(self):
        for value in (1, "true", "false", None):
            with self.subTest(success=value):
                rows = report(module.BASE_TESTS)
                rows[0]["success"] = value
                with self.assertRaises(ValueError):
                    self.validate(rows)

    def test_missing_success_is_rejected(self):
        rows = report(module.BASE_TESTS)
        del rows[0]["success"]
        with self.assertRaises(ValueError):
            self.validate(rows)

    def test_duplicate_is_rejected(self):
        rows = report(module.BASE_TESTS)
        rows.append(dict(rows[0]))
        with self.assertRaises(ValueError):
            self.validate(rows)

    def test_unexpected_check_is_rejected(self):
        rows = report(module.BASE_TESTS, {"unexpected"})
        with self.assertRaises(ValueError):
            self.validate(rows)

    def test_profile_checks_not_accepted_when_disabled(self):
        rows = report(module.BASE_TESTS, module.PROFILE_TESTS)
        with self.assertRaises(ValueError):
            self.validate(rows)

    def test_unrequested_upgrade_is_rejected(self):
        rows = report(module.BASE_TESTS, module.UPGRADE_TESTS)
        with self.assertRaises(ValueError):
            self.validate(rows)

    def test_non_string_name_is_rejected(self):
        rows = report(module.BASE_TESTS)
        rows[0]["test"] = ["activity_launch"]
        with self.assertRaises(ValueError):
            self.validate(rows)

    def test_failed_ui_result_cannot_pass(self):
        rows = report(module.BASE_TESTS, module.PROFILE_TESTS)
        for row in rows:
            if row["test"] == "profile_ui":
                row["success"] = False
        with self.assertRaises(ValueError):
            self.validate(rows, profile=True)

    def test_report_order_is_irrelevant(self):
        self.validate(list(reversed(report(module.BASE_TESTS))))


if __name__ == "__main__":
    unittest.main()