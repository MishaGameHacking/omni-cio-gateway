"""Exercise the real lifecycle validators and cleanup, without claiming Android rendering."""
from copy import deepcopy
from pathlib import Path
import sys
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import theme_lifecycle_probe as life

SESSION = "a" * 32
RUN = "b" * 32
UID = "10234"


def node(parent, bounds="[0,0][320,640]", **attributes):
    return ET.SubElement(parent, "node", {"package": life.PACKAGE, "enabled": "true",
        "visible-to-user": "true", "bounds": bounds, "class": "android.view.View", **attributes})


def observation(**updates):
    value = {"theme-lifecycle": "production-v1", "session": SESSION, "run": RUN, "phase": "begin",
        "activity": "00000000-0000-0000-0000-000000000001", "owner": "00000000-0000-0000-0000-000000000002",
        "editor-owner": "00000000-0000-0000-0000-000000000003", "pid": "1234", "uid": UID,
        "page": "home", "draft": "THEME_DRAFT", "mode": "DARK", "saved-mode": "DARK", "stored-mode": "DARK",
        "saved-hash": "c" * 64, "original-mode": "DARK", "original-hash": "d" * 64,
        "app-night": "yes", "system-night": "no", "policy": "no", "background": "ff101a1f", "foreground": "ffe7eff2",
        "native-background": "ff101a1f", "native-window": "ff101a1f", "native-splash": "ff101a1f",
        "launch-night": "yes", "launch-window": "ff101a1f", "launch-splash": "ff101a1f",
        "status-light": "false", "navigation-light": "false", "overlay-permission": "false", "overlay-capability": "false",
        "accent": "OCEAN", "saved-accent": "OCEAN", "font-scale": "1.0", "density": "1.0", "restored": "false"}
    value.update(updates)
    return value


def frame(value=None):
    value = observation() if value is None else value
    tree = ET.Element("hierarchy", {"root-window-present": "true", "root-window-focused": "true",
        "active-window-id": "7", "display-width": "320", "display-height": "640", "keyboard-visible": "false"})
    root = node(tree)
    metrics = {"probe-screen": life.SCREEN, "probe-run": RUN, "probe-refresh-tests": "15",
        "probe-renderer": "native-2d", "probe-flat-draws": "0", "probe-spatial-density": "1.0",
        "probe-spatial-font-scale": "1.0", "probe-spatial-orientation": "1", "probe-spatial-error": "none",
        "probe-spatial-motion": "off", **{"probe-spatial-" + key: "0" for key in ("engines", "windows", "frames", "meshes", "pending", "pool")}}
    node(root, "[0,0][2,2]", **{"content-desc": ";".join(key + ":" + item for key, item in metrics.items())})
    node(root, "[2,0][4,2]", **{"resource-id": "theme-lifecycle-state",
        "content-desc": ";".join(key + ":" + item for key, item in value.items())})
    node(root, "[56,100][320,600]", **{"resource-id": "workspace-content", "scrollable": "true"})
    return tree


def preview():
    return observation(mode="SYSTEM", background="fff5f7f9", foreground="ff1b2930",
                       **{"status-light": "true", "navigation-light": "true"})


def expected_preview(**updates):
    return dict(mode="SYSTEM", saved="DARK", os_night="no", app_night="yes", saved_hash="c" * 64, **updates)


def window_dump(*, uid=UID, kind="BASE_APPLICATION", package=None, component=None, duplicate=False):
    package = package or life.PACKAGE
    component = component or life.ACTIVITY
    block = ("  Window #1 Window{1234 u0 " + component + "}:\n"
             "    mOwnerUid=" + str(uid) + " showForAllUsers=false package=" + package + " appop=NONE\n"
             "    mAttrs={(0,0)(fillxfill) sim=ADJUST_NOTHING ty=" + kind + " fmt=TRANSLUCENT}\n")
    return ("WINDOW MANAGER WINDOWS (dumpsys window windows)\n"
            "  Window #0 Window{aaaa u0 NavigationBar0}:\n"
            "    mOwnerUid=1000 showForAllUsers=false package=com.android.systemui appop=NONE\n"
            "    mAttrs={(0,0)(fillxfill) ty=NAVIGATION_BAR}\n" + block + (block.replace("#1", "#2") if duplicate else ""))


