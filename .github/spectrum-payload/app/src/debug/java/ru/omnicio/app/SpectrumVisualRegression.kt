package ru.omnicio.app

import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.compositeOver
import androidx.compose.ui.graphics.luminance
import ru.omnicio.app.ui.AnalystTab
import ru.omnicio.app.ui.PrimaryAnalystTabs
import ru.omnicio.app.ui.portfolio.HistoryPoint
import ru.omnicio.app.ui.portfolio.portfolioLineHistory
import ru.omnicio.app.ui.spectrum.DarkSpectrumPalette
import ru.omnicio.app.ui.spectrum.LightSpectrumPalette
import ru.omnicio.app.ui.theme.DarkColors
import ru.omnicio.app.ui.theme.LightColors
import java.math.BigDecimal
import kotlin.math.abs

internal fun runSpectrumContrastChecks() {
    check(PrimaryAnalystTabs == listOf(AnalystTab.Home, AnalystTab.Portfolio, AnalystTab.Market, AnalystTab.Education, AnalystTab.Profile))
    check(PrimaryAnalystTabs.distinct().size == 5)
    listOf(DarkColors to DarkSpectrumPalette, LightColors to LightSpectrumPalette).forEach { (theme, palette) ->
        requireContrast(theme.onBackground, theme.background)
        listOf(theme.surface, palette.card, palette.cardStrong).forEach { background ->
            requireContrast(theme.onSurface, background)
            requireContrast(theme.onSurfaceVariant, background)
        }
        requireContrast(theme.onPrimary, theme.primary)
        requireContrast(theme.onSecondaryContainer, theme.secondaryContainer)
        requireContrast(theme.error, palette.card)
        listOf(palette.cyan, palette.blue, palette.violet, palette.rose, palette.emerald, palette.amber).forEach { ink ->
            requireContrast(ink, ink.copy(alpha = .1f).compositeOver(palette.card))
        }
    }
    listOf(0xFF6938E8, 0xFF3154DE, 0xFF007E61, 0xFF00694F, 0xFF345AE0, 0xFF6540C9).forEach { requireContrast(Color.White, Color(it)) }
}

private fun requireContrast(foreground: Color, background: Color) {
    val light = maxOf(foreground.luminance(), background.luminance())
    val dark = minOf(foreground.luminance(), background.luminance())
    val ratio = (light + .05f) / (dark + .05f)
    check(ratio >= 4.5f) { "Spectrum text contrast below 4.5:1: $ratio" }
}

internal fun runSpectrumLineChecks() {
    fun point(day: Int, value: String) = HistoryPoint("2026-10-${day.toString().padStart(2, '0')}T07:00:00Z", BigDecimal(value))
    val flat = portfolioLineHistory(listOf(point(1, "5000.08"), point(2, "5000.08")))!!
    check(flat.coordinates.all { it.y == .5f })
    check(flat.high.compareTo(BigDecimal("5000.08")) == 0)
    val rise = portfolioLineHistory(listOf(point(2, "5000.09"), point(1, "5000.08")))!!
    check(abs(rise.coordinates.first().y - 1f) < .00001f && rise.coordinates.last().y == 0f)
    check(rise.coordinates.first().point.date.startsWith("2026-10-01"))
    val negative = portfolioLineHistory(listOf(point(1, "-4"), point(2, "-2")))!!
    check(negative.coordinates.all { it.y.isFinite() && it.y in 0f..1f })
    check(portfolioLineHistory(listOf(point(1, "1"), point(1, "2"))) == null)
    check(portfolioLineHistory(listOf(HistoryPoint("invalid", BigDecimal.ONE), point(2, "2"))) == null)
    val zero = portfolioLineHistory(listOf(point(1, "0"), point(2, "0")))!!
    check(zero.coordinates.all { it.y == .5f })
    check(portfolioLineHistory(listOf(point(1, "1"))) == null)
    val fixture = portfolioLineHistory(spectrumFixtureHistory())!!
    check(fixture.coordinates.size == 7 && fixture.coordinates.last().point.value == BigDecimal("10160"))
}
