"""Regressions for the lost root cause behind a cascaded system-server failure."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from runtime_crash_evidence import MAX_EXCERPT, bounded_runtime_excerpt


class RuntimeCrashEvidenceTests(unittest.TestCase):
    def test_small_output_is_byte_for_byte_unchanged(self):
        text = "10-18 22:38:10 E AndroidRuntime: FATAL EXCEPTION: main\nProcess: system_server\n"
        self.assertEqual(bounded_runtime_excerpt(text), text)
        self.assertEqual(bounded_runtime_excerpt(""), "")

    def test_native_identity_in_the_middle_survives_later_noise(self):
        root = ("10-18 22:38:00 580 580 F DEBUG   : *** *** *** ***\n"
                "10-18 22:38:00 580 580 F DEBUG   : Cmdline: system_server\n"
                "10-18 22:38:00 580 580 F DEBUG   : Abort message: original cause\n")
        text = "START\n" + "noise\n" * 20000 + root + "later noise\n" * 20000 + "END\n"
        result = bounded_runtime_excerpt(text)
        self.assertIn(root, result)
        self.assertTrue(result.startswith("START\n"))
        self.assertTrue(result.endswith("END\n"))
        self.assertIn("characters omitted", result)
        self.assertLessEqual(len(result), MAX_EXCERPT)

    def test_java_first_failure_is_not_replaced_by_dead_system_tail(self):
        root = ("10-18 22:38:00 E AndroidRuntime: FATAL EXCEPTION: main\n"
                "Process: system_server\njava.lang.IllegalStateException: original cause\n")
        text = "prefix\n" * 15000 + root + "stack\n" * 15000 + "DeadSystemException\n"
        result = bounded_runtime_excerpt(text)
        self.assertIn(root, result)
        self.assertIn("DeadSystemException", result)
        self.assertLess(result.index("original cause"), result.index("DeadSystemException"))

    def test_no_crash_output_keeps_both_edges(self):
        text = "FIRST" + "X" * 100000 + "LAST"
        result = bounded_runtime_excerpt(text)
        self.assertTrue(result.startswith("FIRST"))
        self.assertTrue(result.endswith("LAST"))
        self.assertLessEqual(len(result), MAX_EXCERPT)

    def test_many_failures_are_bounded_but_keep_earliest_and_latest(self):
        text = "prefix\n" * 14000
        for index in range(20):
            text += f"10-18 E AndroidRuntime: FATAL EXCEPTION: thread-{index}\n" + "stack\n" * 2000
        text += "suffix\n" * 14000
        result = bounded_runtime_excerpt(text)
        self.assertIn("thread-0\n", result)
        self.assertIn("thread-19\n", result)
        self.assertLessEqual(len(result), MAX_EXCERPT)

    def test_overlapping_markers_do_not_duplicate_evidence(self):
        crash = ("10-18 F libc: Fatal signal 6\n"
                 "10-18 F DEBUG: *** *** *** ***\nCmdline: unique-crash\n")
        text = "prefix\n" * 15000 + crash + "suffix\n" * 15000
        result = bounded_runtime_excerpt(text)
        self.assertEqual(result.count("unique-crash"), 1)

    def test_no_newline_input_is_still_bounded(self):
        text = ": FATAL EXCEPTION: main " * 20000
        result = bounded_runtime_excerpt(text)
        self.assertLessEqual(len(result), MAX_EXCERPT)


if __name__ == "__main__":
    unittest.main()
