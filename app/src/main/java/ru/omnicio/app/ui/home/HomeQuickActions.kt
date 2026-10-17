package ru.omnicio.app.ui.home

import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.unit.dp
import ru.omnicio.app.ui.spectrum.*

/** Only working, everyday destinations occupy the capital screen. */
@Composable
internal fun HomeQuickActions(onAssets: () -> Unit, onPayments: () -> Unit) {
    val largeFont = LocalDensity.current.fontScale >= 1.4f
    BoxWithConstraints(Modifier.fillMaxWidth()) {
        if (homeActionColumns(maxWidth.value, largeFont) == 1) {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                SpectrumSecondaryButton("Мои активы", onAssets, Modifier.fillMaxWidth())
                SpectrumSecondaryButton("Ближайшие выплаты", onPayments, Modifier.fillMaxWidth())
            }
        } else Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            SpectrumSecondaryButton("Мои активы", onAssets, Modifier.weight(1f))
            SpectrumSecondaryButton("Выплаты", onPayments, Modifier.weight(1f))
        }
    }
}
internal fun homeActionColumns(widthDp: Float, largeFont: Boolean): Int = if (largeFont || widthDp < 260f) 1 else 2
