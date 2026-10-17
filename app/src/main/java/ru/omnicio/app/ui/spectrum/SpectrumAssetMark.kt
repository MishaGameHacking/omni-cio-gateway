package ru.omnicio.app.ui.spectrum

import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Rect
import androidx.compose.ui.unit.dp
import ru.omnicio.app.ui.spatial.*

/** The known asset class and a first-party letter, never an invented company logo. */
@Composable
fun SpectrumAssetMark(assetClass: String, name: String, modifier: Modifier = Modifier) {
    val palette = LocalSpectrumPalette.current
    val model = when (assetClass.lowercase()) {
        "share", "stock", "equity", "акции" -> "stock"
        "bond", "облигации" -> "bond"
        "etf", "fund", "фонд", "фонды" -> "fund"
        "currency", "валюта" -> "currency"
        else -> "monogram"
    }
    val letter = name.firstOrNull(Char::isLetterOrDigit)?.uppercaseChar()?.takeIf(SpatialGlyphs::supported)
    val shared = LocalSpatialObjectKey.current
    val depth = LocalSpatialDepth.current
    Box(modifier) {
        val primitives = mutableListOf(SpatialPrimitive(SpatialAsset.Catalogue(model),
            color = palette.blue, thickness = 32f, depth = depth + 10f,
            sharedKey = shared?.let { "$it/class" }))
        if (letter != null) primitives += SpatialPrimitive(SpatialAsset.Glyph(letter),
            rect = Rect(.53f,.49f,.99f,.99f), color = palette.cyan, depth = depth + 19f,
            thickness = 22f, sharedKey = shared?.let { "$it/letter" })
        SpatialCanvas(primitives, Modifier.fillMaxSize().padding(2.dp))
    }
}
