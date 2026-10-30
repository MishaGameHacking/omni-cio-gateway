package ru.omnicio.app.ui.auth

/** A one-use ticket cannot cross a stop, recreation or a newer access attempt. */
internal class OwnerAccessGate(initiallyForeground: Boolean = false) {
    private var foreground = initiallyForeground
    private var generation = 0L

    fun foreground() { foreground = true }

    fun background() {
        foreground = false
        generation++
    }

    fun begin(): Long? {
        if (!foreground) return null
        generation++
        return generation
    }

    fun isCurrent(ticket: Long): Boolean = foreground && ticket == generation

    fun complete(ticket: Long): Boolean {
        if (!isCurrent(ticket)) return false
        generation++
        return true
    }
}
