package ru.omnicio.app.data.updates

/** An in-process ordering fence, not authentication or device attestation. */
internal class CompatibilityFence(private val publishBlocked: (Boolean) -> Unit) {
    private val lock = Any()
    private var epoch = Any()

    fun beginVerification(): Any = synchronized(lock) { epoch }

    fun reject() = synchronized(lock) {
        // Identity tokens cannot wrap around or be confused with a prior epoch.
        epoch = Any()
        publishBlocked(true)
    }

    fun verifiedCurrent(ticket: Any): Boolean = synchronized(lock) {
        if (ticket !== epoch) return@synchronized false
        // Publication must share the lock with rejection; a stale success may
        // never publish false after a newer HTTP 426 has published true.
        publishBlocked(false)
        true
    }
}
