package ru.omnicio.app.data.updates

private val allowedReleaseNoteControls = setOf('\t'.code, '\n'.code, '\r'.code)

private fun String.hasWellFormedUtf16(): Boolean {
    var index = 0
    while (index < length) {
        val current = this[index]
        when {
            Character.isHighSurrogate(current) -> {
                if (index + 1 >= length || !Character.isLowSurrogate(this[index + 1])) return false
                index += 2
            }
            Character.isLowSurrogate(current) -> return false
            else -> index += 1
        }
    }
    return true
}

private fun String.isValidReleaseText(
    maxUnits: Int,
    allowBlank: Boolean,
    allowedControls: Set<Int> = emptySet(),
): Boolean = length <= maxUnits && hasWellFormedUtf16() &&
    (allowBlank || isNotBlank()) && all { it.code >= 32 || it.code in allowedControls }

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
        require(versionName.isValidReleaseText(maxUnits = 64, allowBlank = false))
        require(Regex("[a-f0-9]{64}").matches(sha256))
        require(Regex("[a-f0-9]{64}").matches(certificateSha256))
        require(bytes in 1..(256L * 1024 * 1024))
        require(minSdk in 33..100)
        require(notes.isValidReleaseText(
            maxUnits = 4000,
            allowBlank = true,
            allowedControls = allowedReleaseNoteControls,
        ))
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
