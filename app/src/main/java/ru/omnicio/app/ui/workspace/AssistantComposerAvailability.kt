package ru.omnicio.app.ui.workspace

/** Local draft input does not dispatch a request while checkpoint verification is pending. */
internal data class AssistantComposerAvailability(
    val checkpointsLoading: Boolean,
    val recoveryRequired: Boolean,
    val operationBusy: Boolean,
) {
    val canEditDraft: Boolean get() = !recoveryRequired && !operationBusy
    val canSubmit: Boolean get() = !checkpointsLoading && canEditDraft

    fun submitIfAllowed(valid: Boolean, dispatch: () -> Unit) {
        if (valid && canSubmit) dispatch()
    }
}
