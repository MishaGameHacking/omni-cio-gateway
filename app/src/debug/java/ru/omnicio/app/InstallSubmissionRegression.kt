package ru.omnicio.app

import java.io.Closeable
import java.io.IOException
import java.util.concurrent.CancellationException
import ru.omnicio.app.data.updates.existingInstallBlocksNewAttempt
import ru.omnicio.app.data.updates.submitInstallSession

/** Runs the same submission owner as the installer, with fake sessions and no APK/OS calls. */
internal fun runInstallSubmissionChecks(): Int {
    var count = 0
    for (where in listOf("open", "stage", "commit", "close")) {
        for (cancelled in listOf(false, true)) {
            checkFailureStage(where, cancelled)
            count++
        }
    }
    val events = mutableListOf<String>()
    submitInstallSession(
        open = { events.add("open"); Closeable { events.add("close") } },
        stage = { events.add("stage") }, commit = { events.add("commit") },
        uncommittedFailure = { error("Unexpected abandonment") },
        committedCloseFailure = { error("Unexpected close failure") },
    )
    check(events == listOf("open", "stage", "commit", "close")); count++
    val original = IOException("stage")
    val closeFailure = IOException("close")
    val cleanupFailure = IOException("cleanup")
    val caught = runCatching {
        submitInstallSession(
            open = { Closeable { throw closeFailure } }, stage = { throw original },
            commit = { error("Must not commit failed staging") },
            uncommittedFailure = { throw cleanupFailure },
            committedCloseFailure = { error("Not submitted") },
        )
    }.exceptionOrNull()
    check(caught === original && original.suppressed.toList() == listOf(closeFailure, cleanupFailure)); count++
    val cancellation = CancellationException("cancel staging")
    val sameFailure = runCatching {
        submitInstallSession(
            open = { Closeable {} }, stage = { throw cancellation }, commit = {},
            uncommittedFailure = { throw it }, committedCloseFailure = {},
        )
    }.exceptionOrNull()
    check(sameFailure === cancellation && cancellation.suppressed.isEmpty()); count++
    check(!existingInstallBlocksNewAttempt(committed = false, active = false)); count++
    check(existingInstallBlocksNewAttempt(committed = true, active = false)); count++
    check(existingInstallBlocksNewAttempt(committed = false, active = true)); count++
    return count
}

private fun checkFailureStage(where: String, cancelled: Boolean) {
    val events = mutableListOf<String>()
    val failure = if (cancelled) CancellationException(where) else IOException(where)
    fun step(name: String) {
        events.add(name)
        if (where == name) throw failure
    }
    val caught = runCatching {
        submitInstallSession(
            open = { step("open"); Closeable { step("close") } },
            stage = { step("stage") },
            commit = { step("commit") },
            uncommittedFailure = { check(it === failure); events.add("abandon") },
            committedCloseFailure = { check(it === failure); events.add("close-warning") },
        )
    }.exceptionOrNull()
    val alreadySubmitted = where == "close"
    check(("abandon" in events) == !alreadySubmitted)
    check(("close-warning" in events) == (alreadySubmitted && !cancelled))
    check(caught === if (alreadySubmitted && !cancelled) null else failure)
    check(("close" in events) == (where != "open"))
}

fun main() { println("INSTALL_SUBMISSION_CHECKS=" + runInstallSubmissionChecks()) }
