package ru.omnicio.app.ui.updates

import ru.omnicio.app.data.updates.ReleaseDecision
import ru.omnicio.app.data.updates.ReleaseDescriptor

/** One automatic attempt per APK identity and process; explicit actions may retry. */
internal class UpdateAttemptGate {
    private val attempted = mutableSetOf<ReleaseDescriptor>()

    @Synchronized
    fun claim(
        release: ReleaseDescriptor,
        decision: ReleaseDecision,
        automatic: Boolean,
        foreground: Boolean,
        permissionGranted: Boolean,
        busy: Boolean,
        installationPending: Boolean,
    ): Boolean {
        if (decision != ReleaseDecision.UPDATE_REQUIRED ||
            !permissionGranted || busy || installationPending
        ) return false
        if (automatic && !foreground) return false

        // Presentation changes must not trigger another install of the same APK.
        val identity = release.copy(notes = "")
        if (automatic && identity in attempted) return false
        attempted.add(identity)
        return true
    }
}

// Survives Activity recreation. Persisted installer sessions are recovered before polling.
internal val processUpdateAttempts = UpdateAttemptGate()
