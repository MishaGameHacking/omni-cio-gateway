package ru.omnicio.app.ui.workspace

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.semantics.testTagsAsResourceId
import androidx.compose.ui.unit.dp
import ru.omnicio.app.ui.spectrum.*

@Composable
fun AssistantWorkspaceScreen(onBack: () -> Unit, onPortfolio: () -> Unit,
    onActions: () -> Unit, onStrategy: () -> Unit) {
    WorkspaceDetailPage("Ассистент", "Данные, объяснения и следующий шаг", onBack, SpectrumSymbol.Analyst) { padding ->
        LazyColumn(Modifier.fillMaxSize().padding(padding).consumeWindowInsets(padding)
            .semantics { testTagsAsResourceId = true }.testTag("workspace-content"), contentPadding = PaddingValues(20.dp),
            verticalArrangement = Arrangement.spacedBy(workspaceGap)) {
            item { WorkspaceEmpty("Диалог ещё не подключён", "Сейчас доступны обзоры и исследования. В будущем вопрос из карточки актива будет открываться с контекстом выбранной позиции.") }
            item { WorkspaceLink("Мой портфель", "Активы и реальные данные счетов", SpectrumSymbol.Portfolio, onPortfolio) }
            item { WorkspaceLink("Что делать сейчас", "Доступный анализ и план", SpectrumSymbol.Goal, onActions) }
            item { WorkspaceLink("Моя стратегия", "Действующие правила и черновик", SpectrumSymbol.Allocation, onStrategy) }
        }
    }
}
