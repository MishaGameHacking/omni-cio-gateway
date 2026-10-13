"""Bounded scrolling inside the tagged Profile list, never system UI."""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from collections.abc import Callable


def _bounds(node: ET.Element) -> tuple[int, int, int, int] | None:
    match = re.fullmatch(r"\[(\d{1,6}),(\d{1,6})\]\[(\d{1,6}),(\d{1,6})\]", node.get("bounds", ""))
    if match is None:
        return None
    left, top, right, bottom = map(int, match.groups())
    if right <= left or bottom <= top:
        return None
    return left, top, right, bottom


def reveal_in_profile(read_tree: Callable, swipe: Callable, text: str,
                      *, max_swipes: int = 10) -> ET.Element | None:
    """Return a visible exact label; missing nodes never become test success.

    None means there is no tagged Profile list; the caller may use its ordinary
    dialog wait. A tagged list with an unreachable target is a hard failure.
    """
    if type(max_swipes) is not int or not 0 <= max_swipes <= 20:
        raise ValueError("invalid_scroll_limit")
    for attempt in range(max_swipes + 1):
        tree = read_tree()
        for node in tree.iter("node"):
            labels = node.get("text", "").splitlines() + node.get("content-desc", "").splitlines()
            if text in [label.strip() for label in labels] and _bounds(node) is not None:
                return node
        area = next((node for node in tree.iter("node")
                     if node.get("resource-id") in {"profile-content", "ru.omnicio.app.debug:id/profile-content"}
                     and node.get("scrollable") == "true"), None)
        bounds = _bounds(area) if area is not None else None
        if bounds is None:
            return None
        left, top, right, bottom = bounds
        if bottom - top < 8 or right - left < 2:
            return None
        if attempt == max_swipes:
            raise AssertionError("Profile target not reachable: " + text)
        inset = max(1, (bottom - top) // 5)
        middle = (left + right) // 2
        swipe(middle, bottom - inset, middle, top + inset)
    raise AssertionError("Profile scroll did not finish")
