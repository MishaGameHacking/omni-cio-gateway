"""Catalogue traversal across simulated fresh native windows and clipped lists.

The real case and bounded reveal helpers run here. Window/layout transitions and
text entry are simulated; these tests do not claim Android runtime coverage.
"""
from copy import deepcopy
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import business_ui_probe as business
import catalogue_ui_probe as catalogue
from profile_scroll import PACKAGE, reveal_in_list, reveal_resource_in_list

AREA = "workspace-content"
ASSET = "СИНТЕТИЧЕСКИЙ НОВЫЙ АКТИВ"
SAVED = "Расчёт сохранён: synthetic-purchase-check"
RESERVE = "Покупка затрагивает защищённый резерв."


class CatalogueViewportProbe:
    def __init__(self, scale=1.0, scenario="ready", *, qualified=False, defect=None,
                 delayed_layout=False, catalogue_resize=False):
        self.scale, self.scenario = scale, scenario
        self.qualified, self.defect = qualified, defect
        self.delayed_layout = delayed_layout
        self.catalogue_resize = catalogue_resize
        self.height, self.offset, self.window = 453, 0, 144
        self.page, self.pending, self.dialog_reads = "catalogue", None, 0
        self.editor, self.values = None, {"catalogue-query": "", "purchase-price": ""}
        self.result = False
        self.actions, self.scrolls, self.check_requests, self.readiness = [], [], [], []
        self.wrong_window_scrolls = 0

    @property
    def extent(self):
        return 800 if self.page == "catalogue" else int((660 if self.result else 450) * self.scale)

    def open_dialog(self):
        self.page, self.offset, self.pending = "dialog", 0, None
        self.window = 144 if self.defect == "same-window" else 145

    def tree(self):
        if self.pending is not None:
            if self.pending > 0:
                self.pending -= 1
            else:
                self.open_dialog()
        tree = ET.Element("hierarchy", {"active-window-id": str(self.window),
                                       "display-width": "320", "display-height": "640"})
        if self.page == "dialog":
            self.dialog_reads += 1
            if self.defect == "invalid-window":
                tree.set("active-window-id", "")
            if self.delayed_layout and self.dialog_reads <= 2:
                self.readiness.append("new-window-without-list")
                return tree
        identifier = f"{PACKAGE}:id/{AREA}" if self.qualified else AREA
        viewport = ET.SubElement(tree, "node", {
            "package": PACKAGE, "resource-id": identifier,
            "bounds": f"[0,163][320,{163 + self.height}]",
            "scrollable": str(self.extent > self.height).lower(),
            "visible-to-user": "true", "enabled": "true",
        })
        if self.page == "catalogue":
            self.row(viewport, 20, 50, resource="catalogue-query")
            if self.defect != "missing-search":
                self.row(viewport, 100, 50, text="Найти", button=True,
                         enabled=self.defect != "disabled-search")
            self.row(viewport, 300, 70, text=ASSET)
            self.row(viewport, 450, 60, text=catalogue.PURCHASE_DIALOG, button=True)
            return tree
        self.dialog_rows(viewport)
        self.alter_dialog(tree, viewport)
        return tree

    def dialog_rows(self, viewport):
        title_ready = not self.delayed_layout or self.dialog_reads > 4
        self.readiness.append("content-ready" if title_ready else "new-list-without-title")
        if title_ready and self.defect not in {"missing-title", "outside-title"}:
            self.row(viewport, 0, 32, text=catalogue.PURCHASE_DIALOG)
        self.row(viewport, 42, 40, text=ASSET)
        self.row(viewport, 100, 45, text="СИНТЕТИЧЕСКИЙ счёт")
        self.row(viewport, 170, 48, resource="purchase-lots")
        self.row(viewport, 240, 48, resource="purchase-price")
        if self.defect != "missing-action":
            self.row(viewport, 300, 48, text=catalogue.PURCHASE_ACTION, button=True,
                     enabled=bool(self.values["purchase-price"]) or self.defect == "enabled-empty-price")
        if self.result:
            self.row(viewport, 360, 60, text=self.verdict())
            if self.scenario == "partial":
                self.row(viewport, 425, 45, text=RESERVE)
            self.row(viewport, 480, 45, text=SAVED)
            self.row(viewport, 600, 48, text="Закрыть", button=True)
        else:
            self.row(viewport, 355, 40, text="Проверка не отправляет заявку.")
            self.row(viewport, 400, 48, text="Закрыть", button=True)

    def alter_dialog(self, tree, viewport):
        if self.defect == "duplicate-list":
            tree.append(deepcopy(viewport))
        elif self.defect == "wrong-package":
            viewport.set("package", "another.app")
        elif self.defect == "missing-list":
            viewport.set("resource-id", "some-other-list")
        elif self.defect == "disabled-list":
            viewport.set("enabled", "false")
        elif self.defect == "hidden-list":
            viewport.set("visible-to-user", "false")
        elif self.defect == "empty-list-bounds":
            viewport.set("bounds", "[0,163][320,163]")
        elif self.defect == "outside-title":
            ET.SubElement(tree, "node", {"package": PACKAGE, "visible-to-user": "true",
                "bounds": "[0,24][320,80]", "text": catalogue.PURCHASE_DIALOG})

    def row(self, parent, top, height, *, text="", resource="", button=False, enabled=True):
        scale = self.scale if self.page == "dialog" else 1.0
        upper, lower = max(0, int(top * scale) - self.offset), min(self.height, int((top + height) * scale) - self.offset)
        if upper >= lower:
            return
        ET.SubElement(parent, "node", {
            "package": PACKAGE, "visible-to-user": "true", "enabled": str(enabled).lower(),
            "bounds": f"[20,{163 + upper}][300,{163 + lower}]", "text": text, "resource-id": resource,
            "class": "android.widget.Button" if button else "android.view.View",
            "clickable": str(button or bool(resource)).lower(),
        })

    def scroll(self, _x1, y1, _x2, y2):
        if self.pending is not None:
            # The read saw the catalogue; the driver's fresh root is the new,
            # fitting dialog, where no scrollable matching list exists.
            self.open_dialog()
            self.wrong_window_scrolls += 1
            if self.extent <= self.height:
                raise ConnectionError("Expected one exact visible app list")
        if self.page == "dialog" and self.delayed_layout and self.dialog_reads <= 4:
            raise AssertionError("Scrolled before dialog content became ready")
        self.scrolls.append((self.page, "end" if y1 > y2 else "start"))
        self.offset = max(0, min(max(0, self.extent - self.height), self.offset + y1 - y2))

    def reveal(self, text, area, direction="end"):
        target = reveal_in_list(self.tree, self.scroll, text, resource_id=area, direction=direction)
        if target is None:
            raise AssertionError("Required catalogue label absent: " + text)
        return target

    def tap(self, text, area, direction="end"):
        target = reveal_in_list(self.tree, self.scroll, text, resource_id=area,
                                direction=direction, for_tap=True)
        if target is None or target.get("enabled") == "false":
            raise AssertionError("Required native action unavailable: " + text)
        self.actions.append(text)
        if text == catalogue.PURCHASE_DIALOG:
            self.pending = 2
        elif text == catalogue.PURCHASE_ACTION:
            self.check_requests.append(self.values["purchase-price"])
            self.result = True
        elif text == "Закрыть":
            self.page, self.window, self.offset = "catalogue", 144, 0

    def tap_resource(self, resource, area, direction="end"):
        target = reveal_resource_in_list(self.tree, self.scroll, resource,
                                         resource_id=area, direction=direction, for_tap=True)
        if target is None:
            raise AssertionError("Required native editor absent: " + resource)
        self.editor = resource

    def type_text(self, probe, previous, addition):
        if probe is not self or self.values.get(self.editor) != previous:
            raise AssertionError("Input lost its exact editor or previous draft")
        self.values[self.editor] = previous + addition
        if self.editor == "purchase-price":
            self.result = False
            self.offset = min(self.offset, max(0, self.extent - self.height))

    def dismiss_keyboard(self):
        if self.editor == "catalogue-query" and self.catalogue_resize:
            # Reflow leaves the catalogue anchored below its already edited form.
            self.offset = self.extent - self.height
        self.editor = None

    @staticmethod
    def wait_for(read, message):
        for _ in range(16):
            value = read()
            if value is not None and value is not False:
                return value
        raise AssertionError(message)

    def verdict(self):
        return "Проверенные ограничения соблюдены" if self.scenario == "ready" else "Покупка не прошла проверку"


