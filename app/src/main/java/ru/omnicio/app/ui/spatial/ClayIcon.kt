package ru.omnicio.app.ui.spatial

import androidx.compose.ui.geometry.CornerRadius
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.drawscope.DrawScope
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.graphics.drawscope.withTransform
import androidx.compose.ui.graphics.lerp

/** First-party, resolution-independent clay tiles. No bitmap downloads or continuous 3D engine. */
internal fun DrawScope.clayIcon(name: String, phase: Float, state: SpatialState) {
    val hue = when (name) {
        "portfolio", "income", "currency" -> Color(0xFFF5BC54)
        "capital", "risk", "home", "devices" -> Color(0xFF75B2F1)
        "messages", "sources", "dividends", "market" -> Color(0xFF67C6BB)
        "notifications", "events" -> Color(0xFFF294AB)
        else -> Color(0xFFB194E7)
    }
    drawRoundRect(hue.copy(alpha = .12f), Offset(5f, 10f), Size(90f, 88f), CornerRadius(25f))
    drawRoundRect(hue.copy(alpha = .20f), Offset(7f, 8f), Size(86f, 88f), CornerRadius(24f))
    drawRoundRect(Brush.linearGradient(listOf(lerp(hue, Color.White, .57f), hue),
        Offset(12f, 6f), Offset(86f, 94f)), Offset(5f, 3f), Size(90f, 90f), CornerRadius(24f))
    drawRoundRect(Brush.linearGradient(listOf(Color.White.copy(alpha = .85f), Color.White.copy(alpha = .08f))),
        Offset(6.5f, 4.5f), Size(87f, 87f), CornerRadius(23f), style = Stroke(1.5f))
    val shadow = Color(0xFF283757).copy(alpha = .18f)
    val raised = FlatArtworkColors(Color(0xFF334785), Color(0xFF248C9D), Color(0xFF7854BE),
        Color(0xFFF6BD51), Color(0xFFED6E8C), Color.White)
    withTransform({ scale(.77f, .77f, Offset(50f, 48f)); translate(0f, 5f) }) {
        flatIcon(name, FlatArtworkColors(shadow, shadow, shadow, shadow, shadow), 0f, state, Color.Unspecified)
    }
    withTransform({ scale(.77f, .77f, Offset(50f, 48f)) }) {
        flatIcon(name, raised, phase, state, Color.Unspecified)
    }
}
