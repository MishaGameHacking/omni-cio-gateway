package ru.omnicio.app

import ru.omnicio.app.data.updates.UpdateProtocol

private const val NOW = 1_792_000_000L
private fun metadata(): Map<String, Any?> = mapOf(
    "schema_version" to 1, "package_name" to UpdateProtocol.PREVIEW_PACKAGE,
    "version_code" to 24, "minimum_version_code" to 24, "version_name" to "0.6.1-preview",
    "apk_sha256" to "a".repeat(64), "apk_bytes" to 4_000_000L,
    "certificate_sha256" to "b".repeat(64), "min_sdk" to 33,
    "published_at" to NOW - 1, "notes" to "Проверенная сборка",
    "apk_path" to "/client/apk/Analyst-AI-24-${"a".repeat(64)}.apk",
)

internal fun runUpdateProtocolChecks(): Int {
    var checks = 0
    fun rejected(key: String, value: Any?) {
        check(runCatching { UpdateProtocol.parse(metadata() + (key to value), NOW) }.isFailure)
        checks++
    }
    val valid = UpdateProtocol.parse(metadata(), NOW)
    check(valid.versionCode == 24L && valid.packageName == UpdateProtocol.PREVIEW_PACKAGE); checks++
    check(valid.apkPath.endsWith("?package_name=${UpdateProtocol.PREVIEW_PACKAGE}")); checks++
    check(UpdateProtocol.parse(metadata() - "notes", NOW).notes == ""); checks++
    for (value in listOf(true, "24", 24.0, null, -1, Long.MAX_VALUE)) rejected("version_code", value)
    for (value in listOf(true, "4000000", 4_000_000.0, 0, UpdateProtocol.MAX_APK_BYTES + 1)) rejected("apk_bytes", value)
    rejected("schema_version", 2)
    rejected("minimum_version_code", 23)
    rejected("published_at", NOW + 1)
    rejected("published_at", "1791999999")
    rejected("published_at", 0)
    rejected("package_name", "other")
    rejected("min_sdk", 32)
    rejected("min_sdk", 101)
    rejected("version_name", true)
    rejected("version_name", "test\n")
    rejected("notes", null)
    rejected("notes", "x".repeat(4001))
    rejected("apk_sha256", "../other")
    rejected("certificate_sha256", "b".repeat(63))
    rejected("apk_path", "https://untrusted.invalid/file.apk")
    rejected("apk_path", "/client/apk/other.apk")
    check(runCatching { UpdateProtocol.parse(metadata() - "schema_version", NOW) }.isFailure); checks++
    val base = "https://${UpdateProtocol.HOST}"
    val path = UpdateProtocol.policyPath(UpdateProtocol.PREVIEW_PACKAGE)
    check(UpdateProtocol.requestUri(base, path).toString() == base + path); checks++
    check(UpdateProtocol.requestUri(base + "/", path).toString() == base + path); checks++
    for (url in listOf("https://other.invalid", "https://user@${UpdateProtocol.HOST}",
        "https://@${UpdateProtocol.HOST}", base + ":443", base + "?x=1", base + "#x", base + "/extra")) {
        check(runCatching { UpdateProtocol.requestUri(url, path) }.isFailure); checks++
    }
    for (badPath in listOf("//other.invalid/file", "/client/../file", "/client/%2e%2e/file",
        "/client/apk/file#part", "/client/fi\\le", "/client/file\n")) {
        check(runCatching { UpdateProtocol.requestUri(base, badPath) }.isFailure); checks++
    }
    check(runCatching { UpdateProtocol.policyPath("other") }.isFailure); checks++
    return checks
}
