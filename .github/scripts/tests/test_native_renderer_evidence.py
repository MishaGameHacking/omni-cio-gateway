"""Synthetic parser regressions; these do not claim an Android runtime pass."""
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from native_renderer_evidence import (
    MAX_DUMP_CHARACTERS, PACKAGE, parse_native_renderer, read_native_renderer,
)

UID, PID = "10207", "3014"


def dump(*, pid=PID, package=PACKAGE, rows="1,1000000000,1016000000,\n"):
    return (
        f"** Graphics info for pid {pid} [{package}] **\n"
        "Pipeline=Skia (Vulkan)\n"
        "---PROFILEDATA---\n"
        "Flags,IntendedVsync,FrameCompleted,\n" + rows +
        "---PROFILEDATA---\n"
    )


def observed(text):
    return parse_native_renderer(text, uid=UID, pid=PID)


def result(text, code=0):
    return subprocess.CompletedProcess([], code, text, "")


class NativeRendererEvidenceTests(unittest.TestCase):
    def test_completed_startup_frame_proves_window_not_gpu_performance(self):
        self.assertEqual(observed(dump()), {
            "source": "candidate-hwui-framestats",
            "evidence_scope": "android-window-rendering",
            "package": PACKAGE, "uid": 10207, "pid": 3014,
            "completed_frames": 1, "first_vsync_ns": 1000000000,
            "last_frame_completed_ns": 1016000000,
            "pipeline": "Skia (Vulkan)",
        })

    def test_missing_wrong_or_multiple_process_headers_cannot_pass(self):
        for text in ("", dump(pid="2999"), dump(package="other.app"),
                     dump() + dump(), dump() + dump(pid="2999"),
                     dump().split("\n", 1)[1]):
            with self.subTest(text=text), self.assertRaises(ValueError):
                observed(text)

    def test_absent_pending_and_malformed_frames_cannot_pass(self):
        for rows in ("", "0,0,0,\n", "0,2,1,\n", "0,1,9223372036854775807,\n",
                     "-1,1,2,\n", "0,nan,3,\n", "0,1,2,3,\n"):
            with self.subTest(rows=rows), self.assertRaises(ValueError):
                observed(dump(rows=rows))
        for text in (dump().replace("---PROFILEDATA---\n", ""),
                     dump().removesuffix("---PROFILEDATA---\n"),
                     dump().replace("Flags,IntendedVsync,FrameCompleted,",
                                    "Flags,IntendedVsync,FrameCompleted,Flags,")):
            with self.subTest(text=text), self.assertRaises(ValueError):
                observed(text)

    def test_profile_rows_deduplicate_and_ignore_uncompleted_ring_entries(self):
        row = observed(dump(rows="0,100,200,\n0,100,200,\n0,300,400,\n0,0,0,\n"))
        self.assertEqual(row["completed_frames"], 2)
        self.assertEqual(row["last_frame_completed_ns"], 400)
        self.assertEqual(observed(dump().replace("Pipeline=Skia (Vulkan)\n", ""))["pipeline"],
                         "not-reported")

    def test_unbounded_conflicting_or_impossible_evidence_fails_closed(self):
        for text in (dump() + "x" * MAX_DUMP_CHARACTERS,
                     dump() + "Pipeline=Skia (OpenGL)\n",
                     dump(rows="0,1,60000000002,\n")):
            with self.subTest(length=len(text)), self.assertRaises(ValueError):
                observed(text)

    def test_invalid_identity_cannot_reach_adb(self):
        for invalid in ("", "0", "3 4", "3\n4", "1;id", "-1", "2147483648", None):
            for key in ("uid", "pid"):
                args = {"uid": UID, "pid": PID, key: invalid}
                device = Mock()
                with self.subTest(key=key, value=invalid), self.assertRaises(ValueError):
                    read_native_renderer(device, **args)
                device.assert_not_called()

    def test_read_checks_same_live_process_before_and_after_bounded_dump(self):
        device = Mock(side_effect=[result(PID), result(dump()), result(PID)])
        evidence = read_native_renderer(device, uid=UID, pid=PID + "\n")
        self.assertEqual(evidence["pid"], int(PID))
        self.assertEqual(device.call_args_list[0].args, ("shell", "pidof", PACKAGE))
        self.assertEqual(device.call_args_list[1].args,
                         ("shell", "dumpsys", "gfxinfo", PACKAGE, "framestats"))
        self.assertEqual(device.call_args_list[1].kwargs, {"timeout": 20})
        self.assertEqual(device.call_args_list[2].args, ("shell", "pidof", PACKAGE))

    def test_failed_read_or_process_restart_cannot_pass(self):
        for responses in (
            [result("", 1)],
            [result("2999")],
            [result(PID), result("", 1)],
            [result(PID), result(dump()), result("2999")],
            [result(PID), result(dump()), result(PID, 1)],
        ):
            with self.subTest(count=len(responses)), self.assertRaises((ValueError, RuntimeError)):
                read_native_renderer(Mock(side_effect=responses), uid=UID, pid=PID)
