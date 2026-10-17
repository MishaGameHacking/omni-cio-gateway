#!/usr/bin/env python3
"""Validate the actual distributable GLBs, topology and numerical data contract."""
import hashlib
import json
import math
import pathlib
import struct
import unittest

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


if __name__ == '__main__': unittest.main()
