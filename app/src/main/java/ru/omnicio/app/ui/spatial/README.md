# Spectrum mesh scene

`SpatialSceneRoot` lives inside the app's palette provider. It creates one
Filament 1.72.1 engine after the first Compose frame. Each Android window gets
one transparent TextureView, orthographic camera and scene. Dialog content uses
`SpatialWindow`; it inherits the same engine, lighting and asset pool.

## Integration

- `SpatialSurface` supplies real bevelled geometry behind native text and controls.
- `SpatialIcon` registers a versioned GLB; it never creates an engine or TextureView.
- `SpatialField`, `SpatialToggleVisual` and `SpatialChoiceVisual` provide decoration.
  The surrounding native field/toggle/selectable row owns focus, label, state,
  semantics and the minimum 48dp touch target.
- `SpatialObject(stableKey)` preserves one mesh instance between a position row
  and its details in the same window. The destination slot wins during overlap;
  the actual mesh bounds interpolate. This is not a cross-window transition.
- `SpatialBars`, `SpatialCandles` and `SpatialRing` receive real data. The caller
  owns units, dates, exact values, touch selection and equivalent accessible text.
  Missing observations remain absent. Zero/doji markers are small baseline marks,
  not inflated values. Selection changes Z/material only; camera projection and
  data height never change.

All mesh placements use unclipped layout bounds plus ancestor-clipped window
bounds. Scissor is applied per material; dynamic resolution must stay disabled
because it is incompatible with this scissor contract. Opaque Compose containers
above the shared texture would hide its meshes, so app containers stay transparent.
The root supplies the solid accessible background. A temporary native fill preserves
readable controls until their first mesh frame is submitted and if the graphical
module fails; diagnostics explicitly report failures. This is especially necessary
for white button labels in the light theme while initial shaders/assets load.

## Motion, lifecycle and cost

Live is a finite state response, with continuous rotation only for an explicit
Loading state. Subdued is shorter and rate-limited. Off retains actual 3D geometry.
Android disabled animators override preferences. Moderate heat or battery saver
uses smaller meshes and Subdued motion; severe heat stops decorative motion.
The power and thermal listeners are removed on disposal. Backgrounding stops
Choreographer callbacks and withdraws the Surface frame-rate vote.

One Choreographer callback serves all scenes. Idle scenes stop submitting frames.
Only visible clipped slots allocate instances; a pool recycles their high-water
mark. Changed allocation wedges have a bounded unused cache. Colour uniforms,
scissors and transforms update only when their values change. Mesh generation,
disk reads and digest checks run off the UI thread. Rendering invokes no network,
analytics, broker or AI functions.

The GLBs are reproducible first-party geometry with positions, normals, indices,
closed surfaces and real Z. `catalogue.json` pins catalogue version 1 and SHA-256
for each asset. No runtime material compiler, remote models, raster icons or
unverified logo downloads are used. The gltfio UbershaderProvider supplies compiled
materials. Source data remains retained because Filament needs it to create pooled
instances. Destruction releases scenes before instances/materials/assets and the
shared engine; UiHelper detaches and flushes before a native surface disappears.

## Verification and release gates

Local reproducibility/topology tests:

```
python3 tools/generate_spectrum_meshes.py --check
python3 tools/test_spectrum_meshes.py
```

`SpatialChartGeometryTest` covers signed/extreme ranges, missing values, exact zero,
invalid OHLC and proportional extreme allocations through the Android JVM tests.

`spatialDiagnostics()` reports actual submitted/skipped frames, visible mesh and
pool counts, frame-interval p95 and CPU submission p95. It does **not** measure GPU
time, completed display frames, Android frame jank or battery drain. Never label
these counters as a passed device benchmark. Targets for reference-device runs:
responsive first data frame before model loading; no continued idle submissions;
60fps interaction at standard quality, 30fps in economy; no retained activity or
surface after repeated rotation/background cycles. Validate targets using Perfetto
and actual API 35/36 devices/emulators, including an Android 15 16KB environment.

Filament 1.72.1's native build requests a 16384-byte maximum ELF page size. This
source-level fact does not prove the final APK: inspect packaged ELF segments and
zip alignment, then launch the packaged build on a 16KB system before release.
