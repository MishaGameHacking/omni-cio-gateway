package ru.omnicio.app.data.workspace

/** A quote authorizes a bounded route, not trading or an arbitrary model upgrade. */
internal data class ChatRouteQuote(
    val available: Boolean,
    val selectedTier: String,
    val confirmationRequired: Boolean,
    val ceilingMicroRub: Long?,
    val routeId: String,
) {
    val usable: Boolean get() = available && selectedTier in setOf("fast", "standard", "premium") &&
        ceilingMicroRub != null && ceilingMicroRub in 0L..1_000_000_000_000_000L &&
        Regex("[a-f0-9]{64}").matches(routeId)

    fun needsConfirmation(requestedTier: String): Boolean = confirmationRequired ||
        selectedTier == "premium" || requestedTier == "premium"
}
