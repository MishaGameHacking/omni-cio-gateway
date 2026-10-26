"""Finite native color observations; additive to, never a replacement for, original UI gates.

Only an existing authenticated frame session inside the canonical owned-emulator
lease may call exercise_theme_states. The 12 configurations have four captured
groups each. Native controls, live Material/Spectrum colors and captured pixels
must agree. A marker alone is never evidence of a rendered color or a click.
"""
from __future__ import annotations

from contextlib import contextmanager, nullcontext
from datetime import date
import hashlib
import json
import math
from pathlib import Path
import re
import secrets
import time
import xml.etree.ElementTree as ET

PACKAGE = "ru.omnicio.app.debug"
ACTIVITY = PACKAGE + "/ru.omnicio.app.ProfileUiProbeActivity"
PALETTE_SHA = "bec4160ad8794cc251968dd3bc8199dcedcd188d5796eff2e0c3cd320845cf95"
MODES = ("LIGHT", "DARK")
ACCENTS = ("AURORA", "OCEAN", "IRIS")
SCALES = (1.0, 2.0)
GROUPS = ("actions", "fields", "canvas", "overlay")
EXTRA_GROUPS = ("calendar",)
SHA = re.compile(r"[a-f0-9]{64}")
BOUNDS = re.compile(r"\[(-?\d+),(-?\d+)\]\[(-?\d+),(-?\d+)\]")
STATE_KEYS = {"clicks", "down", "native", "spatial", "choice", "tab", "selected", "input", "destination", "overlay", "dialog", "period"}


def _pairs(parts, separator):
    result = {}
    for part in parts:
        key, found, value = part.partition(separator)
        if not found or not key or key in result:
            raise AssertionError("Missing or duplicate theme observation field")
        result[key] = value
    return result


def _json_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise AssertionError("Duplicate expected palette field")
        result[key] = value
    return result


def rgb(value):
    if not isinstance(value, str) or re.fullmatch(r"ff[0-9a-f]{6}", value) is None:
        raise AssertionError("Theme colors must be opaque observed sRGB values")
    return tuple(int(value[index:index + 2], 16) for index in (2, 4, 6))


def _expected(mode, accent):
    if mode not in MODES or accent not in ACCENTS:
        raise ValueError("Unknown theme configuration")
    path = Path(__file__).with_name("theme_palette_expectations.json")
    raw = path.read_bytes()
    if len(raw) > 65536:
        raise AssertionError("Expected palette exceeds its bounded contract")
    data = json.loads(raw, object_pairs_hook=_json_pairs)
    if data.get("schema") != 1 or data.get("approved_palette_sha256") != PALETTE_SHA \
            or set(data.get("accents", {})) != set(ACCENTS):
        raise AssertionError("Unreviewed native palette expectation")
    selected = data["accents"][accent][mode.lower()]
    if len(selected["material"]) != 48 or len(selected["semantic"]) != 19 or len(selected["chartSeries"]) != 6:
        raise AssertionError("Incomplete native palette expectation")
    colors = {key: "ff" + value.lower() for group in ("material", "semantic")
              for key, value in selected[group].items()}
    if len(colors) != 67:
        raise AssertionError("Overlapping expected color roles")
    colors.update({"series" + str(index): "ff" + color.lower() for index, color in enumerate(selected["chartSeries"])})
    for color in colors.values():
        rgb(color)
    # This is the independently computed expected 8% onPrimary state layer.
    colors["pressedPrimary"] = "ff" + "".join(f"{math.floor(a * .92 + b * .08 + .5):02x}"
        for a, b in zip(rgb(colors["primary"]), rgb(colors["onPrimary"])))
    return colors


def owned_window(tree):
    if tree is None or tree.get("root-window-present") != "true" or tree.get("root-window-focused") != "true":
        raise AssertionError("Theme evidence requires a fresh focused application window")
    values = [tree.get(key, "") for key in ("display-width", "display-height", "active-window-id")]
    if any(re.fullmatch(r"[0-9]{1,6}", value) is None for value in values):
        raise AssertionError("Missing theme window geometry or identity")
    width, height, window = map(int, values)
    roots = [child for child in tree if child.tag == "node"]
    if not 16 <= width <= 8192 or not width < height <= 8192 or len(roots) != 1 \
            or roots[0].get("package") != PACKAGE or roots[0].get("visible-to-user") != "true":
        raise AssertionError("Theme frame does not belong to the owned portrait app")
    return width, height, window


def owned_target(tree, resource, *, density=1.0, touch=False, enabled=None, selected=None, checked=None):
    width, height, _ = owned_window(tree)
    if not math.isfinite(density) or density <= 0:
        raise AssertionError("Invalid observed theme density")
    names = {resource, PACKAGE + ":id/" + resource}
    matches = [node for node in tree.iter("node") if node.get("resource-id") in names
               and node.get("visible-to-user") != "false"]
    if len(matches) != 1:
        raise AssertionError("Missing or ambiguous theme target: " + resource)
    node = matches[0]
    parents = {child: parent for parent in tree.iter() for child in parent}
    match = BOUNDS.fullmatch(node.get("bounds", ""))
    if node.get("package") != PACKAGE or node.get("visible-to-user") != "true" or match is None:
        raise AssertionError("Foreign, hidden or malformed theme target: " + resource)
    bounds = tuple(map(int, match.groups()))
    left, top, right, bottom = bounds
    if not (0 <= left < right <= width and 0 <= top < bottom <= height):
        raise AssertionError("Theme target is clipped or off screen: " + resource)
    for attribute, expected in (("enabled", enabled), ("selected", selected), ("checked", checked)):
        if expected is not None and node.get(attribute) != str(expected).lower():
            raise AssertionError("Actual native theme state differs: " + resource + "/" + attribute)
    if touch and (node.get("enabled") != "true" or node.get("clickable") != "true"
                  or node.get("focusable") != "true" or right - left < math.ceil(48 * density)
                  or bottom - top < math.ceil(48 * density)):
        raise AssertionError("Theme action lacks an enabled native 48 dp owner: " + resource)
    current = parents.get(node)
    while current is not None and current.tag == "node":
        if current.get("package") != PACKAGE or current.get("visible-to-user") != "true" \
                or touch and current.get("enabled") == "false":
            raise AssertionError("Theme target has a hidden or foreign native ancestor")
        if current.get("scrollable") == "true":
            parent = BOUNDS.fullmatch(current.get("bounds", ""))
            if parent is None:
                raise AssertionError("Theme target lacks its actual scroll viewport")
            a, b, c, d = map(int, parent.groups())
            if not (a <= left < right <= c and b <= top < bottom <= d):
                raise AssertionError("Theme target is clipped by its actual scroll viewport")
        current = parents.get(current)
    return node, bounds


