"""Reset must commit through a usable native owner, not its clipped text child."""
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import portfolio_preferences_probe as preferences
from native_label_target import label_target
from profile_scroll import PACKAGE
from profile_ui_probe import ProfileProbe, node_bounds


class ResetCommitProbe(ProfileProbe):
    """Conditional native geometry; section setup is unrelated scaffolding."""

    def __init__(self, height, *, already_default=False, accept_apply=True):
        self.height = height
        self.offset = 0
        self.accept_apply = accept_apply
        self.saved = dict(preferences.DEFAULT if already_default else preferences.APPLIED)
        self.prefs = dict(self.saved)
        self.applied = False
        self.actions = []
        self.movements = []
        self.read_tree = self.tree

    def tree(self):
        common = {"package": PACKAGE, "visible-to-user": "true", "enabled": "true"}
        tree = ET.Element("hierarchy", {"display-width": "320", "display-height": "640",
                                       "active-window-id": "57"})
        top = 616 - self.height
        body = ET.SubElement(tree, "node", {**common, "resource-id": preferences.AREA,
            "bounds": f"[56,{top}][320,616]", "scrollable": "true"})

        def row(parent, position, size, **attrs):
            upper = max(0, position - self.offset)
            lower = min(self.height, position + size - self.offset)
            if lower <= upper:
                return None
            return ET.SubElement(parent, "node", {**common,
                "bounds": f"[88,{top + upper}][288,{top + lower}]", **attrs})

        status = "Оформление применено" if self.applied else preferences.DIRTY
        row(body, self.height - 90, 64, text=status)
        position = self.height - 11
        owner = row(body, position, 64, **{"class": "android.view.View", "clickable": "true",
            "enabled": str(self.prefs != self.saved).lower()})
        if owner is not None:
            row(owner, position, 64, **{"class": "android.widget.Button", "clickable": "false"})
            # Compose can expose an enabled label under a disabled Button owner.
            row(owner, position + 2, 56, text="Применить", **{"clickable": "false"})
        return tree

    def _semantic_scroll_callback(self, area, direction):
        if area != preferences.AREA:
            raise AssertionError("Wrong appearance list")

        def scroll(_x1, y1, _x2, y2):
            before = self.offset
            self.offset = max(0, min(self.height, self.offset + y1 - y2))
            self.movements.append((before, self.offset))
        return scroll

    def reveal(self, text, area, direction="end", **kwargs):
        if text in {"Применить", "Оформление применено"}:
            return ProfileProbe.reveal(self, text, area, direction, **kwargs)
        return ET.Element("node", {"package": PACKAGE, "text": text, "enabled": "true"})

    def tap(self, text, area, direction="end", **kwargs):
        if text == "Вернуть оформление по умолчанию":
            self.prefs = dict(preferences.DEFAULT)
            self.actions.append("reset")
            return
        if text != "Применить":
            raise AssertionError("Unexpected reset action")
        return ProfileProbe.tap(self, text, area, direction, **kwargs)

    def command(self, *args):
        if args[:3] != ("shell", "input", "tap"):
            raise AssertionError("Unexpected reset command")
        target = label_target(self.tree(), "Применить")
        if target is None:
            raise AssertionError("Reset Apply attempted without a usable enabled native owner")
        left, top, right, bottom = node_bounds(target)
        if (int(args[3]), int(args[4])) != ((left + right) // 2, (top + bottom) // 2):
            raise AssertionError("Reset Apply used a text coordinate instead of its native owner")
        self.actions.append("apply")
        if self.accept_apply:
            self.saved = dict(self.prefs)
            self.applied = True
        return ""

    @staticmethod
    def wait_for(read, message):
        value = read()
        if value is None or value is False:
            raise AssertionError(message)
        return value


class AppearanceResetCommitTests(unittest.TestCase):
    def case(self, probe):
        def expect(predicate, message):
            value = {"prefs": probe.prefs}
            self.assertTrue(predicate(value), message)
            return value
        return SimpleNamespace(probe=probe, expect=expect)

    def test_reset_reveals_native_owner_and_confirms_defaults_were_applied(self):
        for height in (236, 401):
            with self.subTest(conditional_viewport=height), patch("profile_scroll.time.sleep"):
                probe = ResetCommitProbe(height)
                preferences._reset(self.case(probe))
                self.assertEqual(probe.actions, ["reset", "apply"])
                self.assertEqual(probe.saved, preferences.DEFAULT)
                self.assertTrue(probe.applied)
                self.assertTrue(any(after > before for before, after in probe.movements))

    def test_enabled_text_does_not_enable_the_disabled_native_apply_button(self):
        probe = ResetCommitProbe(401, already_default=True)
        with patch("profile_scroll.time.sleep"):
            preferences._reset(self.case(probe))
        self.assertEqual(probe.actions, ["reset"])
        self.assertEqual(probe.saved, preferences.DEFAULT)

    def test_preview_defaults_do_not_hide_a_missing_save_confirmation(self):
        probe = ResetCommitProbe(236, accept_apply=False)
        with patch("profile_scroll.time.sleep"), self.assertRaisesRegex(
                AssertionError, "List target not reachable: Оформление применено"):
            preferences._reset(self.case(probe))
        self.assertEqual(probe.prefs, preferences.DEFAULT)
        self.assertEqual(probe.saved, preferences.APPLIED)
        self.assertEqual(probe.actions, ["reset", "apply"])
        self.assertLessEqual(len(probe.movements), 11)


if __name__ == "__main__":
    unittest.main()
