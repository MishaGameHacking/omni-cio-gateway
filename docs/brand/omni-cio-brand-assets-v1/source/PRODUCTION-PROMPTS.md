# Production image-generation prompts

Все три операции выполнялись как точечные варианты утверждённого master-logo. Геометрия и композиция были зафиксированы как invariants.

## Simplified small-size source

Preserve the exact composition, silhouette, placement, orbit shape, core shape, trajectory direction, endpoint position, proportions, colors, dark full-bleed background, and institutional 2.5D identity. Change only small-size rendering details: raise the brightness/contrast of the single upper-left core facet by about 8–10%; simplify internal core shading into four broad readable facets; reduce the outer halo radius and intensity around the one signal point by about 30%; simplify very fine highlights and bevel transitions so they survive downsampling. The central core must remain clearly visible at 32 px and distinguish the mark from a generic power symbol. No redesign, repositioning, new elements, arrowhead, text, mask, border, watermark, extra dots, or extra glow.

## Android adaptive color foreground

Extract only the complete approved emblem — incomplete cyan-blue-violet orbit, centered dark rounded-diamond core, one cyan-to-mint analytical trajectory, and one mint signal point — on a genuinely transparent background. Preserve exact geometry, relative proportions, endpoint position, palette, and 2.5D identity. Remove only the midnight background and radial glow. Center and uniformly scale the complete mark into the Android 66×66 safe zone inside the 108×108 canvas. Use clean edges and no background shadow around the outer silhouette. Exactly one orbit, one core, one trajectory, and one signal point; no redesign, text, mask, border, watermark, extra dots, or added shadows outside the logo.

## Android themed / universal monochrome

Trace the exact approved emblem geometry as a single flat solid-white mark on a genuinely transparent background: incomplete orbit, centered rounded-diamond core, one smooth analytical trajectory passing behind the core, and one circular endpoint signal. Preserve placement, relative proportions, ring opening, trajectory direction, core prominence, and endpoint position. Fit all critical geometry inside the Android 66×66 safe zone. Use broad clean anti-aliased edges. Exactly one flat color; no gradients, facets, glow, halo, shadows, background, mask, border, text, watermark, redesign, or extra elements.

The final monochrome deliverable uses the cleaned alpha silhouette of the approved transparent foreground so its geometry remains exactly aligned with the color adaptive layer.
