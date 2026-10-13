package ru.omnicio.app

import ru.omnicio.app.data.portfolio.RefreshBackoff
import ru.omnicio.app.data.portfolio.RefreshSnapshot

private typealias Sample = RefreshSnapshot<String, Int>

private fun loaded(): Sample {
    val pending = Sample().start("RUB")
    return pending.succeed(pending.requestId, 10, 100)
}

private fun initialSuccess() {
    val result = loaded()
    check(result.value == 10 && result.displayedQuery == "RUB")
    check(!result.loading && result.error == null && result.receivedAtMillis == 100L)
}

private fun currencyKeepsPreviousValue() {
    val pending = loaded().start("USD")
    check(pending.value == 10 && pending.loading)
    check(pending.displayedQuery == "RUB" && pending.requestedQuery == "USD")
}

private fun lateSuccessIgnored() {
    val first = loaded().start("USD")
    val latest = first.start("EUR")
    check(latest.succeed(first.requestId, 20, 200) === latest)
}

private fun lateFailureIgnored() {
    val first = loaded().start("USD")
    val latest = first.start("EUR")
    check(latest.fail(first.requestId, "old failure") === latest)
}

private fun oldCancellationIgnored() {
    val first = loaded().start("USD")
    val latest = first.start("EUR")
    check(latest.cancel(first.requestId) === latest)
    check(latest.loading)
}

private fun cancelledResponseIgnored() {
    val pending = loaded().start("USD")
    val stopped = pending.cancel(pending.requestId)
    check(!stopped.loading && stopped.value == 10)
    check(stopped.succeed(pending.requestId, 20, 200) === stopped)
}

private fun failurePreservesTimestamp() {
    val pending = loaded().start("USD")
    val failed = pending.fail(pending.requestId, "offline")
    check(failed.value == 10 && failed.displayedQuery == "RUB")
    check(failed.receivedAtMillis == 100L && failed.error == "offline" && !failed.loading)
}

private fun recoveryReplacesAtomically() {
    val pending = loaded().start("EUR")
    val result = pending.succeed(pending.requestId, 30, 300)
    check(result.value == 30 && result.displayedQuery == "EUR" && result.receivedAtMillis == 300L)
}

private fun duplicateCompletionIgnored() {
    val result = loaded()
    check(result.succeed(result.requestId, 99, 999) === result)
    check(result.fail(result.requestId, "duplicate") === result)
}

private fun initialFailureHasNoInventedData() {
    val pending = Sample().start("RUB")
    val result = pending.fail(pending.requestId, "offline")
    check(result.value == null && result.displayedQuery == null && result.receivedAtMillis == null)
}

private fun sameQueryStillRefreshes() {
    val previous = loaded()
    val pending = previous.start("RUB")
    check(pending.requestId > previous.requestId && pending.loading && pending.value == previous.value)
}

private fun newScopeStartsEmpty() {
    val oldScope = loaded()
    val newScope = Sample()
    check(oldScope.value != null && newScope.value == null && newScope.error == null)
    check(newScope.receivedAtMillis == null)
}

private fun backoffIsBoundedAndResets() {
    val backoff = RefreshBackoff(15_000)
    check(listOf(backoff.failure(), backoff.failure(), backoff.failure(), backoff.failure()) ==
        listOf(30_000L, 60_000L, 120_000L, 120_000L))
    check(backoff.success() == 15_000L && backoff.failure() == 30_000L)
}

private fun backoffCannotOverflow() {
    val backoff = RefreshBackoff(Long.MAX_VALUE / 2 + 1, Long.MAX_VALUE)
    check(backoff.failure() == Long.MAX_VALUE)
}

private fun invalidBackoffRejected() {
    check(runCatching { RefreshBackoff(0) }.exceptionOrNull() is IllegalArgumentException)
    check(runCatching { RefreshBackoff(10, 5) }.exceptionOrNull() is IllegalArgumentException)
}

/** Runs in the debug-only emulator fixture and also with kotlinc, without Android or network. */
internal fun runRefreshStateRegressionChecks(): Int {
    val cases = listOf(::initialSuccess, ::currencyKeepsPreviousValue, ::lateSuccessIgnored,
        ::lateFailureIgnored, ::oldCancellationIgnored, ::cancelledResponseIgnored,
        ::failurePreservesTimestamp, ::recoveryReplacesAtomically, ::duplicateCompletionIgnored,
        ::initialFailureHasNoInventedData, ::sameQueryStillRefreshes, ::newScopeStartsEmpty,
        ::backoffIsBoundedAndResets, ::backoffCannotOverflow, ::invalidBackoffRejected)
    cases.forEach { it() }
    return cases.size
}

fun main() {
    println("REFRESH_STATE_TESTS=passed:" + runRefreshStateRegressionChecks())
}
