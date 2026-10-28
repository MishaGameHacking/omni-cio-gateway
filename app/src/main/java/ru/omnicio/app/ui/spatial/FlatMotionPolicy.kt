package ru.omnicio.app.ui.spatial

/** User choice, accessibility and device state all constrain motion. */
internal fun flatMotionPolicy(requested: SpatialMotion, foreground: Boolean,
    systemEnabled: Boolean, constrained: Boolean, severeThermal: Boolean = false): SpatialMotion = when {
    !foreground || !systemEnabled || severeThermal || requested == SpatialMotion.Off -> SpatialMotion.Off
    constrained -> SpatialMotion.Subdued
    else -> requested
}
