"""Negative native-frame and actual-pixel regressions, executed only by the Windows gate."""
from __future__ import annotations

import math
import hashlib
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import theme_state_evidence as theme
from spatial_frame_evidence import Screenshot


NONCE = "a" * 32


def frame(mode="DARK", accent="AURORA", scale=2.0):
    # Keep the original observed 320x640 phone viewport, including negative cases.
    tree = ET.Element("hierarchy", {"display-width": "320", "display-height": "640", "active-window-id": "9",
        "root-window-present": "true", "root-window-focused": "true", "keyboard-visible": "false"})
    root = ET.SubElement(tree, "node", {"package": theme.PACKAGE, "visible-to-user": "true", "enabled": "true",
                                     "bounds": "[0,0][320,640]"})
    state = "clicks=1,down=true,native=true,spatial=true,choice=true,tab=1,selected=-1,input=ТЕМА,destination=Home,overlay=drawer,dialog=false,period=2026-10-24/2026-10-25/2026-10-26"
    colors = theme._expected(mode, accent)
    fields = {"theme-probe": "production-v1", "theme-group": "actions", "theme-run": NONCE,
              "theme-mode": mode, "theme-accent": accent, "theme-motion": "OFF", "theme-saved-mode": mode,
              "theme-saved-accent": accent, "theme-saved-motion": "OFF", "theme-font-scale": str(scale),
              "theme-density": "1.0", "theme-original": "DARK,AURORA,LIVE", "theme-state": state,
              "theme-colors": ",".join(key + "=" + value for key, value in colors.items())}
    ET.SubElement(root, "node", {"package": theme.PACKAGE, "visible-to-user": "true", "enabled": "true",
        "bounds": "[0,0][2,2]", "content-desc": ";".join(key + ":" + value for key, value in fields.items())})
    return tree


def observe(tree, mode="DARK", accent="AURORA", scale=2.0):
    return theme.theme_observation(tree, mode=mode, accent=accent, scale=scale, group="actions", nonce=NONCE)


def target(tree, resource="theme-control-primary", bounds="[8,32][156,106]", **attributes):
    return ET.SubElement(next(iter(tree)), "node", {"package": theme.PACKAGE, "resource-id": resource,
        "visible-to-user": "true", "enabled": "true", "clickable": "true", "focusable": "true", "bounds": bounds,
        **attributes})


class Pixels:
    def __init__(self, background):
        self.data = bytearray(bytes(background) * (320 * 640))

    def paint(self, bounds, color):
        left, top, right, bottom = bounds
        if not (0 <= left < right <= 320 and 0 <= top < bottom <= 640):
            raise AssertionError("Invalid regression fixture geometry")
        for y in range(top, bottom):
            for x in range(left, right):
                offset = (y * 320 + x) * 3
                self.data[offset:offset + 3] = bytes(color)

    def image(self):
        return Screenshot(320, 640, 3, bytes(self.data))


