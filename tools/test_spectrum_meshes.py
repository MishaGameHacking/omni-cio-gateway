#!/usr/bin/env python3
"""Validate the actual distributable GLBs, topology and numerical data contract."""
import hashlib
import json
import math
import pathlib
import struct
import unittest
from contextlib import ExitStack
from unittest.mock import patch

import generate_spectrum_meshes as catalogue


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
    def test_every_distributed_asset_has_finite_volume_normals_and_verified_digest(self):
        manifest = json.loads((catalogue.DEST / 'catalogue.json').read_text())
        self.assertEqual(1, manifest['version'])
        for name, expected in manifest['models'].items():
            with self.subTest(model=name):
                data = (catalogue.DEST / (name + '.glb')).read_bytes()
                self.assertEqual(expected['sha256'], hashlib.sha256(data).hexdigest())
                self.assertEqual(expected['bytes'], len(data))
                doc, binary = decode(data)
                self.assertNotIn('images', doc)
                self.assertNotIn('uri', doc['buffers'][0])
                self.assertEqual('2.0', doc['asset']['version'])
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
                self.assertEqual(expected['triangles'] * 3, doc['accessors'][2]['count'])

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
