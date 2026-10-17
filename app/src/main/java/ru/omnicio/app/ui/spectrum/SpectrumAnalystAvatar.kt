package ru.omnicio.app.ui.spectrum

import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.size
import androidx.compose.runtime.Composable
import androidx.compose.runtime.Immutable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import ru.omnicio.app.ui.spatial.SpatialIcon
import ru.omnicio.app.ui.spatial.SpatialState

@Immutable
enum class AnalystAvatarMood { Ready, Attention, Waiting }

/** The object reacts to actual client state; waiting does not invent AI progress. */
@Composable
fun SpectrumAnalystAvatar(
    mood: AnalystAvatarMood,
    modifier: Modifier = Modifier,
    motionAllowed: Boolean = true,
) {
    val palette = LocalSpectrumPalette.current
    val accent = when (mood) {
        AnalystAvatarMood.Ready -> palette.emerald
        AnalystAvatarMood.Attention -> palette.amber
        AnalystAvatarMood.Waiting -> palette.blue
    }
    val description = when (mood) {
        AnalystAvatarMood.Ready -> "Analyst AI готов показать выводы по данным портфеля"
        AnalystAvatarMood.Attention -> "Analyst AI просит проверить данные портфеля"
        AnalystAvatarMood.Waiting -> "Analyst AI ожидает данные портфеля"
    }
    val state = when (mood) {
        AnalystAvatarMood.Ready -> SpatialState.Success
        AnalystAvatarMood.Attention -> SpatialState.Attention
        AnalystAvatarMood.Waiting -> SpatialState.Idle
    }
    Box(modifier) {
        SpatialIcon("avatar", Modifier.fillMaxSize(), accent, state, motionAllowed, description)
        if (mood != AnalystAvatarMood.Waiting) SpatialIcon(
            if (mood == AnalystAvatarMood.Ready) "check" else "warning",
            Modifier.align(Alignment.BottomEnd).size(28.dp), accent, state, motionAllowed,
        )
    }
}

