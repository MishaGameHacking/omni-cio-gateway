package ru.omnicio.app.data.updates

import java.io.Closeable
import java.util.concurrent.CancellationException

/** Owns submission, not installation success. Only Android's callback reports the outcome.
 *
 * A failure before commit must clean up the uncommitted session. A close failure
 * after a successful commit must not abandon that session or overwrite a newer
 * callback. Cancellation always propagates, including cancellation during close.
 */
internal fun <T : Closeable> submitInstallSession(
    open: () -> T,
    stage: (T) -> Unit,
    commit: (T) -> Unit,
    uncommittedFailure: (Exception) -> Unit,
    committedCloseFailure: (Exception) -> Unit,
) {
    var submitted = false
    try {
        open().use { session ->
            stage(session)
            commit(session)
            submitted = true
        }
    } catch (failure: Exception) {
        if (!submitted) {
            try {
                uncommittedFailure(failure)
            } catch (cleanupFailure: Exception) {
                if (cleanupFailure !== failure) failure.addSuppressed(cleanupFailure)
            }
            throw failure
        }
        if (failure is CancellationException) throw failure
        committedCloseFailure(failure)
    }
}
