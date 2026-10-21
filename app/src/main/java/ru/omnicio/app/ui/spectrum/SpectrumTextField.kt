package ru.omnicio.app.ui.spectrum

import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.isImeVisible
import androidx.compose.foundation.relocation.BringIntoViewRequester
import androidx.compose.foundation.relocation.bringIntoViewRequester
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.OutlinedTextFieldDefaults
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Modifier
import androidx.compose.ui.focus.FocusRequester
import androidx.compose.ui.focus.FocusState
import androidx.compose.ui.focus.focusRequester
import androidx.compose.ui.focus.onFocusChanged
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalSoftwareKeyboardController
import androidx.compose.ui.platform.LocalWindowInfo
import androidx.compose.ui.platform.SoftwareKeyboardController
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.TextRange
import androidx.compose.ui.text.input.TextFieldValue
import androidx.compose.ui.text.input.VisualTransformation
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.compose.LocalLifecycleOwner
import kotlinx.coroutines.flow.first
import ru.omnicio.app.ui.spatial.SpatialField

/** Changes when the Activity composition is recreated, not when a lazy item returns. */
internal val LocalEditorRestorationOwner = staticCompositionLocalOf { "" }

/** The editor remains a native accessible text field; focus/error surfaces are actual meshes. */
@Composable
fun SpectrumTextField(
    value: String,
    onValueChange: (String) -> Unit,
    modifier: Modifier = Modifier,
    enabled: Boolean = true,
    readOnly: Boolean = false,
    label: (@Composable () -> Unit)? = null,
    placeholder: (@Composable () -> Unit)? = null,
    trailingIcon: (@Composable () -> Unit)? = null,
    supportingText: (@Composable () -> Unit)? = null,
    isError: Boolean = false,
    visualTransformation: VisualTransformation = VisualTransformation.None,
    keyboardOptions: KeyboardOptions = KeyboardOptions.Default,
    keyboardActions: KeyboardActions = KeyboardActions.Default,
    singleLine: Boolean = false,
    maxLines: Int = if (singleLine) 1 else Int.MAX_VALUE,
    minLines: Int = 1,
) {
    val focused = remember { mutableStateOf(false) }
    var selectionStart by rememberSaveable { mutableIntStateOf(value.length) }
    var selectionEnd by rememberSaveable { mutableIntStateOf(value.length) }
    var composition by remember { mutableStateOf<TextRange?>(null) }
    val requester = remember { FocusRequester() }
    val viewport = remember { BringIntoViewRequester() }
    val focusChanged = rememberEditorFocus(focused, requester, viewport, enabled, readOnly)
    // Only focus and cursor offsets are saveable here. The caller owns the text:
    // password/token fields must never copy their value into a saved-state Bundle.
    val editor = TextFieldValue(value,
        selection = TextRange(selectionStart.coerceIn(0, value.length), selectionEnd.coerceIn(0, value.length)),
        composition = composition?.takeIf { it.min >= 0 && it.max <= value.length })
    SpatialField(modifier.semantics(mergeDescendants = true) {}, focused.value, isError, enabled) {
        OutlinedTextField(editor, { next ->
            selectionStart = next.selection.start; selectionEnd = next.selection.end; composition = next.composition
            if (next.text != value) onValueChange(next.text)
        }, Modifier.fillMaxWidth().bringIntoViewRequester(viewport).focusRequester(requester).onFocusChanged(focusChanged),
            enabled = enabled, readOnly = readOnly, label = label, placeholder = placeholder,
            trailingIcon = trailingIcon, supportingText = supportingText, isError = isError,
            visualTransformation = visualTransformation, keyboardOptions = keyboardOptions, keyboardActions = keyboardActions,
            singleLine = singleLine, maxLines = maxLines, minLines = minLines,
            colors = OutlinedTextFieldDefaults.colors(
                focusedContainerColor = Color.Transparent, unfocusedContainerColor = Color.Transparent,
                disabledContainerColor = Color.Transparent, errorContainerColor = Color.Transparent,
                focusedBorderColor = Color.Transparent, unfocusedBorderColor = Color.Transparent,
                disabledBorderColor = Color.Transparent, errorBorderColor = Color.Transparent,
            ))
    }
}

@OptIn(ExperimentalLayoutApi::class)
@Composable
private fun rememberEditorFocus(
    focused: MutableState<Boolean>, requester: FocusRequester, viewport: BringIntoViewRequester,
    enabled: Boolean, readOnly: Boolean,
): (FocusState) -> Unit {
    val owner = LocalEditorRestorationOwner.current
    var previousOwner by rememberSaveable { mutableStateOf(owner) }
    var restoreFocus by rememberSaveable { mutableStateOf(false) }
    var restoreKeyboard by rememberSaveable { mutableStateOf(false) }
    var receiveFocusEvents by remember { mutableStateOf(false) }
    val keyboard = LocalSoftwareKeyboardController.current
    val window = LocalWindowInfo.current
    val lifecycle = LocalLifecycleOwner.current.lifecycle
    val imeVisible = WindowInsets.isImeVisible
    LaunchedEffect(Unit) {
        val recreated = previousOwner != owner
        previousOwner = owner
        if (recreated && restoreFocus && enabled) {
            // A Dialog can compose before its new Window is ready for input.
            lifecycle.currentStateFlow.first { it.isAtLeast(Lifecycle.State.RESUMED) }
            snapshotFlow { window.isWindowFocused }.first { it }
            withFrameNanos { }
            viewport.bringIntoView()
            requester.requestFocus()
            snapshotFlow { focused.value }.first { it }
            withFrameNanos { }
            if (!readOnly) restoreKeyboardVisibility(keyboard, restoreKeyboard)
        } else if (!recreated) {
            // Scrolling a lazy item back into view must not steal focus or open IME.
            restoreFocus = focused.value
        }
        receiveFocusEvents = true
    }
    LaunchedEffect(imeVisible, focused.value, receiveFocusEvents, window.isWindowFocused) {
        if (receiveFocusEvents && focused.value && window.isWindowFocused &&
            lifecycle.currentState.isAtLeast(Lifecycle.State.RESUMED)) {
            restoreKeyboard = imeVisible
        }
    }
    return {
        focused.value = it.isFocused
        // Window teardown must not overwrite the editor saved for recreation.
        if (receiveFocusEvents && window.isWindowFocused && lifecycle.currentState.isAtLeast(Lifecycle.State.RESUMED)) {
            restoreFocus = it.isFocused
        }
    }
}

private fun restoreKeyboardVisibility(keyboard: SoftwareKeyboardController?, visible: Boolean) {
    if (visible) keyboard?.show() else keyboard?.hide()
}
