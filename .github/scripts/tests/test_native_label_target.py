"""Native label taps need a unique action owner and stable visible geometry."""
from copy import deepcopy
from pathlib import Path
import re
import sys
import unittest
from unittest.mock import Mock, patch
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import native_label_target as target
import profile_scroll as scroll

PACKAGE = 'ru.omnicio.app.debug'
LABEL = 'Удалить'


def frame(*, width=360, height=800, window=7):
    return ET.Element('hierarchy', {'display-width': str(width), 'display-height': str(height),
                                    'active-window-id': str(window)})


def node(parent, bounds, *, text='', resource='', clickable=False, **attributes):
    values = {'package': PACKAGE, 'visible-to-user': 'true', 'enabled': 'true',
              'class': 'android.view.View', 'bounds': bounds, 'text': text,
              'resource-id': resource, 'clickable': str(clickable).lower()}
    values.update(attributes)
    return ET.SubElement(parent, 'node', values)


def chip(*, top=100, label_height=32, enabled=True, window=7):
    tree = frame(window=window)
    owner = node(tree, f'[16,{top}][244,{top + 92}]', resource='delete-chip',
                 clickable=True, enabled=str(enabled).lower())
    node(owner, f'[36,{top + 20}][120,{top + 20 + label_height}]', text=LABEL,
         **{'class': 'android.widget.TextView'})
    return tree


def rect(element):
    return tuple(map(int, re.fullmatch(r'\[(-?\d+),(-?\d+)\]\[(-?\d+),(-?\d+)\]', element.get('bounds')).groups()))


def center(element):
    left, top, right, bottom = rect(element)
    return (left + right) // 2, (top + bottom) // 2


def viewport_frame(*, owner_bounds='[20,80][220,200]', viewport_bounds='[0,100][360,180]'):
    tree = frame()
    viewport = node(tree, viewport_bounds, resource='profile-content', scrollable='true')
    owner = node(viewport, owner_bounds, resource='delete-row', clickable=True)
    node(owner, '[40,120][120,152]', text=LABEL)
    return tree


class FreshFrames:
    """Every read represents a separate device hierarchy, including equal frames."""
    def __init__(self, *frames):
        self.frames = frames
        self.calls = 0

    def __call__(self):
        if self.calls >= len(self.frames):
            raise AssertionError('Probe read beyond the supplied fresh-frame budget')
        result = self.frames[self.calls]
        self.calls += 1
        if isinstance(result, BaseException):
            raise result
        return deepcopy(result)


