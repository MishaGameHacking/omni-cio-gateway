"""Native fold transitions must finish before a scroll can pass their new content."""
import importlib.util
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock
import xml.etree.ElementTree as ET

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))
SPEC = importlib.util.spec_from_file_location("impact_ui_probe", SCRIPTS / "impact_ui_probe.py")
impact = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(impact)
PACKAGE = "ru.omnicio.app.debug"
SOURCE = "СИНТЕТИЧЕСКИЙ источник визуального теста"
BASIS_LABEL = "Публикация, компания и мои позиции"


def frame(state=impact.COLLAPSED, *, resource=impact.CHANNEL_SOURCES,
          unrelated_state=impact.EXPANDED, window=7, viewport="[0,100][320,300]", **changes):
    tree = ET.Element("hierarchy", {"active-window-id": str(window), "display-width": "320", "display-height": "640"})
    area = ET.SubElement(tree, "node", {"package": PACKAGE, "resource-id": impact.AREA,
                         "bounds": viewport, "scrollable": "true", "visible-to-user": "true"})
    attributes = {"package": PACKAGE, "visible-to-user": "true", "clickable": "true", "enabled": "true",
                  "text": "Основания (1)", "bounds": "[20,100][300,148]", "state-description": unrelated_state}
    ET.SubElement(area, "node", attributes | {"resource-id": "answer-sources"})
    ET.SubElement(area, "node", attributes | {"resource-id": resource,
                  "bounds": "[20,160][300,208]", "state-description": state} | changes)
    return tree


class WaitingProbe:
    def wait_for(self, read, message):
        for _ in range(10):
            try:
                result = read()
                if result is not None and result is not False:
                    return result
            except (RuntimeError, ET.ParseError, ValueError):
                pass
        raise AssertionError(message)


class ImpactProbe(WaitingProbe):
    def __init__(self, expansion_read=3, metadata=True, *, basis_open_read=1, basis_close_read=3,
                 channel_open_read=3):
        self.transitions = {"basis-open": basis_open_read, "basis-close": basis_close_read,
                            "channel-open": channel_open_read, "source-open": expansion_read}
        self.metadata = metadata
        self.phase = None
        self.reads = dict.fromkeys(self.transitions, 0)
        self.taps = dict.fromkeys(self.transitions, 0)
        self.completed = set()
        self.metadata_reads = 0
        self.screenshots = []

    def tap(self, text, _area, **_kwargs):
        if text == BASIS_LABEL:
            self.phase = "basis-close" if self.taps["basis-open"] else "basis-open"
        elif text == "Возможный канал 1":
            if "basis-close" not in self.completed:
                raise AssertionError("Scrolled past the channel before the basis collapse settled")
            self.phase = "channel-open"
        elif text == "Ограничения разбора":
            return
        else:
            raise AssertionError("Unexpected or ambiguous label tap")
        self.taps[self.phase] += 1

    def tap_resource(self, resource, _area):
        if resource == impact.CHANNEL_SOURCES:
            if "channel-open" not in self.completed:
                raise AssertionError("Scrolled past channel content before its expansion settled")
            self.phase = "source-open"
            self.taps[self.phase] += 1
        elif resource != "assistant-impact-position":
            raise AssertionError("Unexpected resource tap")

    def tree(self):
        self.reads[self.phase] += 1
        threshold = self.transitions[self.phase]
        changed = threshold is not None and self.reads[self.phase] >= threshold
        opened = changed != (self.phase == "basis-close")
        resource = {"basis-open": impact.BASIS, "basis-close": impact.BASIS,
                    "channel-open": impact.CHANNEL, "source-open": impact.CHANNEL_SOURCES}[self.phase]
        return frame(impact.EXPANDED if opened else impact.COLLAPSED, resource=resource)

    def wait_for(self, read, message):
        result = super().wait_for(read, message)
        if isinstance(result, ET.Element):
            self.completed.add(self.phase)
        return result

    def reveal(self, text, _area):
        if text in ("СИНТЕТИЧЕСКОЕ событие влияния", "СИНТЕТИЧЕСКИЙ эмитент гипотезы"):
            if "basis-open" not in self.completed:
                raise AssertionError("Scrolled into the basis before its expansion settled")
        if text.startswith("СИНТЕТИЧЕСКИЙ канал:") and "channel-open" not in self.completed:
            raise AssertionError("Scrolled past channel content before its expansion settled")
        if text == SOURCE:
            self.metadata_reads += 1
            if "source-open" not in self.completed or not self.metadata:
                raise AssertionError("Channel source metadata is absent")

    def capture(self, name):
        self.screenshots.append(name)


