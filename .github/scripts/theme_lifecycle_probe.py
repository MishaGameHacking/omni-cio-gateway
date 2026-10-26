"""Finite native theme lifecycle evidence, additive to the unchanged N00 suites.

Only the current test process's leased API37 emulator may be changed. The real
Appearance screen owns every preview/apply/cancel; the debug fixture observes
production state and preserves/restores the exact nine presentation keys.
"""
from __future__ import annotations

from contextlib import contextmanager
import hashlib
import json
import math
from pathlib import Path
import re
import subprocess
import sys
import time
from uuid import uuid4
import xml.etree.ElementTree as ET

from automation_ui_probe import navigation_window
from navigation_detail_probe import _owned_emulator

PACKAGE = "ru.omnicio.app.debug"
ACTIVITY = PACKAGE + "/ru.omnicio.app.ProfileUiProbeActivity"
AREA = "workspace-content"
SCREEN = "theme-lifecycle"
REPORT = "theme-lifecycle-verification.json"
MODES = {"LIGHT": ("no", "fff5f7f9", "ff1b2930"), "DARK": ("yes", "ff101a1f", "ffe7eff2")}
LABELS = {"LIGHT": "Светлая", "DARK": "Тёмная", "SYSTEM": "Как в системе"}
ACCENTS = {"AURORA": "Аврора", "OCEAN": "Океан", "IRIS": "Ирис"}
UUID = r"[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}"
FIELDS = set("theme-lifecycle session run phase activity owner editor-owner pid uid page draft mode saved-mode stored-mode "
             "saved-hash original-mode original-hash app-night system-night policy background foreground native-background "
             "native-window native-splash launch-night launch-window launch-splash status-light navigation-light "
             "overlay-permission overlay-capability accent saved-accent font-scale density restored".split())


def strict_night_setting(output):
    match = re.fullmatch(r"\s*Night mode:\s*(yes|no|auto|custom|custom_schedule|custom_bedtime)\s*", output)
    if match is None:
        raise AssertionError("The actual global night policy is unknown")
    return match.group(1)