class MarkerTests(unittest.TestCase):
    def test_plain_compose_marker_needs_no_decorative_draw_counter(self):
        value = life.lifecycle_marker(frame(), SESSION, RUN, 1.0)
        self.assertEqual(value["pid"], "1234")
        self.assertEqual(value["window"], 7)

    def test_stale_run_session_and_foreign_root_never_pass(self):
        for updates in ({"run": "e" * 32}, {"session": "f" * 32}):
            with self.subTest(updates=updates):
                self.assertIsNone(life.lifecycle_marker(frame(observation(**updates)), SESSION, RUN, 1.0))
        tree = frame()
        tree[0].set("package", "another.app")
        self.assertIsNone(life.lifecycle_marker(tree, SESSION, RUN, 1.0))

    def test_duplicate_marker_or_missing_field_is_rejected(self):
        tree = frame()
        tree[0].append(deepcopy(tree[0][1]))
        with self.assertRaisesRegex(AssertionError, "Duplicate"):
            life.lifecycle_marker(tree, SESSION, RUN, 1.0)
        value = observation()
        del value["app-night"]
        with self.assertRaisesRegex(AssertionError, "incomplete"):
            life.lifecycle_marker(frame(value), SESSION, RUN, 1.0)

    def test_permission_and_invalid_font_are_not_success(self):
        for updates in ({"overlay-capability": "true"}, {"overlay-permission": "true"}, {"font-scale": "2.0"}):
            with self.subTest(updates=updates), self.assertRaises(AssertionError):
                life.lifecycle_marker(frame(observation(**updates)), SESSION, RUN, 1.0)

    def test_opposite_preview_requires_real_independent_observation_and_saved_resources(self):
        self.assertTrue(life.matching_state(preview(), **expected_preview()))
        wrong = ({"system-night": "yes"}, {"system-night": "unknown-NO_DISPLAY"},
                 {"background": "ff101a1f", "foreground": "ffe7eff2"}, {"app-night": "no"},
                 {"saved-mode": "SYSTEM"}, {"saved-hash": "e" * 64}, {"status-light": "false"},
                 {"native-splash": "fff5f7f9"})
        for updates in wrong:
            with self.subTest(updates=updates):
                self.assertFalse(life.matching_state({**preview(), **updates}, **expected_preview()))

    def test_cold_start_checks_actual_launch_resource_colors(self):
        args = dict(mode="DARK", saved="DARK", os_night="no", app_night="yes", cold=True)
        self.assertTrue(life.matching_state(observation(), **args))
        self.assertFalse(life.matching_state(observation(**{"launch-window": "fff5f7f9"}), **args))
        self.assertFalse(life.matching_state(observation(**{"launch-night": "no"}), **args))

    def test_actual_case_rejects_recreated_owner_process_and_window(self):
        initial = life.lifecycle_marker(frame(), SESSION, RUN, 1.0)
        for key, changed in (("activity", "00000000-0000-0000-0000-000000000009"),
                             ("owner", "00000000-0000-0000-0000-000000000009"),
                             ("editor-owner", "00000000-0000-0000-0000-000000000009"), ("pid", "1235")):
            tree = frame(observation(**{key: changed}))
            case = life._LifecycleCase(SimpleNamespace(tree=lambda: tree), SESSION, RUN, 1.0,
                                       time.monotonic() + 60, Path("."), initial)
            with self.subTest(key=key), self.assertRaisesRegex(AssertionError, "replaced"):
                case.tree()
        tree = frame()
        tree.set("active-window-id", "8")
        case = life._LifecycleCase(SimpleNamespace(tree=lambda: tree), SESSION, RUN, 1.0,
                                   time.monotonic() + 60, Path("."), initial)
        with self.assertRaisesRegex(AssertionError, "replaced"):
            case.tree()


