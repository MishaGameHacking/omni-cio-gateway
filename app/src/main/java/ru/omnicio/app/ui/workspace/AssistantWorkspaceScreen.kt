package ru.omnicio.app.ui.workspace

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.semantics.testTagsAsResourceId
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import ru.omnicio.app.ui.spectrum.*
import ru.omnicio.app.ui.theme.LocalSpectrumMotionPreference

/** The conversation surface is ready; no fabricated model reply or silent network send. */
@Composable
fun AssistantWorkspaceScreen(onBack: () -> Unit, onPortfolio: () -> Unit,
    onActions: () -> Unit, onStrategy: () -> Unit) {
    var draft by rememberSaveable { mutableStateOf("") }
    var saved by rememberSaveable { mutableStateOf(false) }
    WorkspaceDetailPage("Ассистент", "Ваше рабочее пространство", onBack) { padding ->
        Column(Modifier.fillMaxSize().padding(padding).consumeWindowInsets(padding).imePadding()) {
            LazyColumn(Modifier.weight(1f).fillMaxWidth().semantics { testTagsAsResourceId = true }.testTag("workspace-content"), contentPadding = PaddingValues(20.dp),
                verticalArrangement = Arrangement.spacedBy(14.dp)) {
                item {
                    SpectrumCard(emphasized = true) {
                        SpectrumAnalystAvatar(AnalystAvatarMood.Waiting, Modifier.size(88.dp),
                            motionAllowed = LocalSpectrumMotionPreference.current.enabled)
                        Text("С чего начнём?", style = MaterialTheme.typography.headlineSmall)
                        Text("Откройте данные или сохраните вопрос для будущего диалога.",
                            color = MaterialTheme.colorScheme.onSurfaceVariant)
                    }
                }
                item { WorkspaceLink("Мой портфель", "Счета, активы и результат", SpectrumSymbol.Portfolio, onPortfolio) }
                item { WorkspaceLink("Что делать сейчас", "Доступные результаты анализа", SpectrumSymbol.Goal, onActions) }
                item { WorkspaceLink("Мои правила", "Риск, горизонт и резерв", SpectrumSymbol.Allocation, onStrategy) }
                if (saved) item {
                    SpectrumCard {
                        Text("Черновик вопроса", style = MaterialTheme.typography.titleMedium)
                        Text(draft)
                        Text("Не отправлен. Чат ещё не подключён.", style = MaterialTheme.typography.bodyMedium,
                            color = MaterialTheme.colorScheme.onSurfaceVariant)
                    }
                }
            }
            Surface(color = LocalSpectrumPalette.current.card) {
                Column(Modifier.fillMaxWidth().padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    OutlinedTextField(draft, { draft = it.take(4000); saved = false },
                        modifier = Modifier.fillMaxWidth(), label = { Text("Ваш вопрос") },
                        placeholder = { Text("Например, объясни изменения портфеля") }, maxLines = 4)
                    SpectrumPrimaryButton("Сохранить черновик", { saved = true }, Modifier.fillMaxWidth(), draft.isNotBlank())
                    Text("Ответы появятся после подключения чата. Вопрос хранится только в текущем сеансе.",
                        style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
            }
        }
    }
}
