"""Native detail-menu and editor-exit evidence in the existing synthetic fixture.

The ordinary automation and business case schemas remain unchanged. This
additional observation must pass independently and never submits a server write.
"""
from __future__ import annotations

from contextlib import contextmanager
import hashlib
import json
import math
import os
from pathlib import Path
import re

from automation_ui_probe import navigation_menu_absent, navigation_target, navigation_window

PACKAGE = "ru.omnicio.app.debug"
DETAILS = {
    "strategy": ("strategies", "Стратегия"),
    "markets": ("market", "Рынок"),
    "notifications": ("messages", "События"),
    "assistant": ("assistant", "Ассистент"),
    "appearance": ("appearance", "Оформление"),
    "library": ("library", "Исследования"),
}


def detail_marker(tree):
    if navigation_window(tree) is None:
        return None
    records = []
    for node in tree.iter("node"):
        if node.get("resource-id") not in {"navigation-detail-page", PACKAGE + ":id/navigation-detail-page"}:
            continue
        if node.get("package") != PACKAGE or node.get("visible-to-user") != "true" or node.get("enabled") != "true":
            continue
        fields = [part.split(":", 1) for part in node.get("content-desc", "").split(";") if ":" in part]
        value = dict(fields)
        expected = {"navigation-detail", "transport", "page", "requests", "writes", "contract-errors", "prefs", "user"}
        if len(fields) != len(value) or set(value) != expected \
                or value["navigation-detail"] != "business-strategy/ready" or value["transport"] != "synthetic":
            raise AssertionError("Detail navigation fixture identity is invalid")
        if value["page"] not in DETAILS or any(re.fullmatch(r"[0-9]{1,12}", value[key]) is None
                                              for key in ("requests", "writes", "contract-errors")):
            raise AssertionError("Detail navigation page/counters are invalid")
        counts = {key: int(value[key]) for key in ("requests", "writes", "contract-errors")}
        if counts["contract-errors"] or counts["writes"] or counts["writes"] > counts["requests"]:
            raise AssertionError("Navigation submitted a mutation or invalid fixture request")
        prefs = value["prefs"].split(",")
        if len(prefs) != 8 or prefs[0] not in {"AURORA", "OCEAN", "IRIS"} \
                or prefs[1] not in {"COMFORT", "COMPACT"} or prefs[2] not in {"LIVE", "SUBDUED", "OFF"} \
                or any(flag not in {"true", "false"} for flag in prefs[3:]) \
                or re.fullmatch(r"synthetic-business-[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}", value["user"]) is None:
            raise AssertionError("Detail fixture preferences or isolated user identity are invalid")
        if counts["requests"]:
            records.append({"page": value["page"], "requests": counts["requests"], "writes": 0,
                            "contract_errors": 0, "preferences": value["prefs"], "user": value["user"]})
    if len(records) > 1:
        raise AssertionError("Ambiguous native detail navigation fixture")
    return records[0] if records else None


def visible_label(tree, label):
    from profile_ui_probe import node_bounds
    window = navigation_window(tree)
    if window is None:
        return None
    matches = []
    for node in tree.iter("node"):
        if node.get("package") != PACKAGE or node.get("visible-to-user") != "true" \
                or node.get("enabled") != "true":
            continue
        values = [part.strip() for key in ("text", "content-desc") for part in node.get(key, "").splitlines()]
        if label not in values:
            continue
        try:
            left, top, right, bottom = node_bounds(node)
        except (ValueError, TypeError, AssertionError):
            continue
        if 0 <= left < right <= window[0] and 0 <= top < bottom <= window[1]:
            matches.append(node)
    if len(matches) > 1:
        raise AssertionError("Ambiguous native dialog title")
    return matches[0] if matches else None


