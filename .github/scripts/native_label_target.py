"""Read native action geometry before one ordinary coordinate tap.

Accepting a semantic scroll is not evidence that its target has stopped moving.
The action still belongs to Android; this module only reads fresh UI frames.
"""
from __future__ import annotations

import json
import time
import xml.etree.ElementTree as ET

from profile_scroll import LIST_IDS, PACKAGE, _bounds, _visible_app_node


def _action_owner(node: ET.Element) -> bool:
    return (
        node.get("clickable") == "true"
        or node.get("editable") == "true"
        or node.get("class") == "android.widget.EditText"
    )


def _label_matches(node: ET.Element, text: str) -> bool:
    labels = node.get("text", "").splitlines() + node.get("content-desc", "").splitlines()
    return _visible_app_node(node) and text in (label.strip() for label in labels)


def _ancestry(node, parents):
    while node is not None and node.tag == "node":
        yield node
        node = parents.get(node)


def _owners(tree, text, parents):
    owners = {}
    for label in tree.iter("node"):
        if not _label_matches(label, text):
            continue
        for node in _ancestry(label, parents):
            # A foreign subtree must never borrow this app's action owner.
            if node.get("package") != PACKAGE or node.get("visible-to-user") == "false":
                break
            if _action_owner(node):
                owners.setdefault(node, []).append(label)
                break
    return owners


def _intersection(first, second):
    left, top = max(first[0], second[0]), max(first[1], second[1])
    right, bottom = min(first[2], second[2]), min(first[3], second[3])
    return (left, top, right, bottom) if right > left and bottom > top else None


def _display(tree):
    values = [tree.get(name, "") for name in ("display-width", "display-height", "active-window-id")]
    if not all(value.isdecimal() and len(value) <= 6 for value in values):
        return None
    width, height, window = map(int, values)
    return ((0, 0, width, height), window) if width > 0 and height > 0 else None


def _viewport(node):
    resource = node.get("resource-id", "").removeprefix(f"{PACKAGE}:id/")
    return node.get("scrollable") == "true" or resource in LIST_IDS


def _visible_geometry(owner, parents, display):
    raw = _bounds(owner)
    if raw is None:
        return None
    clipped = _intersection(raw, display)
    viewports = []
    for ancestor in _ancestry(parents.get(owner), parents):
        if not _visible_app_node(ancestor):
            return None
        if _viewport(ancestor):
            bounds = _bounds(ancestor)
            viewports.append((ancestor.get("resource-id", ""), bounds))
            clipped = _intersection(clipped, bounds) if clipped is not None else None
    if clipped is None:
        return None
    # This is a physical tap margin, not a claim about 48dp accessibility size.
    # The driver may already have clipped raw bounds to the display. Never
    # treat a remaining one-pixel sliver as a complete tiny native control.
    if any(clipped[axis + 2] - clipped[axis] < 48 for axis in (0, 1)):
        return None
    return raw, clipped, tuple(viewports)


def _center(bounds):
    return (bounds[0] + bounds[2]) // 2, (bounds[1] + bounds[3]) // 2


def _covered_by_child(owner, bounds):
    x, y = _center(bounds)
    for child in owner.iter("node"):
        if child is owner or not _visible_app_node(child) or not _action_owner(child):
            continue
        left, top, right, bottom = _bounds(child)
        if left <= x < right and top <= y < bottom:
            return True
    return False


def _tap_bounds(owner, labels, clipped):
    label_rectangles = [visible for label in labels
                        if (visible := _intersection(_bounds(label), clipped)) is not None]
    if not label_rectangles:
        return None
    if not _covered_by_child(owner, clipped):
        return clipped
    # A country card can contain independent position buttons. Its centre is
    # not a safe country action if it lands on one of those native children.
    return next((bounds for bounds in label_rectangles if not _covered_by_child(owner, bounds)), None)


def _identity(node, parents):
    path = []
    while node in parents:
        parent = parents[node]
        path.append(list(parent).index(node))
        node = parent
    return tuple(reversed(path))


def _candidate(tree, text, require_enabled):
    display = _display(tree)
    if display is None:
        return None
    parents = {child: parent for parent in tree.iter() for child in parent}
    owners = _owners(tree, text, parents)
    candidates = []
    for owner, labels in owners.items():
        if not _visible_app_node(owner):
            continue
        geometry = _visible_geometry(owner, parents, display[0])
        if geometry is None:
            continue
        raw, clipped, viewports = geometry
        bounds = _tap_bounds(owner, labels, clipped)
        if bounds is not None:
            candidates.append((owner, labels, raw, bounds, viewports))
    if len(candidates) > 1:
        raise AssertionError("Ambiguous native action label: " + text)
    if not candidates:
        return None
    owner, labels, raw, bounds, viewports = candidates[0]
    if require_enabled and any(node.get("enabled") != "true"
                               for label in labels for node in _ancestry(label, parents)):
        return None
    target = ET.Element(owner.tag, dict(owner.attrib))
    target.set("bounds", f"[{bounds[0]},{bounds[1]}][{bounds[2]},{bounds[3]}]")
    signature = (display[1], _identity(owner, parents), owner.get("resource-id", ""),
                 owner.get("class", ""), raw, bounds, viewports, display[0])
    return target, signature


def label_target(tree: ET.Element, text: str, *, require_enabled: bool = True) -> ET.Element | None:
    """Resolve a unique native action, clipping only its actual ancestors.

    Reveal uses geometry with require_enabled=False: an already visible but
    disabled control must be waited for, not scrolled past or bypassed.
    """
    candidate = _candidate(tree, text, require_enabled)
    return candidate[0] if candidate is not None else None


def settled_label(read_tree, text: str, max_frames: int = 120) -> ET.Element:
    """Wait for three identical fresh native targets; never perform an action."""
    if type(max_frames) is not int or not 3 <= max_frames <= 120:
        raise ValueError("Invalid native action frame limit")
    deadline = time.monotonic() + 12
    previous, stable = None, 0
    last_error = None
    for _ in range(max_frames):
        if time.monotonic() >= deadline:
            break
        try:
            candidate = _candidate(read_tree(), text, True)
        except (RuntimeError, ET.ParseError, ValueError) as error:
            candidate, last_error = None, error
        signature = candidate[1] if candidate is not None else None
        stable = stable + 1 if signature is not None and signature == previous else int(signature is not None)
        if stable >= 3:
            print("NATIVE_TAP_READY=" + json.dumps({
                "window": signature[0], "owner_path": signature[1],
                "resource": signature[2], "class": signature[3],
                "owner_bounds": signature[4], "tap_bounds": signature[5],
                "viewports": signature[6], "display": signature[7],
            }), flush=True)
            return candidate[0]
        previous = signature
        time.sleep(0.1)
    raise AssertionError("Native action geometry or enabled state did not settle: " + text) from last_error
