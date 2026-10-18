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

Every window retains the original FXAA with post-processing enabled for tone
mapping and gamma encoding. PBR materials, directional light, shadows, transparent
composition and exact orthographic geometry remain active. The temporary MSAA
workaround has been removed: avoiding an individual shader cannot fix a general
GLES compiler failure.

The [first API 35 ps16k runtime](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/39069831896)
of `4fa39fd` measured `PAGE_SIZE=16384`, installed/upgraded, then aborted compiling
`fxaa`. The [subsequent runtime](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/39099562552)
of `81b0101` also passed source/package/alignment and installation checks, but its
captured InfoLog rejected a structure constructor in `blitLow`. Both contexts
reported the emulator's old GLES 3.0 SwiftShader 4.0.0.1 frontend. This is broader
than antialiasing and is not an ELF/ZIP page-alignment failure.

The exact [Filament 1.72.1 `blitLow` material](https://github.com/google/filament/blob/v1.72.1/filament/src/materials/blitLow.mat),
compiled with that release's official `matc`, produces a GLES 3.0 expression
`PostProcessInputs(textureLod(...)).color` consistent with the captured constructor
error. CI now requests `-gpu lavapipe -feature Vulkan,GuestAngle`. In the emulator's
[37.2 source](https://android.googlesource.com/platform/external/qemu/+/f0c183f1cc7456ecd6f3607f2f47893768ae4334/android/android-ui/modules/aemu-gl-init/src/android/opengl/emugl_config.cpp),
Windows can fall back to legacy host GLES even when a modern software Vulkan ICD
is selected. Guest ANGLE sends the app's unchanged OpenGL API through Vulkan, as
implemented by Android's [EGL display](https://android.googlesource.com/platform/frameworks/native/+/refs/tags/android-platform-15.0.0_r21/opengl/libs/EGL/egl_display.cpp).
No system Skia mode, advertised GLES version or feature queue is forced separately.

The exact SDK images still have to demonstrate this route in the next API 35/36
run. Before app launch, the runner records bounded system properties/compositor
diagnostics. Each candidate launch additionally requires its own complete Filament
GL vendor/renderer/version header, filtered by installed UID **and the freshly
observed PID**; missing, conflicting or non-ANGLE/non-Vulkan context evidence fails.
The actual renderer is retained inside the existing launch result, separately from
requested flags and system-compositor observations. Neither a SurfaceFlinger line
nor an offline parser test proves app rendering.

The complete mesh-pixel, contrast, clipping, motion, lifetime, long-scroll, 16KB and
upgrade checks remain mandatory. Failure diagnostics retain filtered main/system
shader and installed-UID logs (including dead-process PID/TID) plus the crash
buffer, without clearing logs. Output and command times are bounded. No Java
exception handler can recover an abort on Filament's native engine thread.

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
