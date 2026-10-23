package ru.omnicio.app.ui.spectrum

/** Platform input commands belong to the same prepared editor handoff and cleanup. */
internal data class EditorInputCommands(
    val setKeyboardVisible: (Boolean) -> Unit,
    val prepareInput: () -> Boolean = { true },
    val releaseInput: () -> Unit = {},
)

/** Compose insets can lag the current window; save its native IME visibility when available. */
internal fun editorImeVisibilityForRestore(composeVisible: Boolean, nativeVisible: Boolean?): Boolean =
    nativeVisible ?: composeVisible

/** Restore a saved editor in a newly created input owner, without changing its IME intent. */
internal suspend fun restoreEditorInput(
    showKeyboard: Boolean,
    readOnly: Boolean,
    requestFocus: () -> Boolean,
    awaitFocus: suspend () -> Unit,
    awaitWindowReady: suspend () -> Unit,
    awaitFrame: suspend () -> Unit,
    input: EditorInputCommands,
): Boolean {
    val restoreVisibleKeyboard = showKeyboard && !readOnly
    try {
        // Prepare the visible editor before waiting for the recreated window.
        // Hidden and read-only editors retain the existing window-first order.
        if (!restoreVisibleKeyboard) awaitWindowReady()
        if (!requestFocus()) return false
        // The fresh Compose input session queues an implicit show during requestFocus.
        // Queue hide in the same batch, before any suspension can flush that show.
        if (!readOnly && !showKeyboard) input.setKeyboardVisible(false)
        awaitFocus()
        if (restoreVisibleKeyboard) {
            if (!input.prepareInput()) return false
            awaitWindowReady()
        }
        awaitFrame()
        if (restoreVisibleKeyboard) input.setKeyboardVisible(true)
        return true
    } finally {
        input.releaseInput()
    }
}