def lifecycle_marker(tree, session, run, scale):
    """Read exactly one fresh owned marker, never infer a system value from app mode."""
    from profile_ui_probe import node_bounds
    from spatial_frame_evidence import ready_native_screen_metrics
    window = navigation_window(tree)
    if window is None:
        return None
    required = {"probe-screen:" + SCREEN, "probe-run:" + run, "probe-refresh-tests:15"}
    ready = [node for node in tree.iter("node") if node.get("package") == PACKAGE
             and node.get("visible-to-user") == "true"
             and required.issubset(node.get("content-desc", "").split(";"))]
    # The old generic screen allowlist is intentionally unchanged. Its existing
    # plain-screen metrics are combined with our exact route/run check above.
    if not ready or ready_native_screen_metrics(tree, None, scale) is None:
        return None
    records = []
    for node in tree.iter("node"):
        if node.get("resource-id") not in {"theme-lifecycle-state", PACKAGE + ":id/theme-lifecycle-state"}:
            continue
        if node.get("package") != PACKAGE or node.get("visible-to-user") != "true" or node.get("enabled") != "true":
            continue
        parts = [part.split(":", 1) for part in node.get("content-desc", "").split(";")]
        if any(len(part) != 2 for part in parts):
            raise AssertionError("Malformed lifecycle marker")
        value = dict(parts)
        if len(parts) != len(value) or set(value) != FIELDS:
            raise AssertionError("Ambiguous or incomplete lifecycle fields")
        if value["session"] != session or value["run"] != run:
            continue
        left, top, right, bottom = node_bounds(node)
        if not 0 <= left < right <= window[0] or not 0 <= top < bottom <= window[1]:
            raise AssertionError("Lifecycle marker is outside the active native window")
        if value["theme-lifecycle"] != "production-v1" or value["phase"] not in {"begin", "continue", "restore"} \
                or value["page"] not in {"home", "appearance"} or value["draft"] not in {"THEME", "THEME_DRAFT"}:
            raise AssertionError("Lifecycle fixture identity is invalid")
        if any(re.fullmatch(UUID, value[key]) is None for key in ("activity", "owner", "editor-owner")) \
                or any(re.fullmatch(r"[1-9][0-9]{0,8}", value[key]) is None for key in ("pid", "uid")) \
                or any(re.fullmatch(r"[a-f0-9]{64}", value[key]) is None for key in ("saved-hash", "original-hash")):
            raise AssertionError("Lifecycle owner or persisted-state identity is invalid")
        if any(value[key] not in LABELS for key in ("mode", "saved-mode", "original-mode")) \
                or value["stored-mode"] not in {*LABELS, "absent"} \
                or value["accent"] not in ACCENTS or value["saved-accent"] not in {*ACCENTS, "absent"}:
            raise AssertionError("Lifecycle preferences are outside the finite fixture")
        if any(value[key] not in {"yes", "no", "undefined"} for key in ("app-night", "launch-night")) \
                or value["system-night"] not in {"yes", "no", "unknown-INITIALIZING", "unknown-NO_DISPLAY",
                    "unknown-DISPLAY_UNAVAILABLE", "unknown-CONTEXT_UNAVAILABLE", "unknown-UNDEFINED_CONFIGURATION"} \
                or value["policy"] not in {"yes", "no", "auto", "custom", "unknown"}:
            raise AssertionError("Lifecycle native configuration is invalid")
        if any(value[key] not in {"true", "false", "unknown"} for key in ("status-light", "navigation-light")) \
                or value["restored"] not in {"true", "false"}:
            raise AssertionError("Lifecycle bars/restoration observation is invalid")
        if value["overlay-permission"] != "false" or value["overlay-capability"] != "false":
            raise AssertionError("The theme observer gained an overlay capability")
        color_keys = ("background", "foreground", "native-background", "native-window", "native-splash", "launch-window", "launch-splash")
        if any(re.fullmatch(r"[a-f0-9]{8}", value[key]) is None for key in color_keys):
            raise AssertionError("Lifecycle native or Compose colors are missing")
        try:
            density, actual_scale = float(value["density"]), float(value["font-scale"])
        except ValueError as error:
            raise AssertionError("Lifecycle density is invalid") from error
        if not math.isfinite(density) or not 0.5 <= density <= 4 or actual_scale != scale:
            raise AssertionError("Lifecycle density/font scale did not match the actual case")
        records.append({**value, "window": window[2], "width": window[0], "height": window[1]})
    if len(records) > 1:
        raise AssertionError("Duplicate native lifecycle marker")
    return records[0] if records else None


def matching_state(value, *, mode, saved, os_night, app_night, page=None, draft=None,
                   saved_hash=None, accent=None, stored=None, cold=False):
    """The decisive opposite-OS check independently binds body, resources and saved mode."""
    if value is None:
        return False
    body = ("DARK" if os_night == "yes" else "LIGHT") if mode == "SYSTEM" else mode
    native = "DARK" if app_night == "yes" else "LIGHT"
    expected = {"mode": mode, "saved-mode": saved, "system-night": os_night, "policy": os_night,
                "app-night": app_night, "background": MODES[body][1], "foreground": MODES[body][2],
                "native-background": MODES[native][1], "native-window": MODES[native][1],
                "native-splash": MODES[native][1], "status-light": str(body == "LIGHT").lower(),
                "navigation-light": str(body == "LIGHT").lower()}
    for key, item in (("page", page), ("draft", draft), ("saved-hash", saved_hash), ("accent", accent), ("stored-mode", stored)):
        if item is not None:
            expected[key] = item
    if cold:
        expected.update({"launch-night": app_night, "launch-window": MODES[native][1], "launch-splash": MODES[native][1]})
    return all(value[key] == item for key, item in expected.items())


