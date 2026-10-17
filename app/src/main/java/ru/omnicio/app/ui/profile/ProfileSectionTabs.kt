package ru.omnicio.app.ui.profile

import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.selection.selectable
import androidx.compose.foundation.selection.selectableGroup
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.interaction.collectIsFocusedAsState
import androidx.compose.foundation.interaction.collectIsPressedAsState
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.remember
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
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
import ru.omnicio.app.ui.spatial.*

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
        val naturalWidths = measuredWidths.map { it + 20.dp }
        val availableForCells = (maxWidth - gap * (labels.size - 1)).coerceAtLeast(0.dp)
        val spare = (availableForCells - naturalWidths.sumDp()).coerceAtLeast(0.dp)
        val distributed = spare / labels.size
        val widths = naturalWidths.map { it + distributed }
        val safeSelected = selected.coerceIn(labels.indices)

        LaunchedEffect(safeSelected, widths, maxWidth, scroll.maxValue) {
            if (scroll.maxValue == 0) {
                scroll.scrollTo(0)
            } else {
                val selectedStart = widths.take(safeSelected).sumDp() + gap * safeSelected
                val selectedCenterPx = with(density) {
                    (selectedStart + widths[safeSelected] / 2).roundToPx()
                }
                val viewportPx = with(density) { maxWidth.roundToPx() }
                val target = selectedCenterPx - viewportPx / 2
                scroll.scrollTo(target.coerceIn(0, scroll.maxValue))
            }
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
                val interaction = remember { MutableInteractionSource() }
                val focused by interaction.collectIsFocusedAsState()
                val pressed by interaction.collectIsPressedAsState()
                val select = rememberSpatialHapticClick { onSelect(index) }
                SpatialSurface(
                    modifier = Modifier
                        .width(widths[index])
                        .height(tabHeight)
                        .selectable(chosen, interactionSource = interaction, indication = null, role = Role.Tab, onClick = select)
                        .testTag("profile-tab-$index")
                        .clearAndSetSemantics {
                            contentDescription = label
                            role = Role.Tab
                            this.selected = chosen
                            onClick(label = "Открыть $label") {
                                select()
                                true
                            }
                        },
                    kind = SpatialSurfaceKind.Chip,
                    color = if (chosen || focused) palette.cardStrong else palette.card,
                    state = when { pressed -> SpatialState.Pressed; chosen || focused -> SpatialState.Selected; else -> SpatialState.Idle },
                    emphasized = chosen,
                ) {
                    Text(
                        label,
                        modifier = Modifier.align(Alignment.Center).padding(horizontal = 8.dp, vertical = 10.dp),
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
