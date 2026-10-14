"""Parser regressions from CI38599387423; no simulated test is device evidence."""
import unittest
from unittest.mock import Mock

from test_profile_launch import ACTIVITY, RESUMED, launch, tree

# Actual API33 diagnostic from job115974376472. The component ends in a brace.
OBSERVED = ('topResumedActivity=ActivityRecord{bff33bd u0 '
            'ru.omnicio.app.debug/ru.omnicio.app.ProfileUiProbeActivity} t10}')


class ForegroundFormatTests(unittest.TestCase):
    def test_observed_android_13_record_is_recognized(self):
        self.assertTrue(launch.profile_resumed(OBSERVED))
        self.assertTrue(launch.profile_resumed('  ' + OBSERVED))

    def test_both_record_layouts_and_labels_are_supported(self):
        for record in (OBSERVED, RESUMED):
            for label in ('topResumedActivity=', 'mResumedActivity: '):
                with self.subTest(record=record, label=label):
                    self.assertTrue(launch.profile_resumed(record.replace('topResumedActivity=', label)))

    def test_component_boundaries_remain_exact(self):
        for component in (ACTIVITY + 'Other', ACTIVITY + '$Nested',
                          'other.' + ACTIVITY, ACTIVITY.replace('.debug/', '.debug.other/'),
                          ACTIVITY + '/Extra', ACTIVITY + '.Other'):
            with self.subTest(component=component):
                self.assertFalse(launch.profile_resumed(OBSERVED.replace(ACTIVITY, component)))

    def test_history_or_unrelated_field_cannot_supply_foreground_identity(self):
        for record in ('lastResumedActivity=' + OBSERVED.split('=', 1)[1],
                       '* Hist #0: ' + OBSERVED,
                       'debug=' + OBSERVED,
                       'topResumedActivity=null previous=' + ACTIVITY,
                       'topResumedActivity=ActivityRecord{123 u0 other.app/Main} previous=' + ACTIVITY,
                       'topResumedActivity=ActivityRecord{123 u0 other.app/Main ' + ACTIVITY + ' t12}'):
            with self.subTest(record=record):
                self.assertFalse(launch.profile_resumed(record))

    def test_observed_foreground_still_requires_actual_marker(self):
        command = Mock(side_effect=['Status: ok', OBSERVED])
        read_tree = Mock(return_value=tree(marker='not-ready'))
        wait = lambda read, message: read()
        with self.assertRaises(AssertionError):
            launch.launch_profile(command, read_tree, wait)
        read_tree.assert_called_once()

    def test_observed_foreground_passes_only_with_marker_and_unchanged_focus(self):
        command = Mock(side_effect=['Status: ok', OBSERVED, OBSERVED])
        read_tree = Mock(return_value=tree())
        launch.launch_profile(command, read_tree, lambda read, message: read())
        self.assertEqual(command.call_count, 3)
        read_tree.assert_called_once()

    def test_observed_foreground_cannot_pass_after_focus_loss(self):
        command = Mock(side_effect=['Status: ok', OBSERVED, OBSERVED.replace(ACTIVITY, 'other.app/Main')])
        wait = lambda read, message: read()
        with self.assertRaises(AssertionError):
            launch.launch_profile(command, tree, wait)
        self.assertEqual(command.call_count, 3)


if __name__ == '__main__':
    unittest.main()