def owned_windows(output, uid):
    """Inspect actual WindowManager owners/types; no hidden API or window creation."""
    if len(output.encode("utf-8")) > 2 * 1024 * 1024 or "DUMP TIMEOUT" in output:
        raise AssertionError("WindowManager observation was incomplete")
    headers = list(re.finditer(r"(?m)^[ \t]*Window #[0-9]+ Window\{([^}\r\n]+)\}:[ \t]*$", output))
    if not headers or "WINDOW MANAGER WINDOWS" not in output:
        raise AssertionError("WindowManager output has no understood window inventory")
    records = []
    for index, header in enumerate(headers):
        block = output[header.end():headers[index + 1].start() if index + 1 < len(headers) else len(output)]
        owners = re.findall(r"(?m)^[ \t]*mOwnerUid=([0-9]+)[^\r\n]*?\bpackage=([a-zA-Z0-9_.]+)\b", block)
        relevant = PACKAGE in header.group(1) or any(owner == str(uid) or package == PACKAGE for owner, package in owners)
        if not relevant:
            continue
        attrs = re.findall(r"(?ms)^[ \t]*mAttrs=\{(.*?)\}", block)
        kinds = re.findall(r"\bty=([A-Z_]+|[0-9]+)\b", attrs[0]) if len(attrs) == 1 else []
        if len(kinds) != 1 or kinds[0] not in {"BASE_APPLICATION", "1", "APPLICATION_STARTING", "3"}:
            raise AssertionError("The theme observer added an unexpected or overlay window")
        if kinds[0] in {"APPLICATION_STARTING", "3"} and re.search(
                r"\bu[0-9]+ Splash Screen " + re.escape(PACKAGE) + r"$", header.group(1)) is not None:
            # A platform splash can briefly overlap the ready Activity. Keep it
            # as pending evidence; it can never satisfy the settled one-window gate.
            records.append({"component": "starting:" + PACKAGE, "type": kinds[0]})
            continue
        if len(owners) != 1 or owners[0] != (str(uid), PACKAGE) \
                or re.search(r"\bu[0-9]+ " + re.escape(ACTIVITY) + r"$", header.group(1)) is None:
            raise AssertionError("An unexpected window claims the fixture package/UID")
        records.append({"component": ACTIVITY, "type": kinds[0]})
    return {"windows": records, "raw_sha256": hashlib.sha256(output.encode("utf-8")).hexdigest()}


def window_receipt(probe, uid, count):
    def read():
        value = owned_windows(probe.command("shell", "dumpsys", "-t", "2", "window", "windows", timeout=5), uid)
        if len(value["windows"]) != count or any(row["type"] not in {"BASE_APPLICATION", "1"} for row in value["windows"]):
            return None
        return value
    return probe.wait_for(read, "The exact fixture window count did not settle without overlays")


def checked_choice(tree, label, minimum):
    """Radio selection is native checked state; tabs' selected contract stays unchanged.

    Compose exports a RadioButton role's selected semantic as isChecked, often
    on a merged android.view.View with a role child. Require the exact visible
    row/label and reject a checked ancestor containing several finite choices.
    """
    from profile_scroll import _bounds
    from profile_ui_probe import node_bounds
    window = navigation_window(tree)
    if window is None:
        return None
    group = set(LABELS.values()) if label in LABELS.values() else set(ACCENTS.values())
    if label not in group:
        raise AssertionError("Unknown lifecycle radio label")
    parents = {child: parent for parent in tree.iter() for child in parent}
    matches = set()
    for node in tree.iter("node"):
        if node.get("package") != PACKAGE or node.get("visible-to-user") != "true" \
                or label not in [part.strip() for name in ("text", "content-desc") for part in node.get(name, "").splitlines()]:
            continue
        label_bounds = _bounds(node)
        if label_bounds is None:
            continue
        owner = node
        while owner is not None and owner.tag == "node":
            if owner.get("package") != PACKAGE or owner.get("enabled") != "true" or owner.get("visible-to-user") != "true":
                break
            if owner.get("scrollable") == "true":
                area = _bounds(owner)
                if area is None or not (area[0] <= label_bounds[0] < label_bounds[2] <= area[2]
                                        and area[1] <= label_bounds[1] < label_bounds[3] <= area[3]):
                    break
            if owner.get("checkable") == "true":
                if owner.get("checked") != "true" or owner.get("class") not in {"android.view.View", "android.widget.RadioButton"}:
                    break
                bounds = node_bounds(owner)
                labels = {part.strip() for child in owner.iter("node") if child.get("package") == PACKAGE
                          and child.get("visible-to-user") == "true" for key in ("text", "content-desc")
                          for part in child.get(key, "").splitlines()}
                if labels & group != {label} or min(bounds[2] - bounds[0], bounds[3] - bounds[1]) < minimum \
                        or not (0 <= bounds[0] <= label_bounds[0] < label_bounds[2] <= bounds[2] <= window[0]
                                and 0 <= bounds[1] <= label_bounds[1] < label_bounds[3] <= bounds[3] <= window[1]):
                    break
                ancestor, valid = parents.get(owner), True
                while ancestor is not None and ancestor.tag == "node":
                    if ancestor.get("package") != PACKAGE or ancestor.get("enabled") != "true" or ancestor.get("visible-to-user") != "true":
                        valid = False
                        break
                    if ancestor.get("scrollable") == "true":
                        area = node_bounds(ancestor)
                        if not (area[0] <= bounds[0] < bounds[2] <= area[2] and area[1] <= bounds[1] < bounds[3] <= area[3]):
                            valid = False
                            break
                    ancestor = parents.get(ancestor)
                if valid:
                    matches.add(owner)
                break
            owner = parents.get(owner)
    if len(matches) > 1:
        raise AssertionError("Ambiguous native checked theme choice")
    return next(iter(matches)) if matches else None


