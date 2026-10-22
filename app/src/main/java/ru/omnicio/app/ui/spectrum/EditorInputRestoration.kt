package ru.omnicio.app.ui.spectrum

/** Restore a saved editor in a newly created input owner, without changing its IME intent. */
internal suspend fun restoreEditorInput(
    showKeyboard: Boolean,
    readOnly: Boolean,
    requestFocus: () -> Boolean,
    awaitFocus: suspend () -> Unit,
    awaitFrame: suspend () -> Unit,
    setKeyboardVisible: (Boolean) -> Unit,
): Boolean {
    if (!requestFocus()) return false
    // The fresh Compose input session queues an implicit show during requestFocus.
    // Queue hide in the same batch, before any suspension can flush that show.
    if (!readOnly && !showKeyboard) setKeyboardVisible(false)
    awaitFocus()
    awaitFrame()
    if (!readOnly && showKeyboard) setKeyboardVisible(true)
    return true
}