def wide_rail_frame(tree, scale):
    """Require the real portrait breakpoint, production rail and no phone bar."""
    from profile_ui_probe import node_bounds
    from spatial_frame_evidence import ready_native_screen_metrics
    renderer = ready_native_screen_metrics(tree, "business-strategy", scale)
    window = navigation_window(tree)
    if renderer is None or window is None:
        return None
    density = renderer["density"]
    if window[0] / density < 840 or not 0 < window[0] < window[1]:
        raise AssertionError("The wide panel case did not reach the real portrait breakpoint")
    forbidden = {value for resource in ("navigation-menu-open", "analyst-bottom-bar")
                 for value in (resource, PACKAGE + ":id/" + resource)}
    if not navigation_menu_absent(tree) or any(node.get("resource-id") in forbidden
            and node.get("visible-to-user") != "false" for node in tree.iter("node")):
        raise AssertionError("Wide navigation retained a phone menu or bottom bar")
    minimum = math.ceil(48 * density - 1e-6)
    rail = navigation_target(tree, "analyst-side-rail", minimum=minimum, touch=False)
    if rail is None:
        return None
    bounds = node_bounds(rail)
    targets = []
    for destination, label in (("home", "Система"), ("actions", "Решения"), ("profile", "Настройки")):
        resource = "rail-destination-" + destination
        target = navigation_target(tree, resource, minimum=minimum, touch=False, label=label,
                                   selected=destination == "profile")
        if target is None:
            return None
        target_bounds = node_bounds(target)
        if not (bounds[0] <= target_bounds[0] < target_bounds[2] <= bounds[2]
                and bounds[1] <= target_bounds[1] < target_bounds[3] <= bounds[3]):
            raise AssertionError("A primary navigation target is outside the actual side rail")
        targets.append({"resource": resource, "bounds": list(target_bounds),
                        "selected": target.get("selected") == "true"})
    return {"width": window[0], "height": window[1], "width_dp": window[0] / density,
            "density": density, "window_id": window[2], "rail_bounds": list(bounds), "targets": targets}


def _wm_state(command):
    result = {}
    for setting, pattern in (("size", r"([1-9][0-9]{1,3})x([1-9][0-9]{1,3})"),
                             ("density", r"([1-9][0-9]{1,3})")):
        text = command("shell", "wm", setting)
        rows = {}
        for line in text.splitlines():
            match = re.fullmatch(r"(Physical|Override) " + setting + r": " + pattern, line.strip())
            if match is None or match.group(1) in rows:
                raise AssertionError("Cannot establish exact original emulator display " + setting)
            rows[match.group(1)] = line.strip().split(": ", 1)[1]
        if set(rows) not in ({"Physical"}, {"Physical", "Override"}):
            raise AssertionError("Missing original emulator display " + setting)
        for value in rows.values():
            dimensions = tuple(map(int, value.split("x")))
            if setting == "size" and (not 240 <= dimensions[0] < dimensions[1] <= 4096) \
                    or setting == "density" and not 72 <= dimensions[0] <= 1000:
                raise AssertionError("Original display is outside the bounded portrait emulator contract")
        result[setting] = rows
    return result


def _owned_emulator(probe):
    from persistent_ui import FrameReader, assert_disposable
    reader = getattr(probe.read_tree, "__self__", None)
    if not isinstance(reader, FrameReader) or reader.broken:
        raise AssertionError("Wide display changes require the owned persistent frame session")
    # The ordinary caller runs inside test_apk_installation's unchanged canonical
    # exclusive_emulator lease. This identity must also belong to that process,
    # rather than another AVD or a physical device exposed by the same ADB server.
    assert_disposable(probe.device)
    output = probe.command("emu", "avd", "name")
    if len(output) > 4096:
        raise AssertionError("The wide AVD identity response exceeds its protocol limit")
    # Match the existing boot-readiness parser: blank lines and OK are console
    # framing, never identities. Still require exactly one payload belonging
    # to this process; a second name, error or foreign process remains fatal.
    raw_lines = output.splitlines()
    lines = [line.strip() for line in raw_lines if line.strip()]
    identities = [line for line in lines if line != "OK"]
    allowed = {"analyst-install-" + str(os.getpid()) + "-" + str(attempt) for attempt in (1, 2)}
    owned = len(identities) == 1 and identities[0] in allowed
    print("NAVIGATION_AVD_IDENTITY=" + json.dumps({
        "line_count": len(lines), "blank_lines": len(raw_lines) - len(lines),
        "acknowledgements": lines.count("OK"), "payload_count": len(identities),
        "matches_current_process": owned,
    }, sort_keys=True), flush=True)
    if not owned:
        raise AssertionError("The wide case refuses a different process's emulator")
    return {"avd": identities[0], "owner_process_id": os.getpid(), "physical_device": False}


