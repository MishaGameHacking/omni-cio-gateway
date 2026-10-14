package ru.omnicio.app

import ru.omnicio.app.data.updates.InstallFailureReason
import ru.omnicio.app.data.updates.installFailureMessage

/** Pure message checks, not an actual PackageInstaller callback simulation. */
internal fun runInstallFailureChecks(): Int {
    var count = 0
    fun verify(value: Boolean) { check(value); count++ }
    val messages = InstallFailureReason.entries.map(::installFailureMessage)
    verify(messages.toSet().size == InstallFailureReason.entries.size)
    for (message in messages) {
        verify(message.isNotBlank() && message.length <= 420)
        verify("http" !in message && '/' !in message && "ru.omnicio" !in message)
    }
    verify("Не удаляйте" in installFailureMessage(InstallFailureReason.CONFLICT))
    verify("Не отключайте защиту" in installFailureMessage(InstallFailureReason.BLOCKED))
    verify("хранилища" in installFailureMessage(InstallFailureReason.STORAGE))
    verify("несовместима" in installFailureMessage(InstallFailureReason.INCOMPATIBLE))
    verify("Причина не определена" in installFailureMessage(InstallFailureReason.OTHER))
    return count
}

fun main() { println("INSTALL_FAILURE_CHECKS=" + runInstallFailureChecks()) }
