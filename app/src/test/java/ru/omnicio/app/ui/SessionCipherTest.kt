package ru.omnicio.app.ui

import java.security.GeneralSecurityException
import javax.crypto.KeyGenerator
import org.junit.Assert.*
import org.junit.Test

class SessionCipherTest {
    private fun key() = KeyGenerator.getInstance("AES").apply { init(256) }.generateKey()
    private val session = StoredSession("synthetic_session_".repeat(4), "000000123", Long.MAX_VALUE)

    @Test fun sessionSurvivesEncryptionWithoutPlaintextAndUsesFreshNonce() {
        val key = key()
        val first = SessionCipher.encrypt(session, key)
        val second = SessionCipher.encrypt(session, key)
        assertEquals(session, SessionCipher.decrypt(first, key))
        assertFalse(first.contentEquals(second))
        assertFalse(first.toString(Charsets.ISO_8859_1).contains(session.token))
    }

    @Test fun modifiedOrWrongKeySessionCannotBeRestored() {
        val key = key()
        val encrypted = SessionCipher.encrypt(session, key)
        assertThrows(GeneralSecurityException::class.java) { SessionCipher.decrypt(encrypted, key()) }
        encrypted[encrypted.lastIndex] = (encrypted.last().toInt() xor 1).toByte()
        assertThrows(GeneralSecurityException::class.java) { SessionCipher.decrypt(encrypted, key) }
        assertThrows(IllegalArgumentException::class.java) { SessionCipher.decrypt(byteArrayOf(1), key) }
    }

    @Test fun expiredOrMalformedSessionIsRejectedAndCookieRestoresExactly() {
        assertFalse(session.copy(expiresAt = 1000).valid(now = 1000))
        assertFalse(session.copy(token = "bad token").valid())
        assertFalse(session.copy(publicId = "another-profile").valid())
        val api = ServerApi()
        api.restore(session)
        assertEquals(session, api.savedSession())
        assertEquals(session.publicId, api.profile)
    }
}
