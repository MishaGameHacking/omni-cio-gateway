"""Synthetic diagnostic regressions; these do not establish device UI readiness."""
import contextlib
import io
import json
import unittest
from unittest.mock import Mock

from test_profile_launch import ACTIVITY, PACKAGE, RESUMED, launch, tree


def launch_outputs(*after_start):
    return ["", *after_start]


class ReadinessDiagnosticTests(unittest.TestCase):
    def failure_report(self, command, read_tree):
        output = io.StringIO()
        with contextlib.redirect_stdout(output), self.assertRaises(AssertionError):
            launch.launch_profile(command, read_tree, lambda read, message: read())
        line = next(
            line
            for line in output.getvalue().splitlines()
            if line.startswith("PROFILE_READINESS_DIAGNOSTIC=")
        )
        return json.loads(line.split("=", 1)[1])

    def test_records_which_foreground_check_failed_without_reading_stale_tree(self):
        read_tree = Mock()
        report = self.failure_report(
            Mock(
                side_effect=launch_outputs(
                    "Status: ok",
                    "lastResumedActivity " + ACTIVITY,
                )
            ),
            read_tree,
        )
        self.assertEqual(report["stage"], "foreground-before-tree")
        self.assertIn(ACTIVITY, report["foreground_before"][0])
        self.assertEqual(report["expected_screen"], "profile")
        read_tree.assert_not_called()

    def test_records_wrong_package_and_marker_geometry(self):
        report = self.failure_report(
            Mock(side_effect=launch_outputs("Status: ok", RESUMED)),
            lambda: tree(package="other.package", bounds="[0,0][0,10]"),
        )
        self.assertEqual(report["stage"], "accessibility-tree")
        self.assertEqual(report["frame"]["markers"][0]["package"], "other.package")
        self.assertEqual(report["frame"]["markers"][0]["bounds"], "[0,0][0,10]")

    def test_does_not_convert_lost_focus_into_success(self):
        report = self.failure_report(
            Mock(
                side_effect=launch_outputs(
                    "Status: ok",
                    RESUMED,
                    "topResumedActivity: other/Main",
                )
            ),
            tree,
        )
        self.assertEqual(report["stage"], "foreground-after-tree")
        self.assertEqual(report["foreground_after"], ["topResumedActivity: other/Main"])

    def test_diagnostics_do_not_dump_unrelated_activity_fields(self):
        output = "secret-unrelated-field\n" + RESUMED + "\n" + ("unrelated\n" * 10000)
        self.assertEqual(launch.foreground_observation(output), [RESUMED])
        bounded = launch.foreground_observation(
            ("topResumedActivity: " + "x" * 10000 + "\n") * 100
        )
        self.assertEqual(len(bounded), 8)
        self.assertTrue(all(len(line) <= 320 for line in bounded))

    def test_tree_diagnostics_are_bounded_and_omit_ordinary_text(self):
        root = tree(marker="probe-" + "x" * 10000)
        for _ in range(20):
            root.append(tree(marker="probe-more")[0])
        root[0].set("text", "unrelated-secret-value")
        report = launch.frame_observation(root)
        self.assertEqual(len(report["markers"]), 8)
        self.assertEqual(len(report["markers"][0]["content-desc"]), 1400)
        self.assertNotIn("unrelated-secret-value", json.dumps(report))
        self.assertEqual(report["packages"], [PACKAGE])

    def test_original_command_exception_is_preserved_without_extra_adb_calls(self):
        error = RuntimeError("synthetic disconnected")
        command = Mock(side_effect=error)
        read_tree, wait = Mock(), Mock()
        with contextlib.redirect_stdout(io.StringIO()), self.assertRaises(RuntimeError) as raised:
            launch.launch_profile(command, read_tree, wait)
        self.assertIs(raised.exception, error)
        self.assertEqual(command.call_count, 1)
        read_tree.assert_not_called()
        wait.assert_not_called()


if __name__ == "__main__":
    unittest.main()
