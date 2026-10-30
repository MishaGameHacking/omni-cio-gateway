package ru.omnicio.app.ui.terminal

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.graphics.drawscope.scale
import androidx.compose.ui.graphics.drawscope.translate
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

/** Shared geometry for the information terminal. No meshes, tiles or icon animation. */
internal val TerminalShape = RoundedCornerShape(4.dp)
internal val TerminalPurple = Color(0xFFA869FF)
internal val TerminalLime = Color(0xFFA9E34B)
internal val TerminalCyan = Color(0xFF56D3E5)
internal val TerminalAmber = Color(0xFFF2C66D)
internal val TerminalRed = Color(0xFFFF7387)
internal val TerminalSeries = listOf(TerminalPurple, TerminalCyan, TerminalLime, TerminalAmber, TerminalRed, Color(0xFF8B91AA))

@Composable
internal fun TerminalLabel(text: String, modifier: Modifier = Modifier, accent: Color = MaterialTheme.colorScheme.onSurfaceVariant) {
    Text(text, modifier, color = accent, fontFamily = FontFamily.Monospace,
        fontSize = 10.sp, lineHeight = 15.sp, letterSpacing = .7.sp)
}

@Composable
internal fun TerminalPanel(title: String, modifier: Modifier = Modifier, trailing: @Composable (() -> Unit)? = null,
    content: @Composable ColumnScope.() -> Unit) {
    Surface(modifier.fillMaxWidth(), shape = TerminalShape, color = MaterialTheme.colorScheme.surface,
        border = BorderStroke(1.dp, MaterialTheme.colorScheme.outlineVariant)) {
        Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            BoxWithConstraints(Modifier.fillMaxWidth()) {
                if (maxWidth < 300.dp * LocalDensity.current.fontScale && trailing != null) {
                    Column(Modifier.fillMaxWidth(), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                        TerminalPanelTitle(title)
                        trailing()
                    }
                } else Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                    TerminalPanelTitle(title, Modifier.weight(1f))
                    trailing?.invoke()
                }
            }
            content()
        }
    }
}

@Composable
private fun TerminalPanelTitle(title: String, modifier: Modifier = Modifier) {
    Text(title, modifier.semantics { heading() }, fontSize = 13.sp,
        lineHeight = 18.sp, letterSpacing = .5.sp, fontWeight = FontWeight.SemiBold)
}

@Composable
internal fun TerminalAction(text: String, onClick: () -> Unit, modifier: Modifier = Modifier,
    selected: Boolean = false, enabled: Boolean = true) {
    val ink = if (enabled) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.onSurfaceVariant
    Surface(modifier.heightIn(min = 48.dp).clickable(enabled = enabled, role = Role.Button, onClick = onClick),
        shape = TerminalShape, color = if (selected) MaterialTheme.colorScheme.primaryContainer else Color.Transparent) {
        Box(Modifier.padding(horizontal = 10.dp, vertical = 8.dp), contentAlignment = Alignment.Center) {
            Text(text, color = ink, style = MaterialTheme.typography.labelMedium)
        }
    }
}

@Composable
internal fun TerminalIconButton(asset: String, description: String, onClick: () -> Unit, modifier: Modifier = Modifier) {
    Box(modifier.size(48.dp).clickable(role = Role.Button, onClick = onClick)
        .semantics { contentDescription = description }, contentAlignment = Alignment.Center) {
        TerminalGlyph(asset, Modifier.size(21.dp), MaterialTheme.colorScheme.onSurfaceVariant)
    }
}

