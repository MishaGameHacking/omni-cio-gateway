package ru.omnicio.app.ui

import android.content.Context
import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import android.util.AtomicFile
import java.io.ByteArrayInputStream
import java.io.ByteArrayOutputStream
import java.io.DataInputStream
import java.io.DataOutputStream
import java.io.File
import java.io.IOException
import java.security.KeyStore
import javax.crypto.Cipher
import javax.crypto.KeyGenerator
import javax.crypto.SecretKey
import javax.crypto.spec.GCMParameterSpec

internal data class StoredSession(val token: String, val publicId: String, val expiresAt: Long) {
    fun valid(now: Long = System.currentTimeMillis()): Boolean =
        token.matches(Regex("[A-Za-z0-9_-]{32,512}")) &&
            publicId.matches(Regex("[0-9]{9}")) && expiresAt > now
}

/** Only the revocable OMNICIO session is persisted; no broker token or portfolio is stored. */
internal class SessionVault(context: Context) {
    private val file = AtomicFile(File(context.noBackupFilesDir, "omnicio-session"))

    private fun key(): SecretKey {
        val store = KeyStore.getInstance("AndroidKeyStore").apply { load(null) }
        (store.getKey(KEY_ALIAS, null) as? SecretKey)?.let { return it }
        return KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, "AndroidKeyStore").apply {
            init(KeyGenParameterSpec.Builder(KEY_ALIAS,
                KeyProperties.PURPOSE_ENCRYPT or KeyProperties.PURPOSE_DECRYPT)
                .setBlockModes(KeyProperties.BLOCK_MODE_GCM)
                .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
                .setKeySize(256).build())
        }.generateKey()
    }

    fun read(): StoredSession? {
        if (!file.baseFile.exists()) return null
        val encrypted = file.openRead().use { input ->
            val output = ByteArrayOutputStream()
            val buffer = ByteArray(512)
            while (output.size() <= 4096) {
                val count = input.read(buffer)
                if (count < 0) break
                output.write(buffer, 0, count)
            }
            if (output.size() > 4096) throw IOException("Invalid stored session")
            output.toByteArray()
        }
        return SessionCipher.decrypt(encrypted, key()).takeIf { it.valid() }
    }

    fun write(session: StoredSession) {
        require(session.valid())
        val bytes = SessionCipher.encrypt(session, key())
        val output = file.startWrite()
        try {
            output.write(bytes)
            file.finishWrite(output)
        } catch (error: IOException) {
            file.failWrite(output)
            throw error
        }
    }

    fun clear() = file.delete()

    private companion object { const val KEY_ALIAS = "omnicio-session-v1" }
}

/** Authenticated encryption also rejects truncated, modified and wrong-key session files. */
internal object SessionCipher {
    private val context = "OMNICIO session v1".toByteArray(Charsets.UTF_8)

    fun encrypt(session: StoredSession, key: SecretKey): ByteArray {
        val plaintext = ByteArrayOutputStream().also { buffer ->
            DataOutputStream(buffer).use {
                it.writeUTF(session.token)
                it.writeUTF(session.publicId)
                it.writeLong(session.expiresAt)
            }
        }.toByteArray()
        val cipher = Cipher.getInstance("AES/GCM/NoPadding")
        cipher.init(Cipher.ENCRYPT_MODE, key)
        cipher.updateAAD(context)
        return cipher.iv + cipher.doFinal(plaintext)
    }

    fun decrypt(bytes: ByteArray, key: SecretKey): StoredSession {
        require(bytes.size in 29..4096)
        val cipher = Cipher.getInstance("AES/GCM/NoPadding")
        cipher.init(Cipher.DECRYPT_MODE, key, GCMParameterSpec(128, bytes.copyOfRange(0, 12)))
        cipher.updateAAD(context)
        return DataInputStream(ByteArrayInputStream(cipher.doFinal(bytes, 12, bytes.size - 12))).use {
            val session = StoredSession(it.readUTF(), it.readUTF(), it.readLong())
            require(it.available() == 0)
            session
        }
    }
}
