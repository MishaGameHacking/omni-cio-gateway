#!/usr/bin/env python3
"""Reproducible, first-party GLB meshes. No images, downloads or model compiler.

Coordinates are metres in a centred, unit-sized artboard; surfaces are one unit
wide/high with real depth. Runtime applies screen-space orthographic transforms.
Every face carries a normal. The catalogue is versioned and SHA-256 checked.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import pathlib
import struct
import zipfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
DEST = ROOT / "app/src/main/assets/spectrum3d"
VERSION = 1
CATALOGUE_NAME = 'catalogue.json'
COORDINATE_SCALE = 1_000_000
MATERIALS = {
    'ceramic': {'name': 'SpectrumCeramic', 'metallic': .04, 'roughness': .46},
    'metal': {'name': 'SpectrumBrushedMetal', 'metallic': .72, 'roughness': .28},
    'glass_coating': {'name': 'SpectrumGlassCoating', 'metallic': .0, 'roughness': .30,
                      'clearcoat': 1.0, 'clearcoat_roughness': .12},
}
METAL_MODELS = frozenset(('portfolio risk update sources notifications settings calendar '
                          'stock bond fund currency monogram market').split())
COATED_MODELS = frozenset('analyst avatar brand globe orbit goal'.split())


def material_family(name):
    base = name.removesuffix('_low')
    return 'glass_coating' if base in COATED_MODELS else 'metal' if base in METAL_MODELS else 'ceramic'


def gltf_material(family):
    preset = MATERIALS[family]
    material = {'name': preset['name'], 'pbrMetallicRoughness': {
        'baseColorFactor': [1, 1, 1, 1], 'metallicFactor': preset['metallic'],
        'roughnessFactor': preset['roughness']}, 'doubleSided': False, 'alphaMode': 'OPAQUE'}
    if family == 'glass_coating':
        # A real dielectric clearcoat lobe, not screen-space refraction. Text and
        # chart data stay readable over opaque native/mesh surfaces in both themes.
        material['extensions'] = {'KHR_materials_clearcoat': {
            'clearcoatFactor': preset['clearcoat'], 'clearcoatRoughnessFactor': preset['clearcoat_roughness']}}
    return material


def canonical_float32(value):
    """Pin authored floats before either binary encoding or JSON bounds.

    Windows and Linux libm may differ by a few double-precision ULPs. Retaining
    those doubles in accessor min/max made byte-identical geometry non-repeatable.
    A one-microunit grid is below a display pixel even at a 4096px artboard and
    keeps quantized unit normals within 2e-6 of their original length. Both the
    buffer and its bounds use the same final IEEE754 float32, including +0 only.
    """
    if not math.isfinite(value):
        raise ValueError("Non-finite authored mesh coordinate")
    quantized = round(value * COORDINATE_SCALE) / COORDINATE_SCALE
    if quantized == 0:
        return 0.0
    return struct.unpack('<f', struct.pack('<f', quantized))[0]


class Mesh:
    def __init__(self, detail=True):
        self.detail = detail
        self.vertices = []
        self.normals = []
        self.indices = []

    def triangle(self, a, b, c):
        u = [b[i] - a[i] for i in range(3)]
        v = [c[i] - a[i] for i in range(3)]
        n = (u[1]*v[2]-u[2]*v[1], u[2]*v[0]-u[0]*v[2], u[0]*v[1]-u[1]*v[0])
        length = math.sqrt(sum(x*x for x in n))
        if length < 1e-12:
            return
        n = tuple(x/length for x in n)
        offset = len(self.vertices)
        self.vertices.extend((a, b, c))
        self.normals.extend((n, n, n))
        self.indices.extend((offset, offset+1, offset+2))

    def quad(self, a, b, c, d):
        self.triangle(a, b, c)
        self.triangle(a, c, d)

    def append(self, other, rotate_y=0, translate_y=0):
        cosine, sine = math.cos(rotate_y), math.sin(rotate_y)
        offset = len(self.vertices)
        self.vertices.extend((x*cosine+z*sine,y+translate_y,z*cosine-x*sine) for x,y,z in other.vertices)
        self.normals.extend((x*cosine+z*sine,y,z*cosine-x*sine) for x,y,z in other.normals)
        self.indices.extend(index+offset for index in other.indices)

    def box(self, x=0, y=0, z=0, w=1, h=1, d=.12):
        p = [(x+a*w/2, y+b*h/2, z+c*d/2)
             for a,b,c in [(-1,-1,-1),(1,-1,-1),(1,1,-1),(-1,1,-1),
                           (-1,-1,1),(1,-1,1),(1,1,1),(-1,1,1)]]
        for q in [(4,5,6,7),(1,0,3,2),(0,4,7,3),(5,1,2,6),(7,6,2,3),(0,1,5,4)]:
            self.quad(*(p[i] for i in q))

    def prism(self, polygon, depth=.12, z=0):
        # Ear clipping also handles concave bookmarks; normalize winding first.
        polygon = list(polygon)
        area = sum(a[0]*b[1]-b[0]*a[1] for a,b in zip(polygon,polygon[1:]+polygon[:1]))
        if area < 0: polygon.reverse()
        n = len(polygon)
        front = [(x,y,z+depth/2) for x,y in polygon]
        back = [(x,y,z-depth/2) for x,y in polygon]
        remaining = list(range(n))
        def cross(a,b,c): return (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])
        while len(remaining) > 2:
            for k,b in enumerate(remaining):
                a,c = remaining[k-1],remaining[(k+1)%len(remaining)]
                if cross(polygon[a],polygon[b],polygon[c]) <= 1e-10: continue
                if any(all(v >= -1e-10 for v in (
                    cross(polygon[a],polygon[b],polygon[p]),cross(polygon[b],polygon[c],polygon[p]),
                    cross(polygon[c],polygon[a],polygon[p]))) for p in remaining if p not in (a,b,c)): continue
                self.triangle(front[a],front[b],front[c]);self.triangle(back[a],back[c],back[b])
                remaining.pop(k)
                break
            else: raise ValueError('Invalid polygon')
        for i in range(n):
            j=(i+1)%n
            self.quad(back[i],back[j],front[j],front[i])

    def rod(self, x1,y1,x2,y2,r=.035,z=.08,segments=8):
        if not self.detail: segments=max(5,segments//2)
        dx,dy=x2-x1,y2-y1
        length=math.hypot(dx,dy)
        if not length:
            return
        px,py=-dy/length,dx/length
        a=[]; b=[]
        for i in range(segments):
            t=2*math.pi*i/segments
            offset=(px*r*math.cos(t),py*r*math.cos(t),r*math.sin(t))
            a.append((x1+offset[0],y1+offset[1],z+offset[2]))
            b.append((x2+offset[0],y2+offset[1],z+offset[2]))
        for i in range(segments):
            j=(i+1)%segments
            self.quad(a[i],a[j],b[j],b[i])
            self.triangle((x1,y1,z),a[j],a[i])
            self.triangle((x2,y2,z),b[i],b[j])

    def ring(self, radius=.35, tube=.035, z=0, start=0, sweep=2*math.pi, segments=40, tilt=0):
        if not self.detail: segments=max(12,segments//2)
        sides=8 if self.detail else 5
        def point(i,k):
            t=start+sweep*i/segments;v=2*math.pi*k/sides
            x=(radius+tube*math.cos(v))*math.cos(t)
            y=(radius+tube*math.cos(v))*math.sin(t)
            depth=tube*math.sin(v)
            return (x,y*math.cos(tilt)-depth*math.sin(tilt),z+y*math.sin(tilt)+depth*math.cos(tilt))
        for i in range(segments):
            for k in range(sides):
                self.quad(point(i,k),point(i+1,k),point(i+1,k+1),point(i,k+1))

    def sphere(self,x=0,y=0,z=0,r=.2,rings=8,segments=12):
        if not self.detail: rings=max(4,rings//2);segments=max(6,segments//2)
        def point(i,j):
            p=math.pi*i/rings;t=2*math.pi*j/segments
            return (x+r*math.sin(p)*math.cos(t),y+r*math.cos(p),z+r*math.sin(p)*math.sin(t))
        for i in range(rings):
            for j in range(segments):
                self.quad(point(i,j),point(i,j+1),point(i+1,j+1),point(i+1,j))

    def rounded(self,w=1,h=1,r=.12,d=.09,bevel=.022):
        steps=4 if self.detail else 2
        rings=[]
        for inset,z in [(bevel,-d/2),(0,-d/2+bevel),(0,d/2-bevel),(bevel,d/2)]:
            corners=[]
            for cx,cy,start in [(w/2-r,h/2-r,0),(-w/2+r,h/2-r,90),(-w/2+r,-h/2+r,180),(w/2-r,-h/2+r,270)]:
                for step in range(steps+1):
                    t=math.radians(start+step*90/steps)
                    corners.append((cx+(r-inset)*math.cos(t),cy+(r-inset)*math.sin(t),z))
            rings.append(corners)
        n=len(rings[0])
        for j in range(3):
            for i in range(n):
                k=(i+1)%n
                self.quad(rings[j][i],rings[j][k],rings[j+1][k],rings[j+1][i])
        for i in range(n):
            k=(i+1)%n
            self.triangle((0,0,d/2),rings[-1][i],rings[-1][k])
            self.triangle((0,0,-d/2),rings[0][k],rings[0][i])


def icon(name, detail=True):
    m=Mesh(detail)
    if name in ("surface","button","chip","input","dock","heading","bar"):
        m.rounded(r=.11 if name!="bar" else .045,d=.12 if name!="bar" else 1,bevel=.018)
    elif name=="home":
        m.prism([(-.42,.05),(0,.42),(.42,.05)],.17)
        m.box(-.23,-.16,w=.18,h=.4,d=.16);m.box(.23,-.16,w=.18,h=.4,d=.16)
        m.box(0,-.33,w=.58,h=.07,d=.16)
    elif name=="portfolio":
        m.rounded(w=.78,h=.55,r=.09,d=.18)
        for a,b,c,d in [(-.16,.25,-.16,.4),(-.16,.4,.16,.4),(.16,.4,.16,.25)]:m.rod(a,b,c,d)
        m.box(0,0,.14,.12,.12,.07)
    elif name in ("ideas","search"):
        m.ring(.26,.047,0,segments=32);m.rod(.19,-.19,.41,-.41,.06)
        if name=="ideas":m.rod(-.12,0,.12,0);m.rod(0,-.12,0,.12)
    elif name=="pulse":
        m.ring(.4,.025,segments=32)
        for a,b,c,d in [(-.4,0,-.18,0),(-.18,0,-.06,.25),(-.06,.25,.08,-.25),(.08,-.25,.19,0),(.19,0,.4,0)]:m.rod(a,b,c,d,.04)
    elif name in ("messages","sources","education"):
        if name=="education":
            m.prism([(-.45,.16),(0,.38),(.45,.16),(0,-.02)],.1)
            m.box(0,-.15,w=.58,h=.22,d=.19)
        else:
            m.rounded(w=.72,h=.7,r=.1,d=.14)
            if name=="messages":m.prism([(-.28,-.27),(-.28,-.48),(-.05,-.27)],.1)
            for y,w in [(.18,.43),(0,.43),(-.18,.27)]:m.box(-.035,y,.1,w,.04,.04)
    elif name=="profile":
        m.sphere(0,.19,0,.18)
        # Separate shoulder mesh avoids deforming the head.
        n=Mesh(detail);n.rounded(w=.7,h=.29,r=.13,d=.2)
        offset=len(m.vertices);m.vertices.extend((x,y-.27,z) for x,y,z in n.vertices);m.normals.extend(n.normals);m.indices.extend(i+offset for i in n.indices)
    elif name in ("risk","shield"):
        m.prism([(-.34,.29),(0,.42),(.34,.29),(.3,-.16),(0,-.43),(-.3,-.16)],.17)
        m.rod(-.17,0,-.04,-.12,.03,.14);m.rod(-.04,-.12,.19,.16,.03,.14)
    elif name=="allocation":
        for i,h in enumerate((.35,.68,.5)):
            m.box((i-1)*.26,h/2-.36,w=.19,h=h,d=.19)
    elif name=="back":
        m.rod(.3,0,-.3,0,.055);m.rod(-.3,0,-.03,.27,.055);m.rod(-.3,0,-.03,-.27,.055)
    elif name=="forward":
        m.rod(-.3,0,.3,0,.055);m.rod(.3,0,.03,.27,.055);m.rod(.3,0,.03,-.27,.055)
    elif name=="close":
        m.rod(-.28,-.28,.28,.28,.055);m.rod(-.28,.28,.28,-.28,.055)
    elif name in ("plus","minus"):
        m.rod(-.32,0,.32,0,.055)
        if name=="plus":m.rod(0,-.32,0,.32,.055)
    elif name in ("update","arrow"):
        m.box(0,.12,w=.09,h=.43,d=.15)
        m.prism([(-.23,-.07),(0,-.32),(.23,-.07)],.15)
        if name=="update":m.rod(-.35,-.2,-.35,-.42);m.rod(-.35,-.42,.35,-.42);m.rod(.35,-.42,.35,-.2)
    elif name in ("analyst","avatar","brand"):
        m.sphere(r=.26,rings=8 if detail else 5,segments=16 if detail else 8)
        m.ring(.42,.022,tilt=.48,segments=36 if detail else 20)
        if detail:m.ring(.36,.025,tilt=1.25,segments=32)
        m.sphere(-.095,.055,.24,.035,rings=5,segments=6);m.sphere(.095,.055,.24,.035,rings=5,segments=6)
    elif name in ("notifications","bell"):
        m.prism([(-.35,-.2),(-.22,.21),(-.1,.34),(.1,.34),(.22,.21),(.35,-.2)],.18)
        m.box(0,-.23,w=.78,h=.07,d=.19);m.sphere(0,-.34,0,.07,rings=5,segments=8)
    elif name in ("market","charts"):
        for i,h in enumerate((.33,.51,.73)):
            m.box((i-1)*.26,h/2-.38,w=.17,h=h,d=.22)
    elif name=="goal":
        m.ring(.39,.03,segments=32);m.ring(.22,.035,segments=28);m.sphere(r=.065,rings=5,segments=8)
        m.rod(.04,.04,.4,.4,.03,.1)
    elif name=="globe":
        # True spherical latitude/longitude grid. No fictional country markers.
        for longitude in (0,math.pi/3,math.pi*2/3):
            meridian=Mesh(detail);meridian.ring(.4,.014,segments=40)
            m.append(meridian,rotate_y=longitude)
        for latitude in (-.2,0,.2):
            parallel=Mesh(detail);parallel.ring(math.sqrt(.4*.4-latitude*latitude),.014,segments=40,tilt=math.pi/2)
            m.append(parallel,translate_y=latitude)
    elif name=="orbit":
        m.ring(.4,.022,segments=40 if detail else 20)
        for tilt in (.45,1.0,1.55):m.ring(.39,.014,tilt=tilt,segments=36 if detail else 20)
        m.sphere(r=.17)
    elif name=="check":
        m.rod(-.31,0,-.06,-.23,.065);m.rod(-.06,-.23,.34,.3,.065)
    elif name in ("warning","error"):
        m.prism([(-.44,-.34),(.44,-.34),(0,.43)],.14)
        m.box(0,.055,.12,.06,.27,.04);m.sphere(0,-.21,.12,.04,rings=5,segments=6)
    elif name=="settings":
        m.ring(.24,.09,segments=24)
        for i in range(8):
            t=i*math.pi/4;m.rod(.24*math.cos(t),.24*math.sin(t),.4*math.cos(t),.4*math.sin(t),.055)
    elif name=="bookmark":m.prism([(-.28,-.4),(0,-.23),(.28,-.4),(.28,.4),(-.28,.4)],.15)
    elif name=="calendar":
        m.rounded(w=.73,h=.72,r=.07,d=.12)
        for x in (-.23,0,.23):
            for y in (-.2,0,.2):m.box(x,y,.1,.1,.08,.07)
    elif name in ("stock","bond","fund","currency","monogram"):
        m.ring(.34,.085,segments=32)
        if name=="stock":m.rod(-.18,-.15,0,.02);m.rod(0,.02,.18,.19)
        elif name=="bond":m.box(0,0,w=.21,h=.41,d=.13)
        elif name=="fund":m.box(-.08,-.07,w=.2,h=.2);m.box(.1,.09,w=.2,h=.2)
        elif name=="currency":m.rod(0,-.24,0,.24,.04);m.rod(-.15,.11,.15,.11,.04)
    else:
        m.sphere(r=.29,rings=5,segments=8)
    return m


def encode(mesh,name):
    data=bytearray();views=[];accessors=[]
    def pack(values,format_,kind,components):
        if format_ == 'f':
            values = [tuple(canonical_float32(value) for value in point) for point in values]
        while len(data)%4:data.append(0)
        start=len(data)
        flat=[x for v in values for x in v] if components>1 else values
        data.extend(struct.pack('<'+format_*len(flat),*flat))
        views.append({'buffer':0,'byteOffset':start,'byteLength':len(data)-start})
        a={'bufferView':len(views)-1,'componentType':5126 if format_=='f' else 5125,'count':len(values),'type':kind}
        if kind=='VEC3':a.update(min=[min(v[i] for v in values) for i in range(3)],max=[max(v[i] for v in values) for i in range(3)])
        accessors.append(a);return len(accessors)-1
    position=pack(mesh.vertices,'f','VEC3',3);normal=pack(mesh.normals,'f','VEC3',3);indices=pack(mesh.indices,'I','SCALAR',1)
    gltf={'asset':{'version':'2.0','generator':f'Analyst AI Spectrum mesh catalogue {VERSION}'},
          'scene':0,'scenes':[{'nodes':[0]}],'nodes':[{'mesh':0,'name':name}],
          'meshes':[{'primitives':[{'attributes':{'POSITION':position,'NORMAL':normal},'indices':indices,'material':0}]}],
          'materials':[gltf_material(material_family(name))],
          'buffers':[{'byteLength':len(data)}],'bufferViews':views,'accessors':accessors}
    if material_family(name) == 'glass_coating':
        gltf['extensionsUsed'] = ['KHR_materials_clearcoat']
    js=json.dumps(gltf,separators=(',',':')).encode();js+=b' '*((-len(js))%4)
    data+=b'\x00'*((-len(data))%4)
    size=12+8+len(js)+8+len(data)
    return struct.pack('<III',0x46546C67,2,size)+struct.pack('<II',len(js),0x4E4F534A)+js+struct.pack('<II',len(data),0x004E4942)+data


NAMES=('surface button chip input dock heading bar home portfolio ideas pulse messages education profile risk allocation update sources analyst notifications market goal avatar brand globe orbit check warning error settings bookmark calendar stock bond fund currency monogram search arrow back forward close charts plus minus').split()


def verify_packaged_assets(apk, assets):
    """Compare packaged bytes with generated bytes; never extract or rewrite the APK."""
    if apk.is_symlink() or not apk.is_file():
        raise ValueError('The packaged mesh check requires the existing regular preview APK')
    prefix = 'assets/spectrum3d/'
    with zipfile.ZipFile(apk) as archive:
        entries = [entry for entry in archive.infolist() if entry.filename.startswith(prefix) and not entry.is_dir()]
        expected_names = {prefix + name for name in assets}
        if len(entries) != len(expected_names) or {entry.filename for entry in entries} != expected_names:
            raise ValueError('Packaged 3D assets are missing, duplicated or unexpected')
        for entry in entries:
            expected = assets[entry.filename.removeprefix(prefix)]
            if entry.file_size != len(expected) or archive.read(entry) != expected:
                raise ValueError('Packaged 3D asset bytes differ: ' + entry.filename)
    print(f'{len(assets)} packaged 3D files verified byte-for-byte')


def generate(check=False, check_apk=False):
    manifest={'version':VERSION,'format':'glTF 2.0 / GLB','source':'First-party procedural geometry; no remote content','models':{}}
    errors=[]
    assets={}
    for name in NAMES:
        for suffix,detail in (('',True),('_low',False)):
            key=name+suffix;mesh=icon(name,detail);payload=encode(mesh,key);path=DEST/(key+'.glb')
            if check_apk:assets[key+'.glb']=payload
            manifest['models'][key]={'sha256':hashlib.sha256(payload).hexdigest(),'bytes':len(payload),
                                    'triangles':len(mesh.indices)//3,'material':material_family(key)}
            if check:
                if not path.exists() or path.read_bytes()!=payload:errors.append(str(path))
            else:path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(payload)
    payload=(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n').encode('utf-8')
    path=DEST/CATALOGUE_NAME
    if check:
        actual=path.read_bytes() if path.exists() else None
        if actual!=payload:
            errors.append(CATALOGUE_NAME)
            print('SPECTRUM_CATALOGUE_DIFFERENCE='+json.dumps({
                'expected_sha256':hashlib.sha256(payload).hexdigest(),
                'actual_sha256':None if actual is None else hashlib.sha256(actual).hexdigest(),
                'actual_crlf_count':None if actual is None else actual.count(b'\r\n'),
                'exact_checkout_crlf':actual==payload.replace(b'\n',b'\r\n'),
            },sort_keys=True),flush=True)
    else:path.write_bytes(payload)
    if errors:raise SystemExit('Mesh catalogue differs: '+', '.join(errors))
    if check_apk:
        assets[CATALOGUE_NAME]=payload
        verify_packaged_assets(ROOT/'app/build/outputs/apk/preview/app-preview.apk',assets)
    print(f'{len(manifest["models"])} GLB assets {"verified" if check else "generated"}; '+str(sum(v['bytes'] for v in manifest['models'].values()))+' bytes')


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--check',action='store_true')
    parser.add_argument('--check-apk',action='store_true',help='Also verify the fixed preview APK without modifying it')
    args=parser.parse_args()
    if args.check_apk and not args.check:parser.error('--check-apk requires --check')
    generate(args.check,args.check_apk)