def theme_observation(tree, *, mode, accent, scale, group, nonce, validate_palette=True):
    width, height, window = owned_window(tree)
    if group not in GROUPS + EXTRA_GROUPS or re.fullmatch(r"[a-f0-9]{32}", nonce or "") is None:
        raise ValueError("Invalid requested theme frame identity")
    records = []
    for node in tree.iter("node"):
        text = node.get("content-desc", "")
        if "theme-probe:" not in text or node.get("visible-to-user") == "false":
            continue
        if node.get("package") != PACKAGE or node.get("visible-to-user") != "true" or len(text) > 8192:
            raise AssertionError("Foreign or oversized theme marker")
        marker = _pairs(text.split(";"), ":")
        required = {"theme-probe", "theme-group", "theme-run", "theme-mode", "theme-accent", "theme-motion",
                    "theme-saved-mode", "theme-saved-accent", "theme-saved-motion", "theme-font-scale",
                    "theme-density", "theme-original", "theme-state", "theme-colors"}
        if set(marker) != required or marker["theme-probe"] != "production-v1":
            raise AssertionError("Incomplete actual theme observation")
        bounds = BOUNDS.fullmatch(node.get("bounds", ""))
        if bounds is None:
            raise AssertionError("Theme marker has no native bounds")
        a, b, c, d = map(int, bounds.groups())
        if not (0 <= a < c <= width and 0 <= b < d <= height):
            raise AssertionError("Theme marker is not visible in this window")
        records.append(marker)
    if not records or any(record != records[0] for record in records[1:]):
        raise AssertionError("Missing or conflicting actual theme markers")
    marker = records[0]
    for key, expected in {"theme-group": group, "theme-run": nonce, "theme-mode": mode, "theme-accent": accent,
                          "theme-saved-mode": mode, "theme-saved-accent": accent}.items():
        if marker[key] != expected:
            raise AssertionError("Actual theme configuration differs: " + key)
    if marker["theme-motion"] != marker["theme-saved-motion"] or marker["theme-motion"] not in {"OFF", "SUBDUED", "LIVE"}:
        raise AssertionError("Actual theme motion preference did not commit")
    density = float(marker["theme-density"])
    font = float(marker["theme-font-scale"])
    if not math.isfinite(density) or not 0 < density <= 8 or not math.isfinite(font) \
            or not math.isclose(font, scale, rel_tol=0, abs_tol=1e-6):
        raise AssertionError("Actual font scale or density differs from the theme case")
    original = marker["theme-original"].split(",")
    if len(original) != 3 or original[0] not in MODES + ("SYSTEM",) or original[1] not in ACCENTS \
            or original[2] not in {"OFF", "SUBDUED", "LIVE"}:
        raise AssertionError("Theme fixture cannot restore its original saved preferences")
    state = _pairs(marker["theme-state"].split(","), "=")
    if set(state) != STATE_KEYS or any(state[name] not in {"true", "false"} for name in ("down", "native", "spatial", "choice", "dialog")) \
            or not re.fullmatch(r"[0-9]{1,5}", state["clicks"]) or state["tab"] not in {"0", "1"} \
            or state["selected"] not in {"-1", "4"} or state["input"] != "ТЕМА" \
            or state["destination"] not in {"Home", "Actions", "Profile"} or state["overlay"] not in {"drawer", "dialog", "rail"}:
        raise AssertionError("Invalid actual theme component state")
    period = state["period"].split("/")
    if len(period) != 3 or any(re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value) is None for value in period):
        raise AssertionError("Invalid observed synthetic calendar period")
    first, last, today = map(date.fromisoformat, period)
    if not first <= last < today:
        raise AssertionError("Theme calendar does not use the expected past synthetic period")
    colors = _pairs(marker["theme-colors"].split(","), "=")
    for color in colors.values():
        rgb(color)
    if validate_palette:
        expected = _expected(mode, accent)
        if set(colors) != set(expected):
            raise AssertionError("The live theme did not report every expected role")
        for key, color in expected.items():
            tolerance = 1 if key == "pressedPrimary" else 0
            if max(abs(a - b) for a, b in zip(rgb(colors[key]), rgb(color))) > tolerance:
                raise AssertionError("The live compiled color differs from the approved role: " + key)
    return {"mode": mode, "accent": accent, "font_scale": font, "density": density, "group": group, "nonce": nonce,
            "window_id": window, "width": width, "height": height, "original": original,
            "motion": marker["theme-motion"], "state": state, "colors": colors}


def contrast(first, second):
    def luminance(color):
        scaled = [channel / 255 for channel in color]
        linear = [channel / 12.92 if channel <= .04045 else ((channel + .055) / 1.055) ** 2.4 for channel in scaled]
        return sum(channel * weight for channel, weight in zip(linear, (.2126, .7152, .0722)))
    a, b = luminance(first), luminance(second)
    return (max(a, b) + .05) / (min(a, b) + .05)


def color_pixels(image, bounds, color, *, minimum=3, tolerance=5):
    matches = sum(max(abs(a - b) for a, b in zip(pixel, color)) <= tolerance
                  for pixel in image.colors(bounds, step=1))
    if matches < minimum:
        raise AssertionError("Required actual color is absent from its visible component")
    return matches


def paired_pixels(image, bounds, foreground, background, *, threshold=4.5):
    ratio = contrast(foreground, background)
    if ratio < threshold:
        raise AssertionError("Actual component color pair is below its contrast requirement")
    return {"bounds": list(bounds), "foreground_rgb": list(foreground), "background_rgb": list(background),
            "foreground_pixels": color_pixels(image, bounds, foreground),
            "background_pixels": color_pixels(image, bounds, background, minimum=10),
            "contrast": ratio, "required_contrast": threshold}


def primary_button_pixels(image, bounds, density, foreground, background):
    """Sample the actual text region inside the production 18dp-radius button.

    SpectrumPrimaryButton's content padding is 18dp horizontally and 12dp
    vertically. Its rounded exterior is deliberately excluded: in LIGHT a
    white page corner must never impersonate a correctly painted white glyph.
    """
    if not math.isfinite(density) or not 0 < density <= 8:
        raise AssertionError("Invalid actual primary-button density")
    left, top, right, bottom = bounds
    x, y = math.ceil(18 * density), math.ceil(12 * density)
    interior = (left + x, top + y, right - x, bottom - y)
    if interior[0] >= interior[2] or interior[1] >= interior[3]:
        raise AssertionError("The real primary button has no bounded content interior")
    return {"native_bounds": list(bounds),
            **paired_pixels(image, interior, foreground, background)}


