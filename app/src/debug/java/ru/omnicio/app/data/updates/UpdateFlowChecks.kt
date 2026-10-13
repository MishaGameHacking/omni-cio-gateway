package ru.omnicio.app.data.updates

/** Offline regression checks. Not a PackageInstaller/device-install test. */
fun main() {
    var checks = 0
    fun verify(condition: Boolean) { check(condition); checks++ }
    val baseline = UpdateFlow(23, 23)
    verify(baseline.blocksApplication)
    val old = baseline.withInstalledVersion(22)
    verify(old.stage == UpdateStage.Required)
    verify(baseline.withInstalledVersion(23).stage == UpdateStage.Current)
    verify(baseline.withInstalledVersion(999).blocksApplication)
    val started = old.beginDownload()
    verify(started.blocksApplication)
    verify(started.finishDownload() == started)
    val progress = started.progress(40, 100)
    verify(progress.finishDownload() == progress)
    verify(runCatching { progress.progress(39, 100) }.isFailure)
    verify(runCatching { progress.progress(101, 100) }.isFailure)
    verify(runCatching { progress.progress(50, 90) }.isFailure)
    val downloaded = progress.progress(100, 100).finishDownload()
    verify(downloaded.stage == UpdateStage.Verifying)
    verify(downloaded.blocksApplication)
    val verified = downloaded.verified()
    verify(verified.stage == UpdateStage.AwaitingInstaller)
    val confirmation = verified.userActionRequired()
    verify(confirmation.stage == UpdateStage.AwaitingUser)
    val installed = confirmation.installerFinished()
    verify(installed.blocksApplication)
    verify(installed.withInstalledVersion(22).blocksApplication)
    verify(!installed.withInstalledVersion(23).blocksApplication)
    val cancelled = confirmation.failed("Установка отменена")
    verify(cancelled.blocksApplication)
    verify(cancelled.beginDownload().stage is UpdateStage.Downloading)
    verify(runCatching { UpdateFlow(24, 23) }.isFailure)
    println("UPDATE_FLOW_CHECKS=$checks")
}
