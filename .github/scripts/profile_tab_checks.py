"""Geometry and exact-container checks for the disposable Spectrum UI fixture."""
from __future__ import annotations

import json
import time
import xml.etree.ElementTree as ET

from profile_scroll import PACKAGE, visible_label, visible_resource

TAB_IDS = {"Настройки": "profile-tab-0", "Аккаунт": "profile-tab-1", "О приложении": "profile-tab-2"}


def selected_tab(tree: ET.Element, resource_id: str) -> ET.Element | None:
    node = visible_resource(tree, resource_id)
    return node if node is not None and node.get("selected") == "true" else None


def content_tree(tree: ET.Element) -> ET.Element:
    """Never mistake a fixed tab for an identically named content action."""
    names = {"profile-content", f"{PACKAGE}:id/profile-content"}
    nodes = [node for node in tree.iter("node") if node.get("package") == PACKAGE and node.get("resource-id") in names]
    if len(nodes) != 1:
        raise AssertionError("Expected one Analyst profile content container")
    return nodes[0]


def content_label(tree: ET.Element, text: str) -> ET.Element | None:
    return visible_label(content_tree(tree), text)


def assert_horizontal_geometry(peer: tuple[int, int, int, int], target: tuple[int, int, int, int]) -> None:
    _, peer_top, _, peer_bottom = peer
    _, top, _, bottom = target
    peer_height, height = peer_bottom - peer_top, bottom - top
    if min(peer_height, height) <= 0:
        raise AssertionError("Profile tab is empty")
    if height > peer_height * 1.5:
        raise AssertionError("About tab wrapped vertically")
    tolerance = max(peer_height, height) / 2
    if abs((top + bottom - peer_top - peer_bottom) / 2) > tolerance:
        raise AssertionError("Profile tabs are not on the same row")


def tappable_tab(tree: ET.Element, resource_id: str) -> ET.Element | None:
    """Return the exact visible 48dp+ portion of a tab inside its clipped rail.

    Compose accessibility nodes retain their logical child bounds even where a
    horizontalScroll viewport clips an edge. Requiring the complete logical cell
    caused a false second scroll at the start boundary. We accept only a real
    48x48-or-larger intersection whose tap centre is inside the app rail, and
    return that clipped rectangle so the test never taps outside the viewport.
    """
    from profile_scroll import _bounds

    rail = visible_resource(tree, "profile-tabs")
    tab = visible_resource(tree, resource_id)
    if rail is None or tab is None:
        return None
    left, top, right, bottom = _bounds(rail)
    x1, y1, x2, y2 = _bounds(tab)
    if x2 - x1 < 48 or y2 - y1 < 48:
        return None
    visible_left = max(left, x1)
    visible_top = max(top, y1)
    visible_right = min(right, x2)
    visible_bottom = min(bottom, y2)
    if visible_right - visible_left < 48 or visible_bottom - visible_top < 48:
        return None
    tap_x = (visible_left + visible_right) // 2
    tap_y = (visible_top + visible_bottom) // 2
    if not (left <= tap_x < right and top <= tap_y < bottom):
        return None
    target = ET.Element(tab.tag, dict(tab.attrib))
    target.set(
        "bounds",
        f"[{visible_left},{visible_top}][{visible_right},{visible_bottom}]",
    )
    return target


def tab_diagnostic(tree: ET.Element, resource_id: str, attempt: int) -> str:
    """Only fixture geometry; never account labels, tokens, or other apps."""
    ids = {"profile-tabs", "profile-content", *TAB_IDS.values()}
    qualified = ids | {f"{PACKAGE}:id/{name}" for name in ids}
    nodes = [
        {key: node.get(key, "") for key in ("resource-id", "bounds", "selected", "scrollable", "clickable", "visible-to-user")}
        for node in tree.iter("node")
        if node.get("package") == PACKAGE and node.get("resource-id") in qualified
    ]
    return json.dumps({"target": resource_id, "attempt": attempt, "nodes": nodes[:12]}, ensure_ascii=True)


def reveal_tab(read_tree, swipe, resource_id: str, direction: str):
    """Scroll only the exact rail until a safe visible tab target is tappable."""
    from profile_scroll import _gesture, _scroll_area

    if resource_id not in TAB_IDS.values() or direction not in {"start", "end"}:
        raise ValueError("Unknown profile tab or direction")
    for attempt in range(9):
        tree = read_tree()
        target = tappable_tab(tree, resource_id)
        if target is not None:
            return target
        print("PROFILE_TAB_DIAGNOSTIC=" + tab_diagnostic(tree, resource_id, attempt), flush=True)
        bounds = _scroll_area(tree, "profile-tabs")
        gesture = _gesture(bounds, "horizontal", direction) if bounds is not None else None
        if attempt == 8:
            raise AssertionError("Complete profile tab not reachable: " + resource_id)
        if gesture is None:
            # UiAutomation can still expose the departing AlertDialog window.
            # Await the exact app rail; never tap behind a dialog or skip a test.
            time.sleep(0.2)
        else:
            swipe(*gesture)
    raise AssertionError("Tab scroll did not finish")



def settled_tab(read_tree, resource_id: str, max_frames: int = 20):
    """Wait for three equal fresh bounds before a coordinate tap after scrolling.

    Compose's accessibility scroll action returns before its animation settles.
    A visible intermediate rectangle is not a reliable coordinate target. This
    only stabilizes geometry: the caller still taps once and must confirm the
    exact selected tab. Unreachable/continuously moving targets remain failures.
    """
    if resource_id not in TAB_IDS.values() or not 3 <= max_frames <= 30:
        raise ValueError("Unknown tab or invalid frame limit")
    previous = None
    stable = 0
    for _ in range(max_frames):
        target = tappable_tab(read_tree(), resource_id)
        bounds = target.get("bounds") if target is not None else None
        stable = stable + 1 if bounds is not None and bounds == previous else 1 if bounds else 0
        if stable >= 3:
            return target
        previous = bounds
        time.sleep(0.1)
    raise AssertionError("Profile tab geometry did not settle: " + resource_id)
