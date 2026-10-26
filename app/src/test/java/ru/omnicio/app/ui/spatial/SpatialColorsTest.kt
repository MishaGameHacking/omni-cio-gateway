package ru.omnicio.app.ui.spatial

import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.luminance
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import ru.omnicio.app.ui.spectrum.spectrumPalette
import ru.omnicio.app.ui.workspace.AccentStyle

class SpatialColorsTest {
    private fun contrast(a: Color, b: Color): Double =
        (maxOf(a.luminance(), b.luminance()).toDouble() + .05) /
            (minOf(a.luminance(), b.luminance()).toDouble() + .05)

    @Test
    fun theActualCheckedThumbUsesItsPairedInkInBothModesAndEveryAccent() {
        for (dark in listOf(false, true)) for (accent in AccentStyle.entries) {
            val palette = spectrumPalette(dark, accent)
            val checked = spatialToggleColors(palette, checked = true, enabled = true)
            assertEquals(palette.colors.primary, checked.track)
            assertEquals(palette.colors.onPrimary, checked.thumb)
            assertTrue(contrast(checked.thumb, checked.track) >= 3.0)
            val unchecked = spatialToggleColors(palette, checked = false, enabled = true)
            assertTrue(contrast(unchecked.thumb, unchecked.track) >= 3.0)
            assertTrue(contrast(unchecked.outline, palette.card) >= 3.0)
        }
    }

    @Test
    fun monochromeArtworkHonorsAnyActualForegroundRatherThanAWhiteSentinel() {
        for (dark in listOf(false, true)) for (accent in AccentStyle.entries) {
            val palette = spectrumPalette(dark, accent)
            for (ink in listOf(palette.colors.onPrimary, palette.colors.onPrimaryContainer, palette.colors.onSurface)) {
                val actual = flatArtworkColors(palette, ink, SpatialColorMode.Monochrome, SpatialState.Idle)
                assertEquals(listOf(ink, ink, ink, ink), listOf(actual.teal, actual.violet, actual.amber, actual.rose))
                assertEquals(ink, actual.ink)
            }
            val artwork = flatArtworkColors(palette, palette.cyan, SpatialColorMode.Decorative, SpatialState.Idle)
            assertEquals(4, listOf(artwork.teal, artwork.violet, artwork.amber, artwork.rose).distinct().size)
        }
    }

    @Test
    fun disablingArtworkRemovesEverySaturatedSupportInk() {
        for (dark in listOf(false, true)) for (accent in AccentStyle.entries) for (mode in SpatialColorMode.entries) {
            val palette = spectrumPalette(dark, accent)
            val actual = flatArtworkColors(palette, palette.cyan, mode, SpatialState.Disabled)
            assertEquals(setOf(palette.semantic.disabledInk),
                setOf(actual.ink, actual.teal, actual.violet, actual.amber, actual.rose))
            val control = spatialToggleColors(palette, checked = true, enabled = false)
            assertEquals(palette.semantic.disabledContainer, control.track)
            assertTrue(contrast(control.thumb, control.track) >= 3.0)
        }
    }

    @Test
    fun neutralPressedCardsStillSupportSecondaryTextAndFocusHasAVisibleEdge() {
        for (dark in listOf(false, true)) for (accent in AccentStyle.entries) {
            val palette = spectrumPalette(dark, accent)
            val c = palette.colors
            for (fill in listOf(c.background, c.surface, c.surfaceVariant, c.surfaceBright, c.surfaceDim,
                c.surfaceContainerLowest, c.surfaceContainerLow, c.surfaceContainer, c.surfaceContainerHigh,
                c.surfaceContainerHighest)) {
                val pressed = spatialSurfaceColors(palette, fill, SpatialState.Pressed, true, false, false)
                assertTrue("Secondary text lost contrast under a real pressed state", contrast(c.onSurfaceVariant, pressed.fill) >= 4.5)
            }
            val focused = spatialSurfaceColors(palette, c.primary, SpatialState.Selected, true, false, false)
            assertEquals(c.onPrimary, focused.border)
            assertTrue(contrast(focused.border, focused.fill) >= 3.0)
            val disabled = spatialSurfaceColors(palette, c.primary, SpatialState.Disabled, true, false, false)
            assertEquals(palette.semantic.disabledInk, disabled.foreground)
            assertTrue(contrast(disabled.foreground, disabled.fill) >= 3.0)
        }
    }

    @Test
    fun historyColorIsResolvedForEveryObservationWithoutMovingNullOrNegativeSlots() {
        val observations = listOf(120.0, 160.0, 0.0, null, -20.0, 170.0)
        for (dark in listOf(false, true)) for (accent in AccentStyle.entries) {
            val palette = spectrumPalette(dark, accent)
            val actual = historyBarColors(palette, observations)
            assertEquals(observations.size, actual.size)
            assertEquals(listOf(palette.blue, palette.blue, palette.blue, palette.blue, palette.rose, palette.blue), actual)
        }
    }

    @Test
    fun semanticWarningsAndErrorsRemainDistinctWhileExplicitCallerInkWins() {
        for (dark in listOf(false, true)) {
            val palette = spectrumPalette(dark)
            assertEquals(palette.amber, spatialIconInk(palette, "warning", Color.Unspecified, SpatialState.Attention))
            assertEquals(palette.rose, spatialIconInk(palette, "error", Color.Unspecified, SpatialState.Attention))
            assertEquals(palette.emerald, spatialIconInk(palette, "check", Color.Unspecified, SpatialState.Success))
            assertEquals(palette.colors.onPrimary,
                spatialIconInk(palette, "warning", palette.colors.onPrimary, SpatialState.Attention))
        }
    }

    @Test
    fun actualBadgeAndMetricContainersResolveReadablePairedForeground() {
        for (dark in listOf(false, true)) for (accent in AccentStyle.entries) {
            val palette = spectrumPalette(dark, accent)
            for (color in listOf(palette.cyan, palette.blue, palette.violet, palette.rose, palette.emerald, palette.amber)) {
                val fill = palette.containerFor(color)
                val ink = palette.foregroundFor(fill)
                assertTrue("Actual component container lost its foreground pair", contrast(ink, fill) >= 4.5)
            }
        }
    }
}
