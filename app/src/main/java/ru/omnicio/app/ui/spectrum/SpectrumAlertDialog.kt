package ru.omnicio.app.ui.spectrum

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.LocalContentColor
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.ProvideTextStyle
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.semantics.testTagsAsResourceId
import androidx.compose.ui.unit.dp
import androidx.compose.ui.window.Dialog
import androidx.compose.ui.window.DialogProperties
import ru.omnicio.app.ui.spatial.SpatialSurface
import ru.omnicio.app.ui.spatial.SpatialWindow

/** Native modal input/back handling, with a real scene in this Dialog's window. */
@Composable
fun SpectrumAlertDialog(
    onDismissRequest: () -> Unit,
    confirmButton: @Composable () -> Unit,
    modifier: Modifier = Modifier,
    dismissButton: (@Composable () -> Unit)? = null,
    icon: (@Composable () -> Unit)? = null,
    title: (@Composable () -> Unit)? = null,
    text: (@Composable () -> Unit)? = null,
    containerColor: Color = LocalSpectrumPalette.current.card,
    properties: DialogProperties = DialogProperties(),
) {
    SpectrumModal(onDismissRequest = onDismissRequest, properties = properties) {
        SpatialWindow(modifier.widthIn(max = 600.dp).fillMaxWidth().heightIn(max = 680.dp)) {
            SpatialSurface(Modifier.fillMaxWidth(), color = containerColor, emphasized = true) {
                CompositionLocalProvider(LocalContentColor provides MaterialTheme.colorScheme.onSurface) {
                    Column(Modifier.fillMaxWidth().verticalScroll(rememberScrollState())
                        .semantics { testTagsAsResourceId = true }.testTag("workspace-content").padding(20.dp),
                        verticalArrangement = Arrangement.spacedBy(12.dp)) {
                        icon?.invoke()
                        if (title != null) ProvideTextStyle(MaterialTheme.typography.headlineSmall, title)
                        if (text != null) ProvideTextStyle(MaterialTheme.typography.bodyLarge, text)
                        confirmButton()
                        dismissButton?.invoke()
                    }
                }
            }
        }
    }
}

/** Keep the native date-input semantics inside the same modal scene as its actions. */
@Composable
fun SpectrumDatePickerDialog(
    onDismissRequest: () -> Unit,
    confirmButton: @Composable () -> Unit,
    dismissButton: (@Composable () -> Unit)? = null,
    content: @Composable () -> Unit,
) {
    SpectrumAlertDialog(onDismissRequest, confirmButton, Modifier.padding(12.dp), dismissButton = dismissButton,
        text = content, properties = DialogProperties(usePlatformDefaultWidth = false))
}
