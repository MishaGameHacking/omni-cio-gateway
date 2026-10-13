"""Bounded gestures in an explicitly chosen Analyst list; never another app."""
from __future__ import annotations

from collections.abc import Callable
import re
import xml.etree.ElementTree as ET

PACKAGE = "ru.omnicio.app.debug"
SCROLL_AXES = {"profile-content": "vertical", "education-content": "vertical", "profile-tabs": "horizontal"}
LIST_IDS = frozenset(SCROLL_AXES)


def _bounds(node: ET.Element) -> tuple[int, int, int, int] | None:
    match = re.fullmatch(r"\[(\d{1,6}),(\d{1,6})\]\[(\d{1,6}),(\d{1,6})\]", node.get("bounds", ""))
    if match is None:
        return None
    left, top, right, bottom = map(int, match.groups())
    return (left, top, right, bottom) if right > left and bottom > top else None


def visible_label(tree: ET.Element, text: str) -> ET.Element | None:
    for node in tree.iter("node"):
        if node.get("package") != PACKAGE or node.get("visible-to-user") == "false":
            continue
        labels = node.get("text", "").splitlines() + node.get("content-desc", "").splitlines()
        if text in [label.strip() for label in labels] and _bounds(node) is not None:
            return node
    return None


def _scroll_area(tree: ET.Element, resource_id: str):
    names = {resource_id, f"{PACKAGE}:id/{resource_id}"}
    candidates = [node for node in tree.iter("node")
                  if node.get("package") == PACKAGE and node.get("resource-id") in names
                  and node.get("scrollable") == "true" and node.get("visible-to-user") != "false"]
    # Ambiguous simultaneous lists must not pick an arbitrary scroll target.
    return _bounds(candidates[0]) if len(candidates) == 1 else None


def _gesture(bounds, axis: str, direction: str):
    left, top, right, bottom = bounds
    if axis == "horizontal":
        if right - left < 8 or bottom - top < 2:
            return None
        inset = max(1, (right - left) // 5)
        middle = (top + bottom) // 2
        start, end = (right - inset, middle), (left + inset, middle)
    else:
        if bottom - top < 8 or right - left < 2:
            return None
        inset = max(1, (bottom - top) // 5)
        middle = (left + right) // 2
        start, end = (middle, bottom - inset), (middle, top + inset)
    return (*start, *end) if direction == "end" else (*end, *start)


def reveal_in_list(read_tree: Callable, swipe: Callable, text: str,
                   *, resource_id: str, max_swipes: int = 10,
                   direction: str = "end") -> ET.Element | None:
    """Return the visible exact label or fail after a bounded number of gestures.

    None means this particular list is not visible; no other list or system
    window is scrolled. Header/dialog labels may be found without any gesture.
    """
    if resource_id not in LIST_IDS:
        raise ValueError("unknown_scroll_list")
    if direction not in {"start", "end"}:
        raise ValueError("unknown_scroll_direction")
    if type(max_swipes) is not int or not 0 <= max_swipes <= 20:
        raise ValueError("invalid_scroll_limit")
    for attempt in range(max_swipes + 1):
        tree = read_tree()
        target = visible_label(tree, text)
        if target is not None:
            return target
        bounds = _scroll_area(tree, resource_id)
        if bounds is None:
            return None
        gesture = _gesture(bounds, SCROLL_AXES[resource_id], direction)
        if gesture is None:
            return None
        if attempt == max_swipes:
            raise AssertionError("List target not reachable: " + text)
        swipe(*gesture)
    raise AssertionError("List scroll did not finish")


def reveal_in_profile(read_tree: Callable, swipe: Callable, text: str,
                      *, max_swipes: int = 10) -> ET.Element | None:
    return reveal_in_list(read_tree, swipe, text, resource_id="profile-content", max_swipes=max_swipes)
