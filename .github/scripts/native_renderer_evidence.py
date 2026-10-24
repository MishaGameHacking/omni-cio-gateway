"""Evidence from the launched candidate's actual Android HWUI window.

This proves completed window frames, not device GPU speed or battery endurance.
The separate UI/performance gates still require their full interaction samples.
"""
from __future__ import annotations

import re

PACKAGE = "ru.omnicio.app.debug"
MAX_DUMP_CHARACTERS = 2 * 1024 * 1024
_HEADER = re.compile(r"^\s*\*\* Graphics info for pid ([0-9]+) \[([^\]\r\n]+)\] \*\*\s*$")
_REQUIRED = {"Flags", "IntendedVsync", "FrameCompleted"}


def _identity(value: str, name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"Invalid current {name}")
    value = value.strip()
    if not re.fullmatch(r"[1-9][0-9]{0,9}", value) or int(value) >= 2**31:
        raise ValueError(f"Invalid current {name}")
    return value


def parse_native_renderer(output: str, *, uid: str, pid: str) -> dict[str, object]:
    current_uid = _identity(uid, "UID")
    current_pid = _identity(pid, "PID")
    if not isinstance(output, str) or len(output) > MAX_DUMP_CHARACTERS:
        raise ValueError("HWUI evidence must be bounded")
    identity_seen = False
    in_profile = False
    columns = None
    frames: set[tuple[int, int]] = set()
    pipelines: set[str] = set()
    for line in output.splitlines():
        header = _HEADER.fullmatch(line)
        if header:
            if header.groups() != (current_pid, PACKAGE) or identity_seen:
                raise ValueError("HWUI dump includes another or ambiguous process")
            identity_seen = True
            continue
        if not identity_seen:
            continue
        if line.strip().startswith("Pipeline="):
            pipelines.add(line.strip().removeprefix("Pipeline="))
        if line.strip() == "---PROFILEDATA---":
            in_profile = not in_profile
            columns = None
            continue
        if not in_profile:
            continue
        values = [value.strip() for value in line.strip().rstrip(",").split(",")]
        if _REQUIRED <= set(values):
            if len(set(values)) != len(values):
                raise ValueError("Ambiguous HWUI frame columns")
            columns = values
            continue
        if columns is None or len(values) != len(columns):
            continue
        if not all(re.fullmatch(r"-?[0-9]+", value) for value in values):
            continue
        row = dict(zip(columns, map(int, values)))
        start, finish = row["IntendedVsync"], row["FrameCompleted"]
        # Startup frames can carry nonzero flags. They still prove rendering;
        # they do not enter the stricter scroll/performance distribution.
        if 0 <= row["Flags"] < 2**31 and 0 < start < finish < 2**63 - 1:
            if finish - start > 60_000_000_000:
                raise ValueError("Invalid completed HWUI frame duration")
            frames.add((start, finish))
    if not identity_seen or in_profile or not frames:
        raise ValueError("No complete current-process HWUI frame evidence")
    if len(pipelines) > 1 or any(not value or len(value) > 128 for value in pipelines):
        raise ValueError("Conflicting HWUI pipeline evidence")
    return {
        "source": "candidate-hwui-framestats",
        "evidence_scope": "android-window-rendering",
        "package": PACKAGE,
        "uid": int(current_uid),
        "pid": int(current_pid),
        "completed_frames": len(frames),
        "first_vsync_ns": min(start for start, _ in frames),
        "last_frame_completed_ns": max(finish for _, finish in frames),
        "pipeline": next(iter(pipelines), "not-reported"),
    }


def read_native_renderer(device, *, uid: str, pid: str) -> dict[str, object]:
    current_uid = _identity(uid, "UID")
    current_pid = _identity(pid, "PID")

    def require_current_process() -> None:
        alive = device("shell", "pidof", PACKAGE, timeout=10)
        if alive.returncode or alive.stdout.strip() != current_pid:
            raise ValueError("Candidate process changed while reading HWUI evidence")

    require_current_process()
    measured = device("shell", "dumpsys", "gfxinfo", PACKAGE, "framestats", timeout=20)
    if measured.returncode:
        raise RuntimeError("Could not read candidate HWUI frame evidence")
    observed = parse_native_renderer(measured.stdout, uid=current_uid, pid=current_pid)
    require_current_process()
    return observed
