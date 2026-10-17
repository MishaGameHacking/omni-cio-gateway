package ru.omnicio.app.ui.spectrum

import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.OutlinedTextFieldDefaults
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Modifier
import androidx.compose.ui.focus.FocusRequester
import androidx.compose.ui.focus.focusRequester
import androidx.compose.ui.focus.onFocusChanged
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.TextRange
import androidx.compose.ui.text.input.TextFieldValue
import androidx.compose.ui.text.input.VisualTransformation
import ru.omnicio.app.ui.spatial.SpatialField

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
    var focused by remember { mutableStateOf(false) }
    var restoreFocus by rememberSaveable { mutableStateOf(false) }
    var selectionStart by rememberSaveable { mutableIntStateOf(value.length) }
    var selectionEnd by rememberSaveable { mutableIntStateOf(value.length) }
    var composition by remember { mutableStateOf<TextRange?>(null) }
    var receiveFocusEvents by remember { mutableStateOf(false) }
    val requester = remember { FocusRequester() }
    // Only focus and cursor offsets are saveable here. The caller owns the text:
    // password/token fields must never copy their value into a saved-state Bundle.
    val editor = TextFieldValue(value,
        selection = TextRange(selectionStart.coerceIn(0, value.length), selectionEnd.coerceIn(0, value.length)),
        composition = composition?.takeIf { it.min >= 0 && it.max <= value.length })
    LaunchedEffect(Unit) {
        if (restoreFocus && enabled) requester.requestFocus()
        receiveFocusEvents = true
    }
    SpatialField(modifier.semantics(mergeDescendants = true) {}, focused, isError, enabled) {
        OutlinedTextField(editor, { next ->
            selectionStart = next.selection.start; selectionEnd = next.selection.end; composition = next.composition
            if (next.text != value) onValueChange(next.text)
        }, Modifier.fillMaxWidth().focusRequester(requester).onFocusChanged {
            focused = it.isFocused
            if (receiveFocusEvents) restoreFocus = it.isFocused
        },
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