class NativeLabelTargetTests(unittest.TestCase):
    def test_wrapped_32_or_40_pixel_text_width_inside_92_pixel_style_chip(self):
        for width in (32, 40):
            tree = frame()
            owner = node(tree, '[20,100][112,192]', resource='style-subdued', clickable=True)
            node(owner, f'[44,116][{44 + width},176]', text='SUBDUED',
                 **{'class': 'android.widget.TextView'})
            with self.subTest(label_width=width):
                found = target.label_target(tree, 'SUBDUED')
                self.assertIsNotNone(found)
                self.assertEqual(found.get('resource-id'), 'style-subdued')
                self.assertEqual(rect(found), (20, 100, 112, 192))
                self.assertEqual(center(found), (66, 146))

    def test_small_text_inside_92_pixel_chip_uses_clickable_owner(self):
        for height in (32, 40):
            tree = chip(label_height=height)
            before = ET.tostring(tree)
            owner = tree[0]
            with self.subTest(label_height=height):
                found = target.label_target(tree, LABEL)
                self.assertIsNotNone(found)
                self.assertEqual(found.get('resource-id'), 'delete-chip')
                self.assertEqual(rect(found), (16, 100, 244, 192))
                self.assertEqual(center(found), (130, 146))
                self.assertIsNot(found, owner)
                self.assertEqual(ET.tostring(tree), before)
                found.set('bounds', '[0,0][1,1]')
                self.assertEqual(owner.get('bounds'), '[16,100][244,192]')

    def test_plain_label_without_native_action_is_not_a_tap_target(self):
        tree = frame()
        node(tree, '[20,100][220,160]', text=LABEL, **{'class': 'android.widget.TextView'})
        self.assertIsNone(target.label_target(tree, LABEL))

    def test_nearest_clickable_owner_is_used_instead_of_large_outer_card(self):
        tree = frame()
        outer = node(tree, '[0,0][360,700]', resource='outer-card', clickable=True)
        inner = node(outer, '[16,100][244,192]', resource='inner-button', clickable=True)
        node(inner, '[36,120][120,152]', text=LABEL)
        found = target.label_target(tree, LABEL)
        self.assertEqual(found.get('resource-id'), 'inner-button')
        self.assertEqual(rect(found), (16, 100, 244, 192))

    def test_disabled_inner_owner_never_falls_back_to_enabled_outer_owner(self):
        tree = frame()
        outer = node(tree, '[0,0][360,700]', resource='outer-card', clickable=True)
        inner = node(outer, '[16,100][244,192]', resource='inner-button', clickable=True, enabled='false')
        node(inner, '[36,120][120,152]', text=LABEL)
        self.assertIsNone(target.label_target(tree, LABEL))
        geometry = target.label_target(tree, LABEL, require_enabled=False)
        self.assertEqual(geometry.get('resource-id'), 'inner-button')
        self.assertEqual(geometry.get('enabled'), 'false')

    def test_disabled_ancestor_blocks_enabled_child_action(self):
        tree = frame()
        disabled = node(tree, '[0,0][360,700]', enabled='false')
        owner = node(disabled, '[16,100][244,192]', resource='delete-button', clickable=True)
        node(owner, '[36,120][120,152]', text=LABEL)
        self.assertIsNone(target.label_target(tree, LABEL))
        self.assertEqual(target.label_target(tree, LABEL, require_enabled=False).get('resource-id'), 'delete-button')

    def test_disabled_nonclickable_native_button_cannot_lend_label_to_enabled_outer_card(self):
        tree = frame()
        outer = node(tree, '[16,100][344,300]', resource='outer-card', clickable=True)
        disabled = node(outer, '[36,120][244,212]', enabled='false', **{'class': 'android.widget.Button'})
        node(disabled, '[56,140][180,172]', text=LABEL)
        self.assertIsNone(target.label_target(tree, LABEL))
        geometry = target.label_target(tree, LABEL, require_enabled=False)
        self.assertIsNotNone(geometry)
        swipe = Mock()
        read = FreshFrames(tree)
        self.assertIsNotNone(scroll.reveal_in_list(read, swipe, LABEL, resource_id='profile-content', for_tap=True))
        swipe.assert_not_called()

    def test_hidden_label_or_ancestor_cannot_authorize_tap(self):
        for hide in ('owner', 'label', 'ancestor'):
            tree = frame()
            ancestor = node(tree, '[0,0][360,700]')
            owner = node(ancestor, '[16,100][244,192]', clickable=True)
            label = node(owner, '[36,120][120,152]', text=LABEL)
            {'owner': owner, 'label': label, 'ancestor': ancestor}[hide].set('visible-to-user', 'false')
            with self.subTest(hidden=hide):
                self.assertIsNone(target.label_target(tree, LABEL))

    def test_content_description_matches_exact_label_and_does_not_match_substrings(self):
        tree = frame()
        owner = node(tree, '[16,100][244,192]', clickable=True, **{'content-desc': LABEL})
        self.assertEqual(rect(target.label_target(tree, LABEL)), (16, 100, 244, 192))
        owner.set('content-desc', LABEL + ' всё')
        self.assertIsNone(target.label_target(tree, LABEL))
        owner.set('content-desc', LABEL.lower())
        self.assertIsNone(target.label_target(tree, LABEL))

    def test_duplicate_label_nodes_on_same_owner_are_deduplicated(self):
        tree = chip()
        owner = tree[0]
        owner.set('content-desc', LABEL)
        node(owner, '[130,120][214,152]', **{'content-desc': LABEL})
        self.assertEqual(target.label_target(tree, LABEL).get('resource-id'), 'delete-chip')

    def test_equal_labels_on_distinct_action_owners_are_ambiguous(self):
        tree = chip()
        other = node(tree, '[16,300][244,392]', resource='different-delete', clickable=True)
        node(other, '[36,320][120,352]', text=LABEL)
        with self.assertRaises(AssertionError):
            target.label_target(tree, LABEL)

    def test_disabled_duplicate_does_not_silently_choose_another_owner(self):
        tree = chip()
        other = node(tree, '[16,300][244,392]', resource='disabled-delete', clickable=True, enabled='false')
        node(other, '[36,320][120,352]', text=LABEL)
        with self.assertRaises(AssertionError):
            target.label_target(tree, LABEL)

    def test_foreign_matches_are_ignored_and_foreign_parent_cannot_lend_action(self):
        tree = chip()
        node(tree, '[16,300][244,392]', text=LABEL, clickable=True, package='other.app')
        self.assertEqual(target.label_target(tree, LABEL).get('resource-id'), 'delete-chip')
        tree = frame()
        outer = node(tree, '[0,0][360,700]', clickable=True)
        foreign = node(outer, '[16,100][244,192]', clickable=True, package='other.app')
        node(foreign, '[36,120][120,152]', text=LABEL)
        self.assertIsNone(target.label_target(tree, LABEL))

    def test_native_edit_text_or_explicit_editable_field_owns_its_label(self):
        for attributes in ({'class': 'android.widget.EditText'}, {'editable': 'true'}):
            tree = frame()
            owner = node(tree, '[16,100][344,196]', resource='goal-name-input', **attributes)
            node(owner, '[36,120][220,152]', text='Название цели')
            with self.subTest(attributes=attributes):
                found = target.label_target(tree, 'Название цели')
                self.assertEqual(found.get('resource-id'), 'goal-name-input')
                self.assertEqual(rect(found), (16, 100, 344, 196))

    def test_owner_is_clipped_by_nested_actual_scroll_ancestors(self):
        tree = frame()
        outer = node(tree, '[0,180][360,650]', resource=PACKAGE + ':id/profile-content', scrollable='false')
        inner = node(outer, '[20,200][300,400]', resource='custom-scroll-area', scrollable='true')
        owner = node(inner, '[0,250][360,500]', clickable=True)
        node(owner, '[40,270][140,304]', text=LABEL)
        self.assertEqual(rect(target.label_target(tree, LABEL)), (20, 250, 300, 400))

    def test_sibling_scroll_viewport_does_not_clip_header_button(self):
        tree = frame()
        header = node(tree, '[16,40][244,132]', resource='header-delete', clickable=True)
        node(header, '[36,60][120,92]', text=LABEL)
        node(tree, '[0,200][360,700]', resource='profile-content', scrollable='true')
        self.assertEqual(rect(target.label_target(tree, LABEL)), (16, 40, 244, 132))

    def test_non_scroll_semantics_wrapper_does_not_become_a_viewport(self):
        tree = frame()
        wrapper = node(tree, '[36,120][120,152]', resource='semantic-wrapper')
        owner = node(wrapper, '[16,100][244,192]', clickable=True)
        node(owner, '[36,120][120,152]', text=LABEL)
        self.assertEqual(rect(target.label_target(tree, LABEL)), (16, 100, 244, 192))

    def test_partial_owner_requires_48_visible_pixels_on_both_axes(self):
        for width, height, accepted in ((47, 92, False), (92, 47, False), (48, 48, True), (92, 48, True)):
            tree = frame()
            viewport = node(tree, f'[20,100][{20 + width},{100 + height}]', resource='profile-content')
            owner = node(viewport, '[20,100][112,192]', clickable=True)
            node(owner, '[28,108][60,140]', text=LABEL)
            with self.subTest(width=width, height=height):
                found = target.label_target(tree, LABEL)
                self.assertEqual(found is not None, accepted)
                if accepted:
                    self.assertEqual(rect(found), (20, 100, 20 + width, 100 + height))

    def test_already_display_clipped_one_pixel_owner_is_not_a_tiny_valid_control(self):
        tree = frame()
        owner = node(tree, '[20,799][220,800]', clickable=True)
        node(owner, '[40,799][120,800]', text=LABEL)
        self.assertIsNone(target.label_target(tree, LABEL))
        self.assertIsNone(target.label_target(tree, LABEL, require_enabled=False))

    def test_display_edges_clip_owner_before_center_selection(self):
        tree = frame()
        owner = node(tree, '[310,740][402,832]', clickable=True)
        node(owner, '[320,752][352,784]', text=LABEL)
        found = target.label_target(tree, LABEL)
        self.assertEqual(rect(found), (310, 740, 360, 800))
        self.assertEqual(center(found), (335, 770))

    def test_logically_visible_label_outside_actual_viewport_does_not_authorize_owner(self):
        tree = viewport_frame()
        tree[0][0][0].set('bounds', '[40,181][120,199]')
        self.assertIsNone(target.label_target(tree, LABEL))

    def test_missing_or_invalid_required_window_display_metadata_is_not_tappable(self):
        for name, value in (('display-width', None), ('display-height', None), ('active-window-id', None),
                            ('display-width', '0'), ('display-height', '-1'), ('active-window-id', 'unknown')):
            tree = chip()
            if value is None:
                tree.attrib.pop(name)
            else:
                tree.set(name, value)
            with self.subTest(attribute=name, value=value):
                self.assertIsNone(target.label_target(tree, LABEL))

    def test_nested_action_at_owner_center_falls_back_to_visible_label_center(self):
        tree = frame()
        viewport = node(tree, '[50,210][320,300]', resource='profile-content')
        owner = node(viewport, '[20,200][340,320]', resource='country-row', clickable=True)
        node(owner, '[30,230][100,270]', text=LABEL)
        node(owner, '[140,220][230,290]', resource='nested-position', clickable=True)
        found = target.label_target(tree, LABEL)
        self.assertEqual(found.get('resource-id'), 'country-row')
        self.assertEqual(center(found), (75, 250))
        self.assertNotEqual(center(found), (185, 255))

    def test_obstructed_owner_and_label_centers_are_rejected(self):
        tree = frame()
        owner = node(tree, '[20,200][340,320]', clickable=True)
        node(owner, '[40,230][110,270]', text=LABEL)
        node(owner, '[140,220][220,300]', clickable=True)
        node(owner, '[60,230][90,270]', clickable=True)
        self.assertIsNone(target.label_target(tree, LABEL))

    def test_hidden_nested_control_does_not_obstruct_owner_center(self):
        tree = chip()
        node(tree[0], '[100,120][160,180]', clickable=True, **{'visible-to-user': 'false'})
        self.assertEqual(center(target.label_target(tree, LABEL)), (130, 146))


