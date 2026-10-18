"""Parse actual public Android dumps; absence is not a performance pass.

HWUI framestats describe the Android window. Filament's separate CPU submission
metrics and native frame count are retained independently; neither proves GPU
execution time, physical-device frame pacing or battery endurance.
"""
from __future__ import annotations

import math
import re


def memory_pss_kb(output: str) -> int:
    # Current Android prints TOTAL PSS in App Summary. Keep the older table row
    # fallback for the officially supported dumpsys output on API35.
    values = re.findall(r"\bTOTAL PSS:\s*(\d+)\b", output)
    if not values:
        values = re.findall(r"^\s*TOTAL\s+(\d+)\s+", output, flags=re.MULTILINE)
    if len(values) != 1 or int(values[0]) <= 0:
        raise AssertionError("No unambiguous actual process PSS was measured")
    return int(values[0])


def frame_timings(output: str):
    columns = None
    samples = []
    misses = 0
    for line in output.splitlines():
        values = [value.strip() for value in line.strip().rstrip(",").split(",")]
        if {"Flags", "IntendedVsync", "FrameCompleted"} <= set(values):
            columns = values
            continue
        row = _timing_row(columns, values)
        if row is None or row["Flags"] != 0:
            continue
        timing = _frame_duration(row)
        if timing is None:
            continue
        start, finish, duration = timing
        samples.append(duration)
        deadline = row.get("FrameDeadline", 0)
        if deadline > start and finish > deadline:
            misses += 1
    if len(samples) < 20:
        raise AssertionError("Fewer than 20 actual valid HWUI frames were measured")
    samples.sort()
    return {"source": "dumpsys-gfxinfo-framestats", "window": "debug-fixture-HWUI",
            "samples": len(samples), "p50_ms": samples[math.ceil(len(samples)*.5)-1],
            "p95_ms": samples[math.ceil(len(samples)*.95)-1], "max_ms": samples[-1],
            "deadline_misses": misses, "filament_gpu_time": "not-measured"}


def _timing_row(columns, values):
    if columns is None or len(values) != len(columns) or not values:
        return None
    if not all(re.fullmatch(r"-?\d+", value) for value in values):
        return None
    return dict(zip(columns, map(int, values)))


def _frame_duration(row):
    start, finish = row["IntendedVsync"], row["FrameCompleted"]
    if not 0 < start < finish < 2**63 - 1:
        return None
    duration = (finish - start) / 1_000_000
    if not math.isfinite(duration) or duration > 60_000:
        raise AssertionError("Invalid measured frame timing")
    return start, finish, duration
