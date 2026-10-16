"""A missing intermediate list frame must not strand an offscreen target."""
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock, patch
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import profile_scroll as scroll

TARGET = 'Денежные средства'
AREA = 'portfolio-content'


def frame(*, area=AREA, package=scroll.PACKAGE, target=False, visible='true', scrollable='true'):
    root = ET.Element('hierarchy')
    if area is not None:
        node = ET.SubElement(root, 'node', {
            'package': package, 'resource-id': area, 'scrollable': scrollable,
            'visible-to-user': visible, 'bounds': '[20,180][300,600]',
        })
        if target:
            ET.SubElement(node, 'node', {'package': package, 'text': TARGET,
                'resource-id': 'cash-label', 'bounds': '[30,280][250,320]'})
    return root


class Clock:
    now = 0.0
    def monotonic(self):
        return self.now
    def sleep(self, seconds):
        self.now += seconds


class ScrollLayoutReadinessTests(unittest.TestCase):
    def setUp(self):
        self.clock = Clock()
        patcher = patch.object(scroll, 'time', self.clock)
        patcher.start()
        self.addCleanup(patcher.stop)

    def reveal(self, read, swipe, **options):
        return scroll.reveal_in_list(read, swipe, TARGET, resource_id=AREA,
                                     layout_timeout=1, **options)

    def test_initial_missing_list_is_waited_for_then_scrolled(self):
        read = Mock(side_effect=[frame(area=None), frame(), frame(target=True)])
        swipe = Mock()
        self.assertIsNotNone(self.reveal(read, swipe))
        swipe.assert_called_once_with(160, 516, 160, 264)

    def test_disappearing_semantics_between_swipes_do_not_reset_budget(self):
        read = Mock(side_effect=[frame(), frame(area=None), frame(), frame(target=True)])
        swipe = Mock()
        self.assertIsNotNone(self.reveal(read, swipe, max_swipes=2))
        self.assertEqual(swipe.call_count, 2)

    def test_missing_list_cannot_pass_or_scroll_another_area(self):
        for root in (frame(area=None), frame(area='profile-content'),
                     frame(package='other.app'), frame(visible='false'),
                     frame(scrollable='false')):
            self.clock.now = 0
            swipe = Mock()
            with self.assertRaisesRegex(AssertionError, 'Scroll layout not ready'):
                self.reveal(lambda: root, swipe)
            swipe.assert_not_called()
            self.assertLessEqual(self.clock.now, 1.01)

    def test_ambiguous_lists_never_authorize_gesture(self):
        root = frame()
        root.append(frame()[0])
        swipe = Mock()
        with self.assertRaisesRegex(AssertionError, 'Scroll layout not ready'):
            self.reveal(lambda: root, swipe)
        swipe.assert_not_called()

    def test_target_is_still_required_after_scroll_budget(self):
        swipe = Mock()
        with self.assertRaisesRegex(AssertionError, 'not reachable'):
            self.reveal(frame, swipe, max_swipes=2)
        self.assertEqual(swipe.call_count, 2)

    def test_transport_and_ui_exceptions_are_not_swallowed(self):
        for error in (ConnectionError('disconnected'), AssertionError('UI failure')):
            swipe = Mock()
            with self.assertRaises(type(error)):
                self.reveal(Mock(side_effect=error), swipe)
            swipe.assert_not_called()

    def test_resource_target_has_the_same_readiness_contract(self):
        read = Mock(side_effect=[frame(area=None), frame(), frame(target=True)])
        swipe = Mock()
        self.assertIsNotNone(scroll.reveal_resource_in_list(
            read, swipe, 'cash-label', resource_id=AREA, layout_timeout=1))
        swipe.assert_called_once()

    def test_zero_timeout_preserves_immediate_absence_contract(self):
        read, swipe = Mock(return_value=frame(area=None)), Mock()
        self.assertIsNone(scroll.reveal_in_list(read, swipe, TARGET, resource_id=AREA))
        self.assertEqual(read.call_count, 1)
        swipe.assert_not_called()

    def test_invalid_timeout_is_rejected_before_device_access(self):
        for seconds in (-1, 13, True, float('nan'), float('inf')):
            read = Mock()
            with self.assertRaisesRegex(ValueError, 'invalid_layout_timeout'):
                scroll.reveal_in_list(read, Mock(), TARGET, resource_id=AREA, layout_timeout=seconds)
            read.assert_not_called()

    def test_runtime_probe_uses_layout_wait_without_removing_allocation_assertion(self):
        source = (Path(__file__).resolve().parents[1] / 'profile_ui_probe.py').read_text(encoding='utf-8')
        self.assertEqual(source.count('layout_timeout=12,'), 2)
        self.assertIn('self.reveal("Денежные средства", "portfolio-content")', source)
        self.assertIn('self.capture("spectrum-allocation")', source)


if __name__ == '__main__':
    unittest.main()
