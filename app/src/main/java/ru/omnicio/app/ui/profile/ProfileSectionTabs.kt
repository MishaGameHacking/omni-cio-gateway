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
import androidx.compose.ui.semantics.clearAndSetSemantics
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.onClick
import androidx.compose.ui.semantics.role
import androidx.compose.ui.semantics.selected
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.semantics.testTagsAsResourceId
import androidx.compose.ui.text.AnnotatedString
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.rememberTextMeasurer
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import ru.omnicio.app.ui.spectrum.LocalSpectrumPalette

/** Full-size accessible cells; larger fonts scroll horizontally without clipping the active label. */
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
    val measuredWidths = measured.map { with(density) { it.width.toDp() } }
    val tabHeight = with(density) { measured.maxOf { it.height }.toDp() + 20.dp }.coerceAtLeast(52.dp)
    val gap = 6.dp
    val scroll = rememberScrollState()

    BoxWithConstraints(Modifier.fillMaxWidth()) {
        val equalWidth = ((maxWidth - gap * (labels.size - 1)) / labels.size).coerceAtLeast(0.dp)
        val widths = measuredWidths.map { maxOf(equalWidth, it + 20.dp) }
        val safeSelected = selected.coerceIn(labels.indices)

        LaunchedEffect(safeSelected, widths, maxWidth, scroll.maxValue) {
            val selectedStart = widths.take(safeSelected).sumDp() + gap * safeSelected
            val selectedCenterPx = with(density) {
                (selectedStart + widths[safeSelected] / 2).roundToPx()
            }
            val viewportPx = with(density) { maxWidth.roundToPx() }
            val target = selectedCenterPx - viewportPx / 2
            scroll.scrollTo(target.coerceIn(0, scroll.maxValue))
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
                val chosen = safeSelected == index
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
                        .width(widths[index])
                        .height(tabHeight)
                        .clip(RoundedCornerShape(18.dp))
                        .background(brush)
                        .selectable(chosen, role = Role.Tab, onClick = { onSelect(index) })
                        .testTag("profile-tab-$index")
                        .clearAndSetSemantics {
                            contentDescription = label
                            role = Role.Tab
                            this.selected = chosen
                            onClick(label = "Открыть $label") {
                                onSelect(index)
                                true
                            }
                        },
                    contentAlignment = Alignment.Center,
                ) {
                    Text(
                        label,
                        modifier = Modifier.padding(horizontal = 8.dp, vertical = 10.dp),
                        maxLines = 1,
                        softWrap = false,
                        style = style,
                        color = if (chosen) {
                            MaterialTheme.colorScheme.onSurface
                        } else {
                            MaterialTheme.colorScheme.onSurfaceVariant
                        },
                    )
                }
            }
        }
    }
}

private fun List<Dp>.sumDp(): Dp = fold(0.dp) { total, item -> total + item }
