"""Selection proof must reveal the result without injecting or retrying input."""
import unittest
from spatial_ui_probe import _SpatialSession


class Probe:
    def __init__(self, selected=True):
        self.calls = []
        self.selected = selected

    def tap_resource(self, tag, area):
        self.calls.append(("tap", tag, area))

    def reveal_resource(self, tag, area):
        self.calls.append(("reveal", tag, area))

    def find(self, text):
        self.calls.append(("find", text))
        if not self.selected:
            raise AssertionError("Selection did not change")


class SelectionViewportTest(unittest.TestCase):
    def session(self, selected=True):
        session = object.__new__(_SpatialSession)
        session.probe = Probe(selected)
        return session

    def test_result_revealed_after_exactly_one_tap(self):
        session = self.session()
        session.select_second_chart_element()
        self.assertEqual(session.probe.calls, [
            ("tap", "spatial-select-second", "workspace-content"),
            ("reveal", "spatial-selection-result", "workspace-content"),
            ("find", "Выбран элемент: 2"),
        ])

    def test_failed_selection_is_still_a_failure(self):
        session = self.session(False)
        with self.assertRaises(AssertionError):
            session.select_second_chart_element()
        self.assertEqual(len([call for call in session.probe.calls if call[0] == "tap"]), 1)
