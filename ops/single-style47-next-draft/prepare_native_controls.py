"""Prepare explicit native scroll targets for the four real icon rows."""


def apply(files, base):
    def replace(path, before, after):
        value = files.get(path, base(path))
        assert value.count(before) == 1, (path, before)
        files[path] = value.replace(before, after, 1)

    groups = ('main', 'portfolio', 'research', 'personal')
    path = '.github/scripts/persistent_ui.py'
    anchor = '    "navigation-panel-content": 9,\n'
    replace(path, anchor, anchor + ''.join(f'    "navigation-row-{group}": {number},\n'
                                         for number, group in enumerate(groups, 10)))
    path = '.github/scripts/profile_scroll.py'
    anchor = '    "navigation-panel-content": "vertical",\n'
    replace(path, anchor, anchor + ''.join(f'    "navigation-row-{group}": "horizontal",\n' for group in groups))
    path = '.github/scripts/profile_ui_probe.py'
    replace(path, '    if area in {"profile-tabs", "dossier-tabs", "quotes-intervals"}:',
        '    if area in {"profile-tabs", "dossier-tabs", "quotes-intervals",\n'
        '                "navigation-row-main", "navigation-row-portfolio",\n'
        '                "navigation-row-research", "navigation-row-personal"}:')
    path = 'ci-ui-driver/src/main/java/ru/omnicio/ciframe/FrameInstrumentation.java'
    anchor = '    private static final int LIST_NAVIGATION_PANEL = 9;\n'
    replace(path, anchor, anchor + ''.join(f'    private static final int LIST_NAVIGATION_{group.upper()} = {number};\n'
                                         for number, group in enumerate(groups, 10)))
    anchor = '    private static final String NAVIGATION_PANEL = "navigation-panel-content";\n'
    replace(path, anchor, anchor + ''.join(f'    private static final String NAVIGATION_{group.upper()} = "navigation-row-{group}";\n'
                                         for group in groups))
    anchor = '            case LIST_NAVIGATION_PANEL -> NAVIGATION_PANEL;\n'
    replace(path, anchor, anchor + ''.join(f'            case LIST_NAVIGATION_{group.upper()} -> NAVIGATION_{group.upper()};\n'
                                         for group in groups))
    path = '.github/scripts/tests/test_portfolio_semantic_scroll.py'
    anchor = '    def test_unknown_list_or_direction_sends_nothing(self):\n'
    test = '''    def test_dock_rows_use_distinct_bounded_native_requests_without_shell_fallback(self):
        expected = {"navigation-row-main": 10, "navigation-row-portfolio": 11,
                    "navigation-row-research": 12, "navigation-row-personal": 13}
        source = (SCRIPTS.parents[1] / "ci-ui-driver/src/main/java/ru/omnicio/ciframe/FrameInstrumentation.java").read_text(encoding="utf-8")
        for area, code in expected.items():
            for direction, geometry in (("end", (300, 100, 100, 100)), ("start", (100, 100, 300, 100))):
                with self.subTest(area=area, direction=direction):
                    stream = Stream(ack())
                    reader = frames.FrameReader(stream)
                    device = Mock()
                    probe = profile.ProfileProbe(device)
                    probe.read_tree = reader.ready_tree
                    self.assertEqual(frames.SCROLL_LIST_CODES[area], code)
                    self.assertEqual(list(frames.SCROLL_LIST_CODES.values()).count(code), 1)
                    with patch.dict(sys.modules, {"persistent_ui": frames}):
                        probe._semantic_scroll_callback(area, direction)(*geometry)
                    raw = 0x80000000 | (code << 24) | 1
                    if direction == "start": raw |= 0x10000000
                    self.assertEqual(stream.sent, [struct.pack(">I", raw)])
                    device.assert_not_called()
                    key = area.removeprefix("navigation-row-").upper()
                    self.assertIn(f"LIST_NAVIGATION_{key} = {code};", source)
                    self.assertIn(f'NAVIGATION_{key} = "{area}";', source)
                    self.assertIn(f"case LIST_NAVIGATION_{key} -> NAVIGATION_{key};", source)

    def test_dock_rows_reject_vertical_or_wrong_direction_before_any_action(self):
        for group in ("main", "portfolio", "research", "personal"):
            for geometry in ((100, 100, 100, 300), (100, 100, 300, 100)):
                with self.subTest(group=group, geometry=geometry):
                    stream = Stream(b"")
                    reader = frames.FrameReader(stream)
                    device = Mock()
                    probe = profile.ProfileProbe(device)
                    probe.read_tree = reader.ready_tree
                    with patch.dict(sys.modules, {"persistent_ui": frames}):
                        callback = probe._semantic_scroll_callback("navigation-row-" + group, "end")
                        with self.assertRaises(ValueError): callback(*geometry)
                    self.assertEqual(reader.sequence, 0)
                    self.assertEqual(stream.sent, [])
                    device.assert_not_called()

'''
    replace(path, anchor, test + anchor)