def monochrome_pixels(image, bounds, ink, background):
    """Allow anti-aliasing/alpha only along the real ink-to-background segment."""
    vector = [a - b for a, b in zip(ink, background)]
    length = sum(value * value for value in vector)
    if length == 0:
        raise AssertionError("Monochrome glyph is indistinguishable from its surface")
    bad = 0
    for pixel in image.colors(bounds, step=1):
        fraction = max(0, min(1, sum((a - b) * v for a, b, v in zip(pixel, background, vector)) / length))
        if max(abs(a - (b + fraction * v)) for a, b, v in zip(pixel, background, vector)) > 8:
            bad += 1
    if bad:
        raise AssertionError("Monochrome or disabled artwork retained a foreign support color")
    return {"bounds": list(bounds), "ink_pixels": color_pixels(image, bounds, ink, minimum=8), "foreign_pixels": bad}


def switch_pixels(image, bounds, density, *, native, checked, foreground, background):
    left, top, right, bottom = bounds
    cx, cy = (left + right) / 2, (top + bottom) / 2
    # The actual production widgets are 52x32 (Material) and 46x28 (Spatial).
    # Sample inside the thumb, never white page pixels outside its track.
    offset = (10 if native else 11.5) * density
    tx = cx + (offset if checked else -offset)
    bx = cx + (-offset if checked else offset)
    radius = max(1, math.floor(2 * density))
    def region(x):
        return (math.floor(x) - radius, math.floor(cy) - radius,
                math.floor(x) + radius + 1, math.floor(cy) + radius + 1)
    thumb, track = region(tx), region(bx)
    if not (left <= thumb[0] < thumb[2] <= right and top <= thumb[1] < thumb[3] <= bottom
            and left <= track[0] < track[2] <= right and top <= track[1] < track[3] <= bottom):
        raise AssertionError("Switch samples escaped the actual native component")
    ratio = contrast(foreground, background)
    if ratio < 3:
        raise AssertionError("The actual switch thumb lacks control contrast")
    return {"bounds": list(bounds), "thumb_bounds": list(thumb), "track_bounds": list(track),
            "thumb_pixels": color_pixels(image, thumb, foreground, minimum=3),
            "track_pixels": color_pixels(image, track, background, minimum=3), "contrast": ratio,
            "checked": checked, "native_material_switch": native}


def history_pixels(image, bars, colors):
    left, top, right, bottom = bars
    width, height = right - left, bottom - top
    found = []
    for index, value in enumerate((-20, 0, None, 10, 40, 80)):
        if value is None:
            continue
        x = left + width * (index + .5) / 6
        y = top + height * (.8 if value == 0 else (.8 + (.8 - value / 100)) / 2)
        rect = (math.floor(x) - 1, math.floor(y), math.floor(x) + 2, math.floor(y) + (1 if value == 0 else 2))
        ink = rgb(colors["error"] if value < 0 else colors["info"])
        found.append({"index": index, "value": value, "color_rgb": list(ink),
                      "pixels": color_pixels(image, rect, ink, minimum=2)})
    # A missing observation is a baseline mark, not an invented zero-valued bar.
    mx, my = left + width * 2.5 / 6, top + height * .8
    missing = (math.floor(mx) - 4, math.floor(my), math.floor(mx) + 5, math.floor(my) + 1)
    missing_pixels = color_pixels(image, missing, rgb(colors["chartAxis"]), minimum=3)
    selected = (math.floor(left + width * 4.16 / 6), math.floor(top + height * .4),
                math.ceil(left + width * 4.84 / 6), math.ceil(top + height * .8))
    inner = (selected[0] + 2, selected[1] + 2, selected[2] - 2, selected[3] - 2)
    halo = {"chartSelectedOuter": color_pixels(image, selected, rgb(colors["chartSelectedOuter"]), minimum=3),
            "chartSelectedInner": color_pixels(image, inner, rgb(colors["chartSelectedInner"]), minimum=3)}
    return {"bars": found, "missing_axis_pixels": missing_pixels, "selection_halo": halo}


def canvas_pixels(image, tree, colors):
    history = history_pixels(image, owned_target(tree, "theme-sample-bars")[1], colors)
    _, ring = owned_target(tree, "theme-sample-ring")
    a, b, c, d = ring
    cx, cy = (a + c) / 2, (b + d) / 2
    side = min(c - a, d - b)
    radius = side * .405  # middle of the actual production .62 hollow annulus
    cursor, sectors = 0, []
    for index, fraction in enumerate((.30, .20, .15, .15, .10, .10)):
        angle = (cursor + fraction / 2) * 2 * math.pi - math.pi / 2
        x, y = cx + math.cos(angle) * radius, cy + math.sin(angle) * radius
        area = (math.floor(x) - 1, math.floor(y) - 1, math.floor(x) + 2, math.floor(y) + 2)
        sectors.append({"index": index, "fraction": fraction,
                        "pixels": color_pixels(image, area, rgb(colors["series" + str(index)]), minimum=3)})
        cursor += fraction
    mono = owned_target(tree, "theme-sample-mono")[1]
    disabled = owned_target(tree, "theme-sample-decorative-disabled")[1]
    decorative = owned_target(tree, "theme-sample-decorative")[1]
    art = {"mono": monochrome_pixels(image, mono, rgb(colors["onPrimary"]), rgb(colors["primary"])),
           "disabled": monochrome_pixels(image, disabled, rgb(colors["disabledInk"]), rgb(colors["surface"])),
           "decorative_colors": {key: color_pixels(image, decorative, rgb(colors[key]), minimum=3)
                                 for key in ("series5", "tertiary", "warning", "error")}}
    return {**history, "sectors": sectors, "artwork": art}


def _calendar_label(node):
    """Material Day exposes its full localized date; its digit Text clears semantics."""
    role = node.get("class") == "android.widget.Button" or any(
        child.get("class") == "android.widget.Button" and child.get("clickable") == "false"
        and not child.get("text") and not child.get("content-desc") and not list(child) for child in node)
    if not role:
        return None
    for label in (node.get("text", ""), node.get("content-desc", "")):
        numbers = re.findall(r"\d+", label)
        years = [value for value in numbers if len(value) == 4 and 1900 <= int(value) <= 2100]
        rest = [value for value in numbers if value not in years]
        if len(years) == 1 and 1 <= len(rest) <= 2 and all(1 <= int(value) <= 31 for value in rest):
            if len(label) > 320:
                raise AssertionError("Native calendar date label exceeds its bounded contract")
            return label
    return None