def native_draft(tree, text):
    from profile_ui_probe import node_bounds
    window = navigation_window(tree)
    if window is None:
        return None
    matches = []
    for node in tree.iter("node"):
        if node.get("package") == PACKAGE and node.get("visible-to-user") == "true" \
                and node.get("enabled") == "true" and node.get("editable") == "true" and node.get("text") == text:
            left, top, right, bottom = node_bounds(node)
            if 0 <= left < right <= window[0] and 0 <= top < bottom <= window[1]:
                matches.append({"text": text, "bounds": [left, top, right, bottom],
                                "editable": True, "native_class": node.get("class", "")})
    if len(matches) > 1:
        raise AssertionError("Two native editors claim the lifecycle draft")
    return matches[0] if matches else None


@contextmanager
def restore_lifecycle_settings(probe, receipt, restore_application):
    """Attempt every restoration even after a primary failure or lost UI session."""
    receipt["owner"] = _owned_emulator(probe)
    night = strict_night_setting(probe.command("shell", "cmd", "uimode", "night"))
    if night not in {"yes", "no"}:
        # Auto/custom activation overrides cannot be round-tripped by this finite
        # shell command. Refuse before changing anything, rather than guess.
        raise AssertionError("Lifecycle requires an existing explicit yes/no night policy")
    scale = probe.command("shell", "settings", "get", "system", "font_scale").strip()
    if re.fullmatch(r"[0-9](?:\.[0-9]{1,3})?", scale) is None or not 0.5 <= float(scale) <= 3:
        raise AssertionError("Lifecycle cannot restore the original actual font scale")
    receipt.update(original_night=night, original_font_scale=scale, restored=False)
    failure = None
    try:
        yield night, scale
    except BaseException as error:
        failure = error
        raise
    finally:
        errors = []
        for args in (("shell", "cmd", "uimode", "night", night),
                     ("shell", "settings", "put", "system", "font_scale", scale)):
            try:
                probe.command(*args)
            except Exception as error:
                errors.append(type(error).__name__ + ": " + str(error))
        try:
            receipt["application"] = restore_application(night, float(scale))
        except Exception as error:
            errors.append(type(error).__name__ + ": " + str(error))
        try:
            receipt["night_after"] = strict_night_setting(probe.command("shell", "cmd", "uimode", "night"))
            receipt["font_scale_after"] = probe.command("shell", "settings", "get", "system", "font_scale").strip()
            if receipt["night_after"] != night or receipt["font_scale_after"] != scale:
                raise AssertionError("The exact original night/font settings did not return")
        except Exception as error:
            errors.append(type(error).__name__ + ": " + str(error))
        receipt["restored"] = not errors and receipt.get("application", {}).get("restored") is True
        if not receipt["restored"]:
            receipt["errors"] = errors or ["Application restoration was not proved"]
            message = "Lifecycle restoration failed: " + "; ".join(receipt["errors"])
            if failure is None:
                raise AssertionError(message)
            failure.add_note(message)


