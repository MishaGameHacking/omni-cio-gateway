package ru.omnicio.app

import ru.omnicio.app.data.updates.ReleaseDecision
import ru.omnicio.app.data.updates.ReleaseDescriptor
import ru.omnicio.app.ui.updates.UpdateGateUi

internal fun runUpdateGateUiChecks(): Int {
    val initial = UpdateGateUi(null, null, "0.6.0-preview", true, false, 0, null, null)
    check(!initial.canUpdate && !initial.canRetry)
    val release = ReleaseDescriptor("ru.omnicio.app.debug", 24, "0.6.1-preview", "a".repeat(64), 4000, "b".repeat(64), 33, "")
    check(!initial.copy(decision = ReleaseDecision.UPDATE_REQUIRED, checking = false).canUpdate)
    var checks = 2
    for (decision in ReleaseDecision.entries) {
        val state = initial.copy(release = release, decision = decision, checking = false)
        check(state.canUpdate == (decision == ReleaseDecision.UPDATE_REQUIRED)); checks++
        check(!state.copy(busy = true).canUpdate && !state.copy(busy = true).canRetry); checks++
        check(!state.copy(checking = true).canUpdate && !state.copy(checking = true).canRetry); checks++
        check(!state.copy(installationPending = true).canUpdate && !state.copy(installationPending = true).canRetry); checks++
        check(state.explanation.isNotBlank()); checks++
    }
    check(initial.copy(progress = -200).progressPercent == 0); checks++
    check(initial.copy(progress = 200).progressPercent == 100); checks++
    check(initial.copy(progress = 50).progressPercent == 50); checks++
    return checks
}