def _calendar_ancestors(node, parents, bounds, *, scrolling=False):
    a, b, c, d = bounds
    visible, has_scroll = True, False
    current = parents.get(node)
    while current is not None and current.tag == "node":
        if current.get("package") != PACKAGE or current.get("visible-to-user") != "true" \
                or scrolling and current.get("enabled") == "false":
            raise AssertionError("Native calendar target has a foreign, hidden or disabled ancestor")
        if current.get("scrollable") == "true":
            has_scroll = True
            boundary = BOUNDS.fullmatch(current.get("bounds", ""))
            if boundary is None:
                raise AssertionError("Calendar scroll viewport is malformed")
            x1, y1, x2, y2 = map(int, boundary.groups())
            visible = visible and x1 <= a < c <= x2 and y1 <= b < d <= y2
        current = parents.get(current)
    return visible, has_scroll


def calendar_cells(tree, density):
    """Read full native date labels and selected/disabled owners inside the real calendar list."""
    width, height, window = owned_window(tree)
    if not math.isfinite(density) or not 0 < density <= 8:
        raise AssertionError("Invalid actual calendar density")
    parents = {child: parent for parent in tree.iter() for child in parent}
    result = []
    for node in tree.iter("node"):
        if node.get("visible-to-user") != "true":
            continue
        label = _calendar_label(node)
        if label is None:
            continue
        if node.get("package") != PACKAGE:
            raise AssertionError("A foreign button cannot supply native calendar colors")
        raw = BOUNDS.fullmatch(node.get("bounds", ""))
        if raw is None:
            raise AssertionError("Native calendar cell has malformed bounds")
        a, b, c, d = map(int, raw.groups())
        visible, has_scroll = _calendar_ancestors(node, parents, (a, b, c, d))
        if not (0 <= a < c <= width and 0 <= b < d <= height) \
                or c - a < math.ceil(48 * density) or d - b < math.ceil(48 * density) or not visible or not has_scroll:
            continue  # A clipped/undersized cell is never counted or touched.
        enabled, selected = node.get("enabled"), node.get("selected")
        if enabled not in {"true", "false"} or selected not in {"true", "false"}:
            raise AssertionError("Native calendar state is missing")
        result.append({"native_date_label": label,
                       "enabled": enabled == "true", "selected": selected == "true", "bounds": [a, b, c, d],
                       "window_id": window})
    identities = [(tuple(cell["bounds"]), cell["native_date_label"]) for cell in result]
    if len(result) > 84 or len(identities) != len(set(identities)):
        raise AssertionError("Ambiguous or unbounded native calendar cells")
    return result


def calendar_scroll_viewport(tree, density):
    width, height, _ = owned_window(tree)
    if not math.isfinite(density) or not 0 < density <= 8:
        raise AssertionError("Invalid actual calendar density")
    parents = {child: parent for parent in tree.iter() for child in parent}
    candidates = []
    for node in tree.iter("node"):
        if node.get("scrollable") != "true" or node.get("visible-to-user") != "true":
            continue
        if not any(_calendar_label(child) is not None for child in node.iter("node")
                   if child.get("visible-to-user") == "true"):
            continue
        if node.get("package") != PACKAGE or node.get("enabled") != "true":
            raise AssertionError("Calendar scrolling requires an enabled owned viewport")
        raw = BOUNDS.fullmatch(node.get("bounds", ""))
        if raw is None:
            raise AssertionError("Actual calendar scrolling viewport is malformed")
        bounds = tuple(map(int, raw.groups()))
        a, b, c, d = bounds
        visible, _ = _calendar_ancestors(node, parents, bounds, scrolling=True)
        if visible and 0 <= a < c <= width and 0 <= b < d <= height and d - b >= 120 * density:
            candidates.append(bounds)
    if not candidates:
        raise AssertionError("The calendar has no owned visible date-scroll viewport")
    return min(candidates, key=lambda value: (value[2] - value[0]) * (value[3] - value[1]))


def calendar_pixels(image, tree, before):
    width, height, window = owned_window(tree)
    if window == before["window_id"] or (image.width, image.height) != (width, height):
        raise AssertionError("Calendar pixels do not belong to the actual separate dialog")
    cells = calendar_cells(tree, before["density"])
    selected = [cell for cell in cells if cell["selected"] and cell["enabled"]]
    disabled = [cell for cell in cells if not cell["enabled"]]
    if not selected or not disabled:
        raise AssertionError("Actual selected and disabled calendar dates must be visible together")
    colors = before["colors"]
    measurements = []
    # Count only these observed states; no claim about off-screen dates, years,
    # range interiors or the calendar's alternative keyboard input mode.
    for cell in selected + disabled:
        if cell["enabled"]:
            foreground, background, threshold = "onPrimary", "primary", 4.5
        elif cell["selected"]:
            foreground, background, threshold = "disabledInk", "disabledContainer", 3
        else:
            foreground, background, threshold = "disabledInk", "surface", 3
        a, b, c, d = cell["bounds"]
        radius = math.floor(13 * before["density"])
        cx, cy = (a + c) // 2, (b + d) // 2
        ink_bounds = (cx - radius, cy - radius, cx + radius, cy + radius)
        # In light mode onPrimary is also the page color. Restrict the sample to
        # the selected day's central circle so page pixels cannot impersonate ink.
        measurements.append({**cell, "native_bounds": cell["bounds"],
                             **paired_pixels(image, ink_bounds, rgb(colors[foreground]),
                                             rgb(colors[background]), threshold=threshold)})
    return {"window_id": window, "selected_dates_observed": len(selected), "disabled_dates_observed": len(disabled),
            "cells": measurements, "offscreen_states_claimed": False, "keyboard_input_mode_claimed": False}