class _LifecycleCase:
    def __init__(self, probe, session, run, scale, deadline, folder, initial):
        self.probe, self.session, self.run = probe, session, run
        self.scale, self.deadline, self.folder = scale, deadline, folder
        self.identity = {key: initial[key] for key in ("activity", "owner", "editor-owner", "pid", "uid", "window", "original-hash")}
        self.records, self.targets = [], []
        self.phase = "ready"

    def tree(self):
        if time.monotonic() >= self.deadline:
            raise AssertionError("The finite theme lifecycle deadline expired")
        tree = self.probe.tree()
        value = lifecycle_marker(tree, self.session, self.run, self.scale)
        if value is not None and any(value[key] != item for key, item in self.identity.items()):
            raise AssertionError("A theme change replaced the active Activity/root/editor owner")
        return tree

    def observed(self):
        return lifecycle_marker(self.tree(), self.session, self.run, self.scale)

    def expect(self, phase, **expected):
        self.phase = phase
        def read():
            value = self.observed()
            return value if matching_state(value, **expected) else None
        value = self.probe.wait_for(read, "Theme lifecycle state did not settle: " + phase)
        self.records.append({"phase": phase, **value})
        return value

    def current(self):
        return self.probe.wait_for(self.observed, "The current theme lifecycle marker is missing")

    def tap(self, label, direction="end", *, visible=False):
        from native_label_target import settled_label
        from profile_scroll import reveal_in_list
        from profile_ui_probe import node_bounds
        before = self.current()
        if not visible:
            target = reveal_in_list(self.tree, self.probe._semantic_scroll_callback(AREA, direction), label,
                resource_id=AREA, direction=direction, max_swipes=20, layout_timeout=12, for_tap=True)
            if target is None:
                raise AssertionError("The actual lifecycle action list is missing")
        target = settled_label(self.tree, label)
        bounds = node_bounds(target)
        minimum = math.ceil(48 * float(before["density"]) - 1e-6)
        if min(bounds[2] - bounds[0], bounds[3] - bounds[1]) < minimum:
            raise AssertionError("The lifecycle action is smaller than the real 48dp target")
        self.targets.append({"label": label, "bounds": list(bounds), "window": before["window"], "minimum_pixels": minimum})
        self.probe.tap_node(target) # Exactly one native tap; a missing state is never retapped.

    def selected(self, label):
        from profile_scroll import reveal_in_list
        reveal_in_list(self.tree, self.probe._semantic_scroll_callback(AREA, "end"), label,
                       resource_id=AREA, direction="end", max_swipes=20, layout_timeout=12)
        minimum = math.ceil(48 * float(self.current()["density"]) - 1e-6)
        self.probe.wait_for(lambda: checked_choice(self.tree(), label, minimum),
                           "The real checked radio state is missing: " + label)

    def os_mode(self, night):
        if night not in {"yes", "no"}:
            raise AssertionError("Invalid finite OS mode")
        self.probe.command("shell", "cmd", "uimode", "night", night)
        if strict_night_setting(self.probe.command("shell", "cmd", "uimode", "night")) != night:
            raise AssertionError("Android did not apply the requested actual global policy")

    def appearance(self):
        if self.current()["page"] != "home":
            raise AssertionError("Appearance must open from the observed lifecycle home")
        self.tap("Открыть оформление", direction="start")
        self.probe.wait_for(lambda: (value if value["page"] == "appearance" else None)
                            if (value := self.observed()) else None, "The real Appearance screen did not open")

    def choose_mode(self, mode):
        if self.current()["mode"] != mode:
            self.tap(LABELS[mode], direction="start")
            self.probe.wait_for(lambda: (value if value["mode"] == mode else None)
                                if (value := self.observed()) else None, "Theme preview did not change")
        self.selected(LABELS[mode])

    def choose_accent(self):
        current = self.current()["accent"]
        target = "OCEAN" if current != "OCEAN" else "IRIS"
        self.tap(ACCENTS[target], direction="end")
        self.probe.wait_for(lambda: (value if value["accent"] == target else None)
                            if (value := self.observed()) else None, "Appearance accent draft did not change")
        self.selected(ACCENTS[target])
        return target

    def capture(self, name):
        tree = self.tree()
        xml = self.folder / (name + ".xml")
        if xml.is_symlink():
            raise AssertionError("Lifecycle XML evidence is a link")
        xml.write_bytes(ET.tostring(tree, encoding="utf-8", xml_declaration=True))
        png = self.probe.capture(name)
        return {"xml": xml.name, "xml_sha256": hashlib.sha256(xml.read_bytes()).hexdigest(),
                "png": png.name, "png_sha256": hashlib.sha256(png.read_bytes()).hexdigest()}


