"""Exercise the actual detail-navigation verifier with explicit native XML fixtures.

These unit fixtures make no emulator or rendered-image claim. Native acceptance
still requires the separate report written by the real Windows Android run.
"""
import ast
from copy import deepcopy
from pathlib import Path
import os
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import automation_ui_probe as automation
import navigation_detail_probe as details
from native_label_target import label_target
from persistent_ui import FrameReader
from profile_ui_probe import ProfileProbe
import profile_scroll

PACKAGE = details.PACKAGE
USER = "synthetic-business-00000000-0000-0000-0000-000000000001"


def node(parent, *, bounds="[0,0][320,720]", **values):
    return ET.SubElement(parent, "node", {"package": PACKAGE, "bounds": bounds,
        "enabled": "true", "visible-to-user": "true", **values})


def frame(page="strategy", *, window=7, fields=None, menu=True):
    tree = ET.Element("hierarchy", {"root-window-present": "true", "root-window-focused": "true",
        "active-window-id": str(window), "display-width": "320", "display-height": "720"})
    root = node(tree)
    values = {"navigation-detail": "business-strategy/ready", "transport": "synthetic", "page": page,
              "requests": "2", "writes": "0", "contract-errors": "0",
              "prefs": "AURORA,COMFORT,LIVE,true,false,true,true,false", "user": USER}
    values.update(fields or {})
    node(root, **{"resource-id": "navigation-detail-page",
                  "content-desc": ";".join(key + ":" + value for key, value in values.items())})
    if menu:
        node(root, bounds="[0,10][48,58]", **{"resource-id": "navigation-menu-open",
             "content-desc": "Открыть меню", "clickable": "true", "focusable": "true"})
    return tree


def menu_frame(*, selected=True, checked=False, clickable=True):
    tree = frame()
    root = tree[0]
    node(root, bounds="[0,0][300,700]", **{"resource-id": "navigation-panel"})
    node(root, bounds="[240,10][288,58]", **{"resource-id": "navigation-menu-close",
         "content-desc": "Закрыть меню", "clickable": "true", "focusable": "true"})
    owner = node(root, bounds="[0,70][300,700]", **{"resource-id": "navigation-panel-content", "scrollable": "true"})
    node(owner, bounds="[10,100][290,160]", **{"resource-id": "navigation-workspace-strategies",
         "text": "Стратегия", "selected": str(selected).lower(), "checked": str(checked).lower(),
         "clickable": str(clickable).lower(), "focusable": "true"})
    return tree


def dialog_frame(*, window=9, title=True, size=48):
    tree = frame(window=window, menu=False)
    root = tree[0]
    root.clear()
    root.attrib.update({"package": PACKAGE, "bounds": "[0,0][320,720]", "enabled": "true", "visible-to-user": "true"})
    if title:
        node(root, bounds="[20,30][300,90]", text="Изменения стратегии")
    node(root, bounds=f"[20,300][300,{300 + size}]", **{"text": "Продолжить редактирование",
         "class": "android.widget.Button", "clickable": "true", "focusable": "true"})
    return tree


def wide_frame():
    tree = frame(menu=False)
    tree.set("display-width", "960")
    tree.set("display-height", "1600")
    root = tree[0]
    root.set("bounds", "[0,0][960,1600]")
    node(root, bounds="[256,100][960,1600]", **{"resource-id": "workspace-content", "scrollable": "true"})
    metrics = {"probe-refresh-tests": "15", "probe-screen": "business-strategy", "probe-scenario": "ready",
               "probe-renderer": "native-2d", "probe-flat-draws": "0", "probe-spatial-density": "1",
               "probe-spatial-font-scale": "2", "probe-spatial-orientation": "1", "probe-spatial-error": "none",
               "probe-spatial-motion": "Off"}
    metrics.update({"probe-spatial-" + key: "0" for key in ("engines", "windows", "frames", "meshes", "pending", "pool")})
    node(root, bounds="[0,0][960,80]", **{"content-desc": ";".join(key + ":" + value for key, value in metrics.items())})
    rail = node(root, bounds="[0,80][256,1600]", **{"resource-id": "analyst-side-rail"})
    for index, (name, label) in enumerate((("home", "Главная"), ("actions", "Решения"), ("profile", "Настройки"))):
        top = 200 + index * 160
        node(rail, bounds=f"[10,{top}][246,{top + 136}]", **{"resource-id": "rail-destination-" + name,
             "text": label, "clickable": "true", "focusable": "true", "selected": str(name == "profile").lower()})
    return tree