def frame_pixels(image, tree, observed):
    if (image.width, image.height) != (observed["width"], observed["height"]):
        raise AssertionError("Captured pixels and current native viewport differ")
    c = observed["colors"]
    result = {}
    def pair(name, foreground, background, threshold=4.5, resource=None):
        bounds = owned_target(tree, resource or "theme-sample-" + name)[1]
        result[name] = paired_pixels(image, bounds, rgb(c[foreground]), rgb(c[background]), threshold=threshold)
    if observed["group"] == "actions":
        primary = owned_target(tree, "theme-control-primary", enabled=True)[1]
        result["primary"] = primary_button_pixels(image, primary, observed["density"],
            rgb(c["onPrimary"]), rgb(c["pressedPrimary"]))
        pair("primary-disabled", "disabledInk", "disabledContainer", 3)
        pair("secondary", "onSurface", "surfaceContainerHighest")
        pair("secondary-disabled", "disabledInk", "disabledContainer", 3)
        pair("choice", "onPrimaryContainer", "primaryContainer")
        pair("choice-disabled", "disabledInk", "disabledContainer", 3)
        pair("tab-selected", "onPrimaryContainer", "primaryContainer", resource="theme-tabs-item-1")
        pair("text", "onSurface", "surfaceContainerHighest")
        pair("text-disabled", "disabledInk", "disabledContainer", 3)
        for native in (True, False):
            for suffix, checked, enabled in (("on", True, True), ("off", False, True),
                                             ("disabled-on", True, False), ("disabled-off", False, False)):
                name = ("native-" if native else "spatial-") + suffix
                node, _ = owned_target(tree, "theme-control-" + name, enabled=enabled, checked=checked)
                if node.get("checkable") != "true":
                    raise AssertionError("Switch is not an actual checkable native control")
                bounds = owned_target(tree, "theme-sample-" + name)[1]
                foreground, background = ("disabledInk", "disabledContainer") if not enabled else \
                    (("onPrimary", "primary") if checked else ("outline", "surfaceContainerHighest"))
                result[name] = switch_pixels(image, bounds, observed["density"], native=native,
                    checked=checked, foreground=rgb(c[foreground]), background=rgb(c[background]))
    elif observed["group"] == "fields":
        pair("input", "onSurface", "primaryContainer")
        pair("input-error", "onSurface", "surfaceContainerHighest")
        pair("input-disabled", "disabledInk", "disabledContainer", 3)
        for name, foreground, background in (("success", "onSuccessContainer", "successContainer"),
                ("warning", "onWarningContainer", "warningContainer"), ("error", "onErrorContainer", "errorContainer"),
                ("info", "onInfoContainer", "infoContainer")):
            pair(name, foreground, background)
        for name, ink in (("input", "primary"), ("input-error", "error")):
            result[name + "-outline"] = color_pixels(image, owned_target(tree, "theme-sample-" + name)[1], rgb(c[ink]), minimum=6)
        result["input-base-fill"] = color_pixels(image, owned_target(tree, "theme-sample-input")[1],
                                                 rgb(c["surfaceContainerHighest"]), minimum=10)
        for name, foreground, background in (("slider", "primary", "surfaceContainerHighest"),
                                              ("slider-disabled", "disabledInk", "disabledContainer")):
            pair(name, foreground, background, 3)
    elif observed["group"] == "canvas":
        result = canvas_pixels(image, tree, c)
    elif observed["group"] == "overlay":
        variant = observed["state"]["overlay"]
        if variant == "dialog":
            pair("dialog-label", "onSurface", "surface")
            primary = owned_target(tree, "theme-control-dialog-close", enabled=True)[1]
            result["dialog-primary"] = primary_button_pixels(image, primary, observed["density"],
                rgb(c["onPrimary"]), rgb(c["primary"]))
        else:
            prefix = "navigation-primary-" if variant == "drawer" else "rail-destination-"
            owned_target(tree, prefix + "actions", selected=True)
            owned_target(tree, prefix + "home", selected=False)
            pair("selected-destination", "onPrimaryContainer", "primaryContainer", resource=prefix + "actions")
            pair("unselected-destination", "onSurface" if variant == "drawer" else "onSurfaceVariant",
                 "surfaceContainerLow" if variant == "drawer" else "surface", resource=prefix + "home")
    else:
        raise AssertionError("Only the declared finite groups can count as captured theme cases")
    return result


def _installed_apk(probe, package):
    if package not in {PACKAGE, "ru.omnicio.ciframe"}:
        raise ValueError("Unsupported theme artifact package")
    lines = probe.command("shell", "pm", "path", package).splitlines()
    if len(lines) != 1 or not lines[0].startswith("package:"):
        raise AssertionError("Theme APK path is missing, split or ambiguous")
    path = lines[0].removeprefix("package:").strip()
    if re.fullmatch(r"/data/app/[A-Za-z0-9._~+=/-]{1,512}/base\.apk", path) is None or ".." in path:
        raise AssertionError("Unexpected installed theme APK path")
    result = probe.command("shell", "sha256sum", path).split()
    if len(result) != 2 or SHA.fullmatch(result[0]) is None or result[1] != path:
        raise AssertionError("Installed theme APK hash is unavailable")
    return result[0]


def _identity(probe, admitted):
    from navigation_detail_probe import _owned_emulator
    required = {"source_inventory_sha256", "debug_apk_sha256", "driver_apk_sha256", "version_code", "version_name"}
    if set(admitted) != required or any(SHA.fullmatch(admitted.get(key, "")) is None
            for key in ("source_inventory_sha256", "debug_apk_sha256", "driver_apk_sha256")) \
            or type(admitted["version_code"]) is not int or admitted["version_code"] <= 0 \
            or re.fullmatch(r"[0-9][0-9A-Za-z_.-]{0,79}", admitted["version_name"]) is None:
        raise ValueError("Incomplete admitted theme build identity")
    owned = _owned_emulator(probe)
    actual = {"debug_apk_sha256": _installed_apk(probe, PACKAGE),
              "driver_apk_sha256": _installed_apk(probe, "ru.omnicio.ciframe")}
    dump = probe.command("shell", "dumpsys", "package", PACKAGE)
    codes = set(re.findall(r"^\s*versionCode=([0-9]+)\b", dump, re.M))
    names = set(re.findall(r"^\s*versionName=([^\s]+)\s*$", dump, re.M))
    if codes != {str(admitted["version_code"])} or names != {admitted["version_name"]} \
            or any(actual[key] != admitted[key] for key in actual):
        raise AssertionError("The installed fixture/driver differs from the admitted build")
    api = probe.command("shell", "getprop", "ro.build.version.sdk").strip()
    page = probe.command("shell", "getconf", "PAGE_SIZE").strip()
    if api != "37" or page not in {"4096", "16384"}:
        raise AssertionError("Theme evidence is not from the required native API37 kernel")
    return {**owned, **admitted, "installed_debug_apk_sha256": actual["debug_apk_sha256"],
            "installed_driver_apk_sha256": actual["driver_apk_sha256"], "api": 37, "page_size_bytes": int(page)}


