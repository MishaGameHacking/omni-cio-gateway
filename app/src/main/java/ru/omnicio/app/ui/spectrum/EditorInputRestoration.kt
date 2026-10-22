package ru.omnicio.app.ui.spectrum

/** Restore a saved editor in a newly created input owner, without changing its IME intent. */
internal suspend fun restoreEditorInput(
    showKeyboard: Boolean,
    readOnly: Boolean,
    requestFocus: () -> Boolean,
    awaitFocus: suspend () -> Unit,
    awaitWindowReady: suspend () -> Unit,
    awaitFrame: suspend () -> Unit,
    setKeyboardVisible: (Boolean) -> Unit,
): Boolean {
    val restoreVisibleKeyboard = showKeyboard && !readOnly
    // Prepare the visible editor before waiting for the recreated window.
    // Hidden and read-only editors retain the existing window-first order.
    if (!restoreVisibleKeyboard) awaitWindowReady()
    if (!requestFocus()) return false
    // The fresh Compose input session queues an implicit show during requestFocus.
    // Queue hide in the same batch, before any suspension can flush that show.
    if (!readOnly && !showKeyboard) setKeyboardVisible(false)
    awaitFocus()
    if (restoreVisibleKeyboard) awaitWindowReady()
    awaitFrame()
    if (restoreVisibleKeyboard) setKeyboardVisible(true)
    return true
}
