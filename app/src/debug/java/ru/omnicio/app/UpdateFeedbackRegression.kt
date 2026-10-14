package ru.omnicio.app

import ru.omnicio.app.ui.updates.UpdateGateFeedback

/** Pure UI-state checks. No network, installer, session or version gate bypass. */
internal fun runUpdateFeedbackChecks(): Int {
    var checks = 0
    fun verify(condition: Boolean) { check(condition); checks++ }
    val network = "Не удалось проверить версию."
    val download = "Загрузка прервана. Повторите обновление."
    val permission = "Android не разрешил установку."
    val initial = UpdateGateFeedback()
    verify(initial.message == null)
    verify(initial.policyChecked(network).message == network)
    verify(initial.operationFailed(download).message == download)
    val failed = initial.operationFailed(download)
    verify(failed.policyChecked().message == download)
    verify(failed.policyChecked(network).message == "$network\n\n$download")
    verify(failed.policyChecked(network).policyChecked().message == download)
    verify(failed.operationStarted().message == null)
    verify(failed.policyChecked(network).operationStarted().message == network)
    verify(failed.operationFailed(permission).message == permission)
    verify(failed.operationFailed(permission).policyChecked().message == permission)
    verify(initial.policyChecked(network).operationFailed(network).message == network)
    verify(UpdateGateFeedback(" ", "\n").message == null)
    verify(UpdateGateFeedback(null, download).operationStarted().policyChecked().message == null)
    verify(failed.operationError == download && initial.message == null)
    verify(failed.policyChecked(network).operationFailed(permission).message == "$network\n\n$permission")
    return checks
}

fun main() { println("UPDATE_FEEDBACK_CHECKS=" + runUpdateFeedbackChecks()) }