def restored_preference_snapshot(value, original=None):
    """Require acknowledged restoration of the exact original nine keys/presence."""
    if value.get("phase") != "restore" or value.get("restored") != "true" \
            or value.get("mode") != value.get("original-mode") or value.get("saved-mode") != value.get("original-mode") \
            or SHA.fullmatch(value.get("original-hash", "")) is None \
            or value.get("saved-hash") != value.get("original-hash"):
        raise AssertionError("The theme session did not restore the exact original preference snapshot")
    if original is not None and any(value.get(key) != original.get(key)
            for key in ("original-hash", "original-mode", "stored-mode", "saved-accent")):
        raise AssertionError("The restored theme snapshot differs from its pre-write observation")
    return {"sha256": value["original-hash"], "mode": value["original-mode"],
            "initial_marker_observed": original is not None, "exact_key_presence_restored": True}


@contextmanager
def preserve_theme_preferences(probe, folder, scale, receipt):
    """Use the debug run-owned snapshot before the first color preference write.

    The caller has already admitted the exact installed APK/driver; the current
    PID's canonical emulator lease is checked again here. A lost first marker still enters the restore
    path: the native Activity may already have persisted its run-owned snapshot.
    These begin/restore launches capture no extra screenshots.
    """
    from theme_lifecycle_probe import _launch, strict_night_setting, window_receipt
    from navigation_detail_probe import _owned_emulator
    owned = _owned_emulator(probe)
    rows = probe.command("shell", "cmd", "package", "list", "packages", "-U", PACKAGE).strip()
    match = re.fullmatch(r"package:" + re.escape(PACKAGE) + r" uid:([1-9][0-9]{0,8})", rows)
    if match is None:
        raise AssertionError("The admitted theme fixture has no exact native UID")
    uid, session = match.group(1), secrets.token_hex(16)
    policy = strict_night_setting(probe.command("shell", "cmd", "uimode", "night"))
    original, failure = None, None
    receipt.update(session=session, native_uid=uid, owned_emulator=owned, original_global_policy=policy, restored=False)
    try:
        case = _launch(probe, session, "begin", float(scale), uid, time.monotonic() + 180, folder)
        original = case.current()
        if original["phase"] != "begin" or original["saved-hash"] != original["original-hash"]:
            raise AssertionError("The theme snapshot was not observed before preference mutation")
        receipt["pre_write_observation"] = original
        yield
    except BaseException as error:
        failure = error
        raise
    finally:
        errors = []
        try:
            # Restore font geometry before the independently bounded cleanup
            # launch; no color-case marker or exhausted case deadline is needed.
            probe.command("shell", "settings", "put", "system", "font_scale", scale)
            if probe.command("shell", "settings", "get", "system", "font_scale").strip() != scale:
                raise AssertionError("The snapshot restoration font scale did not apply")
        except BaseException as error:
            errors.append(error)
        try:
            # Font transport failure must not suppress the independent nine-key
            # restore before Activity.setContent. Its native proof still fails
            # closed if the expected geometry cannot actually be observed.
            case = _launch(probe, session, "restore", float(scale), uid, time.monotonic() + 180, folder)
            value = case.current()
            snapshot = restored_preference_snapshot(value, original)
            if strict_night_setting(probe.command("shell", "cmd", "uimode", "night")) != policy:
                raise AssertionError("The color suite changed the original global theme policy")
            before = window_receipt(probe, uid, 1)
            case.tap("Закрыть проверку", direction="end")
            after = window_receipt(probe, uid, 0)
            receipt.update(snapshot_restored=True, snapshot=snapshot, restored_observation=value,
                           before_dispose=before, after_dispose=after)
        except BaseException as error:
            errors.append(error)
        receipt["restored"] = not errors and receipt.get("snapshot_restored") is True
        if errors:
            receipt["errors"] = [{"type": type(error).__name__, "message": str(error)} for error in errors]
            if failure is None:
                for extra in errors[1:]:
                    errors[0].add_note("Additional cleanup failure: " + type(extra).__name__ + ": " + str(extra))
                raise errors[0]
            for error in errors:
                failure.add_note("Exact theme snapshot restoration also failed: " + type(error).__name__ + ": " + str(error))


def overlay_variant(mode, accent, scale):
    return ("drawer", "dialog", "rail")[(ACCENTS.index(accent) + (2 if mode == "DARK" else 0) + (1 if scale == 2 else 0)) % 3]


