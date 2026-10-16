package ru.omnicio.app.ui.spectrum

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import ru.omnicio.app.ui.theme.LocalSpectrumMotionPreference

/**
 * The complete OWNER-approved live element catalogue from the Spectrum reference.
 *
 * Phones and large-font configurations use a lazy horizontal rail so only visible
 * animated canvases remain composed. Wider windows use an adaptive grid without
 * assuming a fixed orientation or aspect ratio. The tiles are intentionally not
 * fake navigation: they demonstrate native capabilities while real destinations
 * remain available through the primary actions above.
 */
@Composable
fun SpectrumLiveFeatureShowcase(
    modifier: Modifier = Modifier,
) {
    val palette = LocalSpectrumPalette.current
    val motionAllowed = LocalSpectrumMotionPreference.current.enabled
    val fontScale = LocalDensity.current.fontScale

    SpectrumCard(modifier = modifier) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(10.dp),
        ) {
            Column(
                modifier = Modifier.weight(1f),
                verticalArrangement = Arrangement.spacedBy(3.dp),
            ) {
                Text(
                    text = "Живые возможности",
                    style = MaterialTheme.typography.titleLarge,
                    fontWeight = FontWeight.Bold,
                )
                Text(
                    text = "Нативные элементы Analyst AI — не картинки и не GIF",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
            SpectrumBadge("Android 16", accent = palette.cyan)
        }

        BoxWithConstraints(modifier = Modifier.fillMaxWidth()) {
            val useLazyRail = maxWidth < 600.dp || fontScale > 1.30f
            if (useLazyRail) {
                LazyRow(
                    modifier = Modifier
                        .fillMaxWidth()
                        .testTag("spectrum-live-feature-rail"),
                    contentPadding = PaddingValues(end = 4.dp),
                    horizontalArrangement = Arrangement.spacedBy(10.dp),
                ) {
                    items(
                        items = SpectrumLiveFeature.entries,
                        key = SpectrumLiveFeature::name,
                    ) { feature ->
                        SpectrumLiveFeatureTile(
                            feature = feature,
                            accent = feature.accent(palette),
                            motionAllowed = motionAllowed,
                            modifier = Modifier.size(width = 136.dp, height = 158.dp),
                        )
                    }
                }
            } else {
                val columns = if (maxWidth >= 900.dp) 5 else 3
                Column(
                    modifier = Modifier
                        .fillMaxWidth()
                        .testTag("spectrum-live-feature-grid"),
                    verticalArrangement = Arrangement.spacedBy(10.dp),
                ) {
                    SpectrumLiveFeature.entries.toList().chunked(columns).forEach { rowFeatures ->
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.spacedBy(10.dp),
                        ) {
                            rowFeatures.forEach { feature ->
                                SpectrumLiveFeatureTile(
                                    feature = feature,
                                    accent = feature.accent(palette),
                                    motionAllowed = motionAllowed,
                                    modifier = Modifier
                                        .weight(1f)
                                        .heightIn(min = 154.dp),
                                )
                            }
                            repeat(columns - rowFeatures.size) {
                                Spacer(Modifier.weight(1f))
                            }
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun SpectrumLiveFeatureTile(
    feature: SpectrumLiveFeature,
    accent: Color,
    motionAllowed: Boolean,
    modifier: Modifier,
) {
    val palette = LocalSpectrumPalette.current
    Surface(
        modifier = modifier.testTag("spectrum-live-feature-${feature.name.lowercase()}"),
        shape = RoundedCornerShape(20.dp),
        color = palette.cardStrong.copy(alpha = 0.74f),
        contentColor = MaterialTheme.colorScheme.onSurface,
        border = BorderStroke(1.dp, accent.copy(alpha = 0.36f)),
    ) {
        Column(
            modifier = Modifier.padding(horizontal = 10.dp, vertical = 12.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            SpectrumLiveFeatureIcon(
                feature = feature,
                modifier = Modifier.size(78.dp),
                motionAllowed = motionAllowed,
            )
            Text(
                text = feature.shortTitle(),
                style = MaterialTheme.typography.labelLarge,
                fontWeight = FontWeight.SemiBold,
                textAlign = TextAlign.Center,
                minLines = 2,
                maxLines = 3,
            )
        }
    }
}

private fun SpectrumLiveFeature.shortTitle(): String = when (this) {
    SpectrumLiveFeature.Charts -> "Живые графики"
    SpectrumLiveFeature.Indicators -> "Анимированные индикаторы"
    SpectrumLiveFeature.Spatial -> "2D/3D элементы"
    SpectrumLiveFeature.RgbEffects -> "RGB-эффекты иконок"
    SpectrumLiveFeature.Assistant -> "Интерактивный ИИ-ассистент"
    SpectrumLiveFeature.Notifications -> "Умные уведомления"
    SpectrumLiveFeature.Recommendations -> "Персональные рекомендации"
    SpectrumLiveFeature.RiskControl -> "Контроль рисков"
    SpectrumLiveFeature.WorldMarkets -> "Анализ мировых рынков"
}

private fun SpectrumLiveFeature.accent(palette: SpectrumPalette): Color = when (this) {
    SpectrumLiveFeature.Charts -> palette.emerald
    SpectrumLiveFeature.Indicators -> palette.cyan
    SpectrumLiveFeature.Spatial -> palette.blue
    SpectrumLiveFeature.RgbEffects -> palette.violet
    SpectrumLiveFeature.Assistant -> palette.cyan
    SpectrumLiveFeature.Notifications -> palette.violet
    SpectrumLiveFeature.Recommendations -> palette.rose
    SpectrumLiveFeature.RiskControl -> palette.emerald
    SpectrumLiveFeature.WorldMarkets -> palette.blue
}
