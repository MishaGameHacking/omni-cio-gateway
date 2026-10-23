"""Saved appearance, temporary preview and real Activity recreation."""
from business_ui_probe import labels
from native_input_evidence import display_geometry
from profile_launch import PACKAGE
from spatial_frame_evidence import ready_spatial_metrics

MOTION_DISABLED = 'Без движения'
BRIGHT_LIGHTING = 'Яркое освещение'


AREA = "workspace-content"
DIRTY = "Предпросмотр · настройки ещё не сохранены"
DEFAULT = {"motion": "LIVE", "bright_light": False, "accent": "AURORA", "depth": True, "density": "COMFORT"}
APPLIED = {"motion": "OFF", "bright_light": True, "accent": "OCEAN", "depth": True, "density": "COMPACT"}
PREVIEW = {**APPLIED, "motion": "SUBDUED", "bright_light": False}


def selected_control(tree, text, *, checked=None):
    """Read an actual native selected/radio/switch ancestor of its label."""
    for node in tree.iter("node"):
        if node.get("package") != PACKAGE or node.get("visible-to-user") != "true":
            continue
        selected = node.get("selected") == "true" or node.get("checked") == "true"
        if checked is None and not selected:
            continue
        if checked is not None and (node.get("checkable") != "true" or node.get("checked") != str(checked).lower()):
            continue
        if any(text in labels(child) for child in node.iter("node")
               if child.get("package") == PACKAGE and child.get("visible-to-user") == "true"):
            return node
    return None


def _expect_preferences(case, expected):
    return case.expect(lambda value: value["prefs"] == expected, "Observed appearance differs from the actual chosen controls")


def _reset(case):
    p = case.probe
    p.tap("Вернуть оформление по умолчанию", AREA)
    apply = p.reveal("Применить", AREA, direction="start")
    if apply.get("enabled") == "true":
        p.tap_node(apply)
    _expect_preferences(case, DEFAULT)


def _preview(case):
    p = case.probe
    p.reveal("Предпросмотр объёма, контраста и движения", AREA, direction="start")
    p.tap("Сдержанное", AREA)
    p.tap(BRIGHT_LIGHTING, AREA)
    _expect_preferences(case, PREVIEW)
    p.reveal(DIRTY, AREA, direction="start")


def _rotate_preview(case):
    p = case.probe
    original_geometry = display_geometry(p.tree())
    landscape = original_geometry[0] > original_geometry[1]
    rotation = p.command("shell", "settings", "get", "system", "user_rotation").strip()
    automatic = p.command("shell", "settings", "get", "system", "accelerometer_rotation").strip()
    try:
        p.command("shell", "settings", "put", "system", "accelerometer_rotation", "0")
        p.command("shell", "settings", "put", "system", "user_rotation", "0" if landscape else "1")
        p.wait_for(lambda: (size if ((size := display_geometry(p.tree()))[0] > size[1]) != landscape else None),
                   "Appearance Activity did not change its actual orientation")
        _expect_preferences(case, PREVIEW)
        p.reveal(DIRTY, AREA, direction="start")
        case.capture("preview-rotation")
        case.extra["appearance_rotation"] = {"before_geometry": original_geometry,
                                              "after_geometry": display_geometry(p.tree()),
                                              "unsaved_preview": PREVIEW}
    finally:
        for key, value in (("user_rotation", rotation), ("accelerometer_rotation", automatic)):
            if value in {"0", "1", "2", "3"}:
                p.command("shell", "settings", "put", "system", key, value)
            else:
                p.command("shell", "settings", "delete", "system", key)
        p.wait_for(lambda: display_geometry(p.tree()) == original_geometry, "Appearance rotation did not restore its original geometry")
        _expect_preferences(case, PREVIEW)


def exercise_appearance(case):
    p = case.probe
    p.find("Оформление")
    _reset(case)
    p.tap("Океан", AREA)
    p.tap("Компактно", AREA)
    p.tap(MOTION_DISABLED, AREA)
    p.tap(BRIGHT_LIGHTING, AREA)
    p.reveal(DIRTY, AREA, direction="start")
    p.tap("Применить", AREA)
    _expect_preferences(case, APPLIED)
    p.reveal("Оформление применено", AREA, direction="start")
    case.capture("applied")
    restored = case.launch()  # Same run/user, real process stop and relaunch.
    if restored["prefs"] != APPLIED:
        raise AssertionError("Applied appearance was not persisted across the real process restart")
    p.reveal(MOTION_DISABLED, AREA)
    p.wait_for(lambda: selected_control(p.tree(), MOTION_DISABLED), "Saved motion has no actual native selected state")
    p.reveal(BRIGHT_LIGHTING, AREA)
    p.wait_for(lambda: selected_control(p.tree(), BRIGHT_LIGHTING, checked=True), "Saved bright-light mode has no actual checked switch")
    def motion_off():
        actual = ready_spatial_metrics(p.tree())
        return actual if actual is not None and actual["motion"] == "Off" else None
    p.wait_for(motion_off, "Saved motion preference did not reach the genuine renderer")
    case.extra["saved_preferences_after_restart"] = restored["prefs"]
    case.capture("restored")
    _preview(case)
    p.tap("Отменить", AREA)
    _expect_preferences(case, APPLIED)
    _preview(case)
    _rotate_preview(case)
    p.tap("Отменить", AREA, direction="end")
    _expect_preferences(case, APPLIED)
    _reset(case)
    return ["appearance-explicit-apply", "same-user-process-restart-persistence",
            "native-radio-and-bright-switch-state", "saved-off-reaches-renderer",
            "preview-cancel-restores-saved", "unsaved-preview-survives-rotation"]
