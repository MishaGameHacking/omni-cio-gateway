package ru.omnicio.app.ui.profile

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
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.semantics.testTagsAsResourceId
import androidx.compose.ui.text.AnnotatedString
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.rememberTextMeasurer
import androidx.compose.ui.unit.dp
import ru.omnicio.app.ui.spectrum.LocalSpectrumPalette

/** One measured row at every font size; overflow scrolls instead of wrapping. */
@Composable
internal fun ProfileSectionTabs(selected: Int, onSelect: (Int) -> Unit) {
    val labels = listOf("Настройки", "Аккаунт", "О приложении")
    val density = LocalDensity.current
    val measurer = rememberTextMeasurer()
    val style = MaterialTheme.typography.labelLarge.copy(fontWeight = FontWeight.Bold)
    val palette = LocalSpectrumPalette.current
    val measured = labels.map { label ->
        measurer.measure(AnnotatedString(label), style, softWrap = false, maxLines = 1).size
    }
    val labelWidth = with(density) { measured.maxOf { it.width }.toDp() }
    val tabHeight = with(density) { measured.maxOf { it.height }.toDp() + 20.dp }.coerceAtLeast(52.dp)
    val gap = 6.dp
    val scroll = rememberScrollState()
    BoxWithConstraints(Modifier.fillMaxWidth()) {
        val equalWidth = ((maxWidth - gap * (labels.size - 1)) / labels.size).coerceAtLeast(0.dp)
        val width = maxOf(equalWidth, labelWidth + 24.dp)
        val stepPixels = with(density) { (width + gap).roundToPx() }
        LaunchedEffect(selected, stepPixels, scroll.maxValue) {
            scroll.scrollTo((selected * stepPixels).coerceIn(0, scroll.maxValue))
        }
        Row(
            Modifier
                .fillMaxWidth()
                .height(tabHeight)
                .horizontalScroll(scroll)
                .selectableGroup()
                .semantics { testTagsAsResourceId = true }
                .testTag("profile-tabs"),
            horizontalArrangement = Arrangement.spacedBy(gap),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            labels.forEachIndexed { index, label ->
                val chosen = selected == index
                val brush = if (chosen) {
                    Brush.linearGradient(
                        listOf(
                            palette.cyan.copy(alpha = 0.16f),
                            palette.violet.copy(alpha = 0.22f),
                            palette.rose.copy(alpha = 0.08f),
                        ),
                    )
                } else {
                    Brush.linearGradient(listOf(Color.Transparent, Color.Transparent))
                }
                Box(
                    modifier = Modifier
                        .width(width)
                        .height(tabHeight)
                        .clip(RoundedCornerShape(18.dp))
                        .background(brush)
                        .selectable(chosen, role = Role.Tab, onClick = { onSelect(index) })
                        .testTag("profile-tab-$index")
                        .padding(horizontal = 8.dp, vertical = 10.dp),
                    contentAlignment = Alignment.Center,
                ) {
                    Text(
                        label,
                        modifier = Modifier.testTag("profile-tab-label-$index"),
                        maxLines = 1,
                        softWrap = false,
                        style = style,
                        color = if (chosen) MaterialTheme.colorScheme.onSurface else MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
            }
        }
    }
}
