"""Bound failure output without losing the identities of earlier fatal crashes.

Diagnostics are read-only. They never authorize a retry or change a test result.
Only the already-owned disposable emulator may supply these log buffers.
"""
from __future__ import annotations

from collections import deque
import re

MAX_EXCERPT = 65536
EDGE_CHARS = 8192
CRASH_CHARS = 4096
_FATAL_START = re.compile(
    r": (?:\*\*\* \*\*\* \*\*\*|FATAL EXCEPTION:|Fatal signal |WATCHDOG KILLING SYSTEM PROCESS)"
)


def _crash_offsets(text: str) -> list[int]:
    first = []
    last: deque[int] = deque(maxlen=4)
    for match in _FATAL_START.finditer(text):
        # Keep the timestamp and PID before the marker as well as the cause.
        start = text.rfind("\n", max(0, match.start() - 160), match.start()) + 1
        if start == 0:
            start = max(0, match.start() - 160)
        if len(first) < 4:
            first.append(start)
        last.append(start)
    return sorted(set(first) | set(last))


def _merged_intervals(intervals: list[tuple[int, int]]) -> list[tuple[int, int]]:
    result: list[tuple[int, int]] = []
    for start, end in sorted(intervals):
        if result and start <= result[-1][1]:
            result[-1] = (result[-1][0], max(result[-1][1], end))
        else:
            result.append((start, end))
    return result


def bounded_runtime_excerpt(text: str) -> str:
    """Keep head, tail and the first/last fatal headers in chronological order."""
    if len(text) <= MAX_EXCERPT:
        return text
    intervals = [(0, EDGE_CHARS), (len(text) - EDGE_CHARS, len(text))]
    intervals.extend((start, min(start + CRASH_CHARS, len(text))) for start in _crash_offsets(text))
    parts = []
    previous_end = 0
    for start, end in _merged_intervals(intervals):
        if start > previous_end:
            parts.append(f"\n[diagnostic excerpt: {start - previous_end} characters omitted]\n")
        parts.append(text[start:end])
        previous_end = end
    return "".join(parts)