def _launch(probe, session, phase, scale, uid, deadline, folder):
    from profile_launch import profile_frame, start_status
    run = uuid4().hex
    probe.command("shell", "am", "force-stop", PACKAGE)
    before_windows = window_receipt(probe, uid, 0)
    evidence = {}
    args = ("shell", "am", "start", "-W", "-n", ACTIVITY, "--es", "spectrum_screen", SCREEN,
            "--es", "spectrum_probe_run", run, "--es", "theme_lifecycle_session", session,
            "--es", "theme_lifecycle_phase", phase)
    try:
        status = start_status(probe.command(*args))
    except subprocess.TimeoutExpired:
        status = "command-timeout"
    def ready():
        if time.monotonic() >= deadline:
            raise AssertionError("Lifecycle startup exceeded its finite deadline")
        if profile_frame(probe.command, probe.tree, evidence) is None:
            return None
        value = lifecycle_marker(probe.tree(), session, run, scale)
        return value if value is not None and value["phase"] == phase and value["uid"] == str(uid) else None
    initial = probe.wait_for(ready, "The actual lifecycle Activity did not resume with the new run marker")
    pid = probe.command("shell", "pidof", PACKAGE).strip()
    if pid != initial["pid"]:
        raise AssertionError("The lifecycle fixture marker has a different actual process")
    case = _LifecycleCase(probe, session, run, scale, deadline, folder, initial)
    case.launch_receipt = {"am_start_status": status, "before_windows": before_windows,
                           "after_windows": window_receipt(probe, uid, 1), "initial": initial}
    return case