class ThemeObservationTests(unittest.TestCase):
    def test_every_effective_scheme_is_read_from_complete_actual_marker(self):
        for mode in theme.MODES:
            for accent in theme.ACCENTS:
                for scale in theme.SCALES:
                    with self.subTest(mode=mode, accent=accent, scale=scale):
                        actual = observe(frame(mode, accent, scale), mode, accent, scale)
                        self.assertEqual((actual["width"], actual["height"]), (320, 640))
                        self.assertEqual(len(actual["colors"]), 74)
                        self.assertEqual(actual["state"]["down"], "true")

    def test_requested_mode_cannot_replace_actual_compiled_colors(self):
        tree = frame()
        marker = next(n for n in tree.iter("node") if n.get("content-desc"))
        marker.set("content-desc", marker.get("content-desc").replace("primary=ff80d1c5", "primary=ff006b65"))
        with self.assertRaisesRegex(AssertionError, "approved role: primary"):
            observe(tree)

    def test_missing_fixed_role_and_duplicate_marker_fields_fail(self):
        for change in (lambda s: s.replace("primaryFixed=ffd6f0eb,", ""), lambda s: s + ";theme-mode:DARK"):
            tree = frame()
            marker = next(n for n in tree.iter("node") if n.get("content-desc"))
            marker.set("content-desc", change(marker.get("content-desc")))
            with self.assertRaises(AssertionError):
                observe(tree)

    def test_stale_run_uncommitted_accent_and_wrong_font_fail(self):
        for before, after in (("theme-run:" + NONCE, "theme-run:" + "b" * 32),
                              ("theme-saved-accent:AURORA", "theme-saved-accent:IRIS"),
                              ("theme-font-scale:2.0", "theme-font-scale:1.0")):
            tree = frame()
            marker = next(n for n in tree.iter("node") if n.get("content-desc"))
            marker.set("content-desc", marker.get("content-desc").replace(before, after))
            with self.assertRaises(AssertionError):
                observe(tree)

    def test_foreign_unfocused_and_missing_window_never_supply_a_theme(self):
        for key, value in (("root-window-present", "false"), ("root-window-focused", "false")):
            tree = frame(); tree.set(key, value)
            with self.assertRaises(AssertionError):
                observe(tree)
        tree = frame(); next(iter(tree)).set("package", "foreign.application")
        with self.assertRaises(AssertionError):
            observe(tree)

    def test_foreign_marker_and_conflicting_duplicate_are_rejected(self):
        tree = frame()
        marker = next(n for n in tree.iter("node") if n.get("content-desc"))
        marker.set("package", "foreign.application")
        with self.assertRaises(AssertionError):
            observe(tree)
        tree = frame()
        marker = next(n for n in tree.iter("node") if n.get("content-desc"))
        duplicate = ET.SubElement(next(iter(tree)), "node", dict(marker.attrib))
        duplicate.set("content-desc", duplicate.get("content-desc").replace("clicks=1", "clicks=2"))
        with self.assertRaisesRegex(AssertionError, "conflicting"):
            observe(tree)

    def test_touch_requires_real_enabled_48dp_owner(self):
        tree = frame(); target(tree)
        self.assertEqual(theme.owned_target(tree, "theme-control-primary", touch=True)[1], (8, 32, 156, 106))
        for attribute, value in (("enabled", "false"), ("clickable", "false"), ("focusable", "false"),
                                 ("bounds", "[8,32][156,79]")):
            tree = frame(); target(tree, **{attribute: value})
            with self.assertRaises(AssertionError):
                theme.owned_target(tree, "theme-control-primary", touch=True)

    def test_disabled_observation_is_distinct_from_action_admission(self):
        tree = frame(); target(tree, enabled="false", clickable="false")
        theme.owned_target(tree, "theme-control-primary", enabled=False)
        with self.assertRaises(AssertionError):
            theme.owned_target(tree, "theme-control-primary", touch=True)

    def test_clipped_malformed_hidden_and_ambiguous_targets_fail(self):
        for bounds in ("[-1,32][156,106]", "[8,32][321,106]", "[8,32][8,106]", "broken"):
            tree = frame(); target(tree, bounds=bounds)
            with self.assertRaises(AssertionError):
                theme.owned_target(tree, "theme-control-primary")
        tree = frame(); target(tree, **{"visible-to-user": "false"})
        with self.assertRaises(AssertionError):
            theme.owned_target(tree, "theme-control-primary")
        tree = frame(); target(tree); target(tree)
        with self.assertRaises(AssertionError):
            theme.owned_target(tree, "theme-control-primary")

    def test_scroll_viewport_and_foreign_ancestor_are_enforced(self):
        tree = frame(); root = next(iter(tree)); node = target(tree)
        root.remove(node)
        viewport = ET.SubElement(root, "node", {"package": theme.PACKAGE, "visible-to-user": "true", "enabled": "true",
                                                "scrollable": "true", "bounds": "[8,40][312,600]"})
        viewport.append(node)
        with self.assertRaisesRegex(AssertionError, "scroll viewport"):
            theme.owned_target(tree, "theme-control-primary")
        viewport.set("bounds", "[0,0][320,640]"); viewport.set("package", "foreign.application")
        with self.assertRaisesRegex(AssertionError, "foreign"):
            theme.owned_target(tree, "theme-control-primary")

    def test_overlay_distribution_is_finite_and_covers_both_modes_and_scales(self):
        cases = [(mode, accent, scale, theme.overlay_variant(mode, accent, scale))
                 for mode in theme.MODES for accent in theme.ACCENTS for scale in theme.SCALES]
        self.assertEqual(len(cases), 12)
        for variant in ("drawer", "dialog", "rail"):
            subset = [(mode, scale) for mode, _, scale, observed in cases if observed == variant]
            self.assertEqual(set(subset), {(mode, scale) for mode in theme.MODES for scale in theme.SCALES})

    def test_dialog_state_waits_for_its_actual_new_owned_window(self):
        first = frame()
        marker = next(n for n in first.iter("node") if n.get("content-desc"))
        marker.set("content-desc", marker.get("content-desc").replace("dialog=false", "dialog=true"))
        second = ET.fromstring(ET.tostring(first)); second.set("active-window-id", "10")
        class Probe:
            current = first
            def tree(self):
                return self.current
            def wait_for(self, callback, message):
                self.current = first
                if callback() is not None:
                    raise AssertionError("A main-window state change impersonated the separate dialog")
                self.current = second
                value = callback()
                if value is None:
                    raise AssertionError(message)
                return value
        case = theme._ThemeCase(Probe(), "DARK", "AURORA", 2.0, "actions")
        case.nonce = NONCE
        actual = case.await_state(dialog="true", not_window=9)
        self.assertEqual(actual["window_id"], 10)


