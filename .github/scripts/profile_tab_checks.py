"""Geometry and exact-container checks for the disposable Spectrum UI fixture."""
from __future__ import annotations

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
