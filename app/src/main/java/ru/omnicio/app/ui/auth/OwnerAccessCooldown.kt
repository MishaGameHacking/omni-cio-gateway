package ru.omnicio.app.ui.auth

import ru.omnicio.app.data.backend.MAX_OWNER_RETRY_SECONDS

/**
 * A monotonic deadline survives recomposition/recreation without restarting the
 * server's wait. Saved values contain only timing metadata, never secret inputs.
 */
internal class OwnerAccessCooldown(private val elapsedMillis: () -> Long) {
    private var receivedAtMillis = 0L
    private var deadlineMillis = 0L

    fun start(seconds: Int?): Boolean {
        if (seconds == null || seconds !in 1..MAX_OWNER_RETRY_SECONDS) return false
        val now = elapsedMillis()
        val duration = seconds * 1_000L
        if (now < 0L || now > Long.MAX_VALUE - duration) return false
        receivedAtMillis = now
        deadlineMillis = now + duration
        return true
    }

    fun remainingSeconds(): Int {
        val now = elapsedMillis()
        if (now < receivedAtMillis || now >= deadlineMillis) return 0
        return ((deadlineMillis - now + 999L) / 1_000L).toInt()
    }

    fun snapshot(): List<Long> = listOf(receivedAtMillis, deadlineMillis)

    companion object {
        fun restore(values: List<Long>, elapsedMillis: () -> Long): OwnerAccessCooldown {
            val result = OwnerAccessCooldown(elapsedMillis)
            if (values.size != 2) return result
            val received = values[0]
            val deadline = values[1]
            val now = elapsedMillis()
            if (received < 0L || deadline <= received || now < received ||
                deadline - received > MAX_OWNER_RETRY_SECONDS * 1_000L) return result
            result.receivedAtMillis = received
            result.deadlineMillis = deadline
            return result
        }
    }
}

internal fun ownerWaitLabel(seconds: Int): String {
    val value = seconds.coerceAtLeast(0)
    return (value / 60).toString().padStart(2, '0') + ":" + (value % 60).toString().padStart(2, '0')
}
