package ru.omnicio.app.ui.spectrum

import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.OutlinedTextFieldDefaults
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.focus.onFocusChanged
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.semantics.semantics
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
    SpatialField(modifier.semantics(mergeDescendants = true) {}, focused, isError, enabled) {
        OutlinedTextField(value, onValueChange, Modifier.fillMaxWidth().onFocusChanged { focused = it.isFocused },
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