class ChoiceAndInputTests(unittest.TestCase):
    def make_choice(self, **changes):
        tree = frame()
        row = node(tree[0][-1], "[70,210][300,268]", **{"checkable": "true", "checked": "true",
                   "clickable": "false", "selected": "false", **changes})
        node(row, "[100,216][280,254]", text="Как в системе")
        return tree, row

    def test_real_merged_radio_checked_state_is_observed(self):
        tree, row = self.make_choice()
        self.assertIs(life.checked_choice(tree, "Как в системе", 48), row)
        row.remove(row[0])
        row.set("text", "Как в системе")
        self.assertIs(life.checked_choice(tree, "Как в системе", 48), row)

    def test_actual_selected_path_respects_the_shared_scroll_limit(self):
        tree, row = self.make_choice()
        initial = life.lifecycle_marker(tree, SESSION, RUN, 1.0)
        probe = SimpleNamespace(tree=lambda: tree, wait_for=lambda read, message: read(),
            _semantic_scroll_callback=lambda *args: lambda *coords: self.fail("Visible choice must not scroll"))
        case = life._LifecycleCase(probe, SESSION, RUN, 1.0, time.monotonic() + 60, Path("."), initial)
        # Calls the actual shared reveal_in_list, including its <=20 admission;
        # the old max_swipes=24 draft fails here before any observation or input.
        case.selected("Как в системе")
        self.assertIs(life.checked_choice(tree, "Как в системе", 48), row)

    def test_actual_tap_path_uses_shared_admission_and_exactly_one_tap(self):
        tree, row = self.make_choice(checked="false", clickable="true")
        initial = life.lifecycle_marker(tree, SESSION, RUN, 1.0)
        taps = []
        probe = SimpleNamespace(tree=lambda: tree, wait_for=lambda read, message: read(), tap_node=taps.append,
            _semantic_scroll_callback=lambda *args: lambda *coords: self.fail("Visible choice must not scroll"))
        case = life._LifecycleCase(probe, SESSION, RUN, 1.0, time.monotonic() + 60, Path("."), initial)
        case.tap("Как в системе")
        self.assertEqual(len(taps), 1)
        self.assertEqual(taps[0].get("bounds"), row.get("bounds"))
        self.assertEqual(case.targets[0]["minimum_pixels"], 48)

    def test_selected_only_unchecked_radio_and_wrong_class_fail(self):
        for updates in ({"checked": "false", "selected": "true"}, {"checkable": "false"}, {"class": "android.widget.Switch"}):
            with self.subTest(updates=updates):
                tree, _ = self.make_choice(**updates)
                self.assertIsNone(life.checked_choice(tree, "Как в системе", 48))

    def test_checked_parent_cannot_borrow_another_choice_label(self):
        tree, row = self.make_choice()
        node(row, "[100,255][280,267]", text="Светлая")
        self.assertIsNone(life.checked_choice(tree, "Как в системе", 48))

    def test_clipped_and_under_48dp_checked_rows_fail(self):
        tree, row = self.make_choice()
        row.set("bounds", "[70,80][300,138]")
        self.assertIsNone(life.checked_choice(tree, "Как в системе", 48))
        tree, row = self.make_choice()
        self.assertIsNone(life.checked_choice(tree, "Как в системе", 96))

    def test_checked_owner_cannot_borrow_outside_clipped_or_malformed_label(self):
        for bounds in ("[301,216][319,254]", "[250,216][310,254]", "[100,216][330,254]",
                       "[100,270][280,300]", "[100,216][100,254]", "[-1,216][200,254]", "", "malformed"):
            tree, row = self.make_choice()
            row[0].set("bounds", bounds)
            with self.subTest(bounds=bounds):
                self.assertIsNone(life.checked_choice(tree, "Как в системе", 48))

    def test_label_requires_owned_visible_ancestors_and_its_own_scroll_viewport(self):
        tree, row = self.make_choice()
        row[0].set("package", "foreign.app")
        self.assertIsNone(life.checked_choice(tree, "Как в системе", 48))
        for updates in ({"visible-to-user": "false"}, {"enabled": "false"},
                        {"package": "foreign.app"}, {"scrollable": "true"}):
            tree, row = self.make_choice()
            label = row[0]
            row.remove(label)
            intermediate = node(row, "[100,216][240,254]", **updates)
            intermediate.append(label)
            with self.subTest(updates=updates):
                self.assertIsNone(life.checked_choice(tree, "Как в системе", 48))

    def test_text_marker_cannot_replace_the_actual_editable_draft(self):
        tree = frame()
        editor = node(tree[0][-1], "[70,200][310,270]", text="THEME_DRAFT", editable="false")
        self.assertIsNone(life.native_draft(tree, "THEME_DRAFT"))
        editor.set("editable", "true")
        self.assertEqual(life.native_draft(tree, "THEME_DRAFT")["text"], "THEME_DRAFT")
        editor.set("text", "THEME")
        self.assertIsNone(life.native_draft(tree, "THEME_DRAFT"))


class WindowTests(unittest.TestCase):
    def test_exact_activity_window_is_counted(self):
        value = life.owned_windows(window_dump(), UID)
        self.assertEqual(value["windows"], [{"component": life.ACTIVITY, "type": "BASE_APPLICATION"}])

    def test_overlay_foreign_uid_and_other_component_are_rejected(self):
        for updates in ({"kind": "APPLICATION_OVERLAY"}, {"kind": "2038"}, {"uid": "10235"},
                        {"component": life.PACKAGE + "/.AnotherActivity"}):
            with self.subTest(updates=updates), self.assertRaises(AssertionError):
                life.owned_windows(window_dump(**updates), UID)

    def test_unknown_or_truncated_window_inventory_is_rejected(self):
        for output in ("", "DUMP TIMEOUT", window_dump().replace("mOwnerUid=10234", "mOwner=10234")):
            with self.subTest(output=output[:30]), self.assertRaises(AssertionError):
                life.owned_windows(output, UID)

    def test_starting_window_cannot_satisfy_settled_activity_count(self):
        output = window_dump(kind="APPLICATION_STARTING", component="Splash Screen " + life.PACKAGE)
        value = life.owned_windows(output, UID)
        self.assertEqual(value["windows"][0]["type"], "APPLICATION_STARTING")
        probe = SimpleNamespace(command=lambda *args, **kwargs: output,
                                wait_for=lambda read, message: read())
        self.assertIsNone(life.window_receipt(probe, UID, 1))

    def test_duplicate_activity_windows_cannot_satisfy_exact_count(self):
        probe = SimpleNamespace(command=lambda *args, **kwargs: window_dump(duplicate=True),
                                wait_for=lambda read, message: read())
        self.assertIsNone(life.window_receipt(probe, UID, 1))


