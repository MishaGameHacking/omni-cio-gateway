package ru.omnicio.app

import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicReference
import ru.omnicio.app.data.updates.CompatibilityFence

/** Deterministic ordering checks; not a live server or PackageInstaller test. */
internal fun runCompatibilityFenceChecks(): Int {
    var count = 0
    fun verify(test: () -> Unit) { test(); count += 1 }
    var blocked = false
    val fence = CompatibilityFence { blocked = it }
    verify { check(fence.verifiedCurrent(fence.beginVerification())); check(!blocked) }
    val beforeRejection = fence.beginVerification()
    fence.reject()
    verify { check(blocked); check(!fence.verifiedCurrent(beforeRejection)); check(blocked) }
    val afterRejection = fence.beginVerification()
    verify { check(fence.verifiedCurrent(afterRejection)); check(!blocked) }
    verify { check(!fence.verifiedCurrent(beforeRejection)); check(!blocked) }
    val beforeSecondRejection = fence.beginVerification()
    fence.reject(); fence.reject()
    verify { check(!fence.verifiedCurrent(beforeSecondRejection)); check(blocked) }
    verify { check(!fence.verifiedCurrent(Any())); check(blocked) }
    val otherFence = CompatibilityFence { }
    verify { check(!fence.verifiedCurrent(otherFence.beginVerification())); check(blocked) }
    verify { check(fence.verifiedCurrent(fence.beginVerification())); check(!blocked) }
    verify { fence.reject(); check(blocked) }
    verify {
        val started = CountDownLatch(1)
        val rejected = CountDownLatch(1)
        val failure = AtomicReference<Throwable?>(null)
        val ordered = CompatibilityFence { blocked = it }
        val worker = Thread {
            try {
                val ticket = ordered.beginVerification()
                started.countDown()
                check(rejected.await(5, TimeUnit.SECONDS))
                check(!ordered.verifiedCurrent(ticket))
            } catch (error: Throwable) { failure.set(error) }
        }
        worker.start()
        try {
            check(started.await(5, TimeUnit.SECONDS))
            ordered.reject()
        } finally { rejected.countDown(); worker.join(5000) }
        check(!worker.isAlive)
        failure.get()?.let { throw it }
        check(blocked)
    }
    return count
}

fun main() { println("COMPATIBILITY_FENCE_TESTS=passed:" + runCompatibilityFenceChecks()) }
