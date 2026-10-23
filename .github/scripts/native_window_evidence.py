"""Observe a new app modal before scrolling its own native content."""
from native_input_evidence import active_window_id
from profile_scroll import PACKAGE, visible_label, visible_resource


def wait_for_new_app_window(probe, original_window, label, area="workspace-content"):
    def ready():
        tree = probe.tree()
        if active_window_id(tree) == original_window:
            return None
        names = {area, f"{PACKAGE}:id/{area}"}
        lists = [node for node in tree.iter("node")
                 if node.get("resource-id") in names and node.get("package") == PACKAGE
                 and node.get("visible-to-user") == "true"]
        if len(lists) != 1:
            return None
        content = lists[0]
        if content.get("enabled") != "true" or visible_resource(tree, area) is not content:
            return None
        return visible_label(content, label)

    # A fitting dialog need not be scrollable. Wait for its own window and
    # content before reveal can turn a previous window's frame into a scroll.
    return probe.wait_for(ready, "New app window did not become ready: " + label)
