"""Observe the intended native fold despite duplicate source labels and delayed expansion."""
import importlib.util
from pathlib import Path
import sys
import unittest
import xml.etree.ElementTree as ET

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))
SPEC = importlib.util.spec_from_file_location("impact_ui_probe", SCRIPTS / "impact_ui_probe.py")
impact = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(impact)
PACKAGE = "ru.omnicio.app.debug"
SOURCE = "СИНТЕТИЧЕСКИЙ источник визуального теста"


def frame(state="Свёрнуто", *, unrelated_state="Развёрнуто", **changes):
    tree = ET.Element("hierarchy")
    attributes = {"package": PACKAGE, "visible-to-user": "true", "clickable": "true", "enabled": "true",
                  "text": "Основания (1)", "bounds": "[20,80][300,128]", "state-description": unrelated_state}
    ET.SubElement(tree, "node", attributes | {"resource-id": "answer-sources"})
    ET.SubElement(tree, "node", attributes | {"resource-id": impact.CHANNEL_SOURCES,
                  "bounds": "[20,160][300,208]", "state-description": state} | changes)
    return tree


class ImpactProbe:
    def __init__(self, expansion_read=3, metadata=True):
        self.expansion_read = expansion_read
        self.metadata = metadata
        self.channel_requested = False
        self.channel_expanded = False
        self.unrelated_expanded = False
        self.source_reads = 0
        self.source_taps = 0
        self.metadata_reads = 0
        self.screenshots = []

    def tap(self, text, _area, **_kwargs):
        if text == "Основания (1)":
            self.unrelated_expanded = not self.unrelated_expanded

    def tap_resource(self, resource, _area):
        if resource == impact.CHANNEL_SOURCES:
            self.channel_requested = True
            self.source_taps += 1

    def tree(self):
        if self.channel_requested:
            self.source_reads += 1
            self.channel_expanded = self.expansion_read is not None and self.source_reads >= self.expansion_read
        return frame("Развёрнуто" if self.channel_expanded else "Свёрнуто",
                     unrelated_state="Развёрнуто" if self.unrelated_expanded else "Свёрнуто")

    def wait_for(self, read, message):
        for _ in range(3):
            result = read()
            if result is not None and result is not False:
                return result
        raise AssertionError(message)

    def reveal(self, text, _area):
        if text == SOURCE:
            self.metadata_reads += 1
            if not self.channel_expanded or not self.metadata:
                raise AssertionError("Channel source metadata is absent")

    def capture(self, name):
        self.screenshots.append(name)


def observe_position():
    return {"navigation": "instrument:synthetic-stock:synthetic-account:"}


class ImpactUiProbeTests(unittest.TestCase):
    def test_unrelated_expanded_source_label_cannot_confirm_the_channel_fold(self):
        self.assertIsNone(impact.expanded_channel_sources(frame()))
        for resource in (impact.CHANNEL_SOURCES, PACKAGE + ":id/" + impact.CHANNEL_SOURCES):
            tree = frame("Развёрнуто", **{"resource-id": resource})
            with self.subTest(resource=resource):
                self.assertIs(impact.expanded_channel_sources(tree), tree[1])

    def test_missing_state_or_non_native_target_cannot_confirm_expansion(self):
        for changes in ({"state-description": ""}, {"state-description": "Свёрнуто"},
                        {"clickable": "false"}, {"enabled": "false"}, {"visible-to-user": "false"},
                        {"package": "other.app"}, {"resource-id": "another-channel-sources"}):
            with self.subTest(changes=changes):
                self.assertIsNone(impact.expanded_channel_sources(frame("Развёрнуто", **changes)))

    def test_delayed_target_expansion_precedes_metadata_scroll_without_tap_retry(self):
        probe = ImpactProbe()
        checks = impact.exercise_impact(probe, observe_position, "impact")
        self.assertTrue(probe.channel_expanded)
        self.assertFalse(probe.unrelated_expanded)
        self.assertEqual(probe.source_taps, 1)
        self.assertEqual(probe.source_reads, 3)
        self.assertEqual(probe.metadata_reads, 1)
        self.assertEqual(probe.screenshots, ["impact"])
        self.assertIn("hypothesis-source-metadata", checks)

    def test_failed_expansion_stops_before_metadata_scroll_or_capture(self):
        probe = ImpactProbe(expansion_read=None)
        with self.assertRaisesRegex(AssertionError, "source fold did not expand"):
            impact.exercise_impact(probe, observe_position, "impact")
        self.assertEqual(probe.source_taps, 1)
        self.assertEqual(probe.metadata_reads, 0)
        self.assertEqual(probe.screenshots, [])

    def test_expanded_toggle_does_not_replace_actual_source_metadata(self):
        probe = ImpactProbe(metadata=False)
        with self.assertRaisesRegex(AssertionError, "source metadata is absent"):
            impact.exercise_impact(probe, observe_position, "impact")
        self.assertTrue(probe.channel_expanded)
        self.assertEqual(probe.metadata_reads, 1)
        self.assertEqual(probe.screenshots, [])


if __name__ == "__main__":
    unittest.main()