def _run_case(case, forced):
    from native_input_evidence import append_native_text
    initial = case.current()
    if initial["page"] != "home" or initial["draft"] != "THEME":
        raise AssertionError("The lifecycle case did not start from its fresh synthetic draft")
    case.tap("Черновик темы", direction="start")
    input_record = append_native_text(case.probe, "THEME", "_DRAFT")
    case.probe.dismiss_keyboard()
    case.probe.wait_for(lambda: (value if value["draft"] == "THEME_DRAFT" else None)
                        if (value := case.observed()) else None, "The real native text draft was lost")
    forced_night = MODES[forced][0]
    opposite = "no" if forced_night == "yes" else "yes"
    case.os_mode(opposite)
    case.appearance()
    saved_accent = case.choose_accent() # Dirty real control makes Apply a genuine action even at the initial forced mode.
    case.choose_mode(forced)
    case.tap("Применить", direction="start")
    baseline = case.expect("forced-applied", mode=forced, saved=forced, os_night=opposite,
        app_night=forced_night, page="appearance", draft="THEME_DRAFT", accent=saved_accent, stored=forced)
    if baseline["saved-accent"] != saved_accent:
        raise AssertionError("The real Appearance Apply did not save its dirty control")
    case.tap("Назад", visible=True)
    case.expect("forced-home", mode=forced, saved=forced, os_night=opposite,
        app_night=forced_night, page="home", draft="THEME_DRAFT", saved_hash=baseline["saved-hash"])
    case.appearance()
    preview_accent = case.choose_accent()
    case.choose_mode("SYSTEM")
    preview = case.expect("opposite-system-preview", mode="SYSTEM", saved=forced, os_night=opposite,
        app_night=forced_night, page="appearance", draft="THEME_DRAFT", saved_hash=baseline["saved-hash"], accent=preview_accent)
    prefix = "theme-life-f" + str(int(case.scale * 100)) + "-" + forced.lower()
    captures = [case.capture(prefix + "-preview")]
    for index, night in enumerate((forced_night, opposite)):
        case.os_mode(night)
        case.expect("preview-os-toggle-" + str(index), mode="SYSTEM", saved=forced, os_night=night,
            app_night=forced_night, page="appearance", draft="THEME_DRAFT", saved_hash=baseline["saved-hash"], accent=preview_accent)
    if forced == "DARK":
        case.tap("Отменить", direction="start")
        case.expect("cancel-preserved-saved", mode=forced, saved=forced, os_night=opposite,
            app_night=forced_night, page="appearance", draft="THEME_DRAFT", saved_hash=baseline["saved-hash"], accent=saved_accent)
        case.choose_mode(forced)
        case.tap("Назад", visible=True)
    else:
        case.tap("Назад", visible=True)
    case.expect("leave-discarded-preview", mode=forced, saved=forced, os_night=opposite,
        app_night=forced_night, page="home", draft="THEME_DRAFT", saved_hash=baseline["saved-hash"], accent=saved_accent)
    case.appearance()
    # The original draft controls and theme must also have reset inside the reopened real screen.
    case.selected(LABELS[forced])
    case.selected(ACCENTS[saved_accent])
    applied_accent = case.choose_accent()
    case.choose_mode("SYSTEM")
    case.expect("system-before-apply", mode="SYSTEM", saved=forced, os_night=opposite,
        app_night=forced_night, page="appearance", draft="THEME_DRAFT", saved_hash=baseline["saved-hash"], accent=applied_accent)
    case.tap("Применить", direction="start")
    applied = case.expect("system-applied", mode="SYSTEM", saved="SYSTEM", os_night=opposite,
        app_night=opposite, page="appearance", draft="THEME_DRAFT", accent=applied_accent, stored="SYSTEM")
    if applied["saved-hash"] == baseline["saved-hash"] or applied["saved-accent"] != applied_accent:
        raise AssertionError("SYSTEM Apply did not commit the actual theme and dirty control")
    for index, night in enumerate((forced_night, opposite)):
        case.os_mode(night)
        case.expect("applied-system-os-toggle-" + str(index), mode="SYSTEM", saved="SYSTEM", os_night=night,
            app_night=night, page="appearance", draft="THEME_DRAFT", saved_hash=applied["saved-hash"], accent=applied_accent)
    final_accent = case.choose_accent()
    case.choose_mode(forced)
    case.tap("Применить", direction="start")
    final = case.expect("forced-with-draft-applied", mode=forced, saved=forced, os_night=opposite,
        app_night=forced_night, page="appearance", draft="THEME_DRAFT", accent=final_accent, stored=forced)
    if final["saved-accent"] != final_accent or final["saved-hash"] == applied["saved-hash"]:
        raise AssertionError("Forced Apply lost the dirty Appearance control")
    case.tap("Назад", visible=True)
    case.expect("draft-retained-through-all-switches", mode=forced, saved=forced, os_night=opposite,
        app_night=forced_night, page="home", draft="THEME_DRAFT", saved_hash=final["saved-hash"])
    case.probe.reveal_resource("theme-lifecycle-draft", AREA, direction="start")
    retained_editor = case.probe.wait_for(lambda: native_draft(case.tree(), "THEME_DRAFT"),
                                         "The actual native editor lost its unsaved text")
    windows = window_receipt(case.probe, initial["uid"], 1)
    captures.append(case.capture(prefix + "-retained"))
    cold = _launch(case.probe, case.session, "continue", case.scale, initial["uid"], case.deadline, case.folder)
    restored = cold.expect("forced-cold-start", mode=forced, saved=forced, os_night=opposite,
        app_night=forced_night, page="home", draft="THEME", saved_hash=final["saved-hash"], accent=final_accent, stored=forced, cold=True)
    if any(restored[key] == initial[key] for key in ("activity", "owner", "editor-owner", "pid")) \
            or restored["original-hash"] != initial["original-hash"]:
        raise AssertionError("The explicit cold start reused an old owner or lost its original snapshot")
    captures.append(cold.capture(prefix + "-cold"))
    return {"forced_mode": forced, "font_scale": case.scale, "status": "passed", "opposite_os_night": opposite,
            "cancel_path": "real-cancel-button" if forced == "DARK" else "real-visible-back",
            "native_input": input_record, "retained_native_editor": retained_editor,
            "observations": case.records, "native_targets": case.targets,
            "without_overlay_windows": windows, "cold_start": cold.launch_receipt, "cold_observed": restored,
            "native_starting_window_pixels_captured": False, "captures": captures}, cold