class NativeFrames:
    def __init__(self, value):
        self.value = value
        self.reads = 0
        self.taps = []
        self.reveals = []

    def tree(self):
        self.reads += 1
        return deepcopy(self.value(self.reads) if callable(self.value) else self.value)

    def wait_for(self, predicate, message):
        for _ in range(16):
            value = predicate()
            if value is not None and value is not False:
                return value
        raise AssertionError(message)

    def tap_node(self, target):
        self.taps.append(dict(target.attrib))
        if target.get("resource-id") == "navigation-menu-open":
            self.value = menu_frame()

    def reveal_resource(self, resource, area, direction="end", for_capture=False, minimum_size=(0, 0)):
        self.reveals.append((resource, area, direction, for_capture, minimum_size))

    def label_tap_target(self, label, area, direction="end", *, max_swipes=10):
        # Keep the real shared admission boundary even in isolated dialog tests.
        profile_scroll._validate_request(area, direction, max_swipes, 12)
        target = label_target(self.tree(), label)
        if target is None:
            raise AssertionError("No genuine native action")
        return target


def case(probe):
    value = details._DetailNavigationCase(probe, 2.0)
    value.window = 7
    value.minimum = 48
    value.user = USER
    return value


class DetailMarkerTests(unittest.TestCase):
    def test_requires_actual_owned_ready_synthetic_read_only_observation(self):
        observed = details.detail_marker(frame())
        self.assertEqual(observed["page"], "strategy")
        self.assertEqual(observed["user"], USER)
        for fields in ({"writes": "1"}, {"contract-errors": "1"}, {"requests": "bad"},
                       {"page": "unknown"}, {"transport": "network"}, {"user": "real-user"},
                       {"prefs": "not-a-real-preference-state"}):
            with self.subTest(fields=fields), self.assertRaises(AssertionError):
                details.detail_marker(frame(fields=fields))
        self.assertIsNone(details.detail_marker(frame(fields={"requests": "0"})))

    def test_duplicate_and_foreign_marker_cannot_prove_the_destination(self):
        tree = frame()
        tree[0].append(deepcopy(tree[0][0]))
        with self.assertRaises(AssertionError):
            details.detail_marker(tree)
        tree = frame()
        tree[0][0].set("package", "foreign.app")
        self.assertIsNone(details.detail_marker(tree))
        tree = frame()
        tree[0][0].set("content-desc", tree[0][0].get("content-desc") + ";page:strategy")
        with self.assertRaises(AssertionError):
            details.detail_marker(tree)


