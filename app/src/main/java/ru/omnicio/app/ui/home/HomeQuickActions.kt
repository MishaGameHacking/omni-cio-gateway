package ru.omnicio.app.ui.home

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
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
import ru.omnicio.app.ui.spectrum.SpectrumIcon
import ru.omnicio.app.ui.spectrum.SpectrumSymbol

private data class HomeAction(val title: String, val symbol: SpectrumSymbol, val accent: Color, val open: () -> Unit)

/** One compact icon strip on phones, a two-column grid with large accessibility fonts. */
@Composable
internal fun HomeQuickActions(
    onPortfolio: () -> Unit,
    onRecommendations: () -> Unit,
    onRisk: () -> Unit,
    onMessages: () -> Unit,
) {
    val palette = LocalSpectrumPalette.current
    val largeFont = LocalDensity.current.fontScale >= 1.4f
    val actions = listOf(
        HomeAction("Портфель", SpectrumSymbol.Portfolio, palette.blue, onPortfolio),
        HomeAction("Рекомендации", SpectrumSymbol.Ideas, palette.violet, onRecommendations),
        HomeAction("Риски", SpectrumSymbol.Risk, palette.rose, onRisk),
        HomeAction("Сообщения", SpectrumSymbol.Messages, palette.cyan, onMessages),
    )
    BoxWithConstraints(Modifier.fillMaxWidth()) {
        val columns = homeActionColumns(maxWidth.value, largeFont)
        Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
            actions.chunked(columns).forEach { row ->
                Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(4.dp)) {
                    row.forEach { action -> ActionCell(action, Modifier.weight(1f)) }
                }
            }
        }
    }
}

internal fun homeActionColumns(widthDp: Float, largeFont: Boolean): Int =
    if (largeFont || widthDp < 260f) 2 else 4

@Composable
private fun ActionCell(action: HomeAction, modifier: Modifier) {
    val palette = LocalSpectrumPalette.current
    Column(modifier.clip(RoundedCornerShape(16.dp))
        .clickable(role = Role.Button, onClickLabel = "Открыть ${action.title}", onClick = action.open)
        .padding(vertical = 4.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.spacedBy(7.dp)) {
        Surface(Modifier.size(52.dp), shape = RoundedCornerShape(17.dp),
            color = palette.cardStrong, border = BorderStroke(1.dp, action.accent.copy(alpha = 0.6f))) {
            SpectrumIcon(action.symbol, Modifier.padding(9.dp), selected = true, tile = false, motionAllowed = false)
        }
        Text(action.title, Modifier.fillMaxWidth(), textAlign = TextAlign.Center,
            style = MaterialTheme.typography.labelSmall, fontWeight = FontWeight.Medium,
            color = MaterialTheme.colorScheme.onSurface, softWrap = true)
    }
}
