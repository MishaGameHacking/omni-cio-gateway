#!/usr/bin/env python3
"""Validate the actual distributable GLBs, topology and numerical data contract."""
import hashlib
import json
import math
import os
import pathlib
import struct
import subprocess
import tempfile
import unittest
import zipfile
from contextlib import ExitStack, contextmanager
from unittest.mock import patch

import generate_spectrum_meshes as catalogue
import prepare_spectrum_checkout as preparation


def decode(payload):
    magic, version, length = struct.unpack_from('<III', payload)
    assert (magic, version, length) == (0x46546C67, 2, len(payload))
    size, kind = struct.unpack_from('<II', payload, 12)
    assert kind == 0x4E4F534A
    document = json.loads(payload[20:20+size])
    binary_size, binary_kind = struct.unpack_from('<II', payload, 20+size)
    assert binary_kind == 0x004E4942
    binary = payload[28+size:]
    assert len(binary) == binary_size
    return document, binary


class MeshCatalogueTest(unittest.TestCase):
    @contextmanager
    def reused_windows_checkout(self):
        """Use actual commits and the same cleanup/checkout sequence as Actions."""
        root = pathlib.Path(__file__).resolve().parents[1]
        relative = pathlib.Path('app/src/main/assets/spectrum3d')
        paths = [relative / 'catalogue.json', relative / 'brand.glb']
        original = {path: (root / path).read_bytes() for path in paths}
        with tempfile.TemporaryDirectory(prefix='spectrum-checkout-') as folder:
            checkout = pathlib.Path(folder).resolve()
            def git(*arguments):
                return subprocess.run(['git', '-c', 'core.autocrlf=true', '-c', 'commit.gpgsign=false',
                                       '-c', 'user.name=Spectrum regression', '-c', 'user.email=spectrum@example.invalid',
                                       *arguments], cwd=checkout,
                                      check=True, capture_output=True, timeout=15)
            git('init', '--quiet')
            (checkout / relative).mkdir(parents=True)
            for path, payload in original.items():
                (checkout / path).write_bytes(payload)
            git('add', '--', *(path.as_posix() for path in paths))
            git('commit', '--quiet', '-m', 'Assets before LF attributes')
            previous = git('rev-parse', 'HEAD').stdout.decode().strip()
            (checkout / paths[0]).unlink()
            git('checkout-index', '--force', '--all')
            self.assertEqual(original[paths[0]].replace(b'\n', b'\r\n'), (checkout / paths[0]).read_bytes())
            (checkout / '.gitattributes').write_bytes((root / '.gitattributes').read_bytes())
            git('add', '--', '.gitattributes')
            git('commit', '--quiet', '-m', 'Pin LF without changing the asset blob')
            candidate = git('rev-parse', 'HEAD').stdout.decode().strip()
            git('checkout', '--force', '--detach', previous)
            git('clean', '-ffdx')
            git('reset', '--hard', 'HEAD')
            git('checkout', '--force', '--detach', candidate)
            # No unlink after the attributes commit: this is the reused runner
            # case the old fresh-file regression did not exercise.
            self.assertEqual(git('status', '--porcelain', '--', paths[0].as_posix()).stdout, b'')
            yield checkout, git, paths, original

    def test_windows_git_checkout_preserves_generated_catalogue_and_glb_bytes(self):
        with self.reused_windows_checkout() as (checkout, git, paths, original):
            path = checkout / paths[0]
            self.assertEqual(original[paths[0]].replace(b'\n', b'\r\n'), path.read_bytes())
            # --force still skips the unchanged index entry in a reused worktree.
            git('checkout-index', '--force', '--', paths[0].as_posix())
            self.assertNotEqual(original[paths[0]], path.read_bytes())
            before_head = git('rev-parse', 'HEAD').stdout
            result = preparation.prepare_checkout(checkout)
            self.assertTrue(result['repaired_checkout_crlf'])
            self.assertEqual(result['before_crlf_count'], original[paths[0]].count(b'\n'))
            self.assertEqual(git('rev-parse', 'HEAD').stdout, before_head)
            self.assertEqual(git('diff', '--cached', '--name-only').stdout, b'')
            for path in paths:
                self.assertEqual(original[path], (checkout / path).read_bytes(), str(path))
            self.assertFalse(preparation.prepare_checkout(checkout)['repaired_checkout_crlf'])

    def test_checkout_preparation_rejects_changed_content_without_regenerating_it(self):
        with self.reused_windows_checkout() as (checkout, _, paths, _):
            path = checkout / paths[0]
            changed = path.read_bytes().replace(b'"version": 1', b'"version": 2', 1)
            path.write_bytes(changed)
            with self.assertRaisesRegex(ValueError, 'more than Git LF-to-CRLF'):
                preparation.prepare_checkout(checkout)
            self.assertEqual(path.read_bytes(), changed)

    def test_checkout_preparation_rejects_a_staged_catalogue_from_another_revision(self):
        with self.reused_windows_checkout() as (checkout, git, paths, _):
            path = checkout / paths[0]
            changed = path.read_bytes().replace(b'"version": 1', b'"version": 2', 1)
            path.write_bytes(changed)
            git('add', '--', paths[0].as_posix())
            with self.assertRaisesRegex(ValueError, 'Staged catalogue differs'):
                preparation.prepare_checkout(checkout)
            self.assertEqual(path.read_bytes(), changed)

    def test_checkout_preparation_never_overwrites_a_hardlink(self):
        with self.reused_windows_checkout() as (checkout, _, paths, _):
            path = checkout / paths[0]
            before = path.read_bytes()
            linked = checkout / 'other-catalogue.json'
            os.link(path, linked)
            with self.assertRaisesRegex(ValueError, 'one bounded regular file'):
                preparation.prepare_checkout(checkout)
            self.assertEqual(linked.read_bytes(), before)

    @unittest.skipIf(os.name == 'nt', 'Windows symlink privileges are not assumed')
    def test_checkout_preparation_never_follows_a_symlink(self):
        with self.reused_windows_checkout() as (checkout, _, paths, _):
            path = checkout / paths[0]
            target = checkout / 'other-catalogue.json'
            path.rename(target)
            path.symlink_to(target)
            before = target.read_bytes()
            with self.assertRaisesRegex(ValueError, 'link or reparse point'):
                preparation.prepare_checkout(checkout)
            self.assertEqual(target.read_bytes(), before)

    def test_packaged_asset_check_requires_exact_bytes_even_for_semantically_equal_json(self):
        assets = {'catalogue.json': (catalogue.DEST / 'catalogue.json').read_bytes(),
                  'brand.glb': (catalogue.DEST / 'brand.glb').read_bytes()}
        for altered in ('none', 'crlf', 'mesh-byte'):
            with self.subTest(altered=altered), tempfile.TemporaryDirectory(prefix='spectrum-apk-') as folder:
                apk = pathlib.Path(folder) / 'app-preview.apk'
                with zipfile.ZipFile(apk, 'w') as archive:
                    for name, original in assets.items():
                        payload = original
                        if altered == 'crlf' and name == 'catalogue.json':
                            payload = original.replace(b'\n', b'\r\n')
                            self.assertEqual(json.loads(payload), json.loads(original))
                        if altered == 'mesh-byte' and name == 'brand.glb':
                            payload = original[:-1] + bytes([original[-1] ^ 1])
                        archive.writestr('assets/spectrum3d/' + name, payload)
                before = apk.read_bytes()
                if altered == 'none':
                    catalogue.verify_packaged_assets(apk, assets)
                else:
                    with self.assertRaisesRegex(ValueError, 'asset bytes differ'):
                        catalogue.verify_packaged_assets(apk, assets)
                self.assertEqual(apk.read_bytes(), before)

    def test_packaged_asset_check_rejects_missing_duplicate_and_extra_entries(self):
        assets = {'catalogue.json': b'{"version":1}\n', 'brand.glb': b'glTF\x00'}
        cases = ((['catalogue.json'], ['assets/spectrum3d/brand.glb'], [], []),
                 (['catalogue.json', 'brand.glb', 'brand.glb'], [], [], ['assets/spectrum3d/brand.glb']),
                 (['catalogue.json', 'brand.glb', 'unexpected.glb'], [], ['assets/spectrum3d/unexpected.glb'], []))
        for names, missing, unexpected, duplicates in cases:
            with self.subTest(names=names), tempfile.TemporaryDirectory(prefix='spectrum-apk-') as folder:
                apk = pathlib.Path(folder) / 'app-preview.apk'
                with zipfile.ZipFile(apk, 'w') as archive:
                    for name in names:
                        archive.writestr('assets/spectrum3d/' + name, assets.get(name, b'other mesh'))
                with self.assertRaisesRegex(ValueError, 'missing, duplicated or unexpected') as raised:
                    catalogue.verify_packaged_assets(apk, assets)
                difference = json.loads(str(raised.exception).partition(': ')[2])
                self.assertEqual(difference, {'expected_files': 2, 'actual_entries': len(names),
                                             'missing': missing, 'unexpected': unexpected, 'duplicates': duplicates})

    def test_runtime_source_tree_packages_exact_generated_assets_and_rejects_readme(self):
        """Exercise real source bytes in a ZIP; the Android APK remains a separate CI gate."""
        with tempfile.TemporaryDirectory(prefix='spectrum-source-package-') as folder:
            temporary = pathlib.Path(folder)
            generated = temporary / 'generated'
            with patch.object(catalogue, 'DEST', generated):
                catalogue.generate()
            expected = {path.name: path.read_bytes() for path in generated.iterdir()}
            self.assertEqual(len(expected), 91)
            apk = temporary / 'app-preview.apk'
            with zipfile.ZipFile(apk, 'w') as archive:
                # Do not filter by extension: Android assets include documentation
                # stored alongside models, which caused the extra-entry CI failure.
                for path in sorted(catalogue.DEST.rglob('*')):
                    if path.is_file():
                        archive.writestr('assets/spectrum3d/' + path.relative_to(catalogue.DEST).as_posix(),
                                         path.read_bytes())
            catalogue.verify_packaged_assets(apk, expected)

            with zipfile.ZipFile(apk, 'a') as archive:
                archive.writestr('assets/spectrum3d/README.md',
                                 (catalogue.ROOT / 'docs/SPECTRUM_3D_ASSETS.md').read_bytes())
            before = apk.read_bytes()
            with self.assertRaisesRegex(ValueError, 'missing, duplicated or unexpected') as raised:
                catalogue.verify_packaged_assets(apk, expected)
            difference = json.loads(str(raised.exception).partition(': ')[2])
            self.assertEqual(difference, {'expected_files': 91, 'actual_entries': 92, 'missing': [],
                                         'unexpected': ['assets/spectrum3d/README.md'], 'duplicates': []})
            self.assertEqual(apk.read_bytes(), before)

    def test_every_distributed_asset_has_finite_volume_normals_and_verified_digest(self):
        manifest = json.loads((catalogue.DEST / 'catalogue.json').read_text())
        self.assertEqual(manifest['version'], 1)
        for name, expected in manifest['models'].items():
            with self.subTest(model=name):
                data = (catalogue.DEST / (name + '.glb')).read_bytes()
                self.assertEqual(expected['sha256'], hashlib.sha256(data).hexdigest())
                self.assertEqual(expected['bytes'], len(data))
                doc, binary = decode(data)
                self.assertNotIn('images', doc)
                self.assertNotIn('uri', doc['buffers'][0])
                self.assertEqual(doc['asset']['version'], '2.0')
                for axis in range(3):
                    self.assertGreater(doc['accessors'][0]['max'][axis], doc['accessors'][0]['min'][axis])
                for index in (0, 1):
                    accessor = doc['accessors'][index]
                    view = doc['bufferViews'][accessor['bufferView']]
                    values = struct.unpack_from('<' + 'f' * accessor['count'] * 3, binary, view.get('byteOffset', 0))
                    self.assertTrue(all(math.isfinite(value) for value in values))
                    for axis in range(3):
                        self.assertEqual(accessor['min'][axis], min(values[axis::3]))
                        self.assertEqual(accessor['max'][axis], max(values[axis::3]))
                    self.assertTrue(all(value != 0 or math.copysign(1, value) == 1 for value in values))
                    if index == 1:
                        self.assertTrue(all(abs(sum(v*v for v in values[i:i+3]) - 1) < 1e-5 for i in range(0,len(values),3)))
                self.assertEqual(doc['accessors'][2]['count'], expected['triangles'] * 3)

    def test_sphere_faces_point_outward_and_closed_torus_has_no_gaps(self):
        sphere = catalogue.Mesh(); sphere.sphere()
        for vertex, normal in zip(sphere.vertices, sphere.normals):
            self.assertGreater(sum(v*n for v,n in zip(vertex,normal)), 0)
        torus = catalogue.Mesh(); torus.ring()
        edges = {}
        for i in range(0,len(torus.vertices),3):
            triangle = [tuple(round(x,7) for x in point) for point in torus.vertices[i:i+3]]
            for a,b in zip(triangle,triangle[1:]+triangle[:1]):
                edge = tuple(sorted((a,b))); edges[edge] = edges.get(edge,0)+1
        self.assertTrue(edges)
        self.assertTrue(all(count == 2 for count in edges.values()))

    def test_three_actual_pbr_families_preserve_native_readability_and_lod_identity(self):
        manifest = json.loads((catalogue.DEST / 'catalogue.json').read_text())['models']
        families = set()
        for name, info in manifest.items():
            document, _ = decode((catalogue.DEST / (name + '.glb')).read_bytes())
            material = document['materials'][0]
            family = info['material']; families.add(family)
            self.assertEqual(material['alphaMode'], 'OPAQUE')
            pbr = material['pbrMetallicRoughness']
            self.assertEqual(pbr['baseColorFactor'], [1, 1, 1, 1])
            if family == 'metal':
                self.assertGreater(pbr['metallicFactor'], .5)
            else:
                self.assertLess(pbr['metallicFactor'], .1)
            if family == 'glass_coating':
                self.assertIn('KHR_materials_clearcoat', document['extensionsUsed'])
                coating = material['extensions']['KHR_materials_clearcoat']
                self.assertGreater(coating['clearcoatFactor'], .9)
                self.assertLess(coating['clearcoatRoughnessFactor'], pbr['roughnessFactor'])
            else:
                self.assertNotIn('extensions', material)
            if not name.endswith('_low'):
                low, _ = decode((catalogue.DEST / (name + '_low.glb')).read_bytes())
                self.assertEqual(material, low['materials'][0])
        self.assertEqual(families, {'ceramic', 'metal', 'glass_coating'})
        for readable in ('surface', 'button', 'input', 'heading', 'bar', 'chip', 'dock'):
            self.assertEqual(manifest[readable]['material'], 'ceramic')

    def test_low_detail_reduces_the_real_triangle_budget(self):
        manifest = json.loads((catalogue.DEST / 'catalogue.json').read_text())['models']
        normal = sum(manifest[name]['triangles'] for name in catalogue.NAMES)
        low = sum(manifest[name + '_low']['triangles'] for name in catalogue.NAMES)
        self.assertLess(low, normal * .6)
        for name in catalogue.NAMES:
            self.assertLessEqual(manifest[name + '_low']['triangles'], manifest[name]['triangles'])

    def test_concave_bookmark_surface_has_the_correct_area(self):
        polygon = [(-.28,-.4),(0,-.23),(.28,-.4),(.28,.4),(-.28,.4)]
        mesh = catalogue.Mesh(); mesh.prism(polygon, .15)
        area = 0
        for i in range(0,len(mesh.vertices),3):
            a,b,c = mesh.vertices[i:i+3]
            if all(abs(p[2]-.075)<1e-9 for p in (a,b,c)):
                area += abs((b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0]))/2
        self.assertAlmostEqual(.56*.8-.56*.17/2, area)

    def test_canonical_encoding_resists_platform_libm_ulp_differences(self):
        # Offline cross-platform simulation, not a substitute for Windows CI.
        # Perturb every trig/sqrt/hypot result in both directions. Degenerate
        # topology and JSON bounds must remain identical to the packaged bytes.
        functions = {name: getattr(math, name) for name in ('sin', 'cos', 'sqrt', 'hypot')}
        def shifted(function, direction):
            def evaluate(*args):
                value = function(*args)
                for _ in range(8):
                    value = math.nextafter(value, direction)
                return value
            return evaluate
        for direction in (-math.inf, math.inf):
            with ExitStack() as stack:
                for name, function in functions.items():
                    stack.enter_context(patch.object(catalogue.math, name, shifted(function, direction)))
                for name in catalogue.NAMES:
                    for suffix, detail in (('', True), ('_low', False)):
                        key = name + suffix
                        with self.subTest(direction=direction, model=key):
                            actual = catalogue.encode(catalogue.icon(name, detail), key)
                            self.assertEqual(actual, (catalogue.DEST / (key + '.glb')).read_bytes())

    def test_canonical_coordinates_collapse_signed_zero_and_reject_nonfinite(self):
        for value in (-0.0, 0.0, -1e-17, 1e-17):
            self.assertEqual(struct.pack('<f', catalogue.canonical_float32(value)), bytes(4))
        for value in (math.nan, math.inf, -math.inf):
            with self.assertRaises(ValueError):
                catalogue.canonical_float32(value)


if __name__ == '__main__': unittest.main()
