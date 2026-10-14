package ru.omnicio.app.data.updates

/** Pure client state. No network/install happens here; errors never unlock old builds. */
sealed interface UpdateStage {
    data object Checking : UpdateStage
    data object Required : UpdateStage
    data class UnsupportedVersion(val installedCode: Long) : UpdateStage
    data class Downloading(val received: Long, val total: Long) : UpdateStage
    data object Verifying : UpdateStage
    data object AwaitingInstaller : UpdateStage
    data object AwaitingUser : UpdateStage
    data object VerifyInstalledVersion : UpdateStage
    data object Current : UpdateStage
    data class Failed(val message: String) : UpdateStage
}

data class UpdateFlow(
    val minimumCode: Long,
    val latestCode: Long,
    val stage: UpdateStage = UpdateStage.Checking,
) {
    init { require(minimumCode > 0 && latestCode >= minimumCode) }
    val blocksApplication: Boolean get() = stage != UpdateStage.Current

    fun withInstalledVersion(actualCode: Long): UpdateFlow {
        require(actualCode > 0)
        val next = when {
            actualCode < minimumCode -> UpdateStage.Required
            actualCode <= latestCode -> UpdateStage.Current
            else -> UpdateStage.UnsupportedVersion(actualCode)
        }
        return copy(stage = next)
    }

    fun beginDownload(): UpdateFlow {
        if (stage != UpdateStage.Required && stage !is UpdateStage.Failed) return this
        return copy(stage = UpdateStage.Downloading(0, 0))
    }

    fun progress(received: Long, total: Long): UpdateFlow {
        val previous = stage as? UpdateStage.Downloading ?: return this
        require(total > 0 && received in 0..total)
        require(previous.total == 0L || previous.total == total)
        require(received >= previous.received)
        return copy(stage = UpdateStage.Downloading(received, total))
    }

    fun finishDownload(): UpdateFlow {
        val download = stage as? UpdateStage.Downloading ?: return this
        if (download.total == 0L || download.received != download.total) return this
        return copy(stage = UpdateStage.Verifying)
    }

    fun verified(): UpdateFlow = if (stage == UpdateStage.Verifying) {
        copy(stage = UpdateStage.AwaitingInstaller)
    } else this

    fun userActionRequired(): UpdateFlow = if (stage == UpdateStage.AwaitingInstaller) {
        copy(stage = UpdateStage.AwaitingUser)
    } else this

    fun installerFinished(): UpdateFlow = if (stage == UpdateStage.AwaitingInstaller || stage == UpdateStage.AwaitingUser) {
        copy(stage = UpdateStage.VerifyInstalledVersion)
    } else this

    fun failed(message: String): UpdateFlow {
        require(message.isNotBlank())
        return copy(stage = UpdateStage.Failed(message))
    }
}