class DetailCounterSettlementTests(unittest.TestCase):
    def counters(self, detail, business, *, fields=None, business_errors=0):
        tree = frame(fields={"requests": str(detail), **(fields or {})}, menu=False)
        node(tree[0], bounds="[0,0][320,80]", **{
            "resource-id": "business-probe-marker",
            "content-desc": "business-probe:strategy/ready;transport:synthetic;requests:"
                + str(business) + ";contract-errors:" + str(business_errors)
                + ";scenario-compares:0;navigation:none;message-posts:0;"
                  "message-request-id:none;by-request-gets:0;recovered-request-id:none"})
        return tree

    def probe(self, frames):
        probe = NativeFrames(lambda reads: frames[min(reads - 1, len(frames) - 1)])
        probe.wait_for = lambda predicate, message: ProfileProbe.wait_for(probe, predicate, message)
        return probe

    def clock(self):
        now = [0.0]
        def sleep(seconds):
            now[0] += seconds
        return now, sleep

    def test_async_counter_views_must_converge_before_acceptance(self):
        for early in ((6, 7), (7, 6)):
            probe = self.probe([self.counters(*early), self.counters(7, 7)])
            now, sleep = self.clock()
            with self.subTest(early=early), patch("profile_ui_probe.time.monotonic", lambda: now[0]), \
                    patch("profile_ui_probe.time.sleep", sleep):
                result = case(probe).observed("strategy")
            self.assertEqual(result["requests"], 7)
            self.assertEqual(probe.reads, 2)
            self.assertEqual(probe.taps, [])

    def test_persistent_counter_disagreement_fails_at_the_original_deadline(self):
        probe = self.probe([self.counters(6, 7)])
        now, sleep = self.clock()
        with patch("profile_ui_probe.time.monotonic", lambda: now[0]), \
                patch("profile_ui_probe.time.sleep", sleep), self.assertRaises(AssertionError):
            case(probe).observed("strategy")
        self.assertGreaterEqual(now[0], 12)
        self.assertLessEqual(now[0], 12.21)
        self.assertGreater(probe.reads, 1)
        self.assertEqual(probe.taps, [])

    def test_stale_agreement_cannot_override_a_newer_observed_request_count(self):
        probe = self.probe([self.counters(6, 7), self.counters(6, 6), self.counters(7, 7)])
        now, sleep = self.clock()
        with patch("profile_ui_probe.time.monotonic", lambda: now[0]), patch("profile_ui_probe.time.sleep", sleep):
            result = case(probe).observed("strategy")
        self.assertEqual(result["requests"], 7)
        self.assertEqual(probe.reads, 3)
        self.assertEqual(probe.taps, [])

    def test_a_forever_stale_equal_pair_remains_a_failure(self):
        probe = self.probe([self.counters(6, 7), self.counters(6, 6)])
        now, sleep = self.clock()
        with patch("profile_ui_probe.time.monotonic", lambda: now[0]), \
                patch("profile_ui_probe.time.sleep", sleep), self.assertRaises(AssertionError):
            case(probe).observed("strategy")
        self.assertGreaterEqual(now[0], 12)
        self.assertLessEqual(now[0], 12.21)

    def test_mutation_contract_failure_and_changed_user_still_fail_immediately(self):
        invalid = [self.counters(6, 7, fields={"writes": "1"}),
                   self.counters(6, 7, fields={"contract-errors": "1"}),
                   self.counters(6, 7, business_errors=1),
                   self.counters(6, 7, fields={"user": USER[:-1] + "2"})]
        for first in invalid:
            probe = self.probe([first, self.counters(7, 7)])
            now, sleep = self.clock()
            with self.subTest(marker=first[0][0].get("content-desc")), \
                    patch("profile_ui_probe.time.monotonic", lambda: now[0]), \
                    patch("profile_ui_probe.time.sleep", sleep), self.assertRaises(AssertionError):
                case(probe).observed("strategy")
            self.assertEqual(probe.reads, 1)
            self.assertEqual(now[0], 0)
            self.assertEqual(probe.taps, [])