class _ThemeCase:
    def __init__(self, probe, mode, accent, scale, group):
        self.probe, self.mode, self.accent, self.scale, self.group = probe, mode, accent, scale, group
        self.nonce = secrets.token_hex(16)
        self.phase = "launch"
        self.initial = None

    def observed(self):
        return theme_observation(self.probe.tree(), mode=self.mode, accent=self.accent, scale=self.scale,
                                 group=self.group, nonce=self.nonce, validate_palette=True)

    def await_state(self, *, window=None, not_window=None, **values):
        def ready():
            seen = self.observed()
            return seen if all(seen["state"].get(key) == value for key, value in values.items()) \
                and (window is None or seen["window_id"] == window) \
                and (not_window is None or seen["window_id"] != not_window) else None
        return self.probe.wait_for(ready, "Actual theme component state did not follow its native action")

    def launch(self, motion="OFF"):
        from profile_launch import profile_resumed, start_status
        self.probe.command("shell", "am", "force-stop", PACKAGE)
        self.probe.command("shell", "settings", "put", "system", "font_scale", str(self.scale))
        output = self.probe.command("shell", "am", "start", "-W", "-n", ACTIVITY,
            "--es", "spectrum_screen", "theme", "--es", "spectrum_probe_run", self.nonce,
            "--es", "theme_group", self.group, "--es", "theme_mode", self.mode,
            "--es", "theme_accent", self.accent, "--es", "theme_motion", motion, timeout=45)
        if start_status(output) != "ok":
            raise AssertionError("Theme fixture did not launch successfully")
        self.probe.wait_for(lambda: profile_resumed(self.probe.command("shell", "dumpsys", "activity", "activities")),
                            "Theme fixture is not the resumed native activity")
        # A theme apply can produce a short initial composition with the previous
        # colors. Wait for the exact saved configuration before strict validation.
        def committed():
            tree = self.probe.tree()
            if tree is None:
                return None
            texts = [n.get("content-desc", "") for n in tree.iter("node") if n.get("package") == PACKAGE
                     and n.get("visible-to-user") == "true"]
            required = {"theme-run:" + self.nonce, "theme-group:" + self.group,
                        "theme-mode:" + self.mode, "theme-accent:" + self.accent,
                        "theme-saved-mode:" + self.mode, "theme-saved-accent:" + self.accent,
                        "theme-motion:" + motion, "theme-saved-motion:" + motion}
            if not any(required <= set(text.split(";")) for text in texts):
                return None
            return theme_observation(tree, mode=self.mode, accent=self.accent, scale=self.scale,
                                     group=self.group, nonce=self.nonce, validate_palette=True)
        self.initial = self.probe.wait_for(committed, "Theme preferences did not commit to the actual composition")
        return self.initial

    def tap(self, resource, **state):
        from automation_ui_probe import navigation_target
        def settled():
            tree = self.probe.tree()
            observed = theme_observation(tree, mode=self.mode, accent=self.accent, scale=self.scale,
                                         group=self.group, nonce=self.nonce)
            node = navigation_target(tree, resource, minimum=math.ceil(48 * observed["density"]),
                                     selected=state.get("selected"), touch=True)
            if node is None:
                return None
            owned_target(tree, resource, density=observed["density"], touch=True, **state)
            return node
        node = self.probe.wait_for(settled, "Theme native target did not become visible and actionable: " + resource)
        self.probe.tap_node(node)

    def capture(self):
        from spatial_frame_evidence import read_screenshot
        tree = self.probe.tree()
        observed = theme_observation(tree, mode=self.mode, accent=self.accent, scale=self.scale,
                                     group=self.group, nonce=self.nonce)
        if tree.get("keyboard-visible") != "false":
            raise AssertionError("A theme capture must not hide required components behind the IME")
        self.phase = "pixels"
        path = self.probe.capture(f"theme-{self.mode.lower()}-{self.accent.lower()}-f{int(self.scale * 100)}-{self.group}")
        image = read_screenshot(path)
        measured = frame_pixels(image, tree, observed)
        after = self.observed()
        if observed != after:
            raise AssertionError("The native theme changed while its pixels were captured")
        xml = path.with_suffix(".xml")
        xml.write_bytes(ET.tostring(tree, encoding="utf-8", xml_declaration=True))
        return {"observation": observed, "pixels": measured, "png": path.name,
                "png_sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "xml": xml.name,
                "xml_sha256": hashlib.sha256(xml.read_bytes()).hexdigest()}

    def calendar(self, initial):
        from spatial_frame_evidence import read_screenshot
        self.probe.tap("Период", area="workspace-content")
        def opened():
            tree = self.probe.tree()
            _, _, window = owned_window(tree)
            if window == initial["window_id"]:
                return None
            labels = [n.get("text", "") for n in tree.iter("node") if n.get("package") == PACKAGE
                      and n.get("visible-to-user") == "true"]
            return tree if "Выбор периода" in labels else None
        tree = self.probe.wait_for(opened, "The actual production calendar dialog did not open")
        movements = []
        for step in range(9):
            cells = calendar_cells(tree, initial["density"])
            if any(cell["selected"] and cell["enabled"] for cell in cells) and any(not cell["enabled"] for cell in cells):
                break
            if step == 8:
                raise AssertionError("Selected and disabled dates did not become visible in the production calendar")
            _, _, window = owned_window(tree)
            bounds = calendar_scroll_viewport(tree, initial["density"])
            a, b, c, d = bounds
            x, start = (a + c) // 2, math.floor(d - 24 * initial["density"])
            end = math.ceil(max(b + 24 * initial["density"], start - 160 * initial["density"]))
            if start - end < 48 * initial["density"]:
                raise AssertionError("Actual calendar viewport cannot admit a bounded scroll")
            self.probe.command("shell", "input", "swipe", str(x), str(start), str(x), str(end), "400")
            movements.append({"window_id": window, "viewport": list(bounds), "from": [x, start], "to": [x, end]})
            tree = self.probe.tree()
        self.phase = "calendar-pixels"
        before_cells = calendar_cells(tree, initial["density"])
        path = self.probe.capture(f"theme-{self.mode.lower()}-aurora-f{int(self.scale * 100)}-calendar")
        measured = calendar_pixels(read_screenshot(path), tree, initial)
        after_tree = self.probe.tree()
        if owned_window(after_tree) != owned_window(tree) or calendar_cells(after_tree, initial["density"]) != before_cells:
            raise AssertionError("The observed calendar changed during its pixel capture")
        xml = path.with_suffix(".xml")
        xml.write_bytes(ET.tostring(tree, encoding="utf-8", xml_declaration=True))
        self.probe.tap("Отмена", area="workspace-content")
        self.probe.wait_for(lambda: owned_window(self.probe.tree())[2] == initial["window_id"],
                            "The production calendar did not return to its original window")
        returned = self.observed()
        if returned["colors"] != initial["colors"] or returned["state"]["period"] != initial["state"]["period"]:
            raise AssertionError("Calendar cancellation changed the actual palette or input period")
        return {"observation": initial, "pixels": measured, "calendar_scrolls": movements,
                "production_period_unchanged": True, "date_selection_action_claimed": False,
                "png": path.name, "png_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "xml": xml.name, "xml_sha256": hashlib.sha256(xml.read_bytes()).hexdigest()}

    def run(self):
        initial = self.launch()
        self.phase = "native-actions"
        if self.group == "actions":
            for resource, key in (("theme-control-native-on", "native"), ("theme-control-spatial-on", "spatial"),
                                  ("theme-control-choice", "choice")):
                self.tap(resource)
                self.await_state(**{key: "true"})
            self.tap("theme-tabs-item-1", selected=False)
            self.await_state(tab="1")
            self.tap("theme-control-primary")
            self.await_state(clicks="1")
            tree = self.probe.tree()
            _, bounds = owned_target(tree, "theme-control-primary", density=initial["density"], touch=True)
            x, y = str((bounds[0] + bounds[2]) // 2), str((bounds[1] + bounds[3]) // 2)
            # DOWN/UP are real Android input. Never inject a test-only pressed state.
            try:
                self.probe.command("shell", "input", "motionevent", "DOWN", x, y)
                self.await_state(down="true", clicks="1")
                result = self.capture()
            finally:
                self.probe.command("shell", "input", "motionevent", "UP", x, y)
            after = self.await_state(down="false", clicks="2")
            result["released_state"] = after["state"]
        elif self.group == "fields":
            from native_input_evidence import focused_editor
            tree = self.probe.tree()
            field, field_bounds = owned_target(tree, "theme-control-input")
            editors = [node for node in field.iter("node") if node.get("editable") == "true"
                       and node.get("enabled") == "true" and node.get("package") == PACKAGE
                       and node.get("visible-to-user") == "true" and node.get("focusable") == "true"]
            if len(editors) != 1:
                raise AssertionError("Theme input does not own one real native editor")
            bounds = BOUNDS.fullmatch(editors[0].get("bounds", ""))
            if bounds is None:
                raise AssertionError("Theme editor has no native touch geometry")
            a, b, c, d = map(int, bounds.groups())
            if not (field_bounds[0] <= a < c <= field_bounds[2] and field_bounds[1] <= b < d <= field_bounds[3]) \
                    or c - a < math.ceil(48 * initial["density"]) or d - b < math.ceil(48 * initial["density"]):
                raise AssertionError("Theme editor does not preserve the native 48 dp target")
            self.probe.tap_node(editors[0])
            self.probe.wait_for(lambda: focused_editor(self.probe.tree(), "ТЕМА"), "Theme editor did not receive native focus")
            self.probe.command("shell", "input", "keycombination", "113", "29")
            self.probe.wait_for(lambda: focused_editor(self.probe.tree(), "ТЕМА", (0, 4)), "Theme text was not selected by Android")
            self.probe.dismiss_keyboard()
            selection = self.probe.wait_for(lambda: focused_editor(self.probe.tree(), "ТЕМА", (0, 4)),
                                            "The actual theme text selection was lost")
            result = self.capture()
            result["native_selection"] = selection
        elif self.group == "canvas":
            self.tap("theme-control-select")
            self.await_state(selected="4")
            result = self.capture()
        elif self.group == "calendar":
            result = self.calendar(initial)
        elif self.group == "overlay":
            variant = overlay_variant(self.mode, self.accent, self.scale)
            if initial["state"]["overlay"] != variant:
                raise AssertionError("Observed overlay variant differs from the finite matrix")
            if variant == "dialog":
                self.tap("theme-control-dialog-open")
                self.await_state(dialog="true", not_window=initial["window_id"])
                result = self.capture()
                self.tap("theme-control-dialog-close")
                self.await_state(dialog="false", window=initial["window_id"])
            elif variant == "drawer":
                from automation_ui_probe import navigation_menu_absent
                self.tap("navigation-menu-open")
                self.tap("navigation-primary-actions", selected=False)
                self.await_state(destination="Actions")
                self.probe.wait_for(lambda: navigation_menu_absent(self.probe.tree()), "Theme drawer did not close after selection")
                self.tap("navigation-menu-open")
                result = self.capture()
                self.tap("navigation-menu-close")
                self.probe.wait_for(lambda: navigation_menu_absent(self.probe.tree()), "Theme drawer did not close")
            else:
                if (initial["width"], initial["height"]) != (960, 1600) or not math.isclose(initial["density"], 1.0):
                    raise AssertionError("Theme rail requires the actual owned wide display")
                self.tap("rail-destination-actions", selected=False)
                self.await_state(destination="Actions")
                result = self.capture()
            result["overlay_variant"] = variant
        else:
            raise AssertionError("Only the declared finite groups can count as native color captures")
        result["initial_state"] = initial["state"]
        return initial, result


def exercise_theme_states(probe, admitted):
    """Run 48 palette and four actual-calendar captures in the leased API37 emulator."""
    from navigation_detail_probe import wide_emulator_viewport
    root = Path(__file__).resolve().parents[2]
    folder = root / "app/build/outputs/apk/preview/ui-screens"
    if folder.is_symlink() or not folder.resolve().is_relative_to(root):
        raise ValueError("Theme output directory escapes the admitted source tree")
    folder.mkdir(parents=True, exist_ok=True)
    original_scale = None
    report = {"schema_version": 1, "status": "incomplete", "scope": "additional-native-theme-colors",
              "original15_changed": False, "full_acceptance_claimed": False,
              "expected_capture_count": 52, "base_palette_capture_count": 48, "calendar_capture_count": 4,
              "captures": [], "restoration": {}}
    failure = None
    try:
        report["identity"] = _identity(probe, admitted)
        original_scale = probe.command("shell", "settings", "get", "system", "font_scale").strip()
        if re.fullmatch(r"[0-9](?:\.[0-9]{1,3})?", original_scale) is None or not .5 <= float(original_scale) <= 3:
            raise AssertionError("Theme suite cannot restore the actual font scale")
        report["original_font_scale"] = original_scale
        with preserve_theme_preferences(probe, folder, original_scale, report["restoration"]):
            cases = [(mode, accent, scale, group) for mode in MODES for accent in ACCENTS for scale in SCALES for group in GROUPS]
            cases += [(mode, "AURORA", scale, "calendar") for mode in MODES for scale in SCALES]
            for mode, accent, scale, group in cases:
                case = _ThemeCase(probe, mode, accent, scale, group)
                viewport = {}
                wide = group == "overlay" and overlay_variant(mode, accent, scale) == "rail"
                try:
                    with wide_emulator_viewport(probe, viewport) if wide else nullcontext():
                        initial, result = case.run()
                        if viewport:
                            result["wide_viewport"] = viewport
                    if wide and viewport.get("restored") is not True:
                        raise AssertionError("Theme rail did not restore the exact phone viewport")
                    report["captures"].append(result)
                except Exception:
                    report["failed_case"] = {"mode": mode, "accent": accent, "font_scale": scale,
                                             "group": group, "phase": case.phase, "wide_viewport": viewport}
                    raise
            keys = [(c["observation"]["mode"], c["observation"]["accent"], c["observation"]["font_scale"],
                     c["observation"]["group"]) for c in report["captures"]]
            if len(keys) != 52 or len(set(keys)) != 52 or set(keys) != set(cases):
                raise AssertionError("The finite native color matrix is incomplete or duplicated")
        report["status"] = "passed"
        return report
    except BaseException as error:
        failure = error
        report["error_type"] = type(error).__name__
        report["error"] = str(error)
        raise
    finally:
        errors = []
        if original_scale is not None:
            try:
                probe.command("shell", "settings", "put", "system", "font_scale", original_scale)
                observed_scale = probe.command("shell", "settings", "get", "system", "font_scale").strip()
                if observed_scale != original_scale:
                    raise AssertionError("Theme suite did not restore the original font scale")
                report["restoration"]["font_scale"] = observed_scale
            except Exception as error:
                errors.append(type(error).__name__ + ": " + str(error))
        if errors or report["restoration"].get("restored") is not True:
            report["status"] = "incomplete"
        if errors:
            report["restoration"]["font_scale_errors"] = errors
        report["capture_count"] = len(report["captures"])
        destination = folder / "theme-state-evidence.json"
        if destination.is_symlink():
            raise ValueError("Theme report path is a symlink")
        destination.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print("THEME_STATE_EVIDENCE=" + json.dumps({"status": report["status"], "capture_count": report["capture_count"],
              "original15_changed": False, "full_acceptance_claimed": False}), flush=True)
        if errors:
            if failure is None:
                raise AssertionError("Theme preference restoration failed: " + "; ".join(errors))
            failure.add_note("Theme restoration failed: " + "; ".join(errors))
