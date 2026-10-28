package ru.omnicio.app.ui.spectrum

import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import ru.omnicio.app.ui.spatial.*

/** Stable, first-party mesh identities. Financial meaning comes from adjacent text. */
enum class SpectrumSymbol(val asset: String) {
    Home("home"), Portfolio("portfolio"), Ideas("ideas"), Pulse("pulse"),
    Messages("messages"), Education("education"), Profile("profile"), Risk("risk"),
    Allocation("allocation"), Update("update"), Sources("sources"), Analyst("analyst"),
    Notifications("notifications"), Market("market"), Goal("goal"),
    Back("back"), Forward("forward"), Search("search"), Check("check"), Close("close"), Calendar("calendar"),
    Settings("settings"), Bookmark("bookmark"),
    Expand("plus"), Collapse("minus"), Currency("currency"),
    Brain("brain"), Decisions("decisions"), Strategy("strategy"), Reports("reports"),
    Timeline("timeline"), Events("events"), Rules("rules"), Appearance("appearance"),
    Devices("devices"), Recent("recent"), NewFeatures("new_features"),
}

/** Decorative mesh. The containing native control owns its text label and target. */
@Composable
fun SpectrumIcon(
    symbol: SpectrumSymbol,
    modifier: Modifier = Modifier,
    selected: Boolean = false,
    tile: Boolean = true,
    motionAllowed: Boolean = true,
) {
    val palette = LocalSpectrumPalette.current
    val state = if (selected) SpatialState.Selected else SpatialState.Idle
    val accent = when (symbol) {
        SpectrumSymbol.Risk -> palette.amber
        SpectrumSymbol.Notifications, SpectrumSymbol.Messages -> palette.violet
        SpectrumSymbol.Profile, SpectrumSymbol.Analyst -> palette.cyan
        else -> if (selected) palette.cyan else palette.blue
    }
    if (tile) SpatialSurface(modifier, SpatialSurfaceKind.Chip,
        color = palette.containerFor(accent), state = state) {
        SpatialIcon(symbol.asset, Modifier.fillMaxSize().padding(6.dp), tint = accent,
            state = state, motionAllowed = motionAllowed, colorMode = SpatialColorMode.Decorative)
    } else Box(modifier) {
        SpatialIcon(symbol.asset, Modifier.fillMaxSize(), tint = accent,
            state = state, motionAllowed = motionAllowed, colorMode = SpatialColorMode.Decorative)
    }
}