class DetailMenuActionTests(unittest.TestCase):
    def test_old_detail_frame_without_menu_fails_the_actual_open_path(self):
        probe = NativeFrames(frame(menu=False))
        with self.assertRaisesRegex(AssertionError, "did not settle"):
            case(probe).open_menu()
        self.assertEqual(probe.taps, [])

    def test_waits_for_three_stable_frames_then_taps_once(self):
        def moving_then_settled(read):
            tree = frame()
            x = min(read, 3) * 2
            tree[0][1].set("bounds", f"[{x},10][{x + 48},58]")
            return tree
        probe = NativeFrames(moving_then_settled)
        result = case(probe).open_menu()
        self.assertEqual(result.get("resource-id"), "navigation-menu-close")
        self.assertEqual(len(probe.taps), 1)
        self.assertEqual(probe.taps[0]["bounds"], "[6,10][54,58]")
        self.assertGreaterEqual(probe.reads, 8)

    def test_permanently_moving_target_is_never_tapped(self):
        def moving(read):
            tree = frame()
            x = read % 3
            tree[0][1].set("bounds", f"[{x},10][{x + 48},58]")
            return tree
        probe = NativeFrames(moving)
        with self.assertRaises(AssertionError):
            case(probe).open_menu()
        self.assertEqual(probe.taps, [])

    def test_clipped_disabled_or_wrong_label_controls_are_rejected(self):
        for attribute, value in (("bounds", "[280,10][328,58]"), ("bounds", "[0,10][47,58]"),
                                 ("enabled", "false"), ("package", "foreign.app"),
                                 ("content-desc", "Назад"), ("clickable", "false")):
            tree = frame()
            tree[0][1].set(attribute, value)
            probe = NativeFrames(tree)
            with self.subTest(attribute=attribute, value=value), self.assertRaises(AssertionError):
                case(probe).open_menu()
            self.assertEqual(probe.taps, [])

    def test_wrong_active_window_never_reuses_a_menu_rectangle(self):
        probe = NativeFrames(frame(window=8))
        with self.assertRaises(AssertionError):
            case(probe).open_menu()
        self.assertEqual(probe.taps, [])

    def test_selected_observation_accepts_native_nonclickable_but_not_checked_only(self):
        probe = NativeFrames(menu_frame(clickable=False))
        value = case(probe).menu_item("strategy", selected=True, touch=False)
        self.assertEqual(value.get("selected"), "true")
        self.assertEqual(probe.reveals[0][0:3], ("navigation-primary-home", "navigation-panel-content", "start"))
        self.assertEqual(probe.reveals[1][0:3], ("navigation-workspace-strategies", "navigation-panel-content", "end"))
        bad = NativeFrames(menu_frame(selected=False, checked=True))
        with self.assertRaises(AssertionError):
            case(bad).menu_item("strategy", selected=True, touch=False)


class DirtyConfirmationTests(unittest.TestCase):
    def test_real_separate_confirmation_is_required(self):
        result = case(NativeFrames(dialog_frame())).dirty_dialog()
        self.assertEqual(result["window_id"], 9)
        self.assertEqual(result["title_bounds"], [20, 30, 300, 90])

    def test_actual_destination_bypass_is_rejected_before_any_confirmation_tap(self):
        probe = NativeFrames(frame(page="markets"))
        with self.assertRaisesRegex(AssertionError, "bypassed"):
            case(probe).dirty_dialog()
        self.assertEqual(probe.taps, [])

    def test_inline_title_foreign_window_and_missing_title_do_not_pass(self):
        foreign = dialog_frame()
        foreign[0].set("package", "foreign.app")
        for tree in (dialog_frame(window=7), dialog_frame(title=False), foreign):
            with self.subTest(tree=ET.tostring(tree)), self.assertRaises(AssertionError):
                case(NativeFrames(tree)).dirty_dialog()

    def test_cancel_action_uses_the_dialog_window_once(self):
        probe = NativeFrames(dialog_frame())
        result = case(probe).dialog_action({"window_id": 9}, "Продолжить редактирование")
        self.assertEqual(result["window_id"], 9)
        self.assertEqual(len(probe.taps), 1)

    def test_clipped_or_replaced_confirmation_never_navigates(self):
        for tree in (dialog_frame(size=47), dialog_frame(window=10)):
            probe = NativeFrames(tree)
            with self.subTest(tree=ET.tostring(tree)), self.assertRaises(AssertionError):
                case(probe).dialog_action({"window_id": 9}, "Продолжить редактирование")
            self.assertEqual(probe.taps, [])