class SettingsProbe:
    def __init__(self, night="no", scale="1.0"):
        self.night, self.scale = night, scale
        self.calls = []
        self.fail_night_restore = False
        self.ignore_scale_restore = False

    def command(self, *args):
        self.calls.append(args)
        if args == ("shell", "cmd", "uimode", "night"):
            return "Night mode: " + self.night + "\n"
        if args[:4] == ("shell", "cmd", "uimode", "night"):
            if self.fail_night_restore and args[4] == "no":
                raise RuntimeError("night restoration failed")
            self.night = args[4]
            return "Night mode: " + self.night
        if args == ("shell", "settings", "get", "system", "font_scale"):
            return self.scale + "\n"
        if args[:5] == ("shell", "settings", "put", "system", "font_scale"):
            if not self.ignore_scale_restore:
                self.scale = args[5]
            return ""
        raise AssertionError("Unexpected test command: " + repr(args))


class RestorationTests(unittest.TestCase):
    def test_no_unowned_transport_can_change_settings(self):
        probe = SettingsProbe()
        probe.read_tree = lambda: frame()
        with self.assertRaisesRegex(AssertionError, "owned persistent"):
            with life.restore_lifecycle_settings(probe, {}, lambda *_: {"restored": True}):
                self.fail("Unowned context was entered")
        self.assertEqual(probe.calls, [])

    def test_auto_or_unknown_policy_is_not_guessed_or_mutated(self):
        probe = SettingsProbe(night="auto")
        with patch.object(life, "_owned_emulator", return_value={"avd": "owned"}):
            with self.assertRaisesRegex(AssertionError, "explicit yes/no"):
                with life.restore_lifecycle_settings(probe, {}, lambda *_: self.fail("No restore needed")):
                    self.fail("Auto policy was changed")
        self.assertEqual(probe.calls, [("shell", "cmd", "uimode", "night")])
        with self.assertRaises(AssertionError):
            life.strict_night_setting("Permission denied")

    def test_primary_failure_still_restores_both_settings_and_application(self):
        probe, receipt, restored = SettingsProbe(), {}, []
        def application(night, scale):
            restored.append((night, scale))
            return {"restored": True}
        with patch.object(life, "_owned_emulator", return_value={"avd": "owned"}):
            with self.assertRaisesRegex(AssertionError, "real native failure"):
                with life.restore_lifecycle_settings(probe, receipt, application):
                    probe.night, probe.scale = "yes", "2.0"
                    raise AssertionError("real native failure")
        self.assertEqual(restored, [("no", 1.0)])
        self.assertTrue(receipt["restored"])
        self.assertEqual((probe.night, probe.scale), ("no", "1.0"))

    def test_one_cleanup_error_does_not_skip_other_cleanup_or_hide_primary_error(self):
        probe, receipt, restored = SettingsProbe(), {}, []
        error = AssertionError("primary native failure")
        with patch.object(life, "_owned_emulator", return_value={"avd": "owned"}):
            with self.assertRaisesRegex(AssertionError, "primary native failure"):
                with life.restore_lifecycle_settings(probe, receipt,
                        lambda *args: restored.append(args) or {"restored": True}):
                    probe.night, probe.scale, probe.fail_night_restore = "yes", "2.0", True
                    raise error
        self.assertEqual(probe.scale, "1.0")
        self.assertEqual(restored, [("no", 1.0)])
        self.assertFalse(receipt["restored"])
        self.assertTrue(any("restoration failed" in note for note in error.__notes__))

    def test_false_readback_or_unproved_application_restoration_fails_gate(self):
        for broken in ("font", "application"):
            probe, receipt = SettingsProbe(), {}
            with self.subTest(broken=broken), patch.object(life, "_owned_emulator", return_value={"avd": "owned"}):
                with self.assertRaisesRegex(AssertionError, "restoration failed"):
                    with life.restore_lifecycle_settings(probe, receipt, lambda *_: {"restored": broken != "application"}):
                        if broken == "font":
                            probe.scale, probe.ignore_scale_restore = "2.0", True
                self.assertFalse(receipt["restored"])


if __name__ == "__main__":
    unittest.main()
