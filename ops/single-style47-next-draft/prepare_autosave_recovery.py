"""Administrative source-text corrections; application/test execution stays on Windows."""

def apply(files, base):
    ui = 'app/src/main/java/ru/omnicio/app/ui/'
    def get(path): return files[path] if path in files else base(path)
    def replace(path, old, new, count=1):
        value = get(path)
        assert value.count(old) == count, (path, old[:100], value.count(old))
        files[path] = value.replace(old, new)

    # Compare a new edit to exactly the values shown, never a stale GET response.
    replace(ui+'workspace/NotificationWorkspaceScreens.kt',
        'auto?.edit(AutoSaveKind.Notifications, remote ?: JSONObject(), next, remoteVersion ?: -1, notificationRulesValid(next))',
        'auto?.edit(AutoSaveKind.Notifications, JSONObject(config.toString()), next, remoteVersion ?: -1, notificationRulesValid(next))')
    replace(ui+'workspace/LiveStrategyScreen.kt',
        'auto?.edit(AutoSaveKind.Strategy, active?.optJSONObject("config") ?: defaultStrategy(), next,',
        'auto?.edit(AutoSaveKind.Strategy, config, next,')
    replace(ui+'analysis/AnalysisScreens.kt',
        'auto?.edit(AutoSaveKind.Analysis, resource.data?.let(::analysisEditableDocument) ?: profile.automaticDocument(),',
        'auto?.edit(AutoSaveKind.Analysis, profile.automaticDocument(),')
    replace(ui+'workspace/PersonalWorkspaceScreens.kt',
        'auto?.edit(AutoSaveKind.Goal, baseline, next, 0, goalDocumentValid(next), documentId)',
        'auto?.edit(AutoSaveKind.Goal, config, next, 0, goalDocumentValid(next), documentId)')

    path = ui+'workspace/AutoSaveModel.kt'
    files[path] = get(path) + '''
/** An uncertain command keeps its identity, but another document cannot bypass its retry delay. */
internal fun nextAutoSaveRecord(records: Collection<AutoSaveRecord>, recovery: AutoSaveRecord?): AutoSaveRecord? {
    if (recovery != null) {
        val current = records.firstOrNull { it.key == recovery.key } ?: return null
        return recovery.takeUnless { current.phase == AutoSavePhase.Failed }
    }
    return records.firstOrNull { it.phase == AutoSavePhase.Pending && it.valid }
}
'''
    path = ui+'workspace/WorkspaceAutoSave.kt'
    replace(path, '''            val sent = if (recovery != null) runCatching { restoreAutoSaveRecord(recovery.getJSONObject("record")) }.getOrNull()
                else controller.records.values.firstOrNull { it.phase == AutoSavePhase.Pending && it.valid }''',
        '''            val recovering = recovery?.let { restoreAutoSaveRecord(it.getJSONObject("record")) }
            val sent = nextAutoSaveRecord(controller.records.values, recovering)''')
    replace(path, '            if (controller.records.values.any { it.phase == AutoSavePhase.Pending && it.valid }) controller.wake.trySend(Unit)',
        '            if (controller.inFlight == null && controller.records.values.any { it.phase == AutoSavePhase.Pending && it.valid }) controller.wake.trySend(Unit)')
    replace(path, '                            check(preview.optBoolean("can_confirm")) { "Сервер пока не разрешил применить эти правила." }',
        '''                            check(preview.optBoolean("can_confirm")) {
                                val warnings = preview.optJSONObject("impact")?.optJSONArray("warnings")
                                (0 until (warnings?.length() ?: 0)).mapNotNull { index ->
                                    warnings?.optString(index)?.takeIf(String::isNotBlank)
                                }.joinToString("\\n").ifBlank { "Сервер пока не разрешил применить эти правила." }
                            }''')

    # Do not hide a partially corrupted journal by silently dropping individual records.
    replace(path, '''        controller.loadError = null
        restored?.optJSONArray("records")?.let { rows ->
            for (index in 0 until rows.length()) runCatching { restoreAutoSaveRecord(rows.getJSONObject(index)) }
                .getOrNull()?.let { controller.records[it.key] = it }
        }
        controller.inFlight = restored?.optJSONObject("in_flight")''', '''        val recovered = runCatching {
            val rows = restored?.getJSONArray("records") ?: JSONArray()
            val entries = (0 until rows.length()).map { restoreAutoSaveRecord(rows.getJSONObject(it)) }
            check(entries.map { it.key }.distinct().size == entries.size)
            check(entries.all { it.revision > 0 && it.version >= 0 })
            val command = restored?.optJSONObject("in_flight")
            command?.let {
                val submitted = restoreAutoSaveRecord(it.getJSONObject("record"))
                check(entries.any { current -> current.key == submitted.key && current.revision >= submitted.revision })
                check(it.getInt("version") >= 0 && it.getString("request_id").isNotBlank())
                it.getJSONObject("config")
                if (submitted.kind == AutoSaveKind.Strategy) it.getString("preview_id")
            }
            entries to command
        }.getOrElse {
            controller.loadError = "Не удалось восстановить журнал изменений. Сохранённые данные оставлены без изменений."
            return@LaunchedEffect
        }
        controller.loadError = null
        controller.records.clear()
        recovered.first.forEach { controller.records[it.key] = it }
        controller.inFlight = recovered.second''')

    replace(ui+'workspace/LiveStrategyScreen.kt',
        '                item { WorkspaceRequestState(resource); AutoSaveStatus(record) { auto?.retry(AutoSaveKind.Strategy) } }',
        '''                item {
                    WorkspaceRequestState(resource)
                    Text(if (version > 0) "Действует версия $version" else "Активной версии пока нет",
                        style = MaterialTheme.typography.labelLarge)
                    AutoSaveStatus(record) { auto?.retry(AutoSaveKind.Strategy) }
                }''')

    path = 'app/src/test/java/ru/omnicio/app/ui/workspace/AutoSaveModelTest.kt'
    value = get(path)
    end = value.rfind('}')
    files[path] = value[:end] + '''    @Test fun anotherDocumentCannotSpinAnUncertainFailedRequest() {
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
''' + value[end:]
