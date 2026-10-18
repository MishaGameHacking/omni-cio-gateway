"""Fixture-only Back touch requests over the existing authenticated frame session."""
from __future__ import annotations

import struct
import time

from persistent_ui import FrameReader, read_exact

BACK_REQUEST_FLAG = 0x40000000
BACK_OPERATIONS = {"hold": 1, "cancel": 2, "commit": 3, "advance": 4}


def back_gesture(probe, operation: str) -> None:
    """A transport acknowledgement is not proof of app progress or navigation."""
    code = BACK_OPERATIONS.get(operation)
    if code is None:
        raise ValueError("Unknown Back gesture operation")
    reader = getattr(probe.read_tree, "__self__", None)
    if not isinstance(reader, FrameReader):
        raise ValueError("Back gesture needs the owned frame session")
    if reader.broken:
        raise ConnectionError("Failed UiAutomation stream cannot perform Back gestures")
    try:
        sequence = reader._next_sequence()
        request = BACK_REQUEST_FLAG | (code << 24) | sequence
        deadline = time.monotonic() + 12
        reader.connection.settimeout(12)
        reader.connection.sendall(struct.pack(">I", request))
        received, status, size = struct.unpack(
            ">III", read_exact(reader.connection, 12, deadline=deadline)
        )
        if received != sequence or status != 4 or size != 0:
            raise ValueError("Invalid Back gesture acknowledgement")
        if time.monotonic() >= deadline:
            raise TimeoutError("Back gesture acknowledgement exceeded deadline")
        print(f"UI_BACK_TOUCH=operation-{operation};sequence-{sequence}", flush=True)
    except Exception:
        reader.broken = True
        raise