class SettledNativeLabelTests(unittest.TestCase):
    def setUp(self):
        sleeping = patch.object(target.time, 'sleep')
        sleeping.start()
        self.addCleanup(sleeping.stop)

    def test_three_independent_equal_frames_are_required(self):
        read = FreshFrames(chip(), chip(), chip())
        self.assertEqual(rect(target.settled_label(read, LABEL)), (16, 100, 244, 192))
        self.assertEqual(read.calls, 3)

    def test_moving_owner_waits_until_three_equal_final_frames(self):
        read = FreshFrames(chip(top=100), chip(top=112), chip(top=124), chip(top=124), chip(top=124))
        self.assertEqual(rect(target.settled_label(read, LABEL)), (16, 124, 244, 216))
        self.assertEqual(read.calls, 5)

    def test_partial_frame_resets_stability_instead_of_using_old_valid_target(self):
        partial = viewport_frame(viewport_bounds='[0,100][360,147]')
        read = FreshFrames(chip(), chip(), partial, chip(), chip(), chip())
        target.settled_label(read, LABEL)
        self.assertEqual(read.calls, 6)

    def test_disabled_frame_resets_stability_without_substituting_visible_label(self):
        read = FreshFrames(chip(), chip(), chip(enabled=False), chip(), chip(), chip())
        target.settled_label(read, LABEL)
        self.assertEqual(read.calls, 6)

    def test_window_change_restarts_three_frame_barrier_even_at_equal_coordinates(self):
        read = FreshFrames(chip(window=7), chip(window=7), chip(window=8), chip(window=8), chip(window=8))
        target.settled_label(read, LABEL)
        self.assertEqual(read.calls, 5)

    def test_changed_action_owner_identity_is_not_only_a_rectangle_match(self):
        other = chip()
        other[0].set('resource-id', 'different-owner')
        read = FreshFrames(chip(), chip(), other, other, other)
        self.assertEqual(target.settled_label(read, LABEL).get('resource-id'), 'different-owner')
        self.assertEqual(read.calls, 5)

    def test_changed_raw_owner_restarts_barrier_even_if_clipped_rectangle_is_equal(self):
        first = viewport_frame(owner_bounds='[20,80][220,200]')
        second = viewport_frame(owner_bounds='[20,70][220,210]')
        read = FreshFrames(first, first, second, second, second)
        self.assertEqual(rect(target.settled_label(read, LABEL)), (20, 100, 220, 180))
        self.assertEqual(read.calls, 5)

    def test_changed_ancestor_viewport_restarts_barrier_even_if_owner_is_unclipped(self):
        first = viewport_frame(owner_bounds='[20,100][220,200]', viewport_bounds='[0,80][360,500]')
        second = viewport_frame(owner_bounds='[20,100][220,200]', viewport_bounds='[0,100][360,500]')
        read = FreshFrames(first, first, second, second, second)
        target.settled_label(read, LABEL)
        self.assertEqual(read.calls, 5)

    def test_changed_clipped_owner_restarts_barrier_even_when_label_fallback_is_equal(self):
        first = frame(width=360)
        owner = node(first, '[20,200][380,320]', resource='country-row', clickable=True)
        node(owner, '[40,230][110,270]', text=LABEL)
        node(owner, '[140,220][230,300]', clickable=True)
        second = deepcopy(first)
        second.set('display-width', '320')
        read = FreshFrames(first, first, second, second, second)
        self.assertEqual(center(target.settled_label(read, LABEL)), (75, 250))
        self.assertEqual(read.calls, 5)

    def test_perpetual_motion_or_disabled_owner_fail_after_exact_bounded_budget(self):
        cases = ([chip(top=100 + index) for index in range(30)], [chip(enabled=False) for _ in range(30)])
        for frames in cases:
            read = FreshFrames(*frames)
            with self.subTest(disabled=frames[0][0].get('enabled') == 'false'), self.assertRaises(AssertionError):
                target.settled_label(read, LABEL, max_frames=30)
            self.assertEqual(read.calls, 30)

    def test_invalid_frame_limit_never_reads_device(self):
        for limit in (0, 2, 121, True, 3.0, '3'):
            read = Mock()
            with self.subTest(limit=limit), self.assertRaises(ValueError):
                target.settled_label(read, LABEL, max_frames=limit)
            read.assert_not_called()

    def test_default_deadline_bounds_slow_fresh_reads_without_resending_actions(self):
        class Clock:
            now = 0.0

            def monotonic(self):
                return self.now

            def sleep(self, seconds):
                self.now += seconds

        clock = Clock()
        calls = 0

        def moving_device():
            nonlocal calls
            calls += 1
            clock.now += 0.8  # A real hierarchy dump may consume most of a second.
            return chip(top=100 + calls)

        with patch.object(target, 'time', clock), self.assertRaises(AssertionError):
            target.settled_label(moving_device, LABEL)
        self.assertGreaterEqual(calls, 10)
        self.assertLessEqual(calls, 15)
        self.assertLessEqual(clock.now, 12.8)  # At most one in-flight read past the deadline.

    def test_transient_dump_failure_resets_consecutive_stable_frame_count(self):
        for error in (RuntimeError('synthetic stale dump'), ET.ParseError('synthetic incomplete XML'),
                      ValueError('synthetic incomplete frame')):
            read = FreshFrames(chip(), chip(), error, chip(), chip(), chip())
            with self.subTest(error=type(error).__name__):
                self.assertEqual(rect(target.settled_label(read, LABEL)), (16, 100, 244, 192))
                self.assertEqual(read.calls, 6)

    def test_ambiguous_owners_are_not_a_transient_frame_failure_to_bypass(self):
        tree = chip()
        other = node(tree, '[16,300][244,392]', clickable=True)
        node(other, '[36,320][120,352]', text=LABEL)
        read = FreshFrames(tree, chip(), chip(), chip())
        with self.assertRaises(AssertionError):
            target.settled_label(read, LABEL)
        self.assertEqual(read.calls, 1)

    def test_device_failure_is_not_hidden_by_geometry_retry(self):
        read = Mock(side_effect=ConnectionError('synthetic disconnected device'))
        with self.assertRaises(ConnectionError):
            target.settled_label(read, LABEL)
        read.assert_called_once()


