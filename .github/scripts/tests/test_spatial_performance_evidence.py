"""Offline parser checks; no synthetic sample is called device evidence."""
import importlib.util
from pathlib import Path
import unittest

SPEC = importlib.util.spec_from_file_location("spatial_performance_evidence", Path(__file__).resolve().parents[1] / "spatial_performance_evidence.py")
performance = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(performance)


class SpatialPerformanceEvidenceTests(unittest.TestCase):
    def test_pss_requires_one_real_positive_observation(self):
        self.assertEqual(performance.memory_pss_kb("TOTAL PSS: 182345    TOTAL RSS: 400000"), 182345)
        self.assertEqual(performance.memory_pss_kb("   TOTAL   182345  3500  19000  22\n"), 182345)
        for text in ("No process found", "TOTAL PSS: 0", "TOTAL PSS: 2\nTOTAL PSS: 3"):
            with self.subTest(text=text), self.assertRaises(AssertionError):
                performance.memory_pss_kb(text)

    def test_actual_framestats_columns_trailing_comma_and_nonrendered_flags(self):
        lines = ["---PROFILEDATA---", "Flags,IntendedVsync,FrameCompleted,FrameDeadline,"]
        for index in range(1, 21):
            start = index * 1_000_000_000
            lines.append(f"0,{start},{start+index*1_000_000},{start+16_000_000},")
        lines.append("1,1000,90000000000,2000,")
        actual = performance.frame_timings("\n".join(lines))
        self.assertEqual(actual["samples"], 20)
        self.assertEqual(actual["p50_ms"], 10)
        self.assertEqual(actual["p95_ms"], 19)
        self.assertEqual(actual["max_ms"], 20)
        self.assertEqual(actual["deadline_misses"], 4)
        self.assertEqual(actual["filament_gpu_time"], "not-measured")

    def test_empty_short_and_sentinel_frame_dumps_cannot_pass(self):
        for text in ("No process found", "Flags,IntendedVsync,FrameCompleted\n0,1000,2000",
                     "Flags,IntendedVsync,FrameCompleted\n" + "0,1000,9223372036854775807\n" * 30):
            with self.subTest(text=text[:50]), self.assertRaises(AssertionError):
                performance.frame_timings(text)


if __name__ == "__main__":
    unittest.main()
