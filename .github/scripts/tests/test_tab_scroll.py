"""The profile rail scrolls horizontally; body lists keep their own axis."""
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import Mock
import xml.etree.ElementTree as ET

SPEC = importlib.util.spec_from_file_location('tab_scroll', Path(__file__).resolve().parents[1] / 'profile_scroll.py')
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


def tree(label='', *, resource='profile-tabs', owner=module.PACKAGE, bounds='[10,40][310,100]'):
    root = ET.Element('hierarchy')
    ET.SubElement(root, 'node', {'package': owner, 'resource-id': resource,
                               'scrollable': 'true', 'bounds': bounds})
    if label:
        ET.SubElement(root, 'node', {'package': module.PACKAGE, 'text': label, 'bounds': '[50,50][200,90]'})
    return root


class TabScrollTests(unittest.TestCase):
    def test_end_gesture_is_horizontal_and_inside_rail(self):
        swipe = Mock()
        read = Mock(side_effect=[tree(), tree('Инфо')])
        self.assertIsNotNone(module.reveal_in_list(read, swipe, 'Инфо', resource_id='profile-tabs'))
        swipe.assert_called_once_with(250, 70, 70, 70)

    def test_start_gesture_returns_to_settings(self):
        swipe = Mock()
        read = Mock(side_effect=[tree(), tree('Настройки')])
        module.reveal_in_list(read, swipe, 'Настройки', resource_id='profile-tabs', direction='start')
        swipe.assert_called_once_with(70, 70, 250, 70)

    def test_body_is_not_scrolled_when_rail_is_absent(self):
        swipe = Mock()
        result = module.reveal_in_list(lambda: tree(resource='profile-content'), swipe, 'Инфо', resource_id='profile-tabs')
        self.assertIsNone(result)
        swipe.assert_not_called()

    def test_rail_is_not_scrolled_when_body_was_requested(self):
        swipe = Mock()
        result = module.reveal_in_profile(lambda: tree(), swipe, 'Безопасность')
        self.assertIsNone(result)
        swipe.assert_not_called()

    def test_foreign_rail_cannot_authorize_gestures(self):
        swipe = Mock()
        result = module.reveal_in_list(lambda: tree(owner='android'), swipe, 'Инфо', resource_id='profile-tabs')
        self.assertIsNone(result)
        swipe.assert_not_called()

    def test_invisible_target_is_still_bounded_failure(self):
        swipe = Mock()
        with self.assertRaises(AssertionError):
            module.reveal_in_list(lambda: tree(), swipe, 'Инфо', resource_id='profile-tabs', max_swipes=2)
        self.assertEqual(swipe.call_count, 2)
        self.assertTrue(all(call.args[1] == call.args[3] for call in swipe.call_args_list))

    def test_visible_tab_needs_no_gesture(self):
        swipe = Mock()
        result = module.reveal_in_list(lambda: tree('Инфо'), swipe, 'Инфо', resource_id='profile-tabs')
        self.assertIsNotNone(result)
        swipe.assert_not_called()

    def test_direction_rejected_before_read(self):
        read, swipe = Mock(), Mock()
        with self.assertRaises(ValueError):
            module.reveal_in_list(read, swipe, 'Инфо', resource_id='profile-tabs', direction='arbitrary')
        read.assert_not_called()
        swipe.assert_not_called()

    def test_qualified_rail_id(self):
        read = Mock(side_effect=[tree(resource=module.PACKAGE + ':id/profile-tabs'), tree('Инфо')])
        self.assertIsNotNone(module.reveal_in_list(read, Mock(), 'Инфо', resource_id='profile-tabs'))

    def test_too_narrow_rail_is_not_a_swipe_target(self):
        swipe = Mock()
        result = module.reveal_in_list(lambda: tree(bounds='[10,40][11,100]'), swipe, 'Инфо', resource_id='profile-tabs')
        self.assertIsNone(result)
        swipe.assert_not_called()


if __name__ == '__main__':
    unittest.main()
