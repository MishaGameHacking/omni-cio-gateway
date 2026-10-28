package ru.omnicio.app.data.updates

import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test

class ServerVersionTest {
    private fun metadata(revision: String = "a".repeat(64)) = JSONObject()
        .put("schema_version", 1).put("source_revision", revision).put("version", "srv-" + revision.take(12))

    @Test fun serverReleaseChangesDisplayedVersionWithoutAndroidBuildValues() {
        assertEquals("srv-" + "a".repeat(12), ServerVersion.parse(metadata())?.name)
        assertEquals("srv-" + "b".repeat(12), ServerVersion.parse(metadata("b".repeat(64)))?.name)
    }

    @Test fun oldServerAndMalformedMetadataNeverMasqueradeAsAndroidVersion() {
        assertNull(ServerVersion.parse(null))
        assertNull(ServerVersion.parse(JSONObject()))
        assertNull(ServerVersion.parse(metadata().put("schema_version", 2)))
        assertNull(ServerVersion.parse(metadata().put("schema_version", "1")))
        assertNull(ServerVersion.parse(metadata().put("version", "arbitrary server message")))
        assertNull(ServerVersion.parse(metadata("A".repeat(64))))
        assertNull(ServerVersion.parse(metadata("a".repeat(63))))
        assertNull(ServerVersion.parse(metadata().put("source_revision", JSONObject.NULL)))
        assertEquals("Сервер не сообщил версию системы", ServerVersion.label(null, false, false))
    }

    @Test fun reconnectAndRefreshDoNotClaimOldVersionIsCurrent() {
        assertEquals("Версия системы недоступна", ServerVersion.label(null, false, true))
        assertEquals("Проверяем версию системы…", ServerVersion.label(null, true, false))
        assertTrue(ServerVersion.label(metadata(), false, true).startsWith("Последняя полученная версия системы:"))
        assertTrue(ServerVersion.label(metadata(), true, false).endsWith("проверяем…"))
        assertEquals("Версия системы: srv-" + "b".repeat(12), ServerVersion.label(metadata("b".repeat(64)), false, false))
    }
}
