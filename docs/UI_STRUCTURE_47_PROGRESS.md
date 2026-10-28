# Матрица интерфейса и автосохранения · промежуточная версия47

Это инвентаризация исходников, а не результат проверки экранов на устройстве. Учтены60 существующих экранов, панелей и окон в42 файлах. Количество функциональных узлов не ограничивается этой выборкой.

Единый стиль: глубокий синий фон, сиреневый основной акцент, голубой вспомогательный; системная тема не переключает палитру. Меню вызывается верхней левой кнопкой с мозгом. Двадцать одна иконка распределена по четырём прокручиваемым рядам; доступные названия остаются в семантике и подсказках.

Навигация: Главная → события и состояние; Портфель → счета, активы, инструмент и риски; Решения → аналитик, выводы, исследования; Настройки → персональные правила, уведомления, оформление и устройства. Рабочие разделы остаются доступны напрямую из меню.

Обычные настройки применяются автоматически с отдельными состояниями локального черновика, ожидания, подтверждённой записи и ошибки. Некорректный ввод сохраняется как черновик; серверные действия не повторяются из-за возврата на экран. Создание именованной закладки остаётся самостоятельным действием.

## Предстоящая нативная проверка

НаAPI37,4096/16384 байтах и шрифте100%/200%: настоящая установка и обновление45→47, все21 иконки, шесть существующих экранов, закрытие вне меню, предиктивный возврат, автоматическое оформление и редактирование горизонта стратегии с незавершённым вводом. Полная матрица15 этапов, остальные экраны и внешняя проверка Sonar остаются отдельными критериями.

## Ещё не завершено

| Поверхность | Следующая доработка |
|---|---|
| PeriodControls | Date range still has explicit Apply; persist valid pair on selection and preserve incomplete range independently. |
| watch reason dialog | Note editor still requires Save; needs durable keyed draft and deduplicated apply. |
| navigation_detail | Cancellation of LaunchedEffect does not serialize blocking storage writes; use durable ordered writer. |

## Существующие поверхности