class ScrollBoundaryFrames(NativeFrames):
    """Real ProfileProbe reveal/tap paths, with only native frames/input simulated."""
    def __init__(self, value):
        super().__init__(value)
        self.page = "appearance"
        self.preferences = "AURORA,COMFORT,LIVE,true,false,true,true,false"

    def _semantic_scroll_callback(self, area, direction):
        def unexpected(*coordinates):
            raise AssertionError("This visible contract fixture must not need a native scroll")
        return unexpected

    def reveal(self, text, area="profile-content", direction="end", *, max_swipes=10):
        return ProfileProbe.reveal(self, text, area, direction, max_swipes=max_swipes)

    def label_tap_target(self, label, area, direction="end", *, max_swipes=10):
        return ProfileProbe.label_tap_target(self, label, area, direction, max_swipes=max_swipes)

    def tap(self, label, area="profile-content", direction="end", *, max_swipes=10):
        return ProfileProbe.tap(self, label, area, direction, max_swipes=max_swipes)

    def show_page(self, page):
        self.page = page
        # Navigation/rollback is intentionally synthetic here; this test covers
        # the real helper-call contract, not production Appearance acceptance.
        self.preferences = "AURORA,COMFORT,LIVE,true,false,true,true,false"
        self.update_page()

    def update_page(self):
        tree = frame(self.page, fields={"prefs": self.preferences}, menu=False)
        # observed() requires the real business parser as well as the detail
        # marker. Keep both views of this synthetic transport in the same frame.
        node(tree[0], bounds="[0,0][320,80]", **{
            "resource-id": "business-probe-marker",
            "content-desc": "business-probe:strategy/ready;transport:synthetic;requests:2;"
                "contract-errors:0;scenario-compares:0;navigation:none;"
                "message-posts:0;message-request-id:none;by-request-gets:0;recovered-request-id:none"})
        viewport = node(tree[0], bounds="[56,100][320,700]",
                        **{"resource-id": "workspace-content", "scrollable": "true"})
        node(viewport, bounds="[70,110][310,165]", text="Единый стиль · движение и удобство")
        node(viewport, bounds="[70,180][300,236]", text="Компактно", clickable="true",
             focusable="true", **{"class": "android.widget.Button"})
        node(viewport, bounds="[70,250][310,310]", text="Текущие сохранённые настройки")
        self.value = tree

    def tap_node(self, target):
        super().tap_node(target)
        if target.get("text") == "Компактно":
            self.preferences = "AURORA,COMPACT,LIVE,true,false,true,true,false"
            self.update_page()


class DetailScrollBoundaryTests(unittest.TestCase):
    def test_actual_screen_anchor_uses_the_real_profile_scroll_admission(self):
        anchors = {"markets": "Ваши инструменты", "notifications": "Настроить события",
                   "appearance": "Единый стиль · движение и удобство", "library": "Название, заметка или источник"}
        for page, label in anchors.items():
            tree = frame(page, menu=False)
            viewport = node(tree[0], bounds="[56,100][320,700]",
                            **{"resource-id": "workspace-content", "scrollable": "true"})
            node(viewport, bounds="[70,180][310,240]", text=label)
            probe = ScrollBoundaryFrames(tree)
            with self.subTest(page=page), patch.object(profile_scroll, "_validate_request", wraps=profile_scroll._validate_request) as admission:
                case(probe).screen_anchor(page)
                admission.assert_called_once_with("workspace-content", "start", 20, 12)
                self.assertEqual(probe.taps, [])

    def test_actual_dialog_action_uses_real_reveal_settlement_and_one_native_tap(self):
        probe = ScrollBoundaryFrames(dialog_frame())
        value = case(probe)
        dialog = value.dirty_dialog()
        with patch.object(profile_scroll, "_validate_request", wraps=profile_scroll._validate_request) as admission:
            receipt = value.dialog_action(dialog, "Продолжить редактирование")
            admission.assert_called_once_with("workspace-content", "end", 20, 12)
        self.assertEqual(receipt["window_id"], 9)
        self.assertEqual(len(probe.taps), 1)
        self.assertEqual(probe.taps[0]["bounds"], "[20,300][300,348]")

    def test_appearance_boundary_fixture_requires_matching_business_evidence(self):
        for invalid in ("missing", "different_requests", "contract_error"):
            probe = ScrollBoundaryFrames(frame())
            probe.show_page("appearance")
            marker = next(node for node in probe.value.iter("node")
                          if node.get("resource-id") == "business-probe-marker")
            if invalid == "missing":
                probe.value[0].remove(marker)
            elif invalid == "different_requests":
                marker.set("content-desc", marker.get("content-desc").replace("requests:2;", "requests:3;"))
            else:
                marker.set("content-desc", marker.get("content-desc").replace("contract-errors:0;", "contract-errors:1;"))
            with self.subTest(invalid=invalid), self.assertRaises(AssertionError):
                case(probe).observed("appearance")
            self.assertEqual(probe.taps, [])

    def test_actual_appearance_exit_calls_real_tap_and_return_label_boundaries(self):
        probe = ScrollBoundaryFrames(frame())
        value = case(probe)
        value.choose = probe.show_page
        value.capture = lambda _: {}
        with patch.object(profile_scroll, "_validate_request", wraps=profile_scroll._validate_request) as admission:
            receipt = value.appearance_exit()
            self.assertEqual([call.args for call in admission.call_args_list], [
                ("workspace-content", "end", 20, 12), ("workspace-content", "start", 20, 12),
                ("workspace-content", "end", 20, 12)])
        self.assertEqual(len(probe.taps), 1)
        self.assertTrue(receipt["cancelled_draft_did_not_reappear"])
        self.assertEqual(probe.page, "strategy")


