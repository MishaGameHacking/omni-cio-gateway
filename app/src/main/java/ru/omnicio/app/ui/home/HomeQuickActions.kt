package ru.omnicio.app.ui.home

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import ru.omnicio.app.ui.spectrum.LocalSpectrumPalette
import ru.omnicio.app.ui.spectrum.SpectrumLiveFeature
import ru.omnicio.app.ui.spectrum.SpectrumLiveFeatureIcon
import ru.omnicio.app.ui.theme.LocalSpectrumMotionPreference

private data class HomeAction(
    val title: String,
    val liveFeature: SpectrumLiveFeature,
    val accent: Color,
    val open: () -> Unit,
)

/** Adaptive shortcuts to the assistant, strategies and accessible market overview. */
@Composable
internal fun HomeQuickActions(
    onAssistant: () -> Unit,
    onStrategies: () -> Unit,
    onMarket: () -> Unit,
) {
    val palette = LocalSpectrumPalette.current
    val largeFont = LocalDensity.current.fontScale >= 1.4f
    val actions = listOf(
        HomeAction("Ассистент", SpectrumLiveFeature.Assistant, palette.cyan, onAssistant),
        HomeAction("Стратегии", SpectrumLiveFeature.Recommendations, palette.violet, onStrategies),
        HomeAction("Обзор рынка", SpectrumLiveFeature.WorldMarkets, palette.blue, onMarket),
    )

    BoxWithConstraints(Modifier.fillMaxWidth()) {
        val columns = homeActionColumns(maxWidth.value, largeFont)
        Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
            actions.chunked(columns).forEach { row ->
                Row(
                    Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(4.dp),
                ) {
                    row.forEach { action -> ActionCell(action, Modifier.weight(1f)) }
                }
            }
        }
    }
}

internal fun homeActionColumns(widthDp: Float, largeFont: Boolean): Int =
    if (largeFont || widthDp < 260f) 1 else 3

@Composable
private fun ActionCell(action: HomeAction, modifier: Modifier) {
    val palette = LocalSpectrumPalette.current
    val motion = LocalSpectrumMotionPreference.current
    Column(
        modifier
            .clip(RoundedCornerShape(16.dp))
            .clickable(
                role = Role.Button,
                onClickLabel = "Открыть ${action.title}",
                onClick = action.open,
            )
            .padding(vertical = 4.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.spacedBy(7.dp),
    ) {
        Surface(
            Modifier.size(52.dp),
            shape = RoundedCornerShape(18.dp),
            color = palette.cardStrong,
            border = BorderStroke(1.dp, action.accent.copy(alpha = 0.2f)),
        ) {
            SpectrumLiveFeatureIcon(
                feature = action.liveFeature,
                modifier = Modifier.padding(5.dp),
                motionAllowed = motion.enabled,
            )
        }
        Text(
            action.title,
            Modifier.fillMaxWidth(),
            textAlign = TextAlign.Center,
            style = MaterialTheme.typography.labelSmall,
            fontWeight = FontWeight.Medium,
            color = MaterialTheme.colorScheme.onSurface,
            softWrap = true,
        )
    }
}