/** Purpose-built 24-unit line icons. Legacy asset names are mapped to this new vocabulary. */
@Composable
internal fun TerminalGlyph(asset: String, modifier: Modifier = Modifier, ink: Color = MaterialTheme.colorScheme.primary) {
    Canvas(modifier) {
        val unitScale = minOf(size.width, size.height) / 24f
        translate((size.width - 24f * unitScale) / 2f, (size.height - 24f * unitScale) / 2f) {
            scale(unitScale, unitScale, Offset.Zero) {
                fun line(x: Float, y: Float, xx: Float, yy: Float) = drawLine(ink, Offset(x,y), Offset(xx,yy), 1.5f, StrokeCap.Round)
                fun path(vararg xy: Float) {
                    val p = Path().apply { moveTo(xy[0],xy[1]); for(i in 2 until xy.size step 2) lineTo(xy[i],xy[i+1]) }
                    drawPath(p, ink, style = Stroke(1.5f, cap = StrokeCap.Round))
                }
                fun rect(x: Float, y: Float, w: Float, h: Float) = drawRect(ink, Offset(x,y), Size(w,h), style = Stroke(1.5f))
                when (asset) {
                    "close" -> { line(6f,6f,18f,18f); line(6f,18f,18f,6f) }
                    "back" -> path(15f,5f,8f,12f,15f,19f)
                    "forward", "arrow" -> path(9f,5f,16f,12f,9f,19f)
                    "chevron_down" -> path(5f,9f,12f,16f,19f,9f)
                    "chevron_up" -> path(5f,15f,12f,8f,19f,15f)
                    "plus" -> { line(5f,12f,19f,12f); line(12f,5f,12f,19f) }
                    "minus" -> line(5f,12f,19f,12f)
                    "search" -> { drawCircle(ink,6f,Offset(10f,10f),style=Stroke(1.5f)); line(15f,15f,21f,21f) }
                    "check" -> path(4f,12f,9f,17f,20f,6f)
                    "risk", "warning", "error" -> { path(12f,3f,22f,21f,2f,21f,12f,3f); line(12f,9f,12f,14f); drawCircle(ink,1f,Offset(12f,17f)) }
                    "home" -> { path(3f,10f,12f,3f,21f,10f); path(5f,10f,5f,21f,19f,21f,19f,10f); rect(10f,14f,4f,7f) }
                    "notifications", "events" -> { path(5f,17f,7f,14f,7f,8f,9f,5f,15f,5f,17f,8f,17f,14f,19f,17f,5f,17f); line(10f,21f,14f,21f) }
                    "messages" -> { path(3f,4f,21f,4f,21f,17f,9f,17f,4f,21f,4f,17f,3f,17f,3f,4f); line(7f,8f,17f,8f); line(7f,12f,14f,12f) }
                    "settings", "rules", "appearance", "strategy", "balanced" -> { for(y in listOf(6f,12f,18f)) line(3f,y,21f,y); rect(7f,4f,3f,4f); rect(15f,10f,3f,4f); rect(9f,16f,3f,4f) }
                    "profile", "avatar", "monogram" -> { drawCircle(ink,4f,Offset(12f,7f),style=Stroke(1.5f)); path(4f,21f,5f,17f,8f,14f,16f,14f,19f,17f,20f,21f) }
                    "allocation", "orbit", "goal" -> { drawArc(ink,0f,270f,false,Offset(3f,3f),Size(18f,18f),style=Stroke(1.5f)); path(12f,2f,12f,12f,22f,12f); path(16f,2f,16f,8f,22f,8f) }
                    "sources", "reports", "education", "bookmark", "devices" -> { rect(5f,3f,14f,18f); line(8f,7f,16f,7f); line(8f,11f,16f,11f); line(8f,15f,13f,15f) }
                    "calendar", "recent", "timeline" -> { rect(3f,5f,18f,16f); line(3f,10f,21f,10f); line(7f,2f,7f,7f); line(17f,2f,17f,7f); line(7f,14f,10f,14f); line(14f,14f,17f,14f) }
                    "update" -> { drawArc(ink,35f,280f,false,Offset(4f,4f),Size(16f,16f),style=Stroke(1.5f)); path(17f,2f,20f,6f,16f,7f) }
                    "brain", "analyst", "ideas", "new_features" -> { rect(6f,6f,12f,12f); rect(10f,10f,4f,4f); for(v in listOf(9f,15f)) { line(v,2f,v,6f); line(v,18f,v,22f); line(2f,v,6f,v); line(18f,v,22f,v) } }
                    "pulse", "growth", "market", "income", "dividends" -> { path(2f,15f,6f,15f,9f,7f,13f,18f,17f,10f,22f,10f) }
                    else -> { rect(3f,15f,4f,6f); rect(10f,9f,4f,12f); rect(17f,3f,4f,18f) }
                }
            }
        }
    }
}
