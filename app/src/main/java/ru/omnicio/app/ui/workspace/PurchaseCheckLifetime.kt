package ru.omnicio.app.ui.workspace

import java.time.Duration
import java.time.Instant

/** Request start is monotonic. Server clock differences cannot extend validity. */
internal fun remainingPurchaseCheckMillis(asOf: String, expiresAt: String, requestedAt: Long, now: Long): Long {
    if (requestedAt < 0 || now < requestedAt) return 0
    val lifetime = runCatching {
        Duration.between(Instant.parse(asOf), Instant.parse(expiresAt)).toMillis()
    }.getOrDefault(0L).coerceIn(0L, 60_000L)
    // Start before the network request, not at receipt: network delay and a
    // long response must consume the lifetime, never renew the observation.
    return (lifetime - (now - requestedAt)).coerceAtLeast(0)
}