def exercise_theme_lifecycle(probe):
    """Four real cases; a restoration failure keeps the whole additional gate failed."""
    root = Path(__file__).resolve().parents[2]
    apk = root / "app/build/outputs/apk/debug/app-debug.apk"
    if apk.is_symlink() or not apk.resolve(strict=True).is_relative_to(root):
        raise AssertionError("Lifecycle debug APK escapes the checked source root")
    folder = root / "app/build/outputs/apk/preview/ui-screens"
    if folder.is_symlink() or not folder.resolve().is_relative_to(root):
        raise AssertionError("Lifecycle evidence escapes the checked source root")
    folder.mkdir(parents=True, exist_ok=True)
    session = uuid4().hex
    report = {"schema_version": 1, "fixture": SCREEN, "fixture_apk_sha256": hashlib.sha256(apk.read_bytes()).hexdigest(),
              "session": session, "status": "incomplete", "actual_device_observations": True,
              "external_broker_model_calls": False, "real_order_execution": False, "full_release_gate_claimed": False,
              "native_unavailable_source_path_exercised": False, "cases": [], "restoration": {}}
    begun = False
    original = None
    uid = None
    deadline = time.monotonic() + 900

    def restore_application(night, scale):
        if not begun:
            return {"restored": True, "application_changed": False}
        case = _launch(probe, session, "restore", scale, uid, time.monotonic() + 180, folder)
        first = case.current()
        mode = first["original-mode"]
        app_night = night if mode == "SYSTEM" else MODES[mode][0]
        value = case.expect("original-application-restored", mode=mode, saved=mode, os_night=night,
                            app_night=app_night, page="home", draft="THEME", saved_hash=first["original-hash"])
        if value["restored"] != "true" or original is not None and (
                value["original-hash"] != original["original-hash"] or value["stored-mode"] != original["stored-mode"]):
            raise AssertionError("The fixture did not restore the exact original keys/presence")
        before_close = window_receipt(probe, uid, 1)
        case.tap("Закрыть проверку", direction="end")
        after_close = window_receipt(probe, uid, 0)
        return {"restored": True, "application_changed": True, "observed": value,
                "before_dispose": before_close, "after_dispose": after_close}

    try:
        with restore_lifecycle_settings(probe, report["restoration"], restore_application):
            package_rows = probe.command("shell", "cmd", "package", "list", "packages", "-U", PACKAGE).strip()
            match = re.fullmatch(r"package:" + re.escape(PACKAGE) + r" uid:([1-9][0-9]{0,8})", package_rows)
            if match is None:
                raise AssertionError("The installed synthetic fixture package has no exact UID")
            uid = match.group(1)
            for scale in (1.0, 2.0):
                probe.command("shell", "settings", "put", "system", "font_scale", str(scale))
                phase = "continue" if begun else "begin"
                begun = True # An interrupted start may already have created the run-owned snapshot.
                case = _launch(probe, session, phase, scale, uid, deadline, folder)
                if original is None:
                    original = case.current()
                for forced in ("DARK", "LIGHT"):
                    row, case = _run_case(case, forced)
                    report["cases"].append(row)
        if {(row["forced_mode"], row["font_scale"]) for row in report["cases"]} != {
                (mode, scale) for mode in ("DARK", "LIGHT") for scale in (1.0, 2.0)} \
                or len(report["cases"]) != 4 or report["restoration"].get("restored") is not True:
            raise AssertionError("Lifecycle cases or exact restoration are incomplete")
        report["status"] = "passed"
        return report
    except BaseException as error:
        report["error_type"] = type(error).__name__
        report["error"] = str(error)
        try:
            probe.capture("theme-lifecycle-failure")
        except Exception as capture_error:
            report["failure_capture_error"] = type(capture_error).__name__
        raise
    finally:
        primary = sys.exc_info()[1]
        try:
            destination = folder / REPORT
            if destination.is_symlink():
                raise AssertionError("Lifecycle report destination is a link")
            destination.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            print("THEME_LIFECYCLE_VERIFICATION=" + json.dumps({"status": report["status"],
                "cases": len(report["cases"]), "restored": report["restoration"].get("restored", False),
                "report": REPORT, "sha256": hashlib.sha256(destination.read_bytes()).hexdigest()}), flush=True)
        except Exception as error:
            if primary is None:
                raise
            primary.add_note("Lifecycle evidence writing also failed: " + type(error).__name__ + ": " + str(error))
            print("THEME_LIFECYCLE_EVIDENCE_ERROR=" + type(error).__name__, flush=True)
