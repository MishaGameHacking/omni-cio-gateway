package ru.omnicio.app

import ru.omnicio.app.data.updates.ReleaseDescriptor
import ru.omnicio.app.data.updates.ReleaseDecision

private const val PREVIEW_TEST_PACKAGE = "ru.omnicio.app.debug"

/** Offline pure contract checks. Not a PackageInstaller/device-test substitute. */
internal fun runUpdatePolicyChecks(): Int {
    check(runPolicyReadChecks() == 18)
    check(runCompatibilityFenceChecks() == 10)
    check(runInstallFailureChecks() == 20)
    check(runUpdateTransportChecks() == 27)
    val release = ReleaseDescriptor(PREVIEW_TEST_PACKAGE,24,"0.6.1-preview","a".repeat(64),4000000,"b".repeat(64),33,"")
    check(release.decision(PREVIEW_TEST_PACKAGE,23,33)==ReleaseDecision.UPDATE_REQUIRED)
    check(release.decision(PREVIEW_TEST_PACKAGE,24,36)==ReleaseDecision.CURRENT)
    check(release.decision(PREVIEW_TEST_PACKAGE,25,36)==ReleaseDecision.SERVER_NOT_READY)
    check(release.decision("ru.omnicio.app",24,36)==ReleaseDecision.WRONG_CHANNEL)
    check(release.decision(PREVIEW_TEST_PACKAGE,23,32)==ReleaseDecision.UNSUPPORTED_ANDROID)
    check(release.apkPath.startsWith("/client/apk/Analyst-AI-24-"))
    check(runCatching { release.copy(sha256="../file") }.isFailure)
    check(runCatching { release.copy(bytes=0) }.isFailure)
    check(runCatching { release.copy(versionCode=-1) }.isFailure)
    check(runCatching { release.copy(certificateSha256="a") }.isFailure)
    check(runCatching { release.copy(packageName="other") }.isFailure)
    check(runCatching { release.copy(versionName="x\n") }.isFailure)
    return 12
}

fun main() { println("UPDATE_POLICY_TESTS=passed:"+runUpdatePolicyChecks()) }
