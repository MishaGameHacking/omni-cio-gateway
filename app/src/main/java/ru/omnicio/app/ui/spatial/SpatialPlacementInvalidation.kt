package ru.omnicio.app.ui.spatial

import androidx.compose.ui.geometry.Offset

/** Exact geometry changes redraw even with motion Off; duplicate observations do not. */
internal fun spatialPlacementChanged(
    previousOrigin: Offset,
    previousDensity: Float,
    origin: Offset,
    density: Float,
): Boolean = previousOrigin != origin || previousDensity != density