class ThemePixelTests(unittest.TestCase):
    def test_white_surface_corners_cannot_impersonate_a_primary_button_glyph(self):
        c = theme._expected("LIGHT", "AURORA")
        ink, fill = theme.rgb(c["onPrimary"]), theme.rgb(c["primary"])
        canvas = Pixels(ink)
        bounds = (8, 40, 156, 112)
        canvas.paint((14, 46, 150, 106), fill)
        canvas.paint((64, 62, 88, 90), theme.rgb(c["onSurface"]))
        # The old whole-button measurement would count the unrelated white corners.
        self.assertGreater(theme.paired_pixels(canvas.image(), bounds, ink, fill)["foreground_pixels"], 3)
        with self.assertRaisesRegex(AssertionError, "absent"):
            theme.primary_button_pixels(canvas.image(), bounds, 1.0, ink, fill)
        canvas.paint((64, 62, 88, 90), ink)
        actual = theme.primary_button_pixels(canvas.image(), bounds, 1.0, ink, fill)
        self.assertEqual(actual["bounds"], [26, 52, 138, 100])
        self.assertGreater(actual["foreground_pixels"], 3)

    def test_actual_pair_needs_visible_ink_and_fill_not_only_contrast_numbers(self):
        c = theme._expected("DARK", "AURORA")
        fg, bg = theme.rgb(c["onPrimary"]), theme.rgb(c["pressedPrimary"])
        canvas = Pixels(theme.rgb(c["surface"]))
        area = (8, 32, 156, 106)
        canvas.paint(area, bg)
        with self.assertRaisesRegex(AssertionError, "absent"):
            theme.paired_pixels(canvas.image(), area, fg, bg)
        canvas.paint((60, 55, 72, 75), fg)
        self.assertGreater(theme.paired_pixels(canvas.image(), area, fg, bg)["contrast"], 4.5)

    def test_wrong_white_dark_thumb_cannot_borrow_white_pixels_from_outside_track(self):
        c = theme._expected("DARK", "AURORA")
        thumb, track = theme.rgb(c["onPrimary"]), theme.rgb(c["primary"])
        canvas = Pixels((255, 255, 255))
        bounds = (8, 180, 72, 228)
        canvas.paint((14, 188, 66, 220), track)
        canvas.paint((42, 196, 58, 212), thumb)
        result = theme.switch_pixels(canvas.image(), bounds, 1.0, native=True, checked=True,
                                     foreground=thumb, background=track)
        self.assertGreater(result["thumb_pixels"], 3)
        canvas.paint((42, 196, 58, 212), (255, 255, 255))
        with self.assertRaisesRegex(AssertionError, "absent"):
            theme.switch_pixels(canvas.image(), bounds, 1.0, native=True, checked=True,
                                foreground=thumb, background=track)

    def test_disabled_gray_ink_and_antialiasing_pass_but_opaque_support_color_fails(self):
        c = theme._expected("LIGHT", "AURORA")
        ink, bg = theme.rgb(c["disabledInk"]), theme.rgb(c["surface"])
        canvas = Pixels(bg); area = (8, 300, 72, 364)
        canvas.paint((16, 310, 60, 346), ink)
        edge = tuple(round((a + b) / 2) for a, b in zip(ink, bg))
        canvas.paint((15, 310, 16, 346), edge)
        self.assertEqual(theme.monochrome_pixels(canvas.image(), area, ink, bg)["foreign_pixels"], 0)
        canvas.paint((30, 316, 40, 330), (22, 169, 155))
        with self.assertRaisesRegex(AssertionError, "support color"):
            theme.monochrome_pixels(canvas.image(), area, ink, bg)

    def test_low_contrast_pair_is_not_rounded_up(self):
        canvas = Pixels((255, 255, 255)); canvas.paint((8, 40, 20, 50), (119, 119, 119))
        with self.assertRaisesRegex(AssertionError, "contrast"):
            theme.paired_pixels(canvas.image(), (8, 32, 156, 106), (119, 119, 119), (255, 255, 255), threshold=4.5)

    def history_fixture(self):
        c = theme._expected("LIGHT", "IRIS")
        canvas = Pixels(theme.rgb(c["surface"]))
        bounds = (8, 40, 312, 170); left, top, right, bottom = bounds
        width, height = right - left, bottom - top
        for index, value in enumerate((-20, 0, None, 10, 40, 80)):
            if value is None:
                continue
            y1, y2 = sorted((.8, .8 - value / 100))
            if value == 0:
                y1, y2 = .8 - 1 / height, .8 + 1 / height
            area = (math.floor(left + width * (index + .16) / 6), math.floor(top + height * y1),
                    math.ceil(left + width * (index + .84) / 6), math.ceil(top + height * y2))
            canvas.paint(area, theme.rgb(c["error"] if value < 0 else c["info"]))
        mx, my = left + width * 2.5 / 6, top + height * .8
        canvas.paint((math.floor(mx) - 5, math.floor(my), math.floor(mx) + 6, math.floor(my) + 1), theme.rgb(c["chartAxis"]))
        a, b, d, e = (math.floor(left + width * 4.16 / 6), math.floor(top + height * .4),
                       math.ceil(left + width * 4.84 / 6), math.ceil(top + height * .8))
        canvas.paint((a, b, a + 2, e), theme.rgb(c["chartSelectedOuter"]))
        canvas.paint((a + 2, b + 2, a + 4, e - 2), theme.rgb(c["chartSelectedInner"]))
        return canvas, bounds, c

    def test_history_checks_every_observation_and_both_selected_edges(self):
        canvas, bounds, c = self.history_fixture()
        result = theme.history_pixels(canvas.image(), bounds, c)
        self.assertEqual([row["index"] for row in result["bars"]], [0, 1, 3, 4, 5])
        self.assertEqual(result["bars"][0]["value"], -20)
        self.assertGreater(result["missing_axis_pixels"], 0)

    def test_only_first_positive_bar_using_info_color_is_not_a_valid_single_series(self):
        canvas, bounds, c = self.history_fixture()
        left, top, right, bottom = bounds
        x = left + (right - left) * 5.5 / 6
        y = top + (bottom - top) * .4
        canvas.paint((math.floor(x) - 2, math.floor(y) - 1, math.floor(x) + 3, math.floor(y) + 3), theme.rgb(c["primary"]))
        with self.assertRaisesRegex(AssertionError, "absent"):
            theme.history_pixels(canvas.image(), bounds, c)

    def test_a_missing_sample_cannot_be_replaced_with_an_invented_zero_bar(self):
        canvas, bounds, c = self.history_fixture()
        left, top, right, bottom = bounds
        x = left + (right - left) * 2.5 / 6
        y = top + (bottom - top) * .8
        canvas.paint((math.floor(x) - 5, math.floor(y), math.floor(x) + 6, math.floor(y) + 1), theme.rgb(c["info"]))
        with self.assertRaisesRegex(AssertionError, "absent"):
            theme.history_pixels(canvas.image(), bounds, c)