class CatalogueDialogTransitionTests(unittest.TestCase):
    def exercise(self, probe):
        case = business._BusinessCase(probe, None, "catalogue", probe.scenario, probe.scale)
        with patch.object(catalogue, "append_native_text", side_effect=probe.type_text):
            case.catalogue()
        return case

    def test_full_case_waits_for_fitting_and_scrollable_dialogs(self):
        for scale in (1.0, 2.0):
            for scenario in ("ready", "partial"):
                for qualified in (False, True):
                    with self.subTest(scale=scale, scenario=scenario, qualified=qualified):
                        probe = CatalogueViewportProbe(scale, scenario, qualified=qualified)
                        case = self.exercise(probe)
                        self.assertEqual(probe.wrong_window_scrolls, 0)
                        self.assertEqual(probe.check_requests, ["95"])
                        self.assertEqual(probe.values["purchase-price"], "950")
                        self.assertEqual(probe.window, 144)
                        self.assertFalse(probe.result)
                        self.assertEqual(probe.actions, ["Найти", catalogue.PURCHASE_DIALOG,
                                                       catalogue.PURCHASE_ACTION, "Закрыть"])
                        self.assertIn("missing-price-blocked", case.checks)
                        self.assertIn("edited-input-invalidates-result", case.checks)
                        if scale == 2.0:
                            self.assertIn(("dialog", "end"), probe.scrolls)
                            self.assertIn(("dialog", "start"), probe.scrolls)

    def test_search_survives_keyboard_reflow_above_the_visible_catalogue(self):
        for scale in (1.0, 2.0):
            for scenario in ("ready", "partial"):
                for qualified in (False, True):
                    with self.subTest(scale=scale, scenario=scenario, qualified=qualified):
                        probe = CatalogueViewportProbe(scale, scenario, qualified=qualified,
                                                       catalogue_resize=True)
                        case = self.exercise(probe)
                        self.assertEqual(probe.values["catalogue-query"], "new1")
                        self.assertEqual(probe.check_requests, ["95"])
                        self.assertEqual(probe.values["purchase-price"], "950")
                        self.assertEqual(probe.actions, ["Найти", catalogue.PURCHASE_DIALOG,
                                                       catalogue.PURCHASE_ACTION, "Закрыть"])
                        self.assertFalse(probe.result)
                        self.assertIn("edited-input-invalidates-result", case.checks)

    def test_forward_only_search_cannot_find_the_form_after_keyboard_reflow(self):
        probe = CatalogueViewportProbe(catalogue_resize=True)
        probe.tap_resource("catalogue-query", AREA)
        probe.type_text(probe, "", "new1")
        probe.dismiss_keyboard()
        with self.assertRaisesRegex(AssertionError, "List target not reachable: Найти"):
            probe.tap("Найти", AREA, direction="end")
        self.assertEqual(probe.actions, [])
        self.assertEqual(probe.check_requests, [])
        self.assertEqual(probe.values["catalogue-query"], "new1")

    def test_reflow_does_not_bypass_missing_or_disabled_search(self):
        for defect in ("missing-search", "disabled-search"):
            with self.subTest(defect=defect):
                probe = CatalogueViewportProbe(catalogue_resize=True, defect=defect)
                with self.assertRaisesRegex(AssertionError,
                        "List target not reachable: Найти|Required native action unavailable: Найти"):
                    self.exercise(probe)
                self.assertEqual(probe.actions, [])
                self.assertEqual(probe.check_requests, [])

    def test_removing_barrier_reproduces_old_frame_new_dialog_scroll_failure(self):
        probe = CatalogueViewportProbe()
        with patch.object(catalogue, "wait_for_new_app_window", return_value=None):
            with self.assertRaisesRegex(ConnectionError, "Expected one exact visible app list"):
                self.exercise(probe)
        self.assertEqual(probe.wrong_window_scrolls, 1)
        self.assertEqual(probe.check_requests, [])

    def test_new_window_may_precede_its_list_and_title(self):
        for scale in (1.0, 2.0):
            with self.subTest(scale=scale):
                probe = CatalogueViewportProbe(scale, delayed_layout=True)
                self.exercise(probe)
                self.assertIn("new-window-without-list", probe.readiness)
                self.assertIn("new-list-without-title", probe.readiness)
                self.assertEqual(probe.wrong_window_scrolls, 0)
                self.assertEqual(probe.check_requests, ["95"])

    def test_old_window_cannot_supply_dialog_readiness(self):
        self.assert_rejected_before_check("same-window")

    def test_wrong_or_missing_dialog_scope_cannot_supply_readiness(self):
        for defect in ("wrong-package", "missing-list", "missing-title", "outside-title", "duplicate-list"):
            with self.subTest(defect=defect):
                self.assert_rejected_before_check(defect)

    def test_disabled_hidden_and_empty_lists_cannot_supply_readiness(self):
        for defect in ("disabled-list", "hidden-list", "empty-list-bounds"):
            with self.subTest(defect=defect):
                self.assert_rejected_before_check(defect)

    def test_missing_native_window_identity_fails_closed(self):
        probe = CatalogueViewportProbe(defect="invalid-window")
        with self.assertRaisesRegex(AssertionError, "Missing public active-window identity"):
            self.exercise(probe)
        self.assertEqual(probe.check_requests, [])

    def test_ready_dialog_cannot_replace_the_required_purchase_action(self):
        probe = CatalogueViewportProbe(defect="missing-action")
        with self.assertRaisesRegex(AssertionError, "Required catalogue label absent"):
            self.exercise(probe)
        self.assertEqual(probe.check_requests, [])

    def test_ready_dialog_does_not_weaken_the_missing_price_guard(self):
        probe = CatalogueViewportProbe(defect="enabled-empty-price")
        with self.assertRaisesRegex(AssertionError, "A missing price permits a purchase check"):
            self.exercise(probe)
        self.assertEqual(probe.check_requests, [])

    def assert_rejected_before_check(self, defect):
        probe = CatalogueViewportProbe(defect=defect)
        with self.assertRaisesRegex(AssertionError, "New app window did not become ready"):
            self.exercise(probe)
        self.assertEqual(probe.wrong_window_scrolls, 0)
        self.assertEqual(probe.check_requests, [])


if __name__ == "__main__":
    unittest.main()
