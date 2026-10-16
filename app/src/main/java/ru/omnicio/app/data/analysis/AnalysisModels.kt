package ru.omnicio.app.data.analysis

data class AnalysisEvidence(
    val fact: String,
    val sourceId: String,
    val asOf: String,
)

data class InsightCard(
    val id: String,
    val kind: String,
    val severity: String,
    val title: String,
    val summary: String,
    val actions: List<String>,
    val evidence: List<AnalysisEvidence>,
    val uncertainties: List<String>,
    val validUntil: String?,
    val isRead: Boolean,
    val createdAt: String,
)

data class InsightFeed(
    val unreadCount: Int,
    val cards: List<InsightCard>,
)

data class AnalysisIdea(
    val assetClass: String,
    val currentPercent: Double,
    val targetPercent: Double,
    val gapPercent: Double,
    val suggestedMaxPercent: Double,
    val explanation: String,
)

data class IdeasPayload(
    val state: String,
    val message: String,
    val cashSharePercent: Double?,
    val reservePercent: Double?,
    val ideas: List<AnalysisIdea>,
)

data class AnalysisProfile(
    val riskLevel: String,
    val horizon: String,
    val allowedMarkets: List<String>,
    val maxPositionPercent: Double,
    val minCashPercent: Double,
    val notifyCritical: Boolean,
    val notifyBriefs: Boolean,
    val configured: Boolean,
)

data class AnalysisRunStatus(
    val state: String,
    val reason: String,
    val tier: String,
    val model: String?,
    val errorCode: String?,
    val createdAt: String,
)

data class PortfolioMonitoringStatus(
    val state: String,
    val lastSnapshotAt: String?,
)

data class AnalysisStatus(
    val schedulerEnabled: Boolean,
    val aiConfigured: Boolean,
    val deterministicMonitoring: Boolean,
    val unreadCount: Int,
    val profileConfigured: Boolean,
    val lastRun: AnalysisRunStatus?,
    val monitoring: PortfolioMonitoringStatus? = null,
)

data class RefreshResult(
    val state: String,
    val reason: String,
    val tier: String,
    val model: String?,
    val cardId: String?,
    val errorCode: String?,
)