class CalendarColorTests(unittest.TestCase):
    def fixture(self):
        before = observe(frame("LIGHT", "AURORA"), "LIGHT", "AURORA")
        tree = frame("LIGHT", "AURORA"); tree.set("active-window-id", "10")
        root = next(iter(tree))
        for child in list(root):
            root.remove(child)
        viewport = ET.SubElement(root, "node", {"package": theme.PACKAGE, "visible-to-user": "true",
            "enabled": "true", "scrollable": "true", "bounds": "[8,100][312,520]"})
        for label, bounds, enabled, selected in (
                ("Начальная дата, суббота, 24 октября 2026 г.", "[24,160][72,208]", "true", "true"),
                ("среда, 28 октября 2026 г.", "[96,160][144,208]", "false", "false")):
            ET.SubElement(viewport, "node", {"package": theme.PACKAGE, "visible-to-user": "true",
                "class": "android.widget.Button", "bounds": bounds, "enabled": enabled,
                "selected": selected, "clickable": "true", "focusable": "true", "text": label})
        c = before["colors"]
        canvas = Pixels(theme.rgb(c["surface"]))
        canvas.paint((28, 164, 68, 204), theme.rgb(c["primary"]))
        canvas.paint((42, 177, 54, 191), theme.rgb(c["onPrimary"]))
        canvas.paint((114, 177, 126, 191), theme.rgb(c["disabledInk"]))
        return tree, before, canvas, viewport

    def test_real_full_date_semantics_and_visible_state_pixels_are_required(self):
        tree, before, canvas, _ = self.fixture()
        actual = theme.calendar_pixels(canvas.image(), tree, before)
        self.assertEqual((actual["selected_dates_observed"], actual["disabled_dates_observed"]), (1, 1))
        self.assertEqual(theme.calendar_scroll_viewport(tree, 1.0), (8, 100, 312, 520))
        self.assertFalse(actual["offscreen_states_claimed"])
        self.assertIn("24 октября 2026", actual["cells"][0]["native_date_label"])

    def test_old_faded_disabled_ink_fails_the_actual_calendar_pixels(self):
        tree, before, canvas, _ = self.fixture()
        ink, bg = (theme.rgb(before["colors"][key]) for key in ("disabledInk", "surface"))
        faded = tuple(round(a * .38 + b * .62) for a, b in zip(ink, bg))
        canvas.paint((114, 177, 126, 191), faded)
        with self.assertRaisesRegex(AssertionError, "absent"):
            theme.calendar_pixels(canvas.image(), tree, before)

    def test_white_calendar_page_and_wrong_selected_text_do_not_supply_the_glyph(self):
        tree, before, canvas, _ = self.fixture()
        canvas.paint((42, 177, 54, 191), theme.rgb(before["colors"]["onSurface"]))
        with self.assertRaisesRegex(AssertionError, "absent"):
            theme.calendar_pixels(canvas.image(), tree, before)

    def test_wrong_window_selected_state_and_clipped_cells_fail_closed(self):
        for mutation in (lambda t, v: t.set("active-window-id", "9"),
                         lambda t, v: list(v)[0].set("selected", "false"),
                         lambda t, v: list(v)[0].set("bounds", "[24,80][72,128]"),
                         lambda t, v: list(v)[0].set("text", "24")):
            tree, before, canvas, viewport = self.fixture(); mutation(tree, viewport)
            with self.assertRaises(AssertionError):
                theme.calendar_pixels(canvas.image(), tree, before)

    def test_foreign_hidden_and_malformed_calendar_ancestors_never_admit_scroll(self):
        for key, value in (("package", "foreign.application"), ("visible-to-user", "false"),
                           ("enabled", "false"), ("bounds", "broken")):
            tree, _, _, viewport = self.fixture(); viewport.set(key, value)
            with self.assertRaises(AssertionError):
                theme.calendar_scroll_viewport(tree, 1.0)
        tree, _, _, viewport = self.fixture()
        root = next(iter(tree)); root.remove(viewport)
        foreign = ET.SubElement(root, "node", {"package": "foreign.application", "visible-to-user": "true",
                                               "enabled": "true", "bounds": "[0,0][320,640]"})
        foreign.append(viewport)
        with self.assertRaisesRegex(AssertionError, "foreign"):
            theme.calendar_scroll_viewport(tree, 1.0)


