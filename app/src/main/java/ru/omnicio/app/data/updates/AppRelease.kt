package ru.omnicio.app.data.updates

import android.os.Build
import java.net.URI
import java.time.Instant
import org.json.JSONObject

internal const val UPDATE_HOST = "176.98.178.81.sslip.io"
internal const val MAX_APK_BYTES = 250L * 1024L * 1024L

internal class UpdateValidationException(message: String) : Exception(message)

data class AppRelease(
    val versionCode: Long,
    val minimumSupported: Long,
    val versionName: String,
    val packageName: String,
    val url: String,
    val sha256: String,
    val certificateSha256: String,
    val sizeBytes: Long,
    val minSdk: Int,
    val publishedAt: String,
    val notes: String,
) {
    fun validate(
        expectedPackage: String,
        expectedCertificate: String,
        now: Instant = Instant.now(),
    ) {
        if (versionCode <= 0L || minimumSupported <= 0L || minimumSupported > versionCode) {
            throw UpdateValidationException("Некорректные границы версии обновления.")
        }
        if (versionName.isBlank() || versionName.length > 80 || versionName.any { it.code < 32 }) {
            throw UpdateValidationException("Некорректное имя версии обновления.")
        }
        if (packageName != expectedPackage) {
            throw UpdateValidationException("Обновление предназначено для другого приложения.")
        }
        if (!sha256.matches(SHA256_REGEX) || !certificateSha256.matches(SHA256_REGEX)) {
            throw UpdateValidationException("Некорректная контрольная сумма обновления.")
        }
        if (!expectedCertificate.matches(SHA256_REGEX) || certificateSha256 != expectedCertificate) {
            throw UpdateValidationException("Сертификат обновления не совпадает с установленным приложением.")
        }
        if (sizeBytes !in 1..MAX_APK_BYTES) {
            throw UpdateValidationException("Некорректный размер APK.")
        }
        if (minSdk < 33 || minSdk > Build.VERSION.SDK_INT) {
            throw UpdateValidationException("Обновление несовместимо с этим Android.")
        }
        if (notes.length > 4_000 || '\u0000' in notes) {
            throw UpdateValidationException("Некорректное описание обновления.")
        }
        val location = runCatching { URI(url) }.getOrElse {
            throw UpdateValidationException("Некорректная ссылка обновления.")
        }
        val expectedPath = "/releases/$versionCode/$sha256.apk"
        if (
            location.scheme != "https" ||
            location.host != UPDATE_HOST ||
            location.port != -1 ||
            location.rawPath != expectedPath ||
            location.rawQuery != null ||
            location.rawFragment != null ||
            location.userInfo != null
        ) {
            throw UpdateValidationException("APK должен загружаться только с российского сервера Analyst AI.")
        }
        val published = runCatching { Instant.parse(publishedAt) }.getOrElse {
            throw UpdateValidationException("Некорректная дата публикации обновления.")
        }
        if (published.isAfter(now.plusSeconds(300))) {
            throw UpdateValidationException("Обновление ещё не опубликовано.")
        }
    }

    fun toJson(): String = JSONObject()
        .put("version_code", versionCode)
        .put("minimum_supported", minimumSupported)
        .put("version_name", versionName)
        .put("package_name", packageName)
        .put("url", url)
        .put("sha256", sha256)
        .put("certificate_sha256", certificateSha256)
        .put("size_bytes", sizeBytes)
        .put("min_sdk", minSdk)
        .put("published_at", publishedAt)
        .put("notes", notes)
        .toString()

    companion object {
        private val SHA256_REGEX = Regex("[0-9a-f]{64}")

        fun parse(raw: String): AppRelease {
            val json = try {
                JSONObject(raw)
            } catch (_: Exception) {
                throw UpdateValidationException("Сервер вернул некорректное описание обновления.")
            }
            val expected = setOf(
                "version_code",
                "minimum_supported",
                "version_name",
                "package_name",
                "url",
                "sha256",
                "certificate_sha256",
                "size_bytes",
                "min_sdk",
                "published_at",
                "notes",
            )
            val actual = buildSet {
                val keys = json.keys()
                while (keys.hasNext()) add(keys.next())
            }
            if (actual != expected) {
                throw UpdateValidationException("Схема обновления не совпадает с ожидаемой.")
            }
            return try {
                AppRelease(
                    versionCode = json.getLong("version_code"),
                    minimumSupported = json.getLong("minimum_supported"),
                    versionName = json.getString("version_name"),
                    packageName = json.getString("package_name"),
                    url = json.getString("url"),
                    sha256 = json.getString("sha256").lowercase(),
                    certificateSha256 = json.getString("certificate_sha256").lowercase(),
                    sizeBytes = json.getLong("size_bytes"),
                    minSdk = json.getInt("min_sdk"),
                    publishedAt = json.getString("published_at"),
                    notes = json.getString("notes"),
                )
            } catch (_: Exception) {
                throw UpdateValidationException("Сервер вернул неполное описание обновления.")
            }
        }
    }
}
