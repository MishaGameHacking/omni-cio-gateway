"""Exercise the real acknowledgement probe on clipped, unmerged event frames.

Window changes and acknowledgements are simulated here. These regressions
validate event selection and bounded traversal, not actual device delivery.
"""
from pathlib import Path
import sys
import unittest
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import business_ui_probe as business
from profile_scroll import reveal_in_list, reveal_resource_in_list


PACKAGE = "ru.omnicio.app.debug"
AREA = "workspace-content"
SELECTED_STATE = "notification-state-synthetic-notification"
ACKNOWLEDGE = "Отметить прочитанным"


class NotificationViewportProbe:
    """The title and read state are sibling Text nodes, not a merged label."""

    def __init__(self, scale=1.0, *, changes_selected=True, qualified=False):
        self.scale = scale
        self.height = 453
        self.offset = 0
        self.window = 101
        self.selected_read = False
        self.changes_selected = changes_selected
        self.qualified = qualified
        self.status_visible = True
        self.status_package = PACKAGE
        self.status_id = SELECTED_STATE
        self.open_dialog = True
        self.close_dialog = True
        self.replace_window_after_reveal = False
        self.actions = []
        self.scrolls = []
        self.resources = []

    def tree(self):
        tree = ET.Element("hierarchy", {"active-window-id": str(self.window)})
        viewport = ET.SubElement(tree, "node", {
            "package": PACKAGE, "resource-id": AREA,
            "bounds": f"[0,0][320,{self.height}]", "scrollable": "true",
            "visible-to-user": "true",
        })
        selected = ET.SubElement(viewport, "node", {
            "package": PACKAGE, "clickable": "true", "bounds": "[0,0][320,330]",
        })
        self.add_label(selected, business.SYNTHETIC_LIMIT_CHANGE, 20)
        self.add_label(selected, "Тестовое событие", 110)
        self.add_label(selected, "Прочитано" if self.selected_read else "Устройство сообщило о показе", 260,
                       resource=self.status_id, package=self.status_package, visible=self.status_visible)
        other = ET.SubElement(viewport, "node", {
            "package": PACKAGE, "clickable": "true", "bounds": "[0,330][320,453]",
        })
        self.add_label(other, "Синтетический просмотренный обзор", 350)
        self.add_label(other, "Прочитано", 410, resource="notification-state-synthetic-read")
        return tree

    def add_label(self, parent, text, top, *, resource="", package=PACKAGE, visible=True):
        upper = max(0, top * self.scale - self.offset)
        lower = min(self.height, (top + 40) * self.scale - self.offset)
        if upper >= lower:
            return
        identifier = f"{PACKAGE}:id/{resource}" if resource and self.qualified else resource
        ET.SubElement(parent, "node", {
            "package": package, "text": text, "resource-id": identifier,
            "bounds": f"[16,{int(upper)}][304,{int(lower)}]",
            "visible-to-user": "true" if visible else "false",
        })

    def scroll(self, _x1, y1, _x2, y2):
        self.scrolls.append("end" if y1 > y2 else "start")
        self.offset = max(0, min(600 * self.scale - self.height, self.offset + y1 - y2))

    def reveal(self, text, area, direction="end"):
        return reveal_in_list(self.tree, self.scroll, text, resource_id=area, direction=direction)

    def reveal_resource(self, resource, area, direction="end"):
        node = reveal_resource_in_list(self.tree, self.scroll, resource, resource_id=area, direction=direction)
        self.resources.append(resource)
        if self.replace_window_after_reveal:
            self.window = 103
        return node

    def tap(self, text, area, direction="end"):
        if area != AREA:
            raise AssertionError("Acknowledgement escaped the workspace")
        self.actions.append(text)
        if text == business.SYNTHETIC_LIMIT_CHANGE and self.window == 101:
            self.reveal(text, area, direction=direction)
            if self.open_dialog:
                self.window = 102
        elif text == ACKNOWLEDGE and self.window == 102:
            self.selected_read = self.changes_selected
            if self.close_dialog:
                self.window = 101
                self.offset = 0
        else:
            raise AssertionError("Unexpected acknowledgement action")

    @staticmethod
    def wait_for(condition, message):
        for _ in range(3):
            value = condition()
            if value is not None and value is not False:
                return value
        raise AssertionError(message)


class NotificationReadProbeTests(unittest.TestCase):
    def case(self, probe):
        return business._BusinessCase(probe, None, "notifications", "ready", probe.scale)

    def test_selected_sibling_status_is_observed_at_both_font_scales(self):
        for scale in (1.0, 2.0):
            for qualified in (False, True):
                with self.subTest(scale=scale, qualified=qualified):
                    probe = NotificationViewportProbe(scale, qualified=qualified)
                    case = self.case(probe)
                    case.notifications()
                    self.assertEqual(probe.actions, [business.SYNTHETIC_LIMIT_CHANGE, ACKNOWLEDGE])
                    self.assertEqual(probe.resources, [SELECTED_STATE])
                    self.assertEqual(case.checks, ["read-ack-same-event"])
                    self.assertEqual(probe.window, 101)
                    if scale == 2.0:
                        self.assertIn("start", probe.scrolls)

    def test_another_already_read_event_cannot_acknowledge_the_selected_event(self):
        probe = NotificationViewportProbe(changes_selected=False)
        case = self.case(probe)
        with self.assertRaisesRegex(AssertionError, "The selected event did not change to read"):
            case.mark_notification_read()
        self.assertEqual(case.checks, [])
        self.assertEqual(probe.actions, [business.SYNTHETIC_LIMIT_CHANGE, ACKNOWLEDGE])

    def test_selected_read_text_with_the_wrong_event_id_is_rejected(self):
        probe = NotificationViewportProbe()
        probe.status_id = "notification-state-other-event"
        self.assert_unreachable_selected_status(probe)

    def test_hidden_selected_status_cannot_be_replaced_by_another_visible_read_event(self):
        probe = NotificationViewportProbe()
        probe.status_visible = False
        self.assert_unreachable_selected_status(probe)

    def test_same_tag_from_another_package_cannot_confirm_acknowledgement(self):
        probe = NotificationViewportProbe()
        probe.status_package = "another.app"
        self.assert_unreachable_selected_status(probe)

    def test_final_status_must_still_belong_to_the_original_window(self):
        probe = NotificationViewportProbe()
        probe.replace_window_after_reveal = True
        case = self.case(probe)
        with self.assertRaisesRegex(AssertionError, "The selected event did not change to read"):
            case.mark_notification_read()
        self.assertEqual(case.checks, [])

    def test_dialog_open_and_close_remain_required(self):
        for stage in ("open", "close"):
            with self.subTest(stage=stage):
                probe = NotificationViewportProbe()
                setattr(probe, stage + "_dialog", False)
                case = self.case(probe)
                expected = "did not become the active window" if stage == "open" else "did not close after acknowledgement"
                with self.assertRaisesRegex(AssertionError, expected):
                    case.mark_notification_read()
                self.assertEqual(case.checks, [])
                self.assertEqual(probe.resources, [])

    def assert_unreachable_selected_status(self, probe):
        case = self.case(probe)
        with self.assertRaisesRegex(AssertionError, "List target not reachable: " + SELECTED_STATE):
            case.mark_notification_read()
        self.assertEqual(case.checks, [])
        self.assertLessEqual(len(probe.scrolls), 10)
        self.assertEqual(probe.actions, [business.SYNTHETIC_LIMIT_CHANGE, ACKNOWLEDGE])


if __name__ == "__main__":
    unittest.main()
