package ru.omnicio.app.ui.workspace

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.semantics.testTagsAsResourceId
import androidx.compose.ui.unit.dp
import androidx.compose.ui.window.Dialog
import androidx.compose.ui.window.DialogProperties
import ru.omnicio.app.ui.spatial.SpatialWindow
import ru.omnicio.app.ui.spectrum.SpectrumCard
import ru.omnicio.app.ui.spectrum.DialogImeHostFocus
import ru.omnicio.app.ui.spectrum.LocalDialogImeHostHandoff
import ru.omnicio.app.ui.spectrum.rememberDialogImeHostHandoff

/** Dialog content gets an actual surface in its own Window while sharing the Engine. */
@Composable
fun WorkspaceDialog(title: String, onDismiss: () -> Unit, content: @Composable ColumnScope.() -> Unit) {
    val imeHost = rememberDialogImeHostHandoff()
    CompositionLocalProvider(LocalDialogImeHostHandoff provides imeHost) {
        Dialog(onDismissRequest = onDismiss, properties = DialogProperties(decorFitsSystemWindows = false)) {
            DialogImeHostFocus(imeHost)
            // Keep the scroll viewport above system bars and the keyboard, including
            // while the IME animates. safeDrawing consumes the insets once here.
            Box(Modifier.safeDrawingPadding()) {
                SpatialWindow(Modifier.widthIn(max = 600.dp).fillMaxWidth().heightIn(max = 680.dp)) {
                    SpectrumCard(Modifier.verticalScroll(rememberScrollState()).semantics { testTagsAsResourceId = true }.testTag("workspace-content"), emphasized = true) {
                        Text(title, style = MaterialTheme.typography.titleLarge)
                        content()
                    }
                }
            }
        }
    }
}
