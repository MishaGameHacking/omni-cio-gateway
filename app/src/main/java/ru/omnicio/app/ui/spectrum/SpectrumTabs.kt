package ru.omnicio.app.ui.spectrum

import androidx.compose.foundation.background
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.selection.selectable
import androidx.compose.foundation.selection.selectableGroup
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.text.AnnotatedString
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.rememberTextMeasurer
import androidx.compose.ui.unit.dp

/** Brand-owned segmented navigation: single-line labels and 48dp+ targets. */
@Composable
fun SpectrumTabs(
    labels: List<String>,
    selected: Int,
    onSelect: (Int) -> Unit,
    modifier: Modifier = Modifier,
) {
    if (labels.isEmpty()) return
    val palette = LocalSpectrumPalette.current
    val density = LocalDensity.current
    val style = MaterialTheme.typography.labelLarge.copy(fontWeight = FontWeight.SemiBold)
    val measurer = rememberTextMeasurer()
    val measured = labels.map { measurer.measure(AnnotatedString(it), style, softWrap = false, maxLines = 1).size }
    val labelWidth = with(density) { measured.maxOf { it.width }.toDp() }
    val height = with(density) { measured.maxOf { it.height }.toDp() + 24.dp }.coerceAtLeast(52.dp)
    val gap = 6.dp
    val scroll = rememberScrollState()
    BoxWithConstraints(modifier.fillMaxWidth()) {
        val width = maxOf(((maxWidth - gap * (labels.size - 1)) / labels.size).coerceAtLeast(0.dp), labelWidth + 24.dp)
        val step = with(density) { (width + gap).roundToPx() }
        LaunchedEffect(selected, step, scroll.maxValue) {
            scroll.scrollTo((selected.coerceIn(labels.indices) * step).coerceIn(0, scroll.maxValue))
        }
        Row(
            Modifier.fillMaxWidth().height(height).horizontalScroll(scroll).selectableGroup(),
            horizontalArrangement = Arrangement.spacedBy(gap),
        ) {
            labels.forEachIndexed { index, label ->
                val chosen = index == selected
                Box(
                    modifier = Modifier
                        .width(width)
                        .height(height)
                        .clip(RoundedCornerShape(16.dp))
                        .background(
                            Brush.horizontalGradient(
                                if (chosen) listOf(palette.blue.copy(alpha = 0.30f), palette.violet.copy(alpha = 0.24f))
                                else listOf(palette.card.copy(alpha = 0.65f), palette.card.copy(alpha = 0.65f)),
                            ),
                        )
                        .selectable(chosen, role = Role.Tab, onClick = { onSelect(index) })
                        .padding(horizontal = 10.dp),
                    contentAlignment = Alignment.Center,
                ) {
                    Text(
                        label,
                        style = style,
                        maxLines = 1,
                        softWrap = false,
                        color = if (chosen) MaterialTheme.colorScheme.onSurface else MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
            }
        }
    }
}