@contextmanager
def wide_emulator_viewport(probe, receipt):
    """Temporarily use 960x1600/160dpi only on this run's disposable emulator."""
    receipt["owner"] = _owned_emulator(probe)
    before = _wm_state(probe.command)
    scale = probe.command("shell", "settings", "get", "system", "font_scale").strip()
    if re.fullmatch(r"[0-9](?:\.[0-9]{1,3})?", scale) is None or not 0.5 <= float(scale) <= 3:
        raise AssertionError("The wide case cannot restore the actual original font scale")
    receipt.update(before=before, original_font_scale=scale, restored=False)
    failure = None
    touched = False
    try:
        # Set touched first: a transport error may follow an already applied change.
        touched = True
        probe.command("shell", "wm", "size", "960x1600")
        probe.command("shell", "wm", "density", "160")
        actual = _wm_state(probe.command)
        if actual["size"].get("Override", actual["size"]["Physical"]) != "960x1600" \
                or actual["density"].get("Override", actual["density"]["Physical"]) != "160" \
                or any(actual[key]["Physical"] != before[key]["Physical"] for key in before):
            raise AssertionError("The dedicated wide emulator display did not apply exactly")
        receipt["during"] = actual
        yield
    except BaseException as error:
        failure = error
        raise
    finally:
        errors = []
        if touched:
            for setting in ("density", "size"):
                try:
                    probe.command("shell", "wm", setting, before[setting].get("Override", "reset"))
                except Exception as error:
                    errors.append(type(error).__name__ + ": " + str(error))
            try:
                probe.command("shell", "settings", "put", "system", "font_scale", scale)
            except Exception as error:
                errors.append(type(error).__name__ + ": " + str(error))
            try:
                after = _wm_state(probe.command)
                actual_scale = probe.command("shell", "settings", "get", "system", "font_scale").strip()
                receipt["after"] = after
                receipt["font_scale_after"] = actual_scale
                if after != before or actual_scale != scale:
                    raise AssertionError("The exact original display overrides/font scale were not restored")
                width, height = map(int, before["size"].get("Override", before["size"]["Physical"]).split("x"))
                def restored_frame():
                    tree = probe.tree()
                    return tree is not None and tree.get("display-width") == str(width) \
                        and tree.get("display-height") == str(height)
                probe.wait_for(restored_frame, "The original phone viewport did not return")
            except Exception as error:
                errors.append(type(error).__name__ + ": " + str(error))
        receipt["restored"] = not errors and touched
        if errors:
            receipt["restore_errors"] = errors
            message = "Failed to restore the owned emulator display: " + "; ".join(errors)
            if failure is None:
                raise AssertionError(message)
            failure.add_note(message)


