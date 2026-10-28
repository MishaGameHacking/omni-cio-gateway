package ru.omnicio.app.data.workspace

import android.content.Context
import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import android.util.AtomicFile
import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.nio.ByteBuffer
import java.security.KeyStore
import java.security.MessageDigest
import java.util.Locale
import javax.crypto.Cipher
import javax.crypto.KeyGenerator
import javax.crypto.SecretKey
import javax.crypto.spec.GCMParameterSpec

/** Device-only, account-isolated cache. Credentials never belong in this store. */
class EncryptedWorkspaceStore(context: Context) {
    private val directory = File(context.applicationContext.noBackupFilesDir, "workspace-v1")

    fun saveJson(userId: String, key: String, value: JSONObject): Boolean = synchronized(lock) {
        runCatching {
            require(userId.isNotBlank() && key.isNotBlank() && userId !in revokedUsers)
            require(!containsCredentials(value))
            val plain = value.toString().toByteArray(Charsets.UTF_8)
            require(plain.size <= MAX_BYTES)
            check(directory.isDirectory || directory.mkdirs())
            val cipher = Cipher.getInstance("AES/GCM/NoPadding")
            cipher.init(Cipher.ENCRYPT_MODE, encryptionKey(userId, create = true))
            cipher.updateAAD(aad(userId, key))
            val encrypted = cipher.doFinal(plain)
            val bytes = ByteBuffer.allocate(2 + cipher.iv.size + encrypted.size)
                .put(1.toByte()).put(cipher.iv.size.toByte()).put(cipher.iv).put(encrypted).array()
            val file = AtomicFile(file(userId, key))
            val stream = file.startWrite()
            try { stream.write(bytes); file.finishWrite(stream) }
            catch (failure: Throwable) { file.failWrite(stream); throw failure }
            true
        }.getOrDefault(false)
    }

    fun readJson(userId: String, key: String): JSONObject? = synchronized(lock) {
        runCatching {
            require(userId.isNotBlank() && key.isNotBlank() && userId !in revokedUsers)
            val target = file(userId, key)
            val backup = File(target.path + ".bak")
            if ((!target.exists() && !backup.exists()) || target.length() > MAX_BYTES + 128 || backup.length() > MAX_BYTES + 128) return@runCatching null
            val bytes = AtomicFile(target).readFully()
            require(bytes.size in 31..MAX_BYTES + 128 && bytes[0].toInt() == 1)
            val ivSize = bytes[1].toInt() and 255
            require(ivSize == 12 && bytes.size > ivSize + 18)
            val cipher = Cipher.getInstance("AES/GCM/NoPadding")
            cipher.init(Cipher.DECRYPT_MODE, encryptionKey(userId, create = false),
                GCMParameterSpec(128, bytes.copyOfRange(2, 2 + ivSize)))
            cipher.updateAAD(aad(userId, key))
            JSONObject(String(cipher.doFinal(bytes, 2 + ivSize, bytes.size - 2 - ivSize), Charsets.UTF_8))
        }.getOrNull()
    }

    fun remove(userId: String, key: String): Boolean = synchronized(lock) {
        runCatching {
            require(userId.isNotBlank() && key.isNotBlank())
            val target = file(userId, key)
            AtomicFile(target).delete()
            !target.exists() && !File(target.path + ".bak").exists() && !File(target.path + ".new").exists()
        }.getOrDefault(false)
    }

    fun hasEntry(userId: String, key: String): Boolean = synchronized(lock) {
        val target = file(userId, key)
        target.exists() || File(target.path + ".bak").exists()
    }

    /** Call only after the server confirms a new authenticated session. */
    fun activateUser(userId: String) = synchronized(lock) { require(userId.isNotBlank()); revokedUsers.remove(userId); Unit }

    /** Stops late writes at logout while retaining encrypted research for the same account. */
    fun deactivateUser(userId: String) = synchronized(lock) { require(userId.isNotBlank()); revokedUsers.add(userId); Unit }

    /** Also deletes the user's key so removed backups cannot be read later. */
    fun clearUser(userId: String): Boolean = synchronized(lock) {
        runCatching {
            require(userId.isNotBlank())
            revokedUsers.add(userId)
            val keys = KeyStore.getInstance("AndroidKeyStore").apply { load(null) }
            keys.deleteEntry(alias(userId))
            val prefix = digest(userId) + "-"
            directory.listFiles()?.filter { it.name.startsWith(prefix) }?.map { it.delete() }?.all { it } ?: true
        }.getOrDefault(false)
    }

    private fun file(userId: String, key: String) = File(directory, "${digest(userId)}-${digest(key)}.bin")
    private fun alias(userId: String) = "analyst.workspace.v1.${digest(userId)}"
    private fun aad(userId: String, key: String) = "workspace-v1:${digest(userId)}:${digest(key)}".toByteArray(Charsets.UTF_8)
    private fun encryptionKey(userId: String, create: Boolean): SecretKey {
        val keys = KeyStore.getInstance("AndroidKeyStore").apply { load(null) }
        (keys.getKey(alias(userId), null) as? SecretKey)?.let { return it }
        check(create) { "Cache key unavailable" }
        return KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, "AndroidKeyStore").apply {
            init(KeyGenParameterSpec.Builder(alias(userId), KeyProperties.PURPOSE_ENCRYPT or KeyProperties.PURPOSE_DECRYPT)
                .setBlockModes(KeyProperties.BLOCK_MODE_GCM).setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
                .setKeySize(256).setRandomizedEncryptionRequired(true).build())
        }.generateKey()
    }

    private fun containsCredentials(value: Any?): Boolean = when (value) {
        is JSONObject -> value.keys().asSequence().any { name ->
            name.lowercase(Locale.ROOT) in forbidden || containsCredentials(value.opt(name))
        }
        is JSONArray -> (0 until value.length()).any { containsCredentials(value.opt(it)) }
        else -> false
    }

    companion object {
        private val lock = Any()
        private val revokedUsers = mutableSetOf<String>()
        private const val MAX_BYTES = 2_000_000
        private val forbidden = setOf("token", "access_token", "accesstoken", "refresh_token", "refreshtoken",
            "authorization", "password", "api_key", "apikey", "secret", "tinvest_token", "tinvest_token_encrypted")
        internal fun digest(value: String): String = MessageDigest.getInstance("SHA-256")
            .digest(value.toByteArray(Charsets.UTF_8)).joinToString("") { "%02x".format(it) }
    }
}
