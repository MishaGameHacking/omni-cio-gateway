package ru.omnicio.app.data.backend

import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.cancelAndJoin
import kotlinx.coroutines.launch
import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class SessionTransitionsTest {
    @Test(timeout = 5000) fun cleanupFinishesBeforeAReplacementSessionCanBeSaved() = runBlocking {
        val owner = CoroutineScope(SupervisorJob() + Dispatchers.Default)
        try {
            val queue = SessionTransitionQueue(owner)
            val started = CompletableDeferred<Unit>()
            val finish = CompletableDeferred<Unit>()
            var stored: String? = "old-session"
            val cleanup = queue.submit { started.complete(Unit); finish.await(); stored = null }
            started.await()
            val replacement = queue.submit { assertEquals(null, stored); stored = "new-session" }
            assertFalse(replacement.isCompleted)
            finish.complete(Unit)
            cleanup.await(); replacement.await()
            assertEquals("new-session", stored)
        } finally { owner.cancel() }
    }

    @Test(timeout = 5000) fun recreatingTheAwaitingActivityDoesNotCancelCleanup() = runBlocking {
        val owner = CoroutineScope(SupervisorJob() + Dispatchers.Default)
        try {
            val queue = SessionTransitionQueue(owner)
            val started = CompletableDeferred<Unit>()
            val finish = CompletableDeferred<Unit>()
            var signedIn = true
            val cleanup = queue.submit { started.complete(Unit); finish.await(); signedIn = false }
            val activity = launch { cleanup.await() }
            started.await()
            activity.cancelAndJoin()
            assertFalse(cleanup.isCancelled)
            val restored = queue.submit { signedIn }
            assertFalse(restored.isCompleted)
            finish.complete(Unit)
            assertFalse(restored.await())
        } finally { owner.cancel() }
    }

    @Test(timeout = 5000) fun failedTransitionDoesNotPreventTheNextLogin() = runBlocking {
        val owner = CoroutineScope(SupervisorJob() + Dispatchers.Default)
        try {
            val queue = SessionTransitionQueue(owner)
            val failed = queue.submit { throw IllegalStateException("Synthetic persistence failure") }
            val next = queue.submit { "confirmed-session" }
            assertTrue(runCatching { failed.await() }.exceptionOrNull() is IllegalStateException)
            assertEquals("confirmed-session", next.await())
        } finally { owner.cancel() }
    }
}
