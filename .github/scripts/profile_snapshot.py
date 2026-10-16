"""Fresh, bounded UI evidence; cleanup must never replace the primary failure."""
from __future__ import annotations

from uuid import uuid4
import xml.etree.ElementTree as ET

TREE_TIMEOUT_SECONDS = 45
MAX_TREE_BYTES = 2 * 1024 * 1024


def fresh_tree(command) -> ET.Element:
    # The AVD is disposable. Unique files are discarded with it; a failed dump
    # can never cause a previous screen's XML to be read as a current frame.
    target = f"/sdcard/analyst-ui-{uuid4().hex}.xml"
    output = command("shell", "uiautomator", "dump", target, timeout=TREE_TIMEOUT_SECONDS)
    if target not in output:
        raise RuntimeError("UiAutomator did not confirm the current tree file")
    xml = command("shell", "cat", target)
    if len(xml.encode("utf-8")) > MAX_TREE_BYTES:
        raise ValueError("Accessibility tree exceeds the evidence size limit")
    root = ET.fromstring(xml[xml.index("<?xml"):])
    if root.tag != "hierarchy" or next(root.iter("node"), None) is None:
        raise ValueError("Accessibility tree is empty or has an unexpected root")
    return root


def restore_device_settings(command, scale: str, night: str, original=None) -> None:
    failures = []
    for args in (
        ("shell", "settings", "put", "system", "font_scale", scale),
        ("shell", "cmd", "uimode", "night", night),
    ):
        try:
            command(*args)
        except Exception as error:
            failures.append(error)
            print("PROFILE_CLEANUP_FAILURE=" + type(error).__name__, flush=True)
    if not failures:
        return
    if original is not None:
        original.add_note("UI settings cleanup also failed: " + ", ".join(type(e).__name__ for e in failures))
    else:
        raise failures[0]
