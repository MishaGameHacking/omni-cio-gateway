"""Source-text continuation for independent goal and analysis-profile autosave."""

def apply(files, base):
    ui='app/src/main/java/ru/omnicio/app/ui/'
    def get(p): return files[p] if p in files else base(p)
    def replace(p,old,new,count=1):
        s=get(p); assert s.count(old)==count,(p,old[:100],s.count(old)); files[p]=s.replace(old,new)

    files[ui+'workspace/AutoSaveDocuments.kt']='''package ru.omnicio.app.ui.workspace

import org.json.JSONArray
import org.json.JSONObject
import ru.omnicio.app.data.analysis.AnalysisProfile

internal fun goalEditableDocument(goal: JSONObject): JSONObject = JSONObject()
    .put("id", goal.optionalText("id") ?: JSONObject.NULL).put("title", goal.optString("title", ""))
    .put("target", goal.optJSONObject("target") ?: JSONObject().put("amount", "").put("currency", "RUB"))
    .put("reserve", goal.optJSONObject("reserve") ?: JSONObject().put("amount", "0").put("currency", "RUB"))

internal fun goalDocumentValid(goal: JSONObject): Boolean {
    val target = goal.optJSONObject("target") ?: return false
    val reserve = goal.optJSONObject("reserve") ?: return false
    return goal.optString("title").trim().isNotEmpty() && goal.optString("title").length <= 100 &&
        target.optString("amount").toBigDecimalOrNull()?.signum() == 1 &&
        reserve.optString("amount").toBigDecimalOrNull()?.signum()?.let { it >= 0 } == true &&
        target.optString("currency") in listOf("RUB", "USD", "EUR") &&
        reserve.optString("currency") == target.optString("currency")
}

/** Server presentation fields never become writable preferences. */
internal fun analysisEditableDocument(value: JSONObject): JSONObject {
    val result = JSONObject()
    listOf("risk_level", "horizon", "allowed_markets", "max_position_percent", "min_cash_percent",
        "notify_critical", "notify_briefs").forEach { key -> if (value.has(key)) result.put(key, value.get(key)) }
    return result
}

fun AnalysisProfile.automaticDocument(): JSONObject = JSONObject().put("risk_level", riskLevel).put("horizon", horizon)
    .put("allowed_markets", JSONArray(allowedMarkets)).put("max_position_percent", maxPositionPercent)
    .put("min_cash_percent", minCashPercent).put("notify_critical", notifyCritical).put("notify_briefs", notifyBriefs)

fun automaticAnalysisProfile(value: JSONObject): AnalysisProfile = AnalysisProfile(
    riskLevel = value.getString("risk_level"), horizon = value.getString("horizon"),
    allowedMarkets = value.getJSONArray("allowed_markets").let { rows -> (0 until rows.length()).map { rows.getString(it) } },
    maxPositionPercent = value.getDouble("max_position_percent"), minCashPercent = value.getDouble("min_cash_percent"),
    notifyCritical = value.getBoolean("notify_critical"), notifyBriefs = value.getBoolean("notify_briefs"), configured = true)
'''
    replace(ui+'workspace/WorkspaceAutoSave.kt','AutoSaveKind.Analysis -> data','AutoSaveKind.Analysis -> analysisEditableDocument(data)',2)
    path='app/src/main/java/ru/omnicio/app/data/workspace/WorkspaceEndpointPolicy.kt'
    replace(path,'path.startsWith("/workspace?") || path in automationPaths',
        'path.startsWith("/workspace?") || path == "/analysis/profile" || path in automationPaths')

    path=ui+'workspace/PersonalWorkspaceScreens.kt'
    value=get(path)
    value=value.replace('    val editing = goals.firstOrNull { it.text("id") == editingId }','''    val auto = LocalWorkspaceAutoSave.current
    val records = auto?.documents(AutoSaveKind.Goal).orEmpty()
    val pendingGoals = records.filter { it.phase != AutoSavePhase.Saved }
    val editingRecord = records.firstOrNull { it.documentId == editingId }
    val editing = goals.firstOrNull { it.text("id") == editingId }
        ?: editingRecord?.let { JSONObject(it.draft) }
''')
    value=value.replace('editingId = null; open = true','editingId = "draft:" + UUID.randomUUID().toString(); open = true')
    value=value.replace('editingId = goal.text("id"); open = true',
        'editingId = records.firstOrNull { JSONObject(it.draft).optionalText("id") == goal.text("id") }?.documentId ?: goal.text("id"); open = true')
    value=value.replace('!action.busy, symbol = SpectrumSymbol.Goal)', 'auto?.ready == true && !action.busy, symbol = SpectrumSymbol.Goal)')
    anchor='            items(resource.data?.records("items").orEmpty(), key = { it.text("id") }) { goal ->'
    assert value.count(anchor)==1
    value=value.replace(anchor,'''            if (pendingGoals.isNotEmpty()) item { SpectrumCard {
                Text("Изменения целей", style = MaterialTheme.typography.titleMedium)
                pendingGoals.forEach { pending ->
                    SpectrumTextButton(JSONObject(pending.draft).optString("title").ifBlank { "Новая цель" },
                        { editingId = pending.documentId; open = true }, symbol = SpectrumSymbol.Goal)
                    AutoSaveStatus(pending) { auto?.retry(AutoSaveKind.Goal, pending.documentId) }
                }
            } }
'''+anchor)
    a=value.index('    if (open && (editingId == null || editing != null)) GoalEditor(')
    b=value.index('    deleting?.let',a)
    value=value[:a]+'''    if (open && editingId != null && (editingId!!.startsWith("draft:") || editing != null)) {
        GoalEditor(editingId!!, editing, { open = false }, resource.refresh)
    }
    if (open && editingId != null && !editingId!!.startsWith("draft:") && editing == null && resource.data != null && !resource.busy) {
        WorkspaceDialog("Цель больше недоступна", { open = false }) {
            Text("Выбранная цель отсутствует в текущем ответе сервера. Новая цель вместо неё не создаётся.")
            SpectrumSecondaryButton("К списку целей", { open = false }, Modifier.fillMaxWidth())
        }
    }
'''+value[b:]
    a=value.index('@Composable\nprivate fun GoalEditor('); b=value.index('@Composable\nfun RecentWorkspaceScreen',a)
    value=value[:a]+'''@Composable
private fun GoalEditor(documentId: String, existing: JSONObject?, close: () -> Unit, refresh: () -> Unit) {
    val auto = LocalWorkspaceAutoSave.current
    val record = auto?.get(AutoSaveKind.Goal, documentId)
    val baseline = remember(existing?.toString()) { goalEditableDocument(existing ?: JSONObject()) }
    val config = remember(record?.draft, baseline.toString()) { record?.draft?.let(::JSONObject) ?: baseline }
    val editable = auto?.ready == true
    val edit: (JSONObject) -> Unit = { next ->
        auto?.edit(AutoSaveKind.Goal, baseline, next, 0, goalDocumentValid(next), documentId)
    }
    LaunchedEffect(record?.phase, record?.revision) { if (record?.phase == AutoSavePhase.Saved) refresh() }
    WorkspaceDialog(if (config.optionalText("id") == null) "Новая цель" else "Изменить цель", close) {
        AutoSaveStatus(record) { auto?.retry(AutoSaveKind.Goal, documentId) }
        WorkspaceTextInput(config.optString("title"), { edit(JSONObject(config.toString()).put("title", it.take(100))) },
            "Название", Modifier.fillMaxWidth().testTag("goal-title"), enabled = editable)
        val target = config.getJSONObject("target")
        val reserve = config.getJSONObject("reserve")
        WorkspaceTextInput(target.optString("amount"), {
            edit(JSONObject(config.toString()).put("target", JSONObject(target.toString()).put("amount", it.replace(',', '.').take(18))))
        }, "Целевая сумма", Modifier.fillMaxWidth().testTag("goal-amount"), enabled = editable,
            keyboard = KeyboardOptions(keyboardType = KeyboardType.Decimal))
        WorkspaceTextInput(reserve.optString("amount"), {
            edit(JSONObject(config.toString()).put("reserve", JSONObject(reserve.toString()).put("amount", it.replace(',', '.').take(18))))
        }, "Резерв", Modifier.fillMaxWidth(), enabled = editable, keyboard = KeyboardOptions(keyboardType = KeyboardType.Decimal))
        WorkspaceChoicePicker("Валюта", target.optString("currency"), listOf("RUB", "USD", "EUR").map {
            WorkspaceSuggestion(it, it)
        }, editable) { currency ->
            edit(JSONObject(config.toString()).put("target", JSONObject(target.toString()).put("currency", currency))
                .put("reserve", JSONObject(reserve.toString()).put("currency", currency)))
        }
        Text("Корректные значения применяются автоматически. Незавершённый ввод сохраняется на устройстве.", style = MaterialTheme.typography.bodySmall)
        SpectrumSecondaryButton("Готово", close, Modifier.fillMaxWidth())
    }
}

'''+value[b:]
    files[path]=value

    path=ui+'analysis/AnalysisScreens.kt'
    value=get(path)
    if 'import org.json.JSONObject' not in value: value=value.replace('package ru.omnicio.app.ui.analysis\n','package ru.omnicio.app.ui.analysis\n\nimport org.json.JSONObject\n')
    a=value.index('    var section by rememberSaveable',value.index('private fun AnalysisProfileContent('))
    b=value.index('@Composable\nprivate fun MonitoringStatus',a)
    value=value[:a]+'''    var section by rememberSaveable { mutableIntStateOf(initialSection.coerceIn(0, 2)) }
    val client = remember { AnalysisBackendClient() }
    val auto = LocalWorkspaceAutoSave.current
    val record = auto?.get(AutoSaveKind.Analysis)
    val resource = rememberWorkspaceResource("/analysis/profile")
    val profile = remember(record?.draft, resource.data?.toString()) {
        runCatching { automaticAnalysisProfile(record?.draft?.let(::JSONObject) ?: resource.data ?: return@remember null) }.getOrNull()
    }
    var status by remember { mutableStateOf<AnalysisStatus?>(null) }
    BackHandler(onBack = onBack)
    LaunchedEffect(token) {
        when (val result = withContext(Dispatchers.IO) { client.fetchStatus(token) }) {
            is BackendResult.Success -> status = result.value
            is BackendResult.Failure -> status = null
        }
    }
    AnalysisScaffold(selected = AnalystTab.Profile, title = "Инвестиционный профиль",
        subtitle = "Настройки применяются автоматически", symbol = SpectrumSymbol.Profile,
        onPortfolioClick = onPortfolioClick, onProfileClick = onProfileClick, modifier = modifier,
        showBottomBar = false) { padding ->
        LazyColumn(Modifier.fillMaxSize().padding(padding).consumeWindowInsets(padding),
            contentPadding = PaddingValues(20.dp), verticalArrangement = Arrangement.spacedBy(workspaceGap)) {
            item(key = "back") { SpectrumSecondaryButton("Назад", onBack, Modifier.fillMaxWidth()) }
            item { WorkspaceRequestState(resource); AutoSaveStatus(record) { auto?.retry(AutoSaveKind.Analysis) } }
            if (profile != null) {
                item { SpectrumTabs(listOf("Правила", "Уведомления", "Наблюдение"), section, { section = it }) }
                if (section == 2) item { MonitoringStatus(status) }
                if (section == 1) item { NotificationDeliverySettingsLink(enabled = true) }
                profileControls(profile, section, enabled = auto?.ready == true) { changed ->
                    auto?.edit(AutoSaveKind.Analysis, resource.data?.let(::analysisEditableDocument) ?: profile.automaticDocument(),
                        changed.automaticDocument(), 0, supportedProfile(changed))
                }
                if (!supportedProfile(profile)) item { Text("Проверьте значения профиля. Применение приостановлено.") }
            }
        }
    }
}

'''+value[b:]
    files[path]=value

    path='app/src/test/java/ru/omnicio/app/ui/workspace/AutoSaveModelTest.kt'
    value=get(path); end=value.rfind('}')
    value=value[:end]+'''    @Test fun twoGoalsHaveIndependentIdentityEvenAtSameRevision() {
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
'''+value[end:]; files[path]=value