def observe_position():
    return {"navigation": "instrument:synthetic-stock:synthetic-account:"}


class ImpactUiProbeTests(unittest.TestCase):
    def test_unrelated_state_cannot_confirm_the_exact_native_fold(self):
        for resource in (impact.BASIS, impact.CHANNEL, impact.CHANNEL_SOURCES):
            for state in (impact.EXPANDED, impact.COLLAPSED):
                other = impact.COLLAPSED if state == impact.EXPANDED else impact.EXPANDED
                with self.subTest(resource=resource, state=state):
                    self.assertIsNone(impact.native_fold_state(frame(other, resource=resource, unrelated_state=state), resource, state))
                    for observed_id in (resource, PACKAGE + ":id/" + resource):
                        tree = frame(state, resource=observed_id)
                        self.assertIs(impact.native_fold_state(tree, resource, state), tree[0][1])

    def test_missing_state_or_non_native_target_cannot_confirm_transition(self):
        for changes in ({"state-description": ""}, {"state-description": impact.COLLAPSED},
                        {"clickable": "false"}, {"enabled": "false"}, {"visible-to-user": "false"},
                        {"package": "other.app"}, {"resource-id": "another-fold"}):
            with self.subTest(changes=changes):
                tree = frame(impact.EXPANDED, resource=impact.BASIS, **changes)
                self.assertIsNone(impact.native_fold_state(tree, impact.BASIS, impact.EXPANDED))

    def test_duplicate_exact_native_resource_ids_cannot_confirm_one_message(self):
        for duplicate_id in (impact.BASIS, PACKAGE + ":id/" + impact.BASIS):
            tree = frame(impact.EXPANDED, resource=impact.BASIS)
            duplicate = dict(tree[0][1].attrib) | {"resource-id": duplicate_id}
            ET.SubElement(tree[0], "node", duplicate)
            with self.subTest(resource=duplicate_id):
                self.assertIsNone(impact.native_fold_state(tree, impact.BASIS, impact.EXPANDED))

    def test_delayed_transitions_finish_before_following_scroll_without_tap_retry(self):
        probe = ImpactProbe()
        checks = impact.exercise_impact(probe, observe_position, "impact")
        self.assertEqual(probe.completed, set(probe.transitions))
        self.assertEqual(probe.taps, dict.fromkeys(probe.transitions, 1))
        self.assertEqual(probe.reads, {"basis-open": 3, "basis-close": 5, "channel-open": 5, "source-open": 5})
        self.assertEqual(probe.metadata_reads, 1)
        self.assertEqual(probe.screenshots, ["impact"])
        self.assertIn("hypothesis-source-metadata", checks)

    def test_failed_basis_expansion_stops_before_scrolling_or_closing_it(self):
        probe = ImpactProbe(basis_open_read=None)
        with self.assertRaisesRegex(AssertionError, "basis fold did not expand"):
            impact.exercise_impact(probe, observe_position, "impact")
        self.assertEqual(probe.taps, {"basis-open": 1, "basis-close": 0, "channel-open": 0, "source-open": 0})
        self.assertEqual(probe.screenshots, [])

    def test_failed_basis_collapse_stops_before_channel_scroll_and_does_not_retap(self):
        probe = ImpactProbe(basis_close_read=None)
        with self.assertRaisesRegex(AssertionError, "basis fold did not collapse"):
            impact.exercise_impact(probe, observe_position, "impact")
        self.assertEqual(probe.taps, {"basis-open": 1, "basis-close": 1, "channel-open": 0, "source-open": 0})
        self.assertEqual(probe.metadata_reads, 0)
        self.assertEqual(probe.screenshots, [])

    def test_failed_channel_expansion_stops_before_its_content(self):
        probe = ImpactProbe(channel_open_read=None)
        with self.assertRaisesRegex(AssertionError, "channel fold did not expand"):
            impact.exercise_impact(probe, observe_position, "impact")
        self.assertEqual(probe.taps["channel-open"], 1)
        self.assertEqual(probe.taps["source-open"], 0)
        self.assertEqual(probe.screenshots, [])

    def test_failed_source_expansion_stops_before_metadata_scroll_or_capture(self):
        probe = ImpactProbe(expansion_read=None)
        with self.assertRaisesRegex(AssertionError, "source fold did not expand"):
            impact.exercise_impact(probe, observe_position, "impact")
        self.assertEqual(probe.taps["source-open"], 1)
        self.assertEqual(probe.metadata_reads, 0)
        self.assertEqual(probe.screenshots, [])

    def test_expanded_toggle_does_not_replace_actual_source_metadata(self):
        probe = ImpactProbe(metadata=False)
        with self.assertRaisesRegex(AssertionError, "source metadata is absent"):
            impact.exercise_impact(probe, observe_position, "impact")
        self.assertIn("source-open", probe.completed)
        self.assertEqual(probe.metadata_reads, 1)
        self.assertEqual(probe.screenshots, [])

    def test_state_geometry_and_window_must_be_stable_for_three_fresh_frames(self):
        for interrupted in (
            frame(impact.EXPANDED),
            frame(bounds="[20,180][300,228]"),
            frame(window=8),
            frame(viewport="[0,110][320,300]"),
            frame(viewport="[0,170][320,300]"),
            RuntimeError("Temporary frame unavailable"),
        ):
            with self.subTest(interruption=type(interrupted).__name__):
                probe = WaitingProbe()
                probe.tree = Mock(side_effect=[frame(), frame(), interrupted, frame(), frame(), frame()])
                impact.wait_for_fold(probe, impact.CHANNEL_SOURCES, impact.COLLAPSED, "not settled")
                self.assertEqual(probe.tree.call_count, 6)

    def test_invalid_or_absent_window_and_display_never_confirm_settlement(self):
        for name in ("active-window-id", "display-width", "display-height"):
            for value in ("", "-1", "x", "1000000"):
                tree = frame()
                tree.set(name, value)
                probe = WaitingProbe()
                probe.tree = Mock(return_value=tree)
                with self.subTest(name=name, value=value):
                    with self.assertRaisesRegex(AssertionError, "not settled"):
                        impact.wait_for_fold(probe, impact.CHANNEL_SOURCES, impact.COLLAPSED, "not settled")
        for name in ("display-width", "display-height"):
            tree = frame()
            tree.set(name, "0")
            probe = WaitingProbe()
            probe.tree = Mock(return_value=tree)
            with self.subTest(name=name, value="0"):
                with self.assertRaisesRegex(AssertionError, "not settled"):
                    impact.wait_for_fold(probe, impact.CHANNEL_SOURCES, impact.COLLAPSED, "not settled")

    def test_continuously_moving_fold_never_allows_a_following_scroll(self):
        probe = WaitingProbe()
        probe.tree = Mock(side_effect=[frame(bounds=f"[20,{160 + n}][300,{208 + n}]") for n in range(10)])
        with self.assertRaisesRegex(AssertionError, "not settled"):
            impact.wait_for_fold(probe, impact.CHANNEL_SOURCES, impact.COLLAPSED, "not settled")
        self.assertEqual(probe.tree.call_count, 10)


if __name__ == "__main__":
    unittest.main()