| Экран / панель / окно | Исходник | Нативная проверка |
|---|---|---|
| `PlaceholderTabScreen` | `app/src/main/java/ru/omnicio/app/ui/PlaceholderTabScreen.kt` | Ожидает |
| `InsightFeedScreen` | `app/src/main/java/ru/omnicio/app/ui/analysis/AnalysisScreens.kt` | Ожидает |
| `PulseScreen` | `app/src/main/java/ru/omnicio/app/ui/analysis/AnalysisScreens.kt` | Ожидает |
| `InsightScreen` | `app/src/main/java/ru/omnicio/app/ui/analysis/AnalysisScreens.kt` | Ожидает |
| `IdeasScreen` | `app/src/main/java/ru/omnicio/app/ui/analysis/AnalysisScreens.kt` | Ожидает |
| `AnalysisProfileSettingsScreen` | `app/src/main/java/ru/omnicio/app/ui/analysis/AnalysisScreens.kt` | Ожидает |
| `TelegramLoginScreen` | `app/src/main/java/ru/omnicio/app/ui/auth/TelegramLoginScreen.kt` | Ожидает |
| `EducationScreen` | `app/src/main/java/ru/omnicio/app/ui/education/EducationScreen.kt` | Ожидает |
| `HomeScreen` | `app/src/main/java/ru/omnicio/app/ui/home/HomeScreen.kt` | Ожидает |
| `OperationTargetDialog` | `app/src/main/java/ru/omnicio/app/ui/portfolio/AccountOperations.kt` | Ожидает |
| `OperationDetailDialog` | `app/src/main/java/ru/omnicio/app/ui/portfolio/AccountOperations.kt` | Ожидает |
| `AssetComparisonDialog` | `app/src/main/java/ru/omnicio/app/ui/portfolio/AssetComparisonScreen.kt` | Ожидает |
| `DossierNewsPanel` | `app/src/main/java/ru/omnicio/app/ui/portfolio/DossierNewsPanel.kt` | Ожидает |
| `DossierRatingsPanel` | `app/src/main/java/ru/omnicio/app/ui/portfolio/DossierRatingsPanel.kt` | Ожидает |
| `DossierReportsPanel` | `app/src/main/java/ru/omnicio/app/ui/portfolio/DossierReportsPanel.kt` | Ожидает |
| `InstrumentDetailsScreen` | `app/src/main/java/ru/omnicio/app/ui/portfolio/InstrumentDetailsScreen.kt` | Ожидает |
| `InstrumentDossierPanel` | `app/src/main/java/ru/omnicio/app/ui/portfolio/InstrumentDossierPanel.kt` | Ожидает |
| `DossierHoldingsPanel` | `app/src/main/java/ru/omnicio/app/ui/portfolio/InstrumentDossierPanel.kt` | Ожидает |
| `DossierMetricsPanel` | `app/src/main/java/ru/omnicio/app/ui/portfolio/InstrumentDossierPanel.kt` | Ожидает |
| `InstrumentQuotesPanel` | `app/src/main/java/ru/omnicio/app/ui/portfolio/InstrumentQuotesPanel.kt` | Ожидает |
| `PortfolioScreen` | `app/src/main/java/ru/omnicio/app/ui/portfolio/PortfolioScreen.kt` | Ожидает |
| `AccountScreen` | `app/src/main/java/ru/omnicio/app/ui/portfolio/PortfolioScreen.kt` | Ожидает |
| `VerifiedExposurePanel` | `app/src/main/java/ru/omnicio/app/ui/portfolio/VerifiedExposurePanel.kt` | Ожидает |
| `ProfileScreen` | `app/src/main/java/ru/omnicio/app/ui/profile/ProfileScreen.kt` | Ожидает |
| `TApiScreen` | `app/src/main/java/ru/omnicio/app/ui/profile/TApiScreen.kt` | Ожидает |
| `PortfolioResearchPanel` | `app/src/main/java/ru/omnicio/app/ui/research/PortfolioResearchPanel.kt` | Ожидает |
| `RequiredUpdateScreen` | `app/src/main/java/ru/omnicio/app/ui/spectrum/RequiredUpdateScreen.kt` | Ожидает |
| `SpectrumAlertDialog` | `app/src/main/java/ru/omnicio/app/ui/spectrum/SpectrumAlertDialog.kt` | Ожидает |
| `SpectrumDatePickerDialog` | `app/src/main/java/ru/omnicio/app/ui/spectrum/SpectrumAlertDialog.kt` | Ожидает |
| `DefaultUpdateScreen` | `app/src/main/java/ru/omnicio/app/ui/updates/MandatoryUpdateHost.kt` | Ожидает |
| `AnalysisCheckDialog` | `app/src/main/java/ru/omnicio/app/ui/workspace/AnalysisMonitorPanels.kt` | Ожидает |
| `AnalysisTimelineScreen` | `app/src/main/java/ru/omnicio/app/ui/workspace/AnalysisTimelineScreen.kt` | Ожидает |
| `AnalysisFactsDialog` | `app/src/main/java/ru/omnicio/app/ui/workspace/AnalysisTimelineScreen.kt` | Ожидает |
| `AppearanceScreen` | `app/src/main/java/ru/omnicio/app/ui/workspace/AppearanceScreen.kt` | Ожидает |
| `AssistantWorkspaceScreen` | `app/src/main/java/ru/omnicio/app/ui/workspace/AssistantWorkspaceScreen.kt` | Ожидает |
| `AutonomousDecisionsScreen` | `app/src/main/java/ru/omnicio/app/ui/workspace/AutonomousDecisionsScreen.kt` | Ожидает |
| `DiscoveryWorkspaceScreen` | `app/src/main/java/ru/omnicio/app/ui/workspace/DiscoveryWorkspaceScreen.kt` | Ожидает |
| `DiscoveryResearchDialog` | `app/src/main/java/ru/omnicio/app/ui/workspace/DiscoveryWorkspaceScreen.kt` | Ожидает |
| `GeographyWorkspacePanel` | `app/src/main/java/ru/omnicio/app/ui/workspace/GeographyWorkspacePanel.kt` | Ожидает |
| `ImpactHypothesisPanel` | `app/src/main/java/ru/omnicio/app/ui/workspace/ImpactHypothesisPanel.kt` | Ожидает |
| `LiveStrategyScreen` | `app/src/main/java/ru/omnicio/app/ui/workspace/LiveStrategyScreen.kt` | Ожидает |
| `MarketCatalogueScreen` | `app/src/main/java/ru/omnicio/app/ui/workspace/MarketCatalogueScreen.kt` | Ожидает |
| `PurchaseCheckDialog` | `app/src/main/java/ru/omnicio/app/ui/workspace/MarketCatalogueScreen.kt` | Ожидает |
| `MarketWorkspaceScreen` | `app/src/main/java/ru/omnicio/app/ui/workspace/MarketWorkspaceScreen.kt` | Ожидает |
| `NotificationSettingsScreen` | `app/src/main/java/ru/omnicio/app/ui/workspace/NotificationWorkspaceScreens.kt` | Ожидает |
| `NotificationEventsScreen` | `app/src/main/java/ru/omnicio/app/ui/workspace/NotificationWorkspaceScreens.kt` | Ожидает |
| `DevicesWorkspaceScreen` | `app/src/main/java/ru/omnicio/app/ui/workspace/PersonalWorkspaceScreens.kt` | Ожидает |
| `GoalsWorkspaceScreen` | `app/src/main/java/ru/omnicio/app/ui/workspace/PersonalWorkspaceScreens.kt` | Ожидает |
| `RecentWorkspaceScreen` | `app/src/main/java/ru/omnicio/app/ui/workspace/PersonalWorkspaceScreens.kt` | Ожидает |
| `NewFeaturesWorkspaceScreen` | `app/src/main/java/ru/omnicio/app/ui/workspace/PersonalWorkspaceScreens.kt` | Ожидает |
| `PlansWorkspaceScreen` | `app/src/main/java/ru/omnicio/app/ui/workspace/PlansWorkspaceScreen.kt` | Ожидает |
| `ResearchLibraryScreen` | `app/src/main/java/ru/omnicio/app/ui/workspace/ResearchLibraryScreen.kt` | Ожидает |
| `RiskScenarioDialog` | `app/src/main/java/ru/omnicio/app/ui/workspace/RiskScenarioDialog.kt` | Ожидает |
| `RiskWorkspaceScreen` | `app/src/main/java/ru/omnicio/app/ui/workspace/RiskWorkspaceScreen.kt` | Ожидает |
| `StrategyWorkspaceScreen` | `app/src/main/java/ru/omnicio/app/ui/workspace/StrategyWorkspaceScreen.kt` | Ожидает |
| `DraftLeaveDialog` | `app/src/main/java/ru/omnicio/app/ui/workspace/StrategyWorkspaceScreen.kt` | Ожидает |
| `TradingCalendarPanel` | `app/src/main/java/ru/omnicio/app/ui/workspace/TradingCalendarPanel.kt` | Ожидает |
| `WorkspaceDialog` | `app/src/main/java/ru/omnicio/app/ui/workspace/WorkspaceDialog.kt` | Ожидает |
| `WorkspaceJobPanel` | `app/src/main/java/ru/omnicio/app/ui/workspace/WorkspacePanels.kt` | Ожидает |
| `WorkspaceJobPanel` | `app/src/main/java/ru/omnicio/app/ui/workspace/WorkspacePanels.kt` | Ожидает |

N00 иN01–N11 остаются открытыми. Этот документ не подтверждает выпуск APK или установку на телефоне.
