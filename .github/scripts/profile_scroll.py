"""Bounded gestures in an explicitly chosen Analyst list; never another app."""
from __future__ import annotations

from collections.abc import Callable
import re
import time
import json
import math
import xml.etree.ElementTree as ET

PACKAGE = "ru.omnicio.app.debug"
SCROLL_AXES = {
    "profile-content": "vertical",
    "education-content": "vertical",
    "portfolio-content": "vertical",
    "workspace-content": "vertical",
    "profile-tabs": "horizontal",
    "dossier-tabs": "horizontal",
    "quotes-intervals": "horizontal",
}
LIST_IDS = frozenset(SCROLL_AXES)


def _bounds(node: ET.Element) -> tuple[int, int, int, int] | None:
    match = re.fullmatch(r"\[(\d{1,6}),(\d{1,6})\]\[(\d{1,6}),(\d{1,6})\]", node.get("bounds", ""))
    if match is None:
        return None
    left, top, right, bottom = map(int, match.groups())
    return (left, top, right, bottom) if right > left and bottom > top else None


def _visible_app_node(node: ET.Element) -> bool:
    return (
        node.get("package") == PACKAGE
        and node.get("visible-to-user") != "false"
        and _bounds(node) is not None
    )


def visible_label(tree: ET.Element, text: str) -> ET.Element | None:
    for node in tree.iter("node"):
        if not _visible_app_node(node):
            continue
        labels = node.get("text", "").splitlines() + node.get("content-desc", "").splitlines()
        if text in [label.strip() for label in labels]:
            return node
    return None


def visible_resource(tree: ET.Element, resource_id: str) -> ET.Element | None:
    """Find an exact Compose testTag exposed to UiAutomator as a resource id.

    Compose commonly exposes the tag itself (for example ``lesson-toggle-x``),
    while older dumps can contain the package-qualified Android spelling. Both
    exact forms are accepted; substrings and nodes from another package are not.
    """
    names = {resource_id, f"{PACKAGE}:id/{resource_id}"}
    for node in tree.iter("node"):
        if _visible_app_node(node) and node.get("resource-id") in names:
            return node
    return None


def tappable_resource(tree: ET.Element, target_id: str, list_id: str) -> ET.Element | None:
    """Clip a target to its list viewport before using its tap coordinates.

    Compose can report a child's logical bounds while most of the button is
    still below the clipped list. Canvas pointer-input targets need not expose
    clickable=true, so the caller must assert the resulting interaction state.
    """
    target = visible_resource(tree, target_id)
    viewport = _list_area(tree, list_id, require_scrollable=False)
    if target is None or viewport is None:
        return None
    if target.get("enabled") == "false":
        return None
    left, top, right, bottom = _bounds(target)
    x1, y1, x2, y2 = viewport
    left, top = max(left, x1), max(top, y1)
    right, bottom = min(right, x2), min(bottom, y2)
    if right - left < 48 or bottom - top < 48:
        return None
    clipped = ET.Element(target.tag, dict(target.attrib))
    clipped.set("bounds", f"[{left},{top}][{right},{bottom}]")
    return clipped


def fully_visible_resource(tree: ET.Element, target_id: str, list_id: str,
                           minimum_size: tuple[float, float] = (0, 0)) -> ET.Element | None:
    """Require the whole evidence target inside its current list viewport.

    A Compose node can retain logical bounds and visible-to-user=true after
    scrolling behind a sticky header. Such bounds cannot identify captured pixels.
    """
    target = visible_resource(tree, target_id)
    viewport = _scroll_area(tree, list_id)
    if target is None or viewport is None:
        return None
    left, top, right, bottom = _bounds(target)
    x1, y1, x2, y2 = viewport
    # UiAutomator may return an ALREADY clipped rectangle. Containment alone
    # cannot prove the whole target is visible; use the fixture's declared size.
    if right - left < minimum_size[0] or bottom - top < minimum_size[1]:
        return None
    return target if x1 <= left < right <= x2 and y1 <= top < bottom <= y2 else None


def settled_resource(read_tree, target_id: str, list_id: str, max_frames: int = 20):
    """Require three equal fresh rectangles after an asynchronous scroll."""
    if list_id not in LIST_IDS or not 3 <= max_frames <= 30:
        raise ValueError("Unknown list or invalid frame limit")
    previous, stable = None, 0
    for _ in range(max_frames):
        target = tappable_resource(read_tree(), target_id, list_id)
        bounds = target.get("bounds") if target is not None else None
        stable = stable + 1 if bounds is not None and bounds == previous else int(bounds is not None)
        if stable >= 3:
            return target
        previous = bounds
        time.sleep(0.1)
    raise AssertionError("List button geometry did not settle: " + target_id)


def _scroll_area(tree: ET.Element, resource_id: str):
    return _list_area(tree, resource_id, require_scrollable=True)


def _list_area(tree: ET.Element, resource_id: str, *, require_scrollable: bool):
    names = {resource_id, f"{PACKAGE}:id/{resource_id}"}
    candidates = [
        node
        for node in tree.iter("node")
        if node.get("package") == PACKAGE
        and node.get("resource-id") in names
        and (not require_scrollable or node.get("scrollable") == "true")
        and node.get("visible-to-user") != "false"
    ]
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


