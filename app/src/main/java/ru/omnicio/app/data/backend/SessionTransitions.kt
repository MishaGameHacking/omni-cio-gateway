package ru.omnicio.app.data.backend

import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Deferred
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.async

/** Submissions keep their order even if the Activity awaiting them is recreated. */
internal class SessionTransitionQueue(private val scope: CoroutineScope) {
    private val lock = Any()
    private var previous: Deferred<*>? = null

    fun <T> submit(operation: suspend () -> T): Deferred<T> = synchronized(lock) {
        val predecessor = previous
        scope.async {
            // A failed transition is complete too; it must not poison later login.
            predecessor?.join()
            operation()
        }.also { transition ->
            previous = transition
            transition.invokeOnCompletion {
                synchronized(lock) {
                    if (previous === transition) previous = null
                }
            }
        }
    }

    suspend fun <T> run(operation: suspend () -> T): T = submit(operation).await()
}

/** Process-owned ordering survives Activity recreation; completed results are not retained. */
internal object SessionTransitions {
    private val queue = SessionTransitionQueue(CoroutineScope(SupervisorJob() + Dispatchers.IO))
    fun <T> submit(operation: suspend () -> T): Deferred<T> = queue.submit(operation)
    suspend fun <T> run(operation: suspend () -> T): T = queue.run(operation)
}
