package ru.omnicio.app.ui.workspace

import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test

class PresentationSettingsTest {
    @Test fun captureIsBlockedUntilTheCurrentAccountPolicyIsConfirmed() {
        assertTrue(screenCaptureBlocked(false, true, false))
        assertTrue(screenCaptureBlocked(true, false, false))
        assertTrue(screenCaptureBlocked(true, true, true))
        assertFalse(screenCaptureBlocked(true, true, false))
    }

    @Test fun everyPreferenceRoundTripsIncludingScreenPrivacy() {
        val expected = WorkspacePreferences(AccentStyle.IRIS, InterfaceDensity.COMPACT, false, true, false,
            false, MotionLevel.OFF, true, true)
        assertEquals(expected, presentationSettings(expected.toSettings()))
    }

    @Test fun partialChangeDoesNotOverwriteOtherServerSettings() {
        val server = WorkspacePreferences(motion = MotionLevel.OFF).toSettings()
        val local = WorkspacePreferences(haptics = false)
        val patch = settingsDifference(WorkspacePreferences().toSettings(), local.toSettings())
        val merged = presentationSettings(mergeSettings(server, patch))!!
        assertEquals(MotionLevel.OFF, merged.motion)
        assertFalse(merged.haptics)
        assertEquals(listOf("haptics"), patch.keys().asSequence().toList())
    }

    @Test fun responseFromEarlierWritePreservesNewerUserIntent() {
        val sent = JSONObject().put("motion", "OFF").put("haptics", false)
        val pending = JSONObject(sent.toString()).put("motion", "SUBDUED").put("screenshots_blocked", true)
        val remaining = acknowledgeSettings(pending, sent)
        assertEquals("SUBDUED", remaining.getString("motion"))
        assertTrue(remaining.getBoolean("screenshots_blocked"))
        assertFalse(remaining.has("haptics"))
    }

    @Test fun readAfterLostAcknowledgementDoesNotRepeatAlreadySavedChanges() {
        val server = WorkspacePreferences(haptics = false).toSettings()
        val pending = JSONObject().put("haptics", false)
        assertEquals(0, settingsDifference(server, mergeSettings(server, pending)).length())
    }

    @Test fun offlinePatchSurvivesRestorationButMalformedValuesAreRejected() {
        val pending = JSONObject().put("motion", "OFF").put("screenshots_blocked", true)
        assertEquals(pending.toString(), restoredSettingsPatch(pending.toString()).toString())
        for (raw in listOf("bad", "{\"haptics\":1}", "{\"token\":\"x\"}", "{\"motion\":null}"))
            assertEquals(0, restoredSettingsPatch(raw).length())
    }

    @Test fun serverResponseRequiresConfirmedVersionAndAllTypedSettings() {
        val reply = JSONObject().put("schema_version", 1).put("version", 2)
            .put("settings", WorkspacePreferences().toSettings())
        assertEquals(2L, PresentationSnapshot.parse(reply)?.version)
        assertNull(PresentationSnapshot.parse(JSONObject(reply.toString()).put("version", "2")))
        assertNull(PresentationSnapshot.parse(JSONObject(reply.toString()).put("version", -1)))
        assertNull(PresentationSnapshot.parse(JSONObject(reply.toString()).put("schema_version", 2)))
        reply.getJSONObject("settings").put("screenshots_blocked", "false")
        assertNull(PresentationSnapshot.parse(reply))
    }
}
