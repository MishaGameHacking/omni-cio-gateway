package ru.omnicio.app.data.updates

import java.net.URI

/** One wire contract for the updater and Spectrum; version headers are not authentication. */
object UpdateProtocol {
    const val HOST = "176.98.178.81.sslip.io"
    const val PACKAGE_HEADER = "X-Analyst-Package"
    const val CODE_HEADER = "X-Analyst-Version-Code"
    const val MAX_MANIFEST_BYTES = 16_384
    const val MAX_APK_BYTES = 256L * 1024 * 1024
    const val PREVIEW_PACKAGE = "ru.omnicio.app.debug"
    const val RELEASE_PACKAGE = "ru.omnicio.app"
    private val packages = setOf(PREVIEW_PACKAGE, RELEASE_PACKAGE)

    fun policyPath(packageName: String): String {
        require(packageName in packages)
        return "/client/update-policy?package_name=$packageName"
    }

    fun requestUri(baseUrl: String, path: String): URI {
        val base = URI(baseUrl)
        require(base.scheme == "https" && base.host == HOST && base.rawAuthority == HOST)
        require(base.rawUserInfo == null && base.port == -1 && base.rawQuery == null && base.rawFragment == null)
        require(base.rawPath.isNullOrEmpty() || base.rawPath == "/")
        require(path.startsWith("/client/") && !path.contains(".."))
        val request = URI(baseUrl.trimEnd('/') + path)
        require(request.host == HOST && request.rawAuthority == HOST && request.rawFragment == null)
        require(request.rawPath == request.path && request.path.startsWith("/client/"))
        require(path.none { it.code <= 32 || it.code == 127 || it == '\\' })
        return request
    }

    /** JSONObject must pass the original typed values, never coerce numbers/booleans to strings. */
    fun parse(fields: Map<String, Any?>, nowEpochSeconds: Long): ReleaseDescriptor {
        require(integer(fields, "schema_version") == 1L)
        val code = integer(fields, "version_code")
        require(integer(fields, "minimum_version_code") == code)
        val published = integer(fields, "published_at")
        require(nowEpochSeconds > 0 && published in 1..32_503_680_000L && published <= nowEpochSeconds)
        val sdk = integer(fields, "min_sdk")
        require(sdk in 33..100)
        val descriptor = ReleaseDescriptor(
            text(fields, "package_name"), code, text(fields, "version_name"),
            text(fields, "apk_sha256"), integer(fields, "apk_bytes"),
            text(fields, "certificate_sha256"), sdk.toInt(),
            if (fields.containsKey("notes")) text(fields, "notes") else "",
        )
        require(text(fields, "apk_path") == "/client/apk/${descriptor.filename}")
        return descriptor
    }

    private fun integer(fields: Map<String, Any?>, key: String): Long = when (val value = fields[key]) {
        is Int -> value.toLong()
        is Long -> value
        else -> error("Invalid integer in update metadata: $key")
    }

    private fun text(fields: Map<String, Any?>, key: String): String = fields[key] as? String
        ?: error("Invalid text in update metadata: $key")
}
