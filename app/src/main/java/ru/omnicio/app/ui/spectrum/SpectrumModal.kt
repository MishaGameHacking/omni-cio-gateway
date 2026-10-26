package ru.omnicio.app.ui.spectrum

import androidx.compose.animation.core.Animatable
import androidx.compose.animation.core.tween
import androidx.compose.foundation.layout.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.unit.dp
import androidx.compose.ui.window.Dialog
import androidx.compose.ui.window.DialogProperties
import kotlinx.coroutines.launch
import ru.omnicio.app.ui.spatial.LocalFlatMotion
import ru.omnicio.app.ui.spatial.SpatialMotion

/** Outside/Back delegates to the caller, so an editor can retain its draft. */
@Composable
internal fun SpectrumModal(onDismissRequest: () -> Unit,
    properties: DialogProperties = DialogProperties(), content: @Composable () -> Unit) {
    val imeHost = rememberDialogImeHostHandoff()
    val animated = LocalFlatMotion.current != SpatialMotion.Off
    val progress = remember { Animatable(if (animated) 0f else 1f) }
    val scope = rememberCoroutineScope()
    val dismiss by rememberUpdatedState(onDismissRequest)
    var closing by remember { mutableStateOf(false) }
    val requestDismiss: () -> Unit = {
        if (!closing) {
            closing = true
            scope.launch {
                progress.animateTo(0f, tween(if (animated) 130 else 0))
                dismiss()
                // A guarded dismissal may deliberately leave this dialog mounted.
                closing = false
                progress.animateTo(1f, tween(if (animated) 130 else 0))
            }
        }
    }
    LaunchedEffect(animated) { progress.animateTo(1f, tween(if (animated) 200 else 0)) }
    CompositionLocalProvider(LocalDialogImeHostHandoff provides imeHost) {
      Dialog(onDismissRequest = requestDismiss, properties = properties) {
        DialogImeHostFocus(imeHost)
        BoxWithConstraints(Modifier.safeDrawingPadding().padding(vertical = 12.dp)) {
            Box(Modifier.widthIn(max = 600.dp).fillMaxWidth().heightIn(max = maxHeight * .82f)
                .graphicsLayer {
                    alpha = progress.value
                    scaleX = .96f + progress.value * .04f; scaleY = scaleX
                    translationY = (1f - progress.value) * 16.dp.toPx()
                }) { content() }
        }
      }
    }
}
