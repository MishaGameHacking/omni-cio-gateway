package ru.omnicio.app

import androidx.activity.ComponentActivity
import androidx.compose.foundation.layout.*
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.dp
import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import kotlinx.coroutines.flow.MutableStateFlow
import org.json.JSONArray
import org.json.JSONObject
import ru.omnicio.app.data.workspace.VolumeReply
import ru.omnicio.app.data.workspace.WorkspaceTransport
import ru.omnicio.app.ui.workspace.*

private const val GOAL_PATH = "/workspace/goals"
private const val FIXTURE_TOKEN = "debug-goal-fixture"

/** Production goal editor, with a disclosed lost-response fixture and no network client. */
@Composable
internal fun GoalWorkflowProbe(onBack: () -> Unit) {
    val activity = LocalContext.current as ComponentActivity
    val transport = remember(activity) { ViewModelProvider(activity)[GoalProbeTransport::class.java] }
    val marker by transport.marker.collectAsState()
    var revision by remember { mutableIntStateOf(0) }
    Column(Modifier.fillMaxSize()) {
        Text("ВИЗУАЛЬНЫЙ ТЕСТ · НЕ РЕАЛЬНЫЕ ДАННЫЕ", style = MaterialTheme.typography.labelSmall,
            modifier = Modifier.statusBarsPadding().padding(6.dp).semantics { contentDescription = marker })
        CompositionLocalProvider(LocalWorkspaceSession provides WorkspaceSession(FIXTURE_TOKEN, "synthetic-goal-owner"),
            LocalWorkspaceTransport provides transport, LocalWorkspaceRefreshKey provides revision,
            LocalWorkspaceInvalidate provides { revision++ }) {
            Box(Modifier.weight(1f)) { GoalsWorkspaceScreen(onBack) }
        }
    }
}

/** Retained across Activity recreation; dropped when this isolated fixture finishes. */
class GoalProbeTransport : ViewModel(), WorkspaceTransport {
    private var goal: JSONObject? = null
    private var submitted: String? = null
    private var receipt: JSONObject? = null
    private var posts = 0
    private var creates = 0
    private var sameRequest = true
    val marker = MutableStateFlow("")

    @Synchronized
    override fun request(token: String, path: String, method: String, body: JSONObject?): VolumeReply {
        require(token == FIXTURE_TOKEN)
        val result = when {
            method == "GET" && path == GOAL_PATH -> VolumeReply(data = JSONObject().put("items", JSONArray().apply { goal?.let { put(it) } }))
            method == "POST" && path == GOAL_PATH -> save(checkNotNull(body))
            method == "DELETE" && path == "$GOAL_PATH/synthetic-goal" -> {
                goal = null
                VolumeReply(data = JSONObject().put("deleted", true))
            }
            else -> error("Unexpected goal fixture request: $method $path")
        }
        marker.value = "goal-workflow;posts:$posts;creates:$creates;records:${if (goal == null) 0 else 1};same-request:$sameRequest"
        return result
    }

    private fun save(body: JSONObject): VolumeReply {
        posts++
        if (submitted != null) {
            sameRequest = submitted == body.toString()
            check(sameRequest) { "The unconfirmed goal request changed before recovery" }
            return VolumeReply(data = JSONObject(checkNotNull(receipt).toString()))
        }
        check(body.getString("title") == "GoalDraft" && body.getJSONObject("target").getString("amount") == "500000")
        check(body.getJSONObject("target").getString("currency") == "RUB" && body.getJSONObject("reserve").getString("amount") == "0")
        check(body.getString("request_id").isNotBlank() && body.isNull("id"))
        submitted = body.toString()
        creates++
        receipt = JSONObject(body.toString()).put("id", "synthetic-goal")
        goal = JSONObject(checkNotNull(receipt).toString())
            .put("current", JSONObject().put("amount", "100000").put("currency", "RUB"))
            .put("progress_percent", "20").put("as_of", "2026-10-17T10:00:00Z")
        return VolumeReply(error = "Тест: ответ после сохранения потерян.", code = "network_unavailable", ambiguous = true)
    }
}
