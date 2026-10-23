package ru.omnicio.app.ui.spectrum

import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import ru.omnicio.app.ui.spatial.SpatialIcon
import ru.omnicio.app.ui.theme.LocalSpectrumMotionPreference

/** Decorative 3D orbital mesh; its radius never encodes a financial value. */
@Composable
fun SpectrumCapitalOrbit(modifier: Modifier = Modifier) {
    SpatialIcon("orbit", modifier, tint = LocalSpectrumPalette.current.cyan,
        motionAllowed = LocalSpectrumMotionPreference.current.enabled)
}

