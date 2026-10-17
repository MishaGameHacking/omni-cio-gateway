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
    WorkspaceDetailPage("Ассистент", "Ваше рабочее пространство", onBack, SpectrumSymbol.Analyst) { padding ->
        Column(Modifier.fillMaxSize().padding(padding).consumeWindowInsets(padding).imePadding()) {
            LazyColumn(Modifier.fillMaxSize().semantics { testTagsAsResourceId = true }.testTag("workspace-content"), contentPadding = PaddingValues(20.dp),
                verticalArrangement = Arrangement.spacedBy(14.dp)) {
                item {
                    SpectrumCard(emphasized = true) {
                        Row(verticalAlignment = androidx.compose.ui.Alignment.CenterVertically,
                            horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                            SpectrumAnalystAvatar(AnalystAvatarMood.Waiting, Modifier.size(64.dp),
                                motionAllowed = LocalSpectrumMotionPreference.current.enabled)
                            Text("С чего начнём?", Modifier.weight(1f), style = MaterialTheme.typography.titleLarge)
                        }
                        Text("Откройте данные или сохраните вопрос для будущего диалога.",
                            color = MaterialTheme.colorScheme.onSurfaceVariant)
                    }
                }
                if (saved) item {
                    SpectrumCard {
                        Text("Черновик вопроса", style = MaterialTheme.typography.titleMedium)
                        Text(draft)
                        Text("Не отправлен. Чат ещё не подключён.", style = MaterialTheme.typography.bodyMedium,
                            color = MaterialTheme.colorScheme.onSurfaceVariant)
                    }
                }
                item(key = "composer") {
                    SpectrumCard {
                            OutlinedTextField(draft, { draft = it.take(4000); saved = false },
                                modifier = Modifier.fillMaxWidth(), label = { Text("Ваш вопрос") },
                                placeholder = { Text("Например, объясни изменения портфеля") }, maxLines = 4)
                            SpectrumPrimaryButton("Сохранить черновик", { saved = true }, Modifier.fillMaxWidth(), draft.isNotBlank())
                            Text("Ответы появятся после подключения чата. Вопрос хранится только в текущем сеансе.",
                                style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    }
                }
                item { WorkspaceSection("Быстрый переход") }
                item { WorkspaceLink("Мой портфель", "Счета, активы и результат", SpectrumSymbol.Portfolio, onPortfolio) }
                item { WorkspaceLink("Что делать сейчас", "Доступные результаты анализа", SpectrumSymbol.Goal, onActions) }
                item { WorkspaceLink("Мои правила", "Риск, горизонт и резерв", SpectrumSymbol.Allocation, onStrategy) }
            }
        }
    }
}