class PreferenceSnapshotTests(unittest.TestCase):
    def restored(self):
        return {"phase": "restore", "restored": "true", "mode": "SYSTEM", "saved-mode": "SYSTEM",
                "original-mode": "SYSTEM", "original-hash": "a" * 64, "saved-hash": "a" * 64,
                "stored-mode": "SYSTEM", "saved-accent": "absent"}

    def test_restore_requires_exact_presence_hash_and_original_observation(self):
        original = self.restored(); original["phase"] = "begin"
        self.assertTrue(theme.restored_preference_snapshot(self.restored(), original)["exact_key_presence_restored"])
        for key, value in (("saved-hash", "b" * 64), ("restored", "false"), ("mode", "DARK"),
                           ("stored-mode", "absent"), ("original-hash", "c" * 64)):
            candidate = self.restored(); candidate[key] = value
            with self.assertRaises(AssertionError):
                theme.restored_preference_snapshot(candidate, original)

    def snapshot_fixture(self, *, lose_begin=False, corrupt_restore=False, fail_font_once=False):
        # State includes absence: adding a formerly absent default is not restoration.
        original = {"theme_mode": "SYSTEM", "accent": "OCEAN", "haptics": False}
        state = {"settings": dict(original), "backup": None, "windows": 0, "scale": "1.0", "font_failure": fail_font_once}
        def digest(values):
            return hashlib.sha256(json.dumps(values, sort_keys=True).encode()).hexdigest()
        class Probe:
            def command(self, *args):
                if args == ("shell", "cmd", "package", "list", "packages", "-U", theme.PACKAGE):
                    return "package:" + theme.PACKAGE + " uid:10123"
                if args == ("shell", "cmd", "uimode", "night"):
                    return "Night mode: auto"
                if args == ("shell", "settings", "get", "system", "font_scale"):
                    return state["scale"]
                if args[:5] == ("shell", "settings", "put", "system", "font_scale"):
                    if state["font_failure"]:
                        state["font_failure"] = False
                        raise RuntimeError("Font transport failed during cleanup")
                    state["scale"] = args[5]
                    return ""
                raise AssertionError("Unexpected synthetic transport operation")
        class Case:
            def __init__(self, phase):
                self.phase = phase
            def current(self):
                snapshot = state["backup"]
                return {"phase": self.phase, "restored": str(state["settings"] == snapshot).lower(),
                    "mode": state["settings"].get("theme_mode", "DARK"),
                    "saved-mode": state["settings"].get("theme_mode", "DARK"),
                    "original-mode": snapshot.get("theme_mode", "DARK"), "original-hash": digest(snapshot),
                    "saved-hash": "f" * 64 if corrupt_restore and self.phase == "restore" else digest(state["settings"]),
                    "stored-mode": state["settings"].get("theme_mode", "absent"),
                    "saved-accent": state["settings"].get("accent", "absent")}
            def tap(self, label, direction):
                if label != "Закрыть проверку" or direction != "end" or state["settings"] != state["backup"]:
                    raise AssertionError("An unverified snapshot cannot be disposed")
                state["backup"] = None; state["windows"] = 0
        def launch(probe, session, phase, scale, uid, deadline, folder):
            if phase == "begin":
                if state["backup"] is not None:
                    raise AssertionError("An existing snapshot must not be replaced")
                state["backup"] = dict(state["settings"])
                state["windows"] = 1
                if lose_begin:
                    raise RuntimeError("First native marker lost after snapshot creation")
            elif phase == "restore":
                if state["backup"] is None:
                    raise AssertionError("No owned snapshot")
                state["settings"] = dict(state["backup"]); state["windows"] = 1
            else:
                raise AssertionError("Unexpected snapshot phase")
            return Case(phase)
        def windows(probe, uid, count):
            if state["windows"] != count:
                raise AssertionError("The owned snapshot window did not dispose")
            return {"actual_windows": count}
        return Probe(), original, state, launch, windows

    def test_failed_first_palette_validation_restores_values_and_absence(self):
        probe, original, state, launch, windows = self.snapshot_fixture()
        receipt = {}
        with patch("navigation_detail_probe._owned_emulator", return_value={"lease_owner_pid": 123}), \
                patch("theme_lifecycle_probe._launch", side_effect=launch), \
                patch("theme_lifecycle_probe.window_receipt", side_effect=windows):
            with self.assertRaisesRegex(RuntimeError, "actual palette"):
                with theme.preserve_theme_preferences(probe, Path("unused"), "1.0", receipt):
                    state["settings"].update(theme_mode="LIGHT", accent="IRIS", motion="OFF", depth=True)
                    raise RuntimeError("The first actual palette marker failed validation")
        self.assertEqual(state["settings"], original)
        self.assertIsNone(state["backup"])
        self.assertTrue(receipt["restored"])

    def test_lost_begin_marker_still_restores_and_disposes_owned_snapshot(self):
        probe, original, state, launch, windows = self.snapshot_fixture(lose_begin=True)
        receipt = {}
        with patch("navigation_detail_probe._owned_emulator", return_value={"lease_owner_pid": 123}), \
                patch("theme_lifecycle_probe._launch", side_effect=launch), \
                patch("theme_lifecycle_probe.window_receipt", side_effect=windows):
            with self.assertRaisesRegex(RuntimeError, "First native marker"):
                with theme.preserve_theme_preferences(probe, Path("unused"), "1.0", receipt):
                    self.fail("A lost native marker cannot admit color writes")
        self.assertEqual(state["settings"], original)
        self.assertIsNone(state["backup"])
        self.assertTrue(receipt["restored"])
        self.assertFalse(receipt["snapshot"]["initial_marker_observed"])

    def test_unproved_restore_cannot_close_snapshot_or_report_pass(self):
        probe, _, state, launch, windows = self.snapshot_fixture(corrupt_restore=True)
        receipt = {}
        with patch("navigation_detail_probe._owned_emulator", return_value={"lease_owner_pid": 123}), \
                patch("theme_lifecycle_probe._launch", side_effect=launch), \
                patch("theme_lifecycle_probe.window_receipt", side_effect=windows):
            with self.assertRaisesRegex(AssertionError, "preference snapshot"):
                with theme.preserve_theme_preferences(probe, Path("unused"), "1.0", receipt):
                    state["settings"]["theme_mode"] = "LIGHT"
        self.assertFalse(receipt["restored"])
        self.assertIsNotNone(state["backup"])

    def test_font_transport_failure_does_not_suppress_independent_app_restore(self):
        probe, original, state, launch, windows = self.snapshot_fixture(fail_font_once=True)
        receipt = {}
        with patch("navigation_detail_probe._owned_emulator", return_value={"lease_owner_pid": 123}), \
                patch("theme_lifecycle_probe._launch", side_effect=launch), \
                patch("theme_lifecycle_probe.window_receipt", side_effect=windows):
            with self.assertRaisesRegex(RuntimeError, "Font transport failed"):
                with theme.preserve_theme_preferences(probe, Path("unused"), "1.0", receipt):
                    state["settings"].update(theme_mode="LIGHT", motion="OFF", depth=True)
        self.assertEqual(state["settings"], original)
        self.assertIsNone(state["backup"])
        self.assertTrue(receipt["snapshot_restored"])
        self.assertFalse(receipt["restored"])


if __name__ == "__main__":
    unittest.main()
