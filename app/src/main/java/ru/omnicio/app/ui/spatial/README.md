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

## Antialiasing and GLES compatibility

Every window uses geometry MSAA (4 samples, 2 in the existing thermal/battery
economy profile), with the standard resolve. FXAA is disabled. Post-processing
remains enabled for tone mapping and gamma encoding; the PBR materials, directional
light, shadows, transparent composition and exact orthographic geometry stay active.

The first [API 35 ps16k runtime](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/39069831896)
of candidate `4fa39fd` installed and upgraded successfully, measured
`PAGE_SIZE=16384`, then aborted while compiling Filament's
translucent `fxaa` program on the emulator's GLES 3.0 SwiftShader driver. The
compiler's detailed InfoLog was absent from that run's general log tail. This
is an observed shader failure, not an ELF/ZIP alignment failure.

In pinned Filament 1.72.1, [PostProcessManager](https://github.com/google/filament/blob/v1.72.1/filament/src/PostProcessManager.cpp)
registers material bytes during `init()` and loads/compiles the material lazily.
[Renderer](https://github.com/google/filament/blob/v1.72.1/filament/src/details/Renderer.cpp)
calls `fxaa()` only when the view enables FXAA. Selecting MSAA with `AntiAliasing.NONE`
therefore avoids the failing program, while
[View's MSAA API](https://github.com/google/filament/blob/v1.72.1/android/filament-android/src/main/java/com/google/android/filament/View.java)
retains geometry antialiasing independently. No Java exception handler can recover
an abort on Filament's native engine thread.

The replacement must pass the complete next API 35/36 runtime before release.
Existing mesh-pixel, contrast, clipping, motion, lifetime, long-scroll and upgrade
checks remain mandatory. On failure, the runner now collects filtered main/system
shader logs and the installed app's UID logs, which retain PID/TID even after an
abort, in addition to the existing crash buffer. Output and command times are
bounded; a diagnostic read never counts as a successful rendering test.

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
