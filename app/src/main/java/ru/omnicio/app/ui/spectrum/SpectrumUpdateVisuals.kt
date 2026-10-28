package ru.omnicio.app.ui.spectrum

import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxScope
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import ru.omnicio.app.ui.spatial.SpatialIcon
import ru.omnicio.app.ui.spatial.SpatialState

@Composable
fun SpectrumUpdateBackdrop(
    motionAllowed: Boolean,
    modifier: Modifier = Modifier,
    content: @Composable BoxScope.() -> Unit,
) {
    Box(modifier) {
        SpatialIcon("orbit", Modifier.align(Alignment.TopCenter).fillMaxWidth(.68f).aspectRatio(1f),
            tint = LocalSpectrumPalette.current.cardStrong, motionAllowed = motionAllowed)
        content()
    }
}

@Composable
fun SpectrumUpdateAlert(
    updateRequired: Boolean,
    motionAllowed: Boolean,
    modifier: Modifier = Modifier,
) {
    val palette = LocalSpectrumPalette.current
    SpatialIcon(if (updateRequired) "warning" else "update", modifier.aspectRatio(1f),
        tint = if (updateRequired) palette.amber else palette.cyan,
        state = if (updateRequired) SpatialState.Attention else SpatialState.Idle,
        motionAllowed = motionAllowed,
        description = if (updateRequired) "Требуется обязательное обновление Analyst AI" else "Обновление Analyst AI",
    )
}

