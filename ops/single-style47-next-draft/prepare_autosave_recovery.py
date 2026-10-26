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

    # The same session-owned journal also remembers ordinary local selections.
    path = ui+'workspace/WorkspaceAutoSave.kt'
    replace(path, '    internal var inFlight: JSONObject? = null', '''    internal var inFlight: JSONObject? = null
    internal val selections = mutableStateMapOf<String, String>()
    var selectionRevision by mutableLongStateOf(0L); private set
    var savedSelectionRevision by mutableLongStateOf(0L); internal set
    var selectionError by mutableStateOf<String?>(null); internal set
    fun selection(name: String): JSONObject? = selections[name]?.let(::JSONObject)
    fun rememberSelection(name: String, value: JSONObject) {
        require(name in setOf("portfolio_filters", "chat_context_editor"))
        if (!ready || selections[name]?.let { equivalentJson(JSONObject(it), value) } == true) return
        selections[name] = value.toString()
        selectionRevision++
        selectionError = null
        storeWake.trySend(Unit)
    }''')
    replace(path, '            entries to command', '''            val memory = restored?.optJSONObject("selections") ?: JSONObject()
            val selections = memory.keys().asSequence().associateWith { name ->
                check(name in setOf("portfolio_filters", "chat_context_editor"))
                memory.getJSONObject(name).toString()
            }
            Triple(entries, command, selections)''')
    replace(path, '        controller.inFlight = recovered.second', '''        controller.inFlight = recovered.second
        controller.selections.clear()
        controller.selections.putAll(recovered.third)''')
    replace(path, '''                .put("in_flight", controller.inFlight ?: JSONObject.NULL)
            withContext(Dispatchers.IO) { storage.saveJson(session.userId, key, value) }''', '''                .put("in_flight", controller.inFlight ?: JSONObject.NULL)
                .put("selections", JSONObject().apply {
                    controller.selections.forEach { (name, content) -> put(name, JSONObject(content)) }
                })
            val revision = controller.selectionRevision
            val saved = withContext(Dispatchers.IO) { storage.saveJson(session.userId, key, value) }
            if (saved) {
                controller.savedSelectionRevision = maxOf(controller.savedSelectionRevision, revision)
                controller.selectionError = null
            } else if (controller.selectionRevision > controller.savedSelectionRevision) {
                controller.selectionError = "Выбор ещё не записан на устройстве. Повторяем сохранение…"
            }
            saved''')
    replace(path, '                    delay(2_000)', '''                    delay(2_000)
                    if (controller.selectionRevision > controller.savedSelectionRevision) controller.storeWake.trySend(Unit)''')

    path = ui+'portfolio/PortfolioAssetBrowser.kt'
    replace(path, '    val personal = rememberPersonalWorkspace()', '''    val memory = LocalWorkspaceAutoSave.current
    val memoryUser = LocalWorkspaceSession.current.userId
    var selectionsRestored by rememberSaveable(memoryUser) { mutableStateOf(memory == null) }
    val personal = rememberPersonalWorkspace()''')
    replace(path, '    val allCurrent = snapshot.accounts.flatMap', '''    LaunchedEffect(memoryUser, memory?.ready, initialQuery, initialKind, initialSector, selectedAccount) {
        if (selectionsRestored || memory?.ready == false) return@LaunchedEffect
        memory?.selection("portfolio_filters")?.let { saved ->
            if (selectedAccount == null) accountId = saved.optString("account_id").takeUnless { it.isBlank() || it == "null" }
            if (initialQuery.isBlank()) query = saved.optString("query", "")
            if (initialKind == null) kind = saved.optString("kind", "all")
            if (initialSector == null) sector = saved.optString("sector").takeUnless { it.isBlank() || it == "null" }
            group = saved.optInt("group", 0).coerceIn(0, 4)
            order = saved.optInt("order", 0).coerceIn(0, 3)
            onlyWatched = saved.optBoolean("only_watched")
            showRestricted = saved.optBoolean("show_restricted")
            showCash = saved.optBoolean("show_cash")
            exposureId = saved.optString("exposure_id").takeUnless { it.isBlank() || it == "null" }
        }
        selectionsRestored = true
    }
    LaunchedEffect(memory?.ready, selectionsRestored, accountId, query, kind, sector, group, order, onlyWatched, showRestricted, showCash, exposureId) {
        if (selectionsRestored) memory?.rememberSelection("portfolio_filters", org.json.JSONObject()
            .put("account_id", accountId ?: org.json.JSONObject.NULL).put("query", query).put("kind", kind)
            .put("sector", sector ?: org.json.JSONObject.NULL).put("group", group).put("order", order)
            .put("only_watched", onlyWatched).put("show_restricted", showRestricted).put("show_cash", showCash)
            .put("exposure_id", exposureId ?: org.json.JSONObject.NULL))
    }
    val allCurrent = snapshot.accounts.flatMap''')
    replace(path, '    Column(modifier.fillMaxWidth()) {', '''    if (!selectionsRestored) {
        Column(modifier.fillMaxWidth().padding(20.dp)) {
            SpectrumLoadingIndicator(description = "Восстанавливаем ваш выбор")
            AutoSaveStatus(null) { memory?.retry(AutoSaveKind.Notifications) }
        }
        return
    }
    Column(modifier.fillMaxWidth()) {
        memory?.selectionError?.let { Text(it, Modifier.padding(horizontal = 20.dp), color = MaterialTheme.colorScheme.error) }''')

    # The isolated fixtures must mount the production provider too.
    path = 'app/src/debug/java/ru/omnicio/app/BusinessWorkspaceProbe.kt'
    replace(path, '            if (navigationFixture) {',
        '            if (navigationFixture) WorkspaceAutoSaveProvider {')
    replace(path, '            } else Box(Modifier.fillMaxSize()) { workspace() }',
        '            } else WorkspaceAutoSaveProvider { Box(Modifier.fillMaxSize()) { workspace() } }')
    path = 'app/src/debug/java/ru/omnicio/app/PortfolioWorkspaceProbe.kt'
    replace(path, '            Box(Modifier.fillMaxSize()) {\n                savedPages.SaveableStateProvider(page) {',
        '            WorkspaceAutoSaveProvider { Box(Modifier.fillMaxSize()) {\n                savedPages.SaveableStateProvider(page) {')
    value = get(path)
    start = value.index('            WorkspaceAutoSaveProvider { Box(Modifier.fillMaxSize()) {')
    # Close the new provider immediately after its original Box.
    level = 0
    opening = value.index('{ Box(', start)
    box_open = value.index('{', opening + 1)
    end = None
    # Use a fixed semantic end anchor rather than scanning braces inside Kotlin strings.
    anchor = '\n            }\n        }\n    }\n}'
    end = value.index(anchor, box_open)
    files[path] = value[:end] + value[end:].replace(anchor, '\n            } }\n        }\n    }\n}', 1)

    path = ui+'workspace/ChatContextEditor.kt'
    replace(path, '    val select = LocalAskAnalyst.current', '''    val select = LocalAskAnalyst.current
    val memory = LocalWorkspaceAutoSave.current
    var restored by rememberSaveable { mutableStateOf(memory == null) }''')
    replace(path, '    var keepEvent by rememberSaveable(current.eventId) { mutableStateOf(current.eventId != null) }',
        '''    val contextEventId by rememberSaveable { mutableStateOf(current.eventId) }
    val contextInstrument by rememberSaveable { mutableStateOf(current.instrumentUid) }
    var keepEvent by rememberSaveable { mutableStateOf(current.eventId != null) }''')
    replace(path, '    WorkspaceDialog("Контекст следующего вопроса", onClose) {', '''    LaunchedEffect(memory?.ready) {
        if (restored || memory?.ready == false) return@LaunchedEffect
        memory?.selection("chat_context_editor")?.takeIf {
            it.optJSONObject("context")?.let { origin -> equivalentJson(origin, current.json()) } == true
        }?.let { saved ->
            mode = saved.optInt("mode", 1).coerceIn(0, 2)
            accountId = saved.optString("account_id").takeUnless { it.isBlank() || it == "null" }
            instrument = saved.optString("instrument").takeUnless { it.isBlank() || it == "null" }
            start = saved.optString("start", ""); end = saved.optString("end", "")
            keepEvent = saved.optBoolean("keep_event")
        }
        restored = true
    }
    val valid = (mode == 0 || validAccount && validRange) && (mode != 2 || selected != null)
    LaunchedEffect(memory?.ready, restored, mode, accountId, instrument, start, end, keepEvent, valid, selected?.title) {
        if (!restored || memory?.ready == false) return@LaunchedEffect
        memory?.rememberSelection("chat_context_editor", JSONObject().put("context", current.json())
            .put("mode", mode).put("account_id", accountId ?: JSONObject.NULL)
            .put("instrument", instrument ?: JSONObject.NULL).put("start", start).put("end", end)
            .put("keep_event", keepEvent))
        if (valid) {
            val title = when (mode) {
                0 -> "Общий вопрос"
                2 -> selected?.title.orEmpty()
                else -> accounts.firstOrNull { it.id == accountId }?.name ?: "Мой портфель"
            }
            val next = editedChatContext(mode, title, instrument, accountId, start to end,
                contextEventId.takeIf { keepEvent && instrument == contextInstrument })
            if (!equivalentJson(current.json(), next.json()) || current.title != next.title) select(next)
        }
    }
    WorkspaceDialog("Контекст следующего вопроса", onClose) {
        if (!restored) {
            SpectrumLoadingIndicator(description = "Восстанавливаем ваш выбор")
            AutoSaveStatus(null) { memory?.retry(AutoSaveKind.Notifications) }
            return@WorkspaceDialog
        }
        Text(memory?.selectionError ?: if (memory != null && memory.savedSelectionRevision < memory.selectionRevision) "Запоминаем выбор…"
            else if (valid) "Выбор применяется автоматически" else
            "Дополните выбранные значения для применения.", style = MaterialTheme.typography.bodySmall)''')
    replace(path, 'if (instrument == current.instrumentUid && current.eventId != null)',
        'if (instrument == contextInstrument && contextEventId != null)')
    replace(path, '''            WorkspaceChoices("Счета", listOf("Все мои счета") + accounts.map { it.name }, if (validAccount) accountIndex + 1 else -1) {
                accountId = if (it == 0) null else accounts[it - 1].id; instrument = null
            }''', '''            WorkspaceChoicePicker("Счёт", accountId.orEmpty(), listOf(WorkspaceSuggestion("", "Все мои счета")) +
                accounts.map { WorkspaceSuggestion(it.id, it.name) }) {
                accountId = it.takeIf(String::isNotBlank); instrument = null
            }''')
    value = get(path)
    start = value.index('        SpectrumPrimaryButton("Использовать этот контекст", {')
    end = value.index('        SpectrumSecondaryButton("Вернуться", onClose, Modifier.fillMaxWidth())', start)
    value = value[:start] + '        SpectrumSecondaryButton("Готово", onClose, Modifier.fillMaxWidth())' + value[end+len('        SpectrumSecondaryButton("Вернуться", onClose, Modifier.fillMaxWidth())'):]
    files[path] = value