class _DetailNavigationCase:
    def __init__(self, probe, scale):
        self.probe, self.scale = probe, scale
        self.window = None
        self.minimum = None
        self.user = None
        self.targets = []
        self.phase = "created"

    def owned_frame(self):
        def read():
            tree = self.probe.tree()
            value = navigation_window(tree)
            return tree if value is not None and value[2] == self.window else None
        return self.probe.wait_for(read, "Detail navigation lost the original owned window")

    def target(self, resource, *, selected=None, touch=True, label=None):
        from profile_ui_probe import node_bounds
        previous, stable = None, 0
        def read():
            nonlocal previous, stable
            tree = self.owned_frame()
            node = navigation_target(tree, resource, minimum=self.minimum,
                                     selected=selected, touch=touch, label=label)
            signature = None if node is None else (node.get("bounds"), node.get("selected"), node.get("clickable"))
            stable = stable + 1 if signature is not None and signature == previous else int(signature is not None)
            previous = signature
            return node if stable >= 3 else None
        node = self.probe.wait_for(read, "Detail menu control did not settle: " + resource)
        self.targets.append({"resource": resource, "bounds": list(node_bounds(node)),
                             "window_id": self.window, "selected": node.get("selected") == "true"})
        return node

    def tap(self, resource, **kwargs):
        self.probe.tap_node(self.target(resource, **kwargs))

    def observed(self, page):
        from business_ui_probe import business_marker
        highest_requests = 0
        pending_frames = 0
        last_counts = None
        settled = False
        def read():
            nonlocal highest_requests, pending_frames, last_counts
            tree = self.owned_frame()
            value = detail_marker(tree)
            business = business_marker(tree, "strategy", "ready")
            if value is None or value["page"] != page or business is None:
                return None
            if self.user is not None and value["user"] != self.user:
                raise AssertionError("Detail navigation changed the isolated user")
            last_counts = (value["requests"], business["requests"])
            highest_requests = max(highest_requests, *last_counts)
            # Accessibility reads can straddle two asynchronous compositions.
            # Require agreement at the newest observed count within the SAME
            # existing wait deadline; stale agreement cannot complete the case.
            if last_counts[0] != last_counts[1] or last_counts[0] < highest_requests:
                pending_frames += 1
                return None
            return value
        try:
            value = self.probe.wait_for(read, "The real detail screen did not reach " + page)
            settled = True
            return value
        finally:
            if pending_frames:
                print("DETAIL_COUNTER_SETTLEMENT=" + json.dumps({
                    "page": page, "pending_frames": pending_frames,
                    "maximum_requests": highest_requests, "last_counts": last_counts,
                    "settled": settled,
                }, sort_keys=True), flush=True)

    def closed(self):
        return self.probe.wait_for(lambda: navigation_menu_absent(self.owned_frame()),
                                   "The detail navigation panel remained visible")

    def open_menu(self):
        self.tap("navigation-menu-open", label="Открыть меню")
        return self.target("navigation-menu-close", label="Закрыть меню")

    def menu_item(self, page, *, selected=None, touch=True):
        key, label = DETAILS[page]
        # The menu keeps its scroll state. Establish its real top first so a
        # previous visit to Library cannot make an earlier item unreachable.
        self.probe.reveal_resource("navigation-primary-home", "navigation-panel-content", direction="start",
                                   for_capture=True, minimum_size=(self.minimum, self.minimum))
        resource = "navigation-workspace-" + key
        self.probe.reveal_resource(resource, "navigation-panel-content", direction="end",
                                   for_capture=True, minimum_size=(self.minimum, self.minimum))
        return self.target(resource, selected=selected, touch=touch, label=label)

    def choose(self, page):
        self.open_menu()
        self.probe.tap_node(self.menu_item(page, selected=False))

    def capture(self, stem):
        from spatial_frame_evidence import read_screenshot
        path = self.probe.capture(stem + ("-font-200" if self.scale == 2.0 else ""))
        picture = read_screenshot(path)
        if not 0 < picture.width < picture.height:
            raise AssertionError("Detail navigation capture is not portrait")
        return {"screenshot": path.name, "screenshot_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "width": picture.width, "height": picture.height}

    def screen_anchor(self, page):
        if page == "strategy":
            self.reveal_horizon()
        elif page == "assistant":
            self.probe.wait_for(lambda: navigation_target(self.owned_frame(), "assistant-composer"),
                               "The real Assistant composer is absent")
        else:
            label = {"markets": "Ваши инструменты", "notifications": "Настроить события",
                     "appearance": "Предпросмотр цвета, контраста и движения",
                     "library": "Название, заметка или источник"}[page]
            self.probe.reveal(label, "workspace-content", direction="start", max_swipes=20)

    def reveal_horizon(self):
        from profile_scroll import fully_visible_resource
        minimum = (self.minimum, self.minimum)
        # The Goal editor places this input after the state, goal and risk
        # cards. Recover the fixture's actual top when returning from a saved
        # scroll position, but keep an already visible editor/IME in place.
        if fully_visible_resource(self.owned_frame(), "strategy-horizon",
                                  "workspace-content", minimum) is None:
            self.probe.reveal("Действует версия 3", "workspace-content",
                              direction="start", max_swipes=20)
        return self.probe.reveal_resource("strategy-horizon", "workspace-content", direction="end",
                                          for_capture=True, minimum_size=minimum)


    def horizon(self, value):
        from native_input_evidence import native_input_ready
        self.reveal_horizon()
        self.probe.tap_resource("strategy-horizon", "workspace-content", direction="end")
        result = self.probe.wait_for(lambda: native_input_ready(self.probe.tree(), value),
                                     "The real strategy editor did not retain " + value)
        return result

    def dirty_dialog(self):
        from profile_ui_probe import node_bounds
        def read():
            tree = self.probe.tree()
            window = navigation_window(tree)
            state = detail_marker(tree)
            if state is not None and state["page"] != "strategy":
                raise AssertionError("Panel navigation bypassed the dirty strategy confirmation")
            if window is None or window[2] == self.window:
                return None
            title = visible_label(tree, "Изменения стратегии")
            return {"window_id": window[2], "title_bounds": list(node_bounds(title))} if title is not None else None
        return self.probe.wait_for(read, "Dirty strategy did not open its real confirmation window")

    def dialog_action(self, dialog, label):
        from profile_ui_probe import node_bounds
        target = self.probe.label_tap_target(label, "workspace-content", direction="end", max_swipes=20)
        window = navigation_window(self.probe.tree())
        bounds = node_bounds(target)
        if window is None or window[2] != dialog["window_id"] or window[2] == self.window \
                or target.get("package") != PACKAGE or target.get("clickable") != "true" \
                or target.get("enabled") != "true" or target.get("visible-to-user") != "true" \
                or not (0 <= bounds[0] < bounds[2] <= window[0] and 0 <= bounds[1] < bounds[3] <= window[1]) \
                or bounds[2] - bounds[0] < self.minimum or bounds[3] - bounds[1] < self.minimum:
            raise AssertionError("The dirty confirmation action lost its owned 48dp target")
        self.probe.tap_node(target)
        return {"label": label, "bounds": list(bounds), "window_id": window[2]}

    def dirty_exit(self):
        from native_input_evidence import append_native_text, native_input_ready
        self.horizon("36")
        self.probe.command("shell", "input", "keyevent", "KEYCODE_MOVE_END")
        for _ in range(2):
            self.probe.command("shell", "input", "keyevent", "KEYCODE_DEL")
        self.probe.wait_for(lambda: native_input_ready(self.probe.tree(), ""), "Strategy draft was not cleared natively")
        append_native_text(self.probe, "", "48")
        # The same menu must remain reachable in the existing compact input
        # gutter. Observe the real IME before tapping, then preserve the draft.
        if self.probe.tree().get("keyboard-visible") != "true":
            raise AssertionError("The compact navigation check lost its native keyboard")
        self.open_menu()
        input_menu = self.capture("navigation-detail-menu-with-ime")
        self.tap("navigation-menu-close", label="Закрыть меню")
        self.closed()
        self.observed("strategy")
        self.horizon("48")
        self.probe.dismiss_keyboard()
        self.observed("strategy")
        self.choose("markets")
        cancelled = self.dirty_dialog()
        cancel_capture = self.capture("navigation-detail-dirty-cancel")
        cancel_action = self.dialog_action(cancelled, "Продолжить редактирование")
        self.closed()
        self.observed("strategy")
        self.horizon("48")
        self.probe.dismiss_keyboard()
        self.choose("markets")
        discarded = self.dirty_dialog()
        discard_action = self.dialog_action(discarded, "Отменить изменения")
        self.closed()
        self.observed("markets")
        self.screen_anchor("markets")
        self.choose("strategy")
        self.closed()
        self.observed("strategy")
        self.horizon("36")
        self.probe.dismiss_keyboard()
        return {"original_months": 36, "edited_months": 48, "cancelled_months": 48, "discarded_months": 36,
                "cancelled_dialog": cancelled, "cancel_action": cancel_action,
                "discarded_dialog": discarded, "discard_action": discard_action,
                "cancel_kept_strategy": True, "confirmed_discard_reached_markets": True,
                "menu_opened_with_native_ime": True, "input_menu": input_menu,
                "server_mutations": 0, **cancel_capture}

    def saved_appearance_anchor(self):
        # The saved caption is below the preview artwork/body, not at the
        # list's top. At large fonts it requires its own downward reveal.
        self.screen_anchor("appearance")
        return self.probe.reveal("Текущие сохранённые настройки", "workspace-content",
                                 direction="end", max_swipes=20)

    def appearance_exit(self):
        self.choose("appearance")
        self.closed()
        before = self.observed("appearance")
        density = before["preferences"].split(",")[1]
        target = "COMPACT" if density == "COMFORT" else "COMFORT"
        label = "Компактно" if target == "COMPACT" else "Свободно"
        self.probe.tap(label, "workspace-content", direction="end", max_swipes=20)
        preview = self.probe.wait_for(
            lambda: (value if value["preferences"].split(",")[1] == target else None)
            if (value := self.observed("appearance")) else None, "Appearance preview did not change natively")
        if preview["preferences"] == before["preferences"]:
            raise AssertionError("Appearance regression did not create a real uncommitted preview")
        self.choose("markets")
        self.closed()
        after = self.observed("markets")
        if after["preferences"] != before["preferences"]:
            raise AssertionError("Panel exit left the uncommitted appearance preview active")
        self.choose("appearance")
        self.closed()
        returned = self.observed("appearance")
        if returned["preferences"] != before["preferences"]:
            raise AssertionError("Returning to Appearance restored a cancelled preview")
        self.saved_appearance_anchor()
        result = {"before": before["preferences"], "preview": preview["preferences"],
                  "after": after["preferences"], "returned": returned["preferences"],
                  "cancelled_draft_did_not_reappear": True, **self.capture("navigation-detail-appearance-return")}
        self.choose("strategy")
        self.closed()
        self.observed("strategy")
        return result

    def start(self):
        from profile_launch import launch_profile
        from spatial_frame_evidence import ready_native_screen_metrics
        self.phase = "launch"
        self.probe.command("shell", "settings", "put", "system", "font_scale", str(self.scale))
        launch_profile(self.probe.command, self.probe.tree, self.probe.wait_for,
                       expected_screen="business-strategy", scenario="ready")
        renderer = self.probe.wait_for(lambda: ready_native_screen_metrics(
            self.probe.tree(), "business-strategy", self.scale),
                                       "Detail navigation lacks actual native rendering evidence")
        density = renderer.get("density", 0)
        if type(density) not in (int, float) or not math.isfinite(density) or not 0 < density <= 10 \
                or not math.isclose(renderer.get("font-scale", 0), self.scale, rel_tol=0, abs_tol=1e-6) \
                or renderer.get("orientation") != "1":
            raise AssertionError("Detail navigation density/font/portrait evidence differs")
        self.minimum = math.ceil(48 * density - 1e-6)
        window = self.probe.wait_for(lambda: navigation_window(self.probe.tree()), "Missing owned detail window")
        self.window = window[2]
        initial = self.observed("strategy")
        self.user = initial["user"]
        pid = self.probe.command("shell", "pidof", PACKAGE).strip()
        if re.fullmatch(r"[1-9][0-9]*", pid) is None:
            raise AssertionError("Missing unique detail fixture process")
        return renderer, density, initial, pid

    def run(self):
        from profile_launch import profile_frame
        renderer, density, initial, pid = self.start()
        destinations = []
        current = "strategy"
        for page in DETAILS:
            self.phase = "destination-" + page
            if page != current:
                self.choose(page)
                self.closed()
            state = self.observed(page)
            self.screen_anchor(page)
            self.open_menu()
            selected = self.menu_item(page, selected=True, touch=False)
            from profile_ui_probe import node_bounds
            capture = self.capture("navigation-detail-" + page)
            self.tap("navigation-menu-close", label="Закрыть меню")
            self.closed()
            self.observed(page)
            destinations.append({"page": page, "observed": state, "selected_bounds": list(node_bounds(selected)), **capture})
            current = page
        self.choose("strategy")
        self.closed()
        self.observed("strategy")
        self.phase = "dirty-confirmation"
        dirty = self.dirty_exit()
        self.phase = "appearance-rollback"
        appearance = self.appearance_exit()
        self.phase = "final-source-observation"
        final = self.observed("strategy")
        if final["preferences"] != initial["preferences"]:
            raise AssertionError("Detail navigation changed committed presentation preferences")
        final_pid = self.probe.command("shell", "pidof", PACKAGE).strip()
        if final_pid != pid:
            raise AssertionError("The app restarted during detail navigation")
        foreground = {}
        self.probe.wait_for(lambda: profile_frame(self.probe.command, self.probe.tree, foreground,
                           expected_screen="business-strategy", scenario="ready"), "Detail fixture lost foreground")
        return {"font_scale": self.scale, "renderer": renderer, "density": density,
                "minimum_touch_dp": 48, "main_window_id": self.window,
                "process_id": pid, "process_id_after": final_pid, "before": initial, "after": final,
                "destinations": destinations, "dirty_exit": dirty, "appearance_exit": appearance,
                "native_targets": self.targets, "foreground": foreground}


    def run_wide(self):
        from native_input_evidence import append_native_text, native_input_ready
        from profile_launch import foreground_observation, profile_resumed
        renderer, density, initial, pid = self.start()
        self.phase = "actual-wide-rail"
        rail = self.probe.wait_for(lambda: wide_rail_frame(self.owned_frame(), self.scale),
                                   "The production wide side rail is absent")
        if (rail["width"], rail["height"]) != (960, 1600) or not math.isclose(density, 1.0, rel_tol=0, abs_tol=1e-6):
            raise AssertionError("Native wide geometry differs from the owned emulator profile")
        self.horizon("36")
        self.probe.command("shell", "input", "keyevent", "KEYCODE_MOVE_END")
        for _ in range(2):
            self.probe.command("shell", "input", "keyevent", "KEYCODE_DEL")
        self.probe.wait_for(lambda: native_input_ready(self.probe.tree(), ""), "Wide strategy draft did not clear")
        append_native_text(self.probe, "", "48")
        self.probe.dismiss_keyboard()
        self.observed("strategy")
        self.probe.wait_for(lambda: wide_rail_frame(self.owned_frame(), self.scale), "Wide rail did not remain visible")
        self.phase = "wide-dirty-cancel"
        self.tap("rail-destination-home", selected=False, label="Система")
        cancelled = self.dirty_dialog()
        cancel_capture = self.capture("navigation-wide-dirty-cancel")
        cancel_action = self.dialog_action(cancelled, "Продолжить редактирование")
        self.closed()
        after_cancel = self.observed("strategy")
        self.horizon("48")
        self.probe.dismiss_keyboard()
        self.probe.wait_for(lambda: wide_rail_frame(self.owned_frame(), self.scale), "Cancellation lost the wide rail")
        self.phase = "wide-dirty-discard"
        self.tap("rail-destination-home", selected=False, label="Система")
        discarded = self.dirty_dialog()
        discard_capture = self.capture("navigation-wide-dirty-discard")
        discard_action = self.dialog_action(discarded, "Отменить изменения")
        self.phase = "wide-confirmed-fixture-exit"
        def exited():
            tree = self.probe.tree()
            if tree is None or any(node.get("package") == PACKAGE and node.get("visible-to-user") != "false"
                                   for node in tree.iter("node")):
                return None
            activities = self.probe.command("shell", "dumpsys", "activity", "activities")
            foreground = foreground_observation(activities)
            if profile_resumed(activities) or not any("ResumedActivity" in line for line in foreground):
                return None
            if self.probe.command("shell", "pidof", PACKAGE).strip() != pid:
                raise AssertionError("A process death cannot prove the confirmed fixture exit")
            return {"profile_no_longer_resumed": True, "owned_app_window_gone": True,
                    "process_id_after": pid, "foreground": foreground}
        exit_observation = self.probe.wait_for(exited, "Confirmed wide navigation did not leave the actual fixture")
        # This fixture's primary callback is its real onBack/Activity.finish.
        # The original four navigation receipts separately cover primary screen
        # rendering; do not relabel this editor-exit observation as a Home render.
        return {"font_scale": self.scale, "renderer": renderer, "density": density,
                "minimum_touch_dp": 48, "actual_wide_rail": rail, "main_window_id": self.window,
                "process_id": pid, "before": initial, "after_cancel": after_cancel,
                "original_months": 36, "edited_months": 48, "cancelled_months": 48,
                "requested_primary": "home", "cancel_kept_strategy": True,
                "cancelled_dialog": cancelled, "cancel_action": cancel_action,
                "discarded_dialog": discarded, "discard_action": discard_action,
                "cancel_capture": cancel_capture, "discard_capture": discard_capture,
                "confirmed_fixture_exit": exit_observation, "primary_screen_render_claimed": False,
                "server_mutations": 0, "native_targets": self.targets}


def exercise_navigation_wide(probe, apk_sha256, folder):
    """Additional owned-emulator case after all phone observations, never a skip."""
    report = {"schema_version": 1, "fixture": "business-strategy/ready", "fixture_apk_sha256": apk_sha256,
              "actual_device_observations": True, "external_broker_model_calls": False,
              "real_order_execution": False, "full_release_gate_claimed": False,
              "status": "incomplete", "viewport": {}, "cases": []}
    try:
        with wide_emulator_viewport(probe, report["viewport"]):
            for scale in (1.0, 2.0):
                case = _DetailNavigationCase(probe, scale)
                try:
                    report["cases"].append(case.run_wide())
                except Exception:
                    report["failed_case"] = {"font_scale": scale, "phase": case.phase,
                                             "main_window_id": case.window, "native_targets": case.targets}
                    raise
        if len(report["cases"]) != 2 or {case["font_scale"] for case in report["cases"]} != {1.0, 2.0} \
                or report["viewport"].get("restored") is not True:
            raise AssertionError("Wide navigation observations or phone viewport restoration are incomplete")
        report["status"] = "passed"
        return report
    except Exception as error:
        report["error_type"] = type(error).__name__
        report["error"] = str(error)
        raise
    finally:
        (folder / "navigation-wide-verification.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print("NAVIGATION_WIDE_VERIFICATION=" + json.dumps(report, ensure_ascii=True), flush=True)


def exercise_navigation_details(probe):
    from persistent_ui import FrameReader
    if not isinstance(getattr(probe.read_tree, "__self__", None), FrameReader):
        raise AssertionError("Detail navigation needs the owned persistent frame session")
    root = Path(__file__).resolve().parents[2]
    apk = root / "app/build/outputs/apk/debug/app-debug.apk"
    if apk.is_symlink() or not apk.resolve(strict=True).is_relative_to(root):
        raise AssertionError("Detail fixture APK escapes checkout")
    report = {"schema_version": 1, "fixture": "business-strategy/ready",
              "fixture_apk_sha256": hashlib.sha256(apk.read_bytes()).hexdigest(),
              "actual_device_observations": True, "external_broker_model_calls": False,
              "real_order_execution": False, "full_release_gate_claimed": False,
              "status": "incomplete", "cases": []}
    folder = root / "app/build/outputs/apk/preview/ui-screens"
    if folder.is_symlink() or not folder.resolve().is_relative_to(root):
        raise AssertionError("Detail navigation evidence escapes checkout")
    try:
        for scale in (1.0, 2.0):
            case = _DetailNavigationCase(probe, scale)
            try:
                report["cases"].append(case.run())
            except Exception:
                report["failed_case"] = {"font_scale": scale, "phase": case.phase,
                                         "main_window_id": case.window, "native_targets": case.targets}
                raise
        if len(report["cases"]) != 2 or {case["font_scale"] for case in report["cases"]} != {1.0, 2.0} \
                or any([row["page"] for row in case["destinations"]] != list(DETAILS) for case in report["cases"]):
            raise AssertionError("Detail navigation observations are incomplete")
        report["wide_report"] = "navigation-wide-verification.json"
        wide = exercise_navigation_wide(probe, report["fixture_apk_sha256"], folder)
        report["wide_status"] = wide["status"]
        report["wide_report_sha256"] = hashlib.sha256((folder / report["wide_report"]).read_bytes()).hexdigest()
        report["status"] = "passed"
        return report
    except Exception as error:
        report["error_type"] = type(error).__name__
        report["error"] = str(error)
        raise
    finally:
        (folder / "navigation-detail-verification.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print("NAVIGATION_DETAIL_VERIFICATION=" + json.dumps(report, ensure_ascii=True), flush=True)
