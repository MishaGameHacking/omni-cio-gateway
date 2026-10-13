package ru.omnicio.app.data.updates

import android.content.Context
import android.content.pm.PackageInfo
import android.content.pm.PackageManager
import android.os.Build
import java.io.File
import java.io.FileInputStream
import java.security.MessageDigest

internal class AppUpdateVerifier(private val context: Context) {
    fun installedVersionCode(): Long = installedPackageInfo().longVersionCode

    fun installedCertificateSha256(): String = signerDigest(installedPackageInfo())

    fun verify(release: AppRelease, apk: File) {
        if (!apk.isFile || apk.length() != release.sizeBytes) {
            throw UpdateValidationException("Размер загруженного APK не совпадает с описанием.")
        }
        val currentCertificate = installedCertificateSha256()
        release.validate(
            expectedPackage = context.packageName,
            expectedCertificate = currentCertificate,
        )
        val calculated = sha256(apk)
        if (calculated != release.sha256) {
            throw UpdateValidationException("Контрольная сумма APK не совпадает.")
        }
        val archive = context.packageManager.getPackageArchiveInfo(
            apk.absolutePath,
            PackageManager.PackageInfoFlags.of(PackageManager.GET_SIGNING_CERTIFICATES.toLong()),
        ) ?: throw UpdateValidationException("Android не распознал загруженный APK.")
        if (archive.packageName != context.packageName) {
            throw UpdateValidationException("APK содержит другое приложение.")
        }
        if (archive.longVersionCode != release.versionCode) {
            throw UpdateValidationException("Код версии APK не совпадает с описанием.")
        }
        if (archive.longVersionCode <= installedVersionCode()) {
            throw UpdateValidationException("Понижение или повторная установка версии запрещены.")
        }
        val archiveMinSdk = archive.applicationInfo?.minSdkVersion
            ?: throw UpdateValidationException("APK не содержит minSdk.")
        if (archiveMinSdk != release.minSdk || archiveMinSdk > Build.VERSION.SDK_INT) {
            throw UpdateValidationException("APK несовместим с этим Android.")
        }
        val archiveCertificate = signerDigest(archive)
        if (archiveCertificate != currentCertificate || archiveCertificate != release.certificateSha256) {
            throw UpdateValidationException("APK подписан другим сертификатом.")
        }
    }

    private fun installedPackageInfo(): PackageInfo = context.packageManager.getPackageInfo(
        context.packageName,
        PackageManager.PackageInfoFlags.of(PackageManager.GET_SIGNING_CERTIFICATES.toLong()),
    )

    private fun signerDigest(info: PackageInfo): String {
        val signingInfo = info.signingInfo
            ?: throw UpdateValidationException("Не удалось проверить подпись приложения.")
        val signers = signingInfo.apkContentsSigners
        if (signers.size != 1) {
            throw UpdateValidationException("Ожидался один сертификат подписи.")
        }
        return MessageDigest.getInstance("SHA-256")
            .digest(signers.single().toByteArray())
            .joinToString("") { "%02x".format(it.toInt() and 0xff) }
    }

    private fun sha256(file: File): String {
        val digest = MessageDigest.getInstance("SHA-256")
        FileInputStream(file).use { input ->
            val buffer = ByteArray(64 * 1024)
            while (true) {
                val count = input.read(buffer)
                if (count < 0) break
                digest.update(buffer, 0, count)
            }
        }
        return digest.digest().joinToString("") { "%02x".format(it.toInt() and 0xff) }
    }
}