def _reveal_target(
    read_tree: Callable,
    swipe: Callable,
    find_target: Callable[[ET.Element], ET.Element | None],
    target_description: str,
    *,
    resource_id: str,
    max_swipes: int,
    direction: str,
    layout_timeout: float,
) -> ET.Element | None:
    _validate_request(resource_id, direction, max_swipes, layout_timeout)
    deadline = time.monotonic() + layout_timeout
    for attempt in range(max_swipes + 1):
        tree, target, bounds = _ready_scroll_frame(
            read_tree, find_target, resource_id, attempt, deadline, layout_timeout > 0
        )
        if target is not None:
            return target
        if bounds is None:
            return None
        gesture = _gesture(bounds, SCROLL_AXES[resource_id], direction)
        if gesture is None:
            return None
        expired = layout_timeout > 0 and time.monotonic() >= deadline
        if attempt == max_swipes or expired:
            _layout_diagnostic(tree, resource_id, attempt)
            raise AssertionError("List target not reachable: " + target_description)
        swipe(*gesture)
        if layout_timeout > 0:
            time.sleep(min(0.2, max(0, deadline - time.monotonic())))
    raise AssertionError("List scroll did not finish")


def _validate_request(resource_id, direction, max_swipes, layout_timeout):
    if resource_id not in LIST_IDS:
        raise ValueError("unknown_scroll_list")
    if direction not in {"start", "end"}:
        raise ValueError("unknown_scroll_direction")
    if type(max_swipes) is not int or not 0 <= max_swipes <= 20:
        raise ValueError("invalid_scroll_limit")
    if type(layout_timeout) not in (int, float) or not math.isfinite(layout_timeout) or not 0 <= layout_timeout <= 12:
        raise ValueError("invalid_layout_timeout")


def _ready_scroll_frame(read_tree, find_target, resource_id, swipes, deadline, wait):
    pending = 0
    while True:
        tree = read_tree()
        target = find_target(tree)
        bounds = _scroll_area(tree, resource_id)
        if target is not None or bounds is not None or not wait:
            return tree, target, bounds
        # A valid active root can precede its Compose scroll semantics. Do not
        # switch to a passive label-only wait: an offscreen target still needs
        # scrolling when this exact list becomes available again.
        expired = time.monotonic() >= deadline
        if pending == 0 or expired:
            _layout_diagnostic(tree, resource_id, swipes)
        if expired:
            raise AssertionError("Scroll layout not ready: " + resource_id)
        pending += 1
        time.sleep(min(0.2, max(0, deadline - time.monotonic())))


def _layout_diagnostic(tree: ET.Element, resource_id: str, swipes: int) -> None:
    # Test tags and geometry only: no ordinary labels, balances or tokens.
    nodes = [
        {key: node.get(key, "") for key in (
            "package", "resource-id", "bounds", "scrollable", "visible-to-user"
        )}
        for node in tree.iter("node")
        if node.get("resource-id") in LIST_IDS
        or node.get("resource-id") in {f"{PACKAGE}:id/{name}" for name in LIST_IDS}
    ][:20]
    print("SCROLL_LAYOUT_DIAGNOSTIC=" + json.dumps({
        "area": resource_id, "swipes": swipes, "lists": nodes,
    }), flush=True)


def reveal_in_list(
    read_tree: Callable,
    swipe: Callable,
    text: str,
    *,
    resource_id: str,
    max_swipes: int = 10,
    direction: str = "end",
    layout_timeout: float = 0,
) -> ET.Element | None:
    """Return the visible exact label or fail after a bounded number of gestures.

    None means this particular list is not visible; no other list or system
    window is scrolled. A positive layout_timeout waits for this exact list
    within one overall deadline without resetting the swipe budget.
    Header/dialog labels may be found without any gesture.
    """
    return _reveal_target(
        read_tree,
        swipe,
        lambda tree: visible_label(tree, text),
        text,
        resource_id=resource_id,
        max_swipes=max_swipes,
        direction=direction,
        layout_timeout=layout_timeout,
    )


def reveal_resource_in_list(
    read_tree: Callable,
    swipe: Callable,
    target_resource_id: str,
    *,
    resource_id: str,
    max_swipes: int = 10,
    direction: str = "end",
    layout_timeout: float = 0,
    for_tap: bool = False,
    for_capture: bool = False,
    minimum_size: tuple[float, float] = (0, 0),
) -> ET.Element | None:
    """Reveal an exact Compose testTag without depending on merged label text."""
    def find(tree):
        if for_capture:
            return fully_visible_resource(tree, target_resource_id, resource_id, minimum_size)
        if for_tap:
            return tappable_resource(tree, target_resource_id, resource_id)
        return visible_resource(tree, target_resource_id)
    return _reveal_target(
        read_tree,
        swipe,
        find,
        target_resource_id,
        resource_id=resource_id,
        max_swipes=max_swipes,
        direction=direction,
        layout_timeout=layout_timeout,
    )


def reveal_in_profile(
    read_tree: Callable,
    swipe: Callable,
    text: str,
    *,
    max_swipes: int = 10,
) -> ET.Element | None:
    return reveal_in_list(
        read_tree,
        swipe,
        text,
        resource_id="profile-content",
        max_swipes=max_swipes,
    )

