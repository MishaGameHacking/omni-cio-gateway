package ru.omnicio.app.ui.spectrum

import androidx.compose.runtime.Composable
import androidx.compose.runtime.Immutable
import androidx.compose.ui.Modifier
import ru.omnicio.app.ui.spatial.SpatialIcon

@Immutable
enum class SpectrumLiveFeature(val description: String, internal val asset: String) {
    Charts("Объёмные графики", "charts"),
    Indicators("Объёмные индикаторы", "pulse"),
    Spatial("Настоящие пространственные элементы", "orbit"),
    RgbEffects("Материалы объёмных иконок", "brand"),
    Assistant("Интерактивный ИИ-ассистент", "avatar"),
    Notifications("Умные уведомления", "notifications"),
    Recommendations("Персональные рекомендации", "goal"),
    RiskControl("Контроль рисков", "risk"),
    WorldMarkets("Анализ мировых рынков", "globe"),
}

/** A feature illustration, never a synthetic market chart or an activity claim. */
@Composable
fun SpectrumLiveFeatureIcon(
    feature: SpectrumLiveFeature,
    modifier: Modifier = Modifier,
    motionAllowed: Boolean = true,
) {
    SpatialIcon(feature.asset, modifier, tint = LocalSpectrumPalette.current.cyan,
        motionAllowed = motionAllowed, description = feature.description)
}