class WideGeometryTests(unittest.TestCase):
    def test_actual_portrait_rail_accepts_plain_native_screen_without_canvas_draws(self):
        result = details.wide_rail_frame(wide_frame(), 2.0)
        self.assertEqual((result["width"], result["height"], result["width_dp"]), (960, 1600, 960))
        self.assertEqual([row["selected"] for row in result["targets"]], [False, False, True])

    def test_missing_rail_and_checked_only_selection_cannot_prove_wide_navigation(self):
        missing = wide_frame()
        missing[0].remove(missing[0][-1])
        self.assertIsNone(details.wide_rail_frame(missing, 2.0))
        checked = wide_frame()
        checked[0][-1][-1].set("selected", "false")
        checked[0][-1][-1].set("checked", "true")
        self.assertIsNone(details.wide_rail_frame(checked, 2.0))

    def test_phone_width_or_visible_phone_controls_cannot_pass_as_wide(self):
        narrow = wide_frame()
        narrow.set("display-width", "800")
        narrow[0].set("bounds", "[0,0][800,1600]")
        narrow[0][1].set("bounds", "[256,100][800,1600]")
        narrow[0][2].set("bounds", "[0,0][800,80]")
        with self.assertRaisesRegex(AssertionError, "breakpoint"):
            details.wide_rail_frame(narrow, 2.0)
        for resource in ("navigation-menu-open", "analyst-bottom-bar", "navigation-panel"):
            tree = wide_frame()
            node(tree[0], bounds="[0,0][1,1]", **{"resource-id": resource, "enabled": "false"})
            with self.subTest(resource=resource), self.assertRaises(AssertionError):
                details.wide_rail_frame(tree, 2.0)

    def test_target_outside_rail_and_wrong_font_are_rejected(self):
        tree = wide_frame()
        tree[0][-1][0].set("bounds", "[250,200][400,336]")
        with self.assertRaisesRegex(AssertionError, "outside"):
            details.wide_rail_frame(tree, 2.0)
        self.assertIsNone(details.wide_rail_frame(wide_frame(), 1.0))


class DisplayCommands(NativeFrames):
    def __init__(self, *, overrides=False):
        super().__init__(frame())
        self.display = {"size": {"Physical": "320x640"}, "density": {"Physical": "160"}}
        if overrides:
            self.display["size"]["Override"] = "360x720"
            self.display["density"]["Override"] = "180"
        self.scale = "2.0"
        self.avd = "analyst-install-" + str(os.getpid()) + "-1"
        self.avd_output = None
        self.qemu = "1"
        self.api = "37"
        self.commands = []
        self.failed_set = None
        self.failed_restore = None
        self.read_tree = FrameReader(None).tree

    def device(self, *args, timeout=15):
        return SimpleNamespace(returncode=0, stdout=self.command(*args, timeout=timeout), stderr="")

    def command(self, *args, timeout=15):
        self.commands.append(args)
        if args == ("emu", "avd", "name"):
            return self.avd_output if self.avd_output is not None else self.avd + "\nOK\n"
        if args[:3] == ("shell", "getprop", "ro.kernel.qemu"):
            return self.qemu + "\n"
        if args[:3] == ("shell", "getprop", "ro.build.version.sdk"):
            return self.api + "\n"
        if args[:2] == ("shell", "wm"):
            setting = args[2]
            if len(args) == 3:
                return "\n".join(key + " " + setting + ": " + value for key, value in self.display[setting].items()) + "\n"
            value = args[3]
            if self.failed_restore == setting and value in {"reset", "180", "360x720"}:
                raise OSError("restore " + setting)
            if value == "reset":
                self.display[setting].pop("Override", None)
            else:
                self.display[setting]["Override"] = value
            if self.failed_set == setting:
                self.failed_set = None
                raise RuntimeError("transport error after applied " + setting)
            return ""
        if args == ("shell", "settings", "get", "system", "font_scale"):
            return self.scale + "\n"
        if args[:5] == ("shell", "settings", "put", "system", "font_scale"):
            self.scale = args[5]
            return ""
        raise AssertionError("Unreviewed display command: " + repr(args))

    def tree(self):
        tree = frame()
        width, height = self.display["size"].get("Override", self.display["size"]["Physical"]).split("x")
        tree.set("display-width", width)
        tree.set("display-height", height)
        return tree


