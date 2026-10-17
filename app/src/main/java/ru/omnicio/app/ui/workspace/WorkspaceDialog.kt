package ru.omnicio.app.ui.workspace

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.compose.ui.window.Dialog
import ru.omnicio.app.ui.spatial.SpatialWindow
import ru.omnicio.app.ui.spectrum.SpectrumCard

/** Dialog content gets an actual surface in its own Window while sharing the Engine. */
@Composable
fun WorkspaceDialog(title: String, onDismiss: () -> Unit, content: @Composable ColumnScope.() -> Unit) {
    Dialog(onDismissRequest = onDismiss) {
        SpatialWindow(Modifier.widthIn(max = 600.dp).fillMaxWidth().heightIn(max = 680.dp)) {
            SpectrumCard(Modifier.verticalScroll(rememberScrollState()), emphasized = true) {
                Text(title, style = MaterialTheme.typography.titleLarge)
                content()
            }
        }
    }
}
