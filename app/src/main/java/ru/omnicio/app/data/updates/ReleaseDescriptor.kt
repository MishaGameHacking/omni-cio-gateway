package ru.omnicio.app.data.updates

/** Platform-independent contract. Do not treat a client-reported code as attestation. */
data class ReleaseDescriptor(
    val packageName: String,
    val versionCode: Long,
    val versionName: String,
    val sha256: String,
    val bytes: Long,
    val certificateSha256: String,
    val minSdk: Int,
    val notes: String,
) {
    init {
        require(packageName in setOf("ru.omnicio.app", "ru.omnicio.app.debug"))
        require(versionCode in 1..2_100_000_000L)
        require(versionName.isNotBlank() && versionName.length <= 64)
        require(versionName.none { it.code < 32 })
        require(Regex("[a-f0-9]{64}").matches(sha256))
        require(Regex("[a-f0-9]{64}").matches(certificateSha256))
        require(bytes in 1..(256L * 1024 * 1024))
        require(minSdk in 33..100 && notes.length <= 4000)
    }

    val filename: String get() = "Analyst-AI-$versionCode-$sha256.apk"
    val apkPath: String get() = "/client/apk/$filename?package_name=$packageName"

    fun decision(installedPackage: String, installedCode: Long, sdk: Int): ReleaseDecision = when {
        installedPackage != packageName -> ReleaseDecision.WRONG_CHANNEL
        sdk < minSdk -> ReleaseDecision.UNSUPPORTED_ANDROID
        installedCode < versionCode -> ReleaseDecision.UPDATE_REQUIRED
        installedCode > versionCode -> ReleaseDecision.SERVER_NOT_READY
        else -> ReleaseDecision.CURRENT
    }
}

enum class ReleaseDecision { CURRENT, UPDATE_REQUIRED, UNSUPPORTED_ANDROID, SERVER_NOT_READY, WRONG_CHANNEL }
