package ru.omnicio.app.ui.workspace

import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test

class AutoSaveModelTest {
    @Test fun newerLocalEditSurvivesOlderServerAcknowledgement() {
        val sent = AutoSaveRecord(AutoSaveKind.Notifications, 1, "{\"morning\":\"08:00\"}",
            "{\"morning\":\"09:00\"}", 4, true, AutoSavePhase.Saving)
        val current = sent.copy(revision = 2, draft = "{\"morning\":\"10:00\"}")
        val next = acknowledgeAutoSave(current, sent, JSONObject(sent.draft), 5)
        assertEquals("10:00", JSONObject(next.draft).getString("morning"))
        assertEquals(5, next.version)
        assertEquals(AutoSavePhase.Pending, next.phase)
    }
    @Test fun concurrentServerFieldsAreRetainedInNestedDocument() {
        val base = JSONObject("{\"limits\":{\"position\":10,\"sector\":40},\"zone\":\"A\"}")
        val local = JSONObject("{\"limits\":{\"position\":15,\"sector\":40},\"zone\":\"A\"}")
        val server = JSONObject("{\"limits\":{\"position\":10,\"sector\":30},\"zone\":\"B\"}")
        val merged = mergeAutoSaveChanges(base, local, server)
        assertEquals(15, merged.getJSONObject("limits").getInt("position"))
        assertEquals(30, merged.getJSONObject("limits").getInt("sector"))
        assertEquals("B", merged.getString("zone"))
    }
    @Test fun malformedNewerDraftNeverBecomesAppliedBecauseOlderRequestSucceeded() {
        val sent = AutoSaveRecord(AutoSaveKind.Strategy, 3, "{}", "{\"horizon_months\":12}", 2, true, AutoSavePhase.Saving)
        val current = sent.copy(revision=4, draft="{\"horizon_months\":\"\"}", valid=false)
        val next = acknowledgeAutoSave(current, sent, JSONObject(sent.draft), 3)
        assertEquals(AutoSavePhase.Invalid, next.phase)
        assertEquals("", JSONObject(next.draft).getString("horizon_months"))
    }
    @Test fun sameRevisionRequiresAcknowledgementBeforeSavedState() {
        val sent = AutoSaveRecord(AutoSaveKind.Notifications, 1, "{}", "{\"enabled\":true}", 0, true, AutoSavePhase.Saving)
        val next = acknowledgeAutoSave(sent, sent, JSONObject(sent.draft), 1)
        assertEquals(AutoSavePhase.Saved, next.phase)
        assertTrue(equivalentJson(JSONObject(next.baseline), JSONObject(next.draft)))
    }
    @Test fun comparisonsIgnoreObjectOrderButPreserveArrayOrderAndNull() {
        assertTrue(equivalentJson(JSONObject("{\"a\":1,\"b\":null}"), JSONObject("{\"b\":null,\"a\":1.0}")))
        assertFalse(equivalentJson(org.json.JSONArray("[1,2]"), org.json.JSONArray("[2,1]")))
        assertFalse(equivalentJson(JSONObject("{\"a\":null}"), JSONObject("{}")))
    }
    @Test fun explicitNullAndDeletionRemainDifferentChanges() {
        val removed = mergeAutoSaveChanges(JSONObject("{\"optional\":null}"), JSONObject("{}"), JSONObject("{\"optional\":null,\"other\":4}"))
        assertFalse(removed.has("optional"))
        assertEquals(4, removed.getInt("other"))
        val added = mergeAutoSaveChanges(JSONObject("{}"), JSONObject("{\"optional\":null}"), JSONObject("{\"other\":4}"))
        assertTrue(added.has("optional")); assertTrue(added.isNull("optional"))
    }
    @Test fun twoGoalsHaveIndependentIdentityEvenAtSameRevision() {
        val a = AutoSaveRecord(AutoSaveKind.Goal, 1, "{}", "{}", 0, true, AutoSavePhase.Pending, documentId = "goal-a")
        val b = a.copy(documentId = "goal-b")
        assertNotEquals(a.key, b.key)
        assertThrows(IllegalArgumentException::class.java) { acknowledgeAutoSave(a, b, JSONObject(), 0) }
    }
    @Test fun serverAssignedGoalIdSurvivesNewerEditsDuringCreation() {
        val original = goalEditableDocument(JSONObject()).put("title", "First")
        val sent = AutoSaveRecord(AutoSaveKind.Goal, 1, "{}", original.toString(), 0, true,
            AutoSavePhase.Saving, documentId = "draft:local")
        val current = sent.copy(revision = 2, draft = JSONObject(original.toString()).put("title", "Second").toString())
        val next = acknowledgeAutoSave(current, sent, JSONObject(original.toString()).put("id", "server-id"), 0)
        assertEquals("server-id", JSONObject(next.draft).getString("id"))
        assertEquals("Second", JSONObject(next.draft).getString("title"))
        assertEquals("draft:local", next.documentId)
    }
    @Test fun profilePresentationMetadataIsNeverSentAsConfiguration() {
        val server = JSONObject().put("risk_level", "moderate").put("configured", true).put("updated_at", "now")
        val writable = analysisEditableDocument(server)
        assertEquals("moderate", writable.getString("risk_level"))
        assertFalse(writable.has("configured")); assertFalse(writable.has("updated_at"))
    }
    @Test fun anotherDocumentCannotSpinAnUncertainFailedRequest() {
        val sent = AutoSaveRecord(AutoSaveKind.Goal, 1, "{}", "{}", 0, true,
            AutoSavePhase.Saving, documentId = "first")
        val failed = sent.copy(phase = AutoSavePhase.Failed)
        val other = sent.copy(documentId = "second", phase = AutoSavePhase.Pending)
        assertNull(nextAutoSaveRecord(listOf(failed, other), sent))
        assertEquals(sent, nextAutoSaveRecord(listOf(failed.copy(phase = AutoSavePhase.Pending), other), sent))
        assertEquals(other, nextAutoSaveRecord(listOf(failed, other), null))
    }
    @Test fun recoveryKeepsTheSubmittedCommandWhenNewerInputIsInvalid() {
        val sent = AutoSaveRecord(AutoSaveKind.Strategy, 1, "{}", "{}", 3, true, AutoSavePhase.Saving)
        val changed = sent.copy(revision = 2, valid = false, phase = AutoSavePhase.Invalid)
        assertEquals(sent, nextAutoSaveRecord(listOf(changed), sent))
        assertNull(nextAutoSaveRecord(listOf(changed), null))
    }
    @Test fun subsequentEditDoesNotRevertAnUnrelatedServerChange() {
        val displayed = JSONObject().put("morning", "09:00").put("evening", "18:00")
        val edited = JSONObject(displayed.toString()).put("morning", "10:00")
        val latest = JSONObject(displayed.toString()).put("evening", "20:00")
        val merged = mergeAutoSaveChanges(displayed, edited, latest)
        assertEquals("10:00", merged.getString("morning"))
        assertEquals("20:00", merged.getString("evening"))
    }
}
