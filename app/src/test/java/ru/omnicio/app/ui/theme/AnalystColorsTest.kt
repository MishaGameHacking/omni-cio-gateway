package ru.omnicio.app.ui.theme

import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.luminance
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import ru.omnicio.app.ui.workspace.AccentStyle

class AnalystColorsTest {
    private fun contrast(a: Color, b: Color): Double {
        val high = maxOf(a.luminance(), b.luminance()).toDouble()
        val low = minOf(a.luminance(), b.luminance()).toDouble()
        return (high + .05) / (low + .05)
    }

    private fun readable(ink: Color, fill: Color, threshold: Double = 4.5) {
        assertEquals("Contrast is evaluated for opaque production tokens", 1f, ink.alpha, 0f)
        assertEquals("Contrast is evaluated for opaque production tokens", 1f, fill.alpha, 0f)
        assertTrue("Actual pair $ink on $fill has contrast ${contrast(ink, fill)}", contrast(ink, fill) >= threshold)
    }

    @Test
    fun everyActionFamilyKeepsPairedMaterialAndSemanticContentReadable() {
        for (dark in listOf(false, true)) for (accent in AccentStyle.entries) {
            val actual = analystColors(dark, accent)
            val c = actual.material
            val s = actual.semantic
            val pairs = listOf(c.onPrimary to c.primary, c.onPrimaryContainer to c.primaryContainer,
                c.onSecondary to c.secondary, c.onSecondaryContainer to c.secondaryContainer,
                c.onTertiary to c.tertiary, c.onTertiaryContainer to c.tertiaryContainer,
                c.onError to c.error, c.onErrorContainer to c.errorContainer,
                c.onBackground to c.background, c.inverseOnSurface to c.inverseSurface,
                s.onSuccess to s.success, s.onSuccessContainer to s.successContainer,
                s.onWarning to s.warning, s.onWarningContainer to s.warningContainer,
                s.onInfo to s.info, s.onInfoContainer to s.infoContainer)
            pairs.forEach { (ink, fill) -> readable(ink, fill) }
            readable(c.onPrimary, analystPressedColor(c.primary, c.onPrimary))
            readable(c.onSurface, c.primaryContainer)
        }
    }

    @Test
    fun surfaceHierarchyKeepsSecondaryTextAndMeaningfulOutlinesReadable() {
        for (dark in listOf(false, true)) for (accent in AccentStyle.entries) {
            val c = analystColors(dark, accent).material
            val surfaces = listOf(c.background, c.surface, c.surfaceVariant, c.surfaceBright, c.surfaceDim,
                c.surfaceContainerLowest, c.surfaceContainerLow, c.surfaceContainer, c.surfaceContainerHigh,
                c.surfaceContainerHighest)
            for (surface in surfaces) {
                readable(c.onSurface, surface)
                readable(c.onSurfaceVariant, surface)
                readable(c.outline, surface, 3.0)
            }
        }
    }

    @Test
    fun fixedPrimaryColorsRemainStableAcrossModesForEveryUserAccent() {
        for (accent in AccentStyle.entries) {
            val light = analystColors(false, accent).material
            val dark = analystColors(true, accent).material
            assertEquals(light.primaryFixed, dark.primaryFixed)
            assertEquals(light.primaryFixedDim, dark.primaryFixedDim)
            assertEquals(light.onPrimaryFixed, dark.onPrimaryFixed)
            assertEquals(light.onPrimaryFixedVariant, dark.onPrimaryFixedVariant)
            for (c in listOf(light, dark)) {
                for (fill in listOf(c.primaryFixed, c.primaryFixedDim)) {
                    readable(c.onPrimaryFixed, fill)
                    readable(c.onPrimaryFixedVariant, fill)
                }
                for (fill in listOf(c.secondaryFixed, c.secondaryFixedDim)) {
                    readable(c.onSecondaryFixed, fill)
                    readable(c.onSecondaryFixedVariant, fill)
                }
                for (fill in listOf(c.tertiaryFixed, c.tertiaryFixedDim)) {
                    readable(c.onTertiaryFixed, fill)
                    readable(c.onTertiaryFixedVariant, fill)
                }
            }
            assertEquals(dark.primary, light.inversePrimary)
            assertEquals(light.primary, dark.inversePrimary)
        }
    }

    @Test
    fun anAccentCannotRecolorFinancialCategoriesOrSuccessWarningError() {
        assertEquals(listOf("AURORA", "OCEAN", "IRIS"), AccentStyle.entries.map { it.name })
        for (dark in listOf(false, true)) {
            val original = analystColors(dark, AccentStyle.AURORA)
            assertEquals(6, original.chartSeries.distinct().size)
            for (accent in AccentStyle.entries) {
                val actual = analystColors(dark, accent)
                assertEquals(original.chartSeries, actual.chartSeries)
                assertEquals(original.semantic, actual.semantic)
                assertEquals(original.material.error, actual.material.error)
                assertEquals(actual.material.primary, actual.material.surfaceTint)
                actual.chartSeries.forEach { readable(it, actual.material.surface, 3.0) }
            }
            assertEquals(original, analystColors(dark, AccentStyle.OCEAN))
            assertEquals(original, analystColors(dark, AccentStyle.IRIS))
        }
    }

    @Test
    fun unavailableCalendarDatesStayReadableOnOrdinarySelectedAndRangeSurfaces() {
        for (dark in listOf(false, true)) for (accent in AccentStyle.entries) {
            val actual = analystColors(dark, accent)
            for (fill in listOf(actual.material.surface, actual.semantic.disabledContainer,
                actual.material.primaryContainer)) {
                readable(actual.semantic.disabledInk, fill, 3.0)
            }
            readable(actual.material.onPrimaryContainer, actual.material.primaryContainer)
            readable(actual.material.primary, actual.material.surface)
        }
    }
}
