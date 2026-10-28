package ru.omnicio.app.ui.spectrum

import androidx.compose.foundation.layout.size
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.semantics.ProgressBarRangeInfo
import androidx.compose.ui.semantics.progressBarRangeInfo
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.dp
import ru.omnicio.app.ui.spatial.SpatialIcon
import ru.omnicio.app.ui.spatial.SpatialState

/** Only compose while a real operation is active. No fabricated percent or timer. */
@Composable
fun SpectrumLoadingIndicator(
    modifier: Modifier = Modifier.size(28.dp),
    description: String = "Загрузка",
    motionAllowed: Boolean = true,
) {
    SpatialIcon("orbit", modifier.semantics { progressBarRangeInfo = ProgressBarRangeInfo.Indeterminate },
        tint = LocalSpectrumPalette.current.cyan, state = SpatialState.Loading,
        motionAllowed = motionAllowed, description = description)
}