class NativeLabelRevealTests(unittest.TestCase):
    def test_disabled_visible_action_is_revealed_without_scrolling_past_it(self):
        tree = viewport_frame()
        tree[0][0].set('enabled', 'false')
        swipe = Mock()
        read = FreshFrames(tree)
        found = scroll.reveal_in_list(read, swipe, LABEL, resource_id='profile-content', for_tap=True)
        self.assertEqual(found.get('resource-id'), 'delete-row')
        self.assertEqual(found.get('enabled'), 'false')
        self.assertEqual(read.calls, 1)
        swipe.assert_not_called()
        self.assertIsNone(target.label_target(tree, LABEL))

    def test_offscreen_logical_label_requires_scroll_then_visible_action_geometry(self):
        outside = viewport_frame(owner_bounds='[20,300][220,392]', viewport_bounds='[0,100][360,250]')
        outside[0][0][0].set('bounds', '[40,320][120,352]')
        inside = viewport_frame(owner_bounds='[20,120][220,212]', viewport_bounds='[0,100][360,250]')
        inside[0][0][0].set('bounds', '[40,140][120,172]')
        read, swipe = FreshFrames(outside, inside), Mock()
        found = scroll.reveal_in_list(read, swipe, LABEL, resource_id='profile-content', max_swipes=1, for_tap=True)
        self.assertEqual(rect(found), (20, 120, 220, 212))
        self.assertEqual(read.calls, 2)
        swipe.assert_called_once_with(180, 220, 180, 130)


if __name__ == '__main__':
    unittest.main()