class WideDisplayOwnershipTests(unittest.TestCase):
    def test_owned_identity_accepts_only_console_whitespace_and_ack_framing(self):
        for attempt in (1, 2):
            name = "analyst-install-" + str(os.getpid()) + "-" + str(attempt)
            for output in (name + "\n", name + "\r\nOK\r\n",
                           "\r\n " + name + " \r\n\r\nOK\r\n\r\n",
                           "OK\n\n" + name + "\nOK\n"):
                probe = DisplayCommands(overrides=True)
                probe.avd_output = output
                before = deepcopy(probe.display)
                receipt = {}
                with self.subTest(attempt=attempt, output=repr(output)):
                    with details.wide_emulator_viewport(probe, receipt):
                        self.assertEqual(probe.display["size"]["Override"], "960x1600")
                        self.assertEqual(receipt["owner"]["avd"], name)
                        self.assertEqual(receipt["owner"]["owner_process_id"], os.getpid())
                    self.assertEqual(probe.display, before)
                    self.assertTrue(receipt["restored"])

    def test_duplicate_owned_identity_is_rejected_before_display_mutation(self):
        probe = DisplayCommands()
        probe.avd_output = probe.avd + "\n\n" + probe.avd + "\nOK\n"
        self.reject_identity_without_mutation(probe)

    def test_foreign_identity_with_valid_framing_is_rejected(self):
        probe = DisplayCommands()
        probe.avd_output = "\nanalyst-install-" + str(os.getpid() + 1) + "-1\n\nOK\n"
        self.reject_identity_without_mutation(probe)

    def test_owned_name_with_extra_payload_or_error_is_rejected(self):
        for extra in ("KO: unknown command", "unexpected", "analyst-install-999999999-1"):
            probe = DisplayCommands()
            probe.avd_output = probe.avd + "\n" + extra + "\nOK\n"
            with self.subTest(extra=extra):
                self.reject_identity_without_mutation(probe)

    def test_missing_identity_is_rejected_before_display_mutation(self):
        for output in ("", "\r\n \n", "\nOK\nOK\n"):
            probe = DisplayCommands()
            probe.avd_output = output
            with self.subTest(output=repr(output)):
                self.reject_identity_without_mutation(probe)

    def test_oversized_response_is_rejected_even_with_one_owned_payload(self):
        probe = DisplayCommands()
        probe.avd_output = probe.avd + "\nOK\n" + "\n" * 4096
        self.reject_identity_without_mutation(probe)

    def reject_identity_without_mutation(self, probe):
        before = deepcopy(probe.display)
        with self.assertRaises((AssertionError, ValueError)):
            with details.wide_emulator_viewport(probe, {}):
                self.fail("Ambiguous or unowned display was admitted")
        self.assertEqual(probe.display, before)
        self.assertFalse(any(command[:2] == ("shell", "wm") and len(command) == 4
                             for command in probe.commands))

    def test_owned_actual_emulator_is_required_before_any_display_mutation(self):
        for field, value in (("qemu", "0"), ("avd", "analyst-install-" + str(os.getpid() + 1) + "-1"), ("api", "36")):
            probe = DisplayCommands()
            setattr(probe, field, value)
            with self.subTest(field=field), self.assertRaises((AssertionError, ValueError)):
                with details.wide_emulator_viewport(probe, {}):
                    self.fail("Unowned display was admitted")
            self.assertFalse(any(command[:2] == ("shell", "wm") and len(command) == 4 for command in probe.commands))
        probe = DisplayCommands()
        probe.read_tree = lambda: frame()
        with self.assertRaises(AssertionError):
            with details.wide_emulator_viewport(probe, {}):
                self.fail("Unauthenticated frame source was admitted")

    def test_exact_prior_overrides_and_font_scale_are_restored_after_success(self):
        for overrides in (False, True):
            probe = DisplayCommands(overrides=overrides)
            before = deepcopy(probe.display)
            receipt = {}
            with details.wide_emulator_viewport(probe, receipt):
                self.assertEqual(probe.display["size"]["Override"], "960x1600")
                self.assertEqual(probe.display["density"]["Override"], "160")
                probe.scale = "1.0"
            self.assertEqual(probe.display, before)
            self.assertEqual(probe.scale, "2.0")
            self.assertTrue(receipt["restored"])
            self.assertEqual(receipt["before"], receipt["after"])

    def test_partially_applied_override_is_restored_before_propagating_transport_error(self):
        probe = DisplayCommands(overrides=True)
        before = deepcopy(probe.display)
        probe.failed_set = "density"
        receipt = {}
        with self.assertRaisesRegex(RuntimeError, "after applied"):
            with details.wide_emulator_viewport(probe, receipt):
                self.fail("Partially failed environment should not run the case")
        self.assertEqual(probe.display, before)
        self.assertTrue(receipt["restored"])

    def test_case_failure_still_restores_every_display_value(self):
        probe = DisplayCommands(overrides=True)
        before = deepcopy(probe.display)
        receipt = {}
        original = AssertionError("actual dirty confirmation failed")
        with self.assertRaises(AssertionError) as caught:
            with details.wide_emulator_viewport(probe, receipt):
                probe.scale = "1.0"
                raise original
        self.assertIs(caught.exception, original)
        self.assertEqual(probe.display, before)
        self.assertEqual(probe.scale, "2.0")
        self.assertTrue(receipt["restored"])

    def test_cleanup_failure_preserves_primary_failure_and_cannot_claim_restore(self):
        probe = DisplayCommands(overrides=True)
        probe.failed_restore = "density"
        receipt = {}
        original = AssertionError("actual dirty confirmation failed")
        with self.assertRaises(AssertionError) as caught:
            with details.wide_emulator_viewport(probe, receipt):
                raise original
        self.assertIs(caught.exception, original)
        self.assertFalse(receipt["restored"])
        self.assertIn(("shell", "wm", "size", "360x720"), probe.commands)
        self.assertIn(("shell", "settings", "put", "system", "font_scale", "2.0"), probe.commands)
        self.assertTrue(any("Failed to restore" in note for note in original.__notes__))

    def test_cleanup_failure_on_success_is_fatal(self):
        probe = DisplayCommands()
        probe.failed_restore = "size"
        receipt = {}
        with self.assertRaisesRegex(AssertionError, "Failed to restore"):
            with details.wide_emulator_viewport(probe, receipt):
                pass
        self.assertFalse(receipt["restored"])


class DetailIntegrationContractTests(unittest.TestCase):
    def test_existing_case_identities_remain_and_actual_helper_is_called(self):
        self.assertEqual(len(automation.CASES), 13)
        self.assertEqual({route for route, _ in automation.CASES}, {"home", "settings", "decisions"})
        tree = ast.parse(Path(automation.__file__).read_text(encoding="utf-8"))
        exercise = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "exercise_automation")
        calls = [node for node in ast.walk(exercise) if isinstance(node, ast.Call)
                 and isinstance(node.func, ast.Name) and node.func.id == "exercise_navigation_details"]
        self.assertEqual(len(calls), 1)
        self.assertEqual(ast.dump(calls[0].args[0]), ast.dump(ast.Name(id="probe", ctx=ast.Load())))
        self.assertEqual(len(details.DETAILS), 6)


if __name__ == "__main__":
    unittest.main()
