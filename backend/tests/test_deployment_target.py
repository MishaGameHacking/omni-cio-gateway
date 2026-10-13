"""Offline regression checks; these tests never execute the deployment or call APIs."""
from __future__ import annotations

import ast
from pathlib import Path
import re
import unittest

SCRIPT = Path(__file__).resolve().parents[2] / '.github/scripts/deploy_timeweb_backend.sh'
SOURCE = SCRIPT.read_text(encoding='utf-8')
BLOCKS = re.findall(r"<<'PY'\n(.*?)\nPY(?:\n|$)", SOURCE, re.S)
TREES = [ast.parse(block) for block in BLOCKS]
FUNCTION = next(node for tree in TREES for node in tree.body
                if isinstance(node, ast.FunctionDef) and node.name == 'select_existing_backend')
NAMESPACE: dict = {}
exec(compile(ast.Module(body=[FUNCTION], type_ignores=[]), '<pure-target-selector>', 'exec'), NAMESPACE)
select = NAMESPACE['select_existing_backend']
NAME = 'analyst-ai-backend'


def inventory(*servers):
    return {'servers': list(servers), 'meta': {'total': len(servers)}}


class DeploymentTargetTests(unittest.TestCase):
    def test_one_existing_server(self):
        self.assertEqual(select(inventory({'id': 42, 'name': NAME}), NAME), 42)

    def test_other_services_are_ignored(self):
        self.assertEqual(select(inventory({'id': 2, 'name': 'other'}, {'id': 42, 'name': NAME}), NAME), 42)

    def test_missing_server_does_not_provision(self):
        with self.assertRaisesRegex(RuntimeError, 'no server will be ordered'):
            select(inventory(), NAME)

    def test_duplicate_names_are_rejected(self):
        with self.assertRaises(RuntimeError):
            select(inventory({'id': 1, 'name': NAME}, {'id': 2, 'name': NAME}), NAME)

    def test_nested_object_is_not_mistaken_for_server(self):
        with self.assertRaises(RuntimeError):
            select(inventory({'id': 1, 'name': 'other', 'extra': {'id': 2, 'name': NAME}}), NAME)

    def test_invalid_inventory_is_rejected(self):
        for payload in (None, [], {}, {'servers': {}}, {'servers': [None]}, inventory('bad')):
            with self.subTest(payload=payload), self.assertRaises(RuntimeError):
                select(payload, NAME)

    def test_partial_inventory_is_rejected(self):
        payload = inventory({'id': 1, 'name': NAME})
        payload['meta']['total'] = 2
        with self.assertRaises(RuntimeError):
            select(payload, NAME)

    def test_inventory_total_is_required(self):
        for meta in (None, {}, {'total': True}, {'total': '1'}, {'total': 1.0}, {'total': -1}):
            payload = {'servers': [{'id': 1, 'name': NAME}], 'meta': meta}
            with self.subTest(meta=meta), self.assertRaises(RuntimeError):
                select(payload, NAME)

    def test_invalid_id_is_rejected(self):
        for identifier in (None, True, False, '42', 42.0, -42, 0):
            with self.subTest(identifier=identifier), self.assertRaises(RuntimeError):
                select(inventory({'id': identifier, 'name': NAME}), NAME)

    def test_only_temporary_ssh_key_post_calls_remain(self):
        calls = [node for tree in TREES for node in ast.walk(tree)
                 if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                 and node.func.id == 'request' and node.args]
        writes = [node for node in calls if isinstance(node.args[0], ast.Constant)
                  and node.args[0].value != 'GET']
        paths = {ast.unparse(node.args[1]) for node in writes}
        self.assertEqual(paths, {"'/ssh-keys'", "f'/servers/{server_id}/ssh-keys'"})
        self.assertTrue(all(node.args[0].value == 'POST' for node in writes))
        self.assertNotIn('preset_id', SOURCE)
        self.assertNotIn('/presets/servers', SOURCE)

    def test_existing_target_is_selected_before_ssh_key_creation(self):
        self.assertLess(SOURCE.index('server_id = select_existing_backend('), SOURCE.index('key_response = request('))

    def test_no_ip_order_fallback(self):
        self.assertIn('Existing backend has no IPv4; no address will be ordered', SOURCE)
        self.assertNotIn('"type": "ipv4"', SOURCE)

    def test_both_embedded_python_blocks_compile(self):
        self.assertEqual(len(BLOCKS), 2)
        for index, block in enumerate(BLOCKS):
            compile(block, f'<deploy-block-{index}>', 'exec')


if __name__ == '__main__':
    unittest.main()
