# 3D100 — код, сценарии и границы проверки

Это реестр реализации кандидата **0.11.0 / 35** в [PR #880](https://github.com/MishaGameHacking/omni-cio-gateway/pull/880).
Он сохраняет связь каждого исходного требования с рабочими обработчиками, компонентами и проверками.
**Ссылка на код или написанный сценарий не обозначает успешное выполнение на устройстве.**
Сами требования не сокращены: [основной список 100 решений](3D100.md).

## Подтверждённое состояние этого среза

- Серверные проверки текущего исходного среза: **779 pytest-тестов и 305 под-тестов** локально; зависимости для разработки отделены от production.
- Проверки Android/релизных Python-сценариев: **404 теста**, один прежний SDK smoke пропущен локально; отдельно **29** проверок installation evidence, **11** проверок native alignment и **7** проверок геометрии/материалов.
- В каталоге **90 GLB**, **2 376 648 байт**. Генератор воспроизводит каталог локально; Windows-проверка нового среза ещё ожидается.
- Предыдущий локальный Android-срез `985819884169e0f28d7554930ba82b748961b10c`: debug/preview/release, оба lint и **16 JVM-тестов** прошли. Следующий срез содержит дополнительные проверки материала, направляющих, точных дат и календаря; результаты полного прогона будут записаны отдельно.
- GitHub Android CI прежнего среза прошёл сборку и lint, затем остановился **до эмуляторов** на сравнении Windows short/long path в тесте. Исправлены ожидания теста; ограничения доверенных путей сохранены.
- Новый код ещё не имеет подтверждённых кадров 3D на API 35/36. Подготовлены реальные 52 сочетания бизнес-сценария и шрифта на каждую API, отдельные проверки ввода, отмены Back, системной анимации, температуры и длительной прокрутки.
- Отчёт публикации версии 35 обязан подтвердить фактические **16 КБ** на API 35, все установочные/обновляющие сценарии и digest установленного APK. Старый отчёт версии 34 не подходит для новой публикации.

Точный SHA, GitHub checks, APK, сервер и канал сверяются в [PLAN_STATUS](PLAN_STATUS.md).
Физический TalkBack, ощущение тактильного отклика, нагрев и расход батареи не подтверждаются по эмулятору.
Синтетические сценарии запускают production-компоненты из отдельной debug fixture; данные не попадают в распространяемый APK.

## Как читать записи

«Код» — реальные файлы реализации. «Проверки» — точные тесты либо явно названные сценарии runner;
их выполнение и охват уточняются в примечании. Если отдельного сценария пока нет, это указано прямо.
Результаты локальных тестов не распространяются на неподтверждённый запуск CI, live-брокера, браузер Telegram или физический телефон.

## 3D001

**Единые материалы.** Настоящие меши с керамикой, стеклом и металлом, согласованные состояния.

Код: [SpatialMaterial.kt](../app/src/main/java/ru/omnicio/app/ui/spatial/SpatialMaterial.kt), [SpatialRenderer.kt](../app/src/main/java/ru/omnicio/app/ui/spatial/SpatialRenderer.kt), [generate_spectrum_meshes.py](../tools/generate_spectrum_meshes.py), [catalogue.json](../app/src/main/assets/spectrum3d/catalogue.json).

Проверки:

- [test_spectrum_meshes.py](../tools/test_spectrum_meshes.py) — `MeshCatalogueTest.test_three_actual_pbr_families_preserve_native_readability_and_lod_identity`.
- [SpatialMaterialTest.kt](../app/src/test/java/ru/omnicio/app/ui/spatial/SpatialMaterialTest.kt).
- [spatial_ui_probe.py](../.github/scripts/spatial_ui_probe.py).

**3D-ядро:** Три настоящих PBR-пресета: керамика, металл, диэлектрическое покрытие KHR_materials_clearcoat. Все поверхности непрозрачны; рефракция не заявлена. GLB-проверки прошли; визуальный результат и новая JVM-проверка ожидают CI.

## 3D002

**Объёмные символы.** 15 исходных символов и новые управляющие значки имеют геометрию и состояния.

Код: [SpectrumIcon.kt](../app/src/main/java/ru/omnicio/app/ui/spectrum/SpectrumIcon.kt), [SpectrumLiveFeatureIcon.kt](../app/src/main/java/ru/omnicio/app/ui/spectrum/SpectrumLiveFeatureIcon.kt), [SpatialComponents.kt](../app/src/main/java/ru/omnicio/app/ui/spatial/SpatialComponents.kt), [SpatialRenderer.kt](../app/src/main/java/ru/omnicio/app/ui/spatial/SpatialRenderer.kt), [generate_spectrum_meshes.py](../tools/generate_spectrum_meshes.py).

Проверки:

- [test_spectrum_meshes.py](../tools/test_spectrum_meshes.py).
- [spatial_ui_probe.py](../.github/scripts/spatial_ui_probe.py).
- [SpatialRendererProbe.kt](../app/src/debug/java/ru/omnicio/app/SpatialRendererProbe.kt).

**3D-ядро:** 15 исходных символов и новые управляющие значки, включая Forward, имеют объёмную геометрию и состояния. 90 GLB проверены локально; распознаваемость всех символов по настоящим кадрам ещё не подтверждена.

## 3D003

**Карточки.** Толщина, фаска, нажатие и раскрытие в общей сцене.

Код: [SpectrumDesignSystem.kt](../app/src/main/java/ru/omnicio/app/ui/spectrum/SpectrumDesignSystem.kt), [SpatialComponents.kt](../app/src/main/java/ru/omnicio/app/ui/spatial/SpatialComponents.kt), [SpatialRenderer.kt](../app/src/main/java/ru/omnicio/app/ui/spatial/SpatialRenderer.kt).

Проверки:

- [spatial_ui_probe.py](../.github/scripts/spatial_ui_probe.py).
- [SpatialRendererProbe.kt](../app/src/debug/java/ru/omnicio/app/SpatialRendererProbe.kt).

**3D-ядро:** Карточки используют extruded GLB, толщину, глубину и реакцию на нажатие; содержимое и hit-test нативные. Реальный raster/click/dialog gate включён, но пока не выполнен на новом head.

## 3D004

**Свет.** Один согласованный ключевой свет на всех экранах.

Код: [SpatialRenderer.kt](../app/src/main/java/ru/omnicio/app/ui/spatial/SpatialRenderer.kt).

Проверки:

- [spatial_ui_probe.py](../.github/scripts/spatial_ui_probe.py).
- [spatial_frame_evidence.py](../.github/scripts/spatial_frame_evidence.py).

**3D-ядро:** Один directional light и ambient irradiance на общий Engine, общий свет во всех окнах; нагрев отключает тени. Источник проверен, полноценная оценка освещения ждёт кадров CI.

## 3D005

**Глубина.** База, выбор и подробности образуют три читаемых уровня.

Код: [SpatialModels.kt](../app/src/main/java/ru/omnicio/app/ui/spatial/SpatialModels.kt), [SpatialComponents.kt](../app/src/main/java/ru/omnicio/app/ui/spatial/SpatialComponents.kt), [SpatialRenderer.kt](../app/src/main/java/ru/omnicio/app/ui/spatial/SpatialRenderer.kt).

Проверки:

- [SpatialChartGeometryTest.kt](../app/src/test/java/ru/omnicio/app/ui/spatial/SpatialChartGeometryTest.kt).
- [spatial_ui_probe.py](../.github/scripts/spatial_ui_probe.py).

**3D-ядро:** Явные уровни base/emphasized/control/icon/selected и ортографическая камера. Выбор финансового элемента меняет Z, сохраняя значение и шкалу; визуальное различение уровней ещё не проверено.

## 3D006

**Управление.** Кнопки, переключатели и поля объёмны; курсор, IME и выделение нативные.

Код: [SpectrumDesignSystem.kt](../app/src/main/java/ru/omnicio/app/ui/spectrum/SpectrumDesignSystem.kt), [SpectrumSelectionControls.kt](../app/src/main/java/ru/omnicio/app/ui/spectrum/SpectrumSelectionControls.kt), [SpectrumTextButton.kt](../app/src/main/java/ru/omnicio/app/ui/spectrum/SpectrumTextButton.kt), [SpectrumTextField.kt](../app/src/main/java/ru/omnicio/app/ui/spectrum/SpectrumTextField.kt), [SpectrumRangeSlider.kt](../app/src/main/java/ru/omnicio/app/ui/spectrum/SpectrumRangeSlider.kt), [SpatialComponents.kt](../app/src/main/java/ru/omnicio/app/ui/spatial/SpatialComponents.kt).

Проверки:

- [spatial_ui_probe.py](../.github/scripts/spatial_ui_probe.py).
- [native_input_evidence.py](../.github/scripts/native_input_evidence.py).
- [test_native_input_evidence.py](../.github/scripts/tests/test_native_input_evidence.py).

**3D-ядро:** Меши оформляют нативные кнопки, переключатели и поля; IME, фокус, курсор и выделение остаются Android. Parser guards прошли; действующие click/toggle/caret сценарии ещё ожидают эмулятор.

## 3D007

**Светлая тема.** Материалы и контраст пересчитаны для светлого окружения.

Код: [SpectrumDesignSystem.kt](../app/src/main/java/ru/omnicio/app/ui/spectrum/SpectrumDesignSystem.kt), [SpatialRenderer.kt](../app/src/main/java/ru/omnicio/app/ui/spatial/SpatialRenderer.kt), [AppearanceScreen.kt](../app/src/main/java/ru/omnicio/app/ui/workspace/AppearanceScreen.kt).

Проверки:

- [test_spectrum_contrast.py](../.github/scripts/tests/test_spectrum_contrast.py).
- [test_spectrum_production_tokens.py](../.github/scripts/tests/test_spectrum_production_tokens.py).
- [spatial_ui_probe.py](../.github/scripts/spatial_ui_probe.py).
- [spatial_frame_evidence.py](../.github/scripts/spatial_frame_evidence.py).

**3D-ядро:** Светлая палитра и материалы связаны с темой. Включена проверка контраста текста по пикселям реальной PBR-кнопки; прошедшие token/parser tests не заменяют ещё отсутствующий raster.

## 3D008

**Состояния.** Loading, empty, offline, error и update соответствуют фактическому состоянию.

Код: [SpectrumLoadingIndicator.kt](../app/src/main/java/ru/omnicio/app/ui/spectrum/SpectrumLoadingIndicator.kt), [SpectrumUpdateVisuals.kt](../app/src/main/java/ru/omnicio/app/ui/spectrum/SpectrumUpdateVisuals.kt), [RequiredUpdateScreen.kt](../app/src/main/java/ru/omnicio/app/ui/spectrum/RequiredUpdateScreen.kt), [BusinessWorkspaceProbe.kt](../app/src/debug/java/ru/omnicio/app/BusinessWorkspaceProbe.kt), [WorkspacePanels.kt](../app/src/main/java/ru/omnicio/app/ui/workspace/WorkspacePanels.kt).

Проверки:

- [business_ui_probe.py](../.github/scripts/business_ui_probe.py).
- [profile_ui_probe.py](../.github/scripts/profile_ui_probe.py).

**3D-ядро:** Loading/empty/partial/error/update связаны с фактическим client state. 26 сценариев × 2 шрифта исполняют реальные production-компоненты с явно синтетическим transport; выполнение на эмуляторе пока не подтверждено.

## 3D009

**Заголовки.** Лёгкий рельеф; текст и денежные значения остаются неподвижными и читаемыми.

Код: [SpectrumDesignSystem.kt](../app/src/main/java/ru/omnicio/app/ui/spectrum/SpectrumDesignSystem.kt), [SpatialComponents.kt](../app/src/main/java/ru/omnicio/app/ui/spatial/SpatialComponents.kt), [generate_spectrum_meshes.py](../tools/generate_spectrum_meshes.py).

Проверки:

- [spatial_ui_probe.py](../.github/scripts/spatial_ui_probe.py).
- [profile_ui_probe.py](../.github/scripts/profile_ui_probe.py).

**3D-ядро:** Нативный читаемый заголовок расположен на неглубокой настоящей mesh-плашке. Сам текст не тесселирован и не вращается; 200%-читаемость должна подтвердиться фактическими кадрами.

## 3D010

**Эмблемы.** Классы активов и монограммы компаний представлены объёмными символами.

Код: [SpectrumAssetMark.kt](../app/src/main/java/ru/omnicio/app/ui/spectrum/SpectrumAssetMark.kt), [SpatialGlyphs.kt](../app/src/main/java/ru/omnicio/app/ui/spatial/SpatialGlyphs.kt), [PortfolioComponents.kt](../app/src/main/java/ru/omnicio/app/ui/portfolio/PortfolioComponents.kt), [InstrumentDetailsScreen.kt](../app/src/main/java/ru/omnicio/app/ui/portfolio/InstrumentDetailsScreen.kt).

Проверки:

- [test_spectrum_meshes.py](../tools/test_spectrum_meshes.py).
- [spatial_ui_probe.py](../.github/scripts/spatial_ui_probe.py).

**3D-ядро:** Объёмные классы активов и латинские/кириллические монограммы; геометрия вместо загружаемых логотипов. Проверка распознаваемости и совпадения в row/detail требует runtime review.

## 3D011

**Навигационная панель.** Пять разделов, реакция выбранного объекта без бесконечных циклов.

Код: [AnalystBottomBar.kt](../app/src/main/java/ru/omnicio/app/ui/AnalystBottomBar.kt), [SpectrumIcon.kt](../app/src/main/java/ru/omnicio/app/ui/spectrum/SpectrumIcon.kt), [SpatialComponents.kt](../app/src/main/java/ru/omnicio/app/ui/spatial/SpatialComponents.kt).

Проверки:

- [profile_ui_probe.py](../.github/scripts/profile_ui_probe.py).

**3D-ядро:** Пять разделов и адаптивная навигация оформлены общей mesh-сценой, выбор нативный, движение конечное. Полная навигационная проверка нового приложения ещё ожидает реальный прогон.

## 3D012

**Переход объекта.** Выбранный объект сохраняет идентичность при открытии подробностей и возврате.

Код: [PortfolioScreen.kt](../app/src/main/java/ru/omnicio/app/ui/portfolio/PortfolioScreen.kt), [PortfolioComponents.kt](../app/src/main/java/ru/omnicio/app/ui/portfolio/PortfolioComponents.kt), [InstrumentDetailsScreen.kt](../app/src/main/java/ru/omnicio/app/ui/portfolio/InstrumentDetailsScreen.kt), [SpatialComponents.kt](../app/src/main/java/ru/omnicio/app/ui/spatial/SpatialComponents.kt), [SpatialRenderer.kt](../app/src/main/java/ru/omnicio/app/ui/spatial/SpatialRenderer.kt).

Проверки:

- [profile_ui_probe.py](../.github/scripts/profile_ui_probe.py).
- [spatial_ui_probe.py](../.github/scripts/spatial_ui_probe.py).
- [WorkspaceFinancialSemanticsTest.kt](../app/src/test/java/ru/omnicio/app/ui/portfolio/WorkspaceFinancialSemanticsTest.kt) — `selectedPositionResolvesTheCurrentAccountAndRefusesAmbiguousOrRemovedRows`.

**3D-ядро:** Основной portfolio row/detail использует SharedTransitionLayout и один SpatialObject key; renderer передаёт одну entity/material lease. Другие отдельные окна не объявлены бесшовным shared-переходом. Точный переход пока не доказан runtime-кадрами.

**Android:** JVM identity passed publish-2. SpatialObject получает одинаковый accountId:UID в строке и встроенных деталях; передача entity и отмена жеста требуют отдельного renderer/device evidence.

## 3D013

**Predictive back.** Жест управляет переходом; отмена полностью восстанавливает состояние.

Код: [SpatialInteraction.kt](../app/src/main/java/ru/omnicio/app/ui/spatial/SpatialInteraction.kt), [SpatialScene.kt](../app/src/main/java/ru/omnicio/app/ui/spatial/SpatialScene.kt), [SpatialRenderer.kt](../app/src/main/java/ru/omnicio/app/ui/spatial/SpatialRenderer.kt), [SpatialRendererProbe.kt](../app/src/debug/java/ru/omnicio/app/SpatialRendererProbe.kt).

Проверки:

- [spatial_policy_probe.py](../.github/scripts/spatial_policy_probe.py).
- [test_spatial_policy_probe.py](../.github/scripts/tests/test_spatial_policy_probe.py).

**3D-ядро:** Production PredictiveBackHandler сбрасывает прогресс в finally и dispose. Gate посылает настоящие DOWN/MOVE/CANCEL, требует прогресс, отсутствие commit при отмене и ровно1 commit отдельного жеста. Доставка событий ещё не выполнена.

## 3D014

**Контекстные действия.** Доступная большому пальцу панель: сравнение, события, риски.

Код: [InstrumentDetailsScreen.kt](../app/src/main/java/ru/omnicio/app/ui/portfolio/InstrumentDetailsScreen.kt), [AssetComparisonScreen.kt](../app/src/main/java/ru/omnicio/app/ui/portfolio/AssetComparisonScreen.kt).

Отдельный сценарий для этого пункта ещё не выполнен; приёмка остаётся открытой.

**Android:** Отдельного runtime-case пока нет. Нижняя контекстная панель открывает исследование, события, риски; сравнение доступно из выбора 2–3 активов. Навигация сохраняет UID/account.

## 3D015

**Общий поиск.** Счета, активы, выплаты, разделы, исследования и настройки.

Код: [DiscoveryWorkspaceScreen.kt](../app/src/main/java/ru/omnicio/app/ui/workspace/DiscoveryWorkspaceScreen.kt).

Отдельный сценарий для этого пункта ещё не выполнен; приёмка остаётся открытой.

**Android:** Отдельного runtime-case пока нет. DiscoveryResults/DiscoverySelection: счета, активы, выплаты, архив, текущие исследования, страницы/настройки, watchlist. Сохраняются ID и запрос, не устаревший JSONObject.

## 3D016

**Быстрый просмотр.** Длительное нажатие и обычная доступная кнопка просмотра.

Код: [PortfolioComponents.kt](../app/src/main/java/ru/omnicio/app/ui/portfolio/PortfolioComponents.kt), [PortfolioQuickPreview.kt](../app/src/main/java/ru/omnicio/app/ui/portfolio/PortfolioQuickPreview.kt).

Отдельный сценарий для этого пункта ещё не выполнен; приёмка остаётся открытой.

**Android:** Отдельного runtime-case пока нет. PositionLine long press и обычная Кратко открывают одну шторку SpatialWindow; ключ выбранной позиции переживает rotation.

## 3D017

**Обновление жестом.** Порог, загрузка, отсутствие новых данных, успех и ошибка различаются.

Код: [HomeScreen.kt](../app/src/main/java/ru/omnicio/app/ui/home/HomeScreen.kt), [HomeWorkspaceSections.kt](../app/src/main/java/ru/omnicio/app/ui/home/HomeWorkspaceSections.kt).

Проверки:

- [profile_ui_probe.py](../.github/scripts/profile_ui_probe.py) — `dashboards/home (smoke only)`.

**Android:** Runtime-сценарий написан; подтверждённого device pass пока нет. HomeScreen различает порог, загрузку, ошибку, новые/неизменившиеся реальные значения по fingerprint. Smoke не проверяет все ответы брокера.

## 3D018

**Адаптация окна.** Фокус и выбранные данные сохраняются при повороте и изменении окна.

Код: [SpectrumTextField.kt](../app/src/main/java/ru/omnicio/app/ui/spectrum/SpectrumTextField.kt), [BusinessWorkspaceProbe.kt](../app/src/debug/java/ru/omnicio/app/BusinessWorkspaceProbe.kt), [FrameInstrumentation.java](../ci-ui-driver/src/main/java/ru/omnicio/ciframe/FrameInstrumentation.java), [PortfolioScreen.kt](../app/src/main/java/ru/omnicio/app/ui/portfolio/PortfolioScreen.kt), [HistoryChart.kt](../app/src/main/java/ru/omnicio/app/ui/portfolio/HistoryChart.kt), [DiscoveryWorkspaceScreen.kt](../app/src/main/java/ru/omnicio/app/ui/workspace/DiscoveryWorkspaceScreen.kt), [AppearanceScreen.kt](../app/src/main/java/ru/omnicio/app/ui/workspace/AppearanceScreen.kt).

Проверки:

- [native_input_evidence.py](../.github/scripts/native_input_evidence.py).
- [test_native_input_evidence.py](../.github/scripts/tests/test_native_input_evidence.py).
- [spatial_ui_probe.py](../.github/scripts/spatial_ui_probe.py).
- [business_ui_probe.py](../.github/scripts/business_ui_probe.py).
- [native_input_evidence.py](../.github/scripts/native_input_evidence.py) — `rotate_focused_draft`.
- [business_ui_probe.py](../.github/scripts/business_ui_probe.py) — `assistant/ready font=1.0,2.0`.

**3D-ядро:** Сохранение фокуса/UTF-16 caret и черновика проверяется реальным поворотом Activity на обоих шрифтах; отдельный renderer case сохраняет input/toggle/counter. Parser прошёл, runtime ещё нет; все варианты split-screen не заявлены.

**Android:** Runtime-сценарий написан; подтверждённого device pass пока нет. Нативный ввод/курсор/фокус и saveable ID/date/draft. Runner проверяет rotation несохранённого Assistant draft; это не доказательство всех диалогов, split screen и всех сочетаний IME.

## 3D019

**Недавние разделы.** Именованные объёмные карточки текущей истории переходов.

Код: [PersonalWorkspaceScreens.kt](../app/src/main/java/ru/omnicio/app/ui/workspace/PersonalWorkspaceScreens.kt), [WorkspaceUi.kt](../app/src/main/java/ru/omnicio/app/ui/workspace/WorkspaceUi.kt), [MainActivity.kt](../app/src/main/java/ru/omnicio/app/MainActivity.kt).

Отдельный сценарий для этого пункта ещё не выполнен; приёмка остаётся открытой.

**Android:** Отдельного runtime-case пока нет. Root: recent route cards и encrypted navigation; мои экраны передают UID/account/operation/date interval. Отдельной проверки стека от этого scope нет.

## 3D020

**Исследования.** Название, актив, период, источник, заметка и явное устаревание при открытии.

Код: [ResearchLibraryScreen.kt](../app/src/main/java/ru/omnicio/app/ui/workspace/ResearchLibraryScreen.kt), [PersonalWorkspaceStore.kt](../app/src/main/java/ru/omnicio/app/data/workspace/PersonalWorkspaceStore.kt), [EncryptedWorkspaceStore.kt](../app/src/main/java/ru/omnicio/app/data/workspace/EncryptedWorkspaceStore.kt).

Отдельный сценарий для этого пункта ещё не выполнен; приёмка остаётся открытой.

**Android:** Отдельного runtime-case пока нет. SaveResearchButton/ArchiveContent: название, UID, период, источник, время, заметка, сохранённый payload и явная давность. Архив не выдаётся за текущую цену.

## 3D021

**Валюта суммы.** Нажатие меняет RUB/USD/EUR через реальную оценку брокера.

Код: [HomeScreen.kt](../app/src/main/java/ru/omnicio/app/ui/home/HomeScreen.kt), [MainActivity.kt](../app/src/main/java/ru/omnicio/app/MainActivity.kt), [portfolio_details.py](../backend/portfolio_details.py), [volume_workspace.py](../backend/volume_workspace.py), [volume_jobs.py](../backend/volume_jobs.py), [volume_state.py](../backend/volume_state.py).

Проверки:

- [profile_ui_probe.py](../.github/scripts/profile_ui_probe.py) — `dashboards/home (smoke only)`.
- [test_portfolio_details.py](../backend/tests/test_portfolio_details.py) — `DashboardApiTests::test_dashboard_currency_cash_dedup_and_unpriced_blocked_position`.
- [test_portfolio_details.py](../backend/tests/test_portfolio_details.py) — `DashboardApiTests::test_recorded_history_is_user_and_currency_scoped`.
- [test_volume_workspace.py](../backend/tests/test_volume_workspace.py) — `test_other_user_and_reconnected_broker_do_not_read_previous_snapshot`.

**Android:** Runtime-сценарий написан; подтверждённого device pass пока нет. InteractiveBalance вызывает root RUB→USD→EUR с реальной оценкой брокера; три валютных ответа smoke ещё не проверяет.

**Сервер:** Брокерская оценка и снимки разделены по пользователю, подключению и RUB/USD/EUR. Валюта не пересчитывается выдуманным курсом; сам жест переключения проверяется на Android.

## 3D022

**Приватный просмотр.** Удержание открывает только выбранную скрытую сумму до отпускания.

Код: [HomeScreen.kt](../app/src/main/java/ru/omnicio/app/ui/home/HomeScreen.kt).

Отдельный сценарий для этого пункта ещё не выполнен; приёмка остаётся открытой.

**Android:** Отдельного runtime-case пока нет. InteractiveBalance показывает только выбранную уже скрытую сумму на время удержания, сбрасывает reveal при release/cancel, не меняет privacy preference.

## 3D023

**Состав капитала.** Вложено, свободно, ограничено: подтверждённые суммы без двойного счёта.

Код: [HomeWorkspaceSections.kt](../app/src/main/java/ru/omnicio/app/ui/home/HomeWorkspaceSections.kt), [portfolio_details.py](../backend/portfolio_details.py), [volume_workspace.py](../backend/volume_workspace.py), [tinvest_portfolio.py](../backend/tinvest_portfolio.py).

Проверки:

- [test_portfolio_details.py](../backend/tests/test_portfolio_details.py) — `ValueTests::test_cash_native_currency_and_blocked_balance`.
- [test_portfolio_details.py](../backend/tests/test_portfolio_details.py) — `ValueTests::test_missing_value_is_not_zero`.
- [test_portfolio_details.py](../backend/tests/test_portfolio_details.py) — `ValueTests::test_bond_missing_accrued_not_invented`.
- [test_portfolio_details.py](../backend/tests/test_portfolio_details.py) — `ValueTests::test_futures_are_not_valued_like_shares`.

**Android:** Отдельного runtime-case пока нет. CapitalComposition: каждое наблюдаемое вложение попадает ровно в одну группу; частичная блокировка честно обозначает ограниченную позицию целиком, не вымышленную доступную к выводу сумму.

**Сервер:** read_account/normalize_position и normalize_snapshot сохраняют реальные денежные остатки, блокировки и неизвестную оценку. GetPositions сам по себе не доказывает доступную к выводу сумму.

## 3D024

**Причины изменения.** Пополнения, выводы, выплаты, переоценка и FX; неизвестный остаток не называется прибылью.

Код: [HomeWorkspaceSections.kt](../app/src/main/java/ru/omnicio/app/ui/home/HomeWorkspaceSections.kt), [WorkspaceClient.kt](../app/src/main/java/ru/omnicio/app/data/market/WorkspaceClient.kt), [volume_workspace.py](../backend/volume_workspace.py), [portfolio_details.py](../backend/portfolio_details.py), [volume_contract.py](../backend/volume_contract.py).

Проверки:

- [test_volume_workspace.py](../backend/tests/test_volume_workspace.py) — `test_attribution_uses_synchronized_boundaries_and_excludes_duplicate_external_flows`.
- [test_volume_workspace.py](../backend/tests/test_volume_workspace.py) — `test_attribution_does_not_invent_unobservable_fx_or_incomplete_flow_remainders`.
- [test_volume_workspace.py](../backend/tests/test_volume_workspace.py) — `test_operation_collection_rejects_conflicting_source_rows_without_replacing_snapshot`.

**Android:** Отдельного runtime-case пока нет. HomeAttribution: подтверждённые opening/closing/external flows/residual. FX явно неизвестен, если его не разложил источник; остаток не называется прибылью.

**Сервер:** Точный остаток возможен только с двумя синхронными снимками всех счетов и полной историей внешних потоков в валюте оценки. FX-компонента неизвестна; residual не называется доходностью.

## 3D025

**Изменения с визита.** Сравниваются подтверждённые снимки пользователя.

Код: [HomeWorkspaceSections.kt](../app/src/main/java/ru/omnicio/app/ui/home/HomeWorkspaceSections.kt), [PersonalWorkspaceStore.kt](../app/src/main/java/ru/omnicio/app/data/workspace/PersonalWorkspaceStore.kt), [volume_workspace.py](../backend/volume_workspace.py), [volume_state.py](../backend/volume_state.py), [volume_analysis.py](../backend/volume_analysis.py).

Проверки:

- [test_volume_workspace.py](../backend/tests/test_volume_workspace.py) — `test_structured_fact_versions_compare_actual_values_and_keep_unchanged`.
- [test_volume_workspace.py](../backend/tests/test_volume_workspace.py) — `test_missing_risk_basis_is_not_recorded_as_resolved`.

**Android:** Отдельного runtime-case пока нет. ChangesSinceVisit: encrypted baseline по visit ID/валюте; rotation сохраняет только ID. Отсутствующий прежний снимок не заменяется текущим.

**Сервер:** Сервер хранит подтверждённые снимки, события и версии фактов; момент последнего визита и сравнение интерфейса с ним принадлежат Android. Эти тесты подтверждают факты/события, а не пользовательский lastVisit.

## 3D026

**Сворачиваемая главная.** При прокрутке сохраняются компактная сумма и валюта.

Код: [HomeScreen.kt](../app/src/main/java/ru/omnicio/app/ui/home/HomeScreen.kt).

Проверки:

- [profile_ui_probe.py](../.github/scripts/profile_ui_probe.py) — `dashboards/home (smoke only)`.

**Android:** Runtime-сценарий написан; подтверждённого device pass пока нет. CapitalHero сворачивается, sticky header сохраняет сумму/валюту. Отдельного collapse/restore assertion пока нет.

## 3D027

**Настройка главной.** Перестановка модулей с предпросмотром, сохранением и отменой.

Код: [DashboardOrderEditor.kt](../app/src/main/java/ru/omnicio/app/ui/home/DashboardOrderEditor.kt), [HomeScreen.kt](../app/src/main/java/ru/omnicio/app/ui/home/HomeScreen.kt), [PersonalWorkspaceStore.kt](../app/src/main/java/ru/omnicio/app/data/workspace/PersonalWorkspaceStore.kt).

Отдельный сценарий для этого пункта ещё не выполнен; приёмка остаётся открытой.

**Android:** Отдельного runtime-case пока нет. DashboardOrderEditor/moveDashboardCard: drag preview, save, cancel, undo, Up/Down; saveable draft. Финансовое внимание остаётся перед shortcuts/what-new.

## 3D028

**Лента выплат.** Объявленные, ожидаемые и полученные выплаты с подтверждением источника.

Код: [HomeWorkspaceSections.kt](../app/src/main/java/ru/omnicio/app/ui/home/HomeWorkspaceSections.kt), [AccountAnalytics.kt](../app/src/main/java/ru/omnicio/app/ui/portfolio/AccountAnalytics.kt), [volume_workspace.py](../backend/volume_workspace.py), [portfolio_details.py](../backend/portfolio_details.py).

Проверки:

- [test_volume_workspace.py](../backend/tests/test_volume_workspace.py) — `test_collected_payouts_and_operation_links_keep_actual_status_account_and_source`.
- [test_portfolio_details.py](../backend/tests/test_portfolio_details.py) — `ValueTests::test_dividend_past_record_date_not_guaranteed`.
- [test_portfolio_details.py](../backend/tests/test_portfolio_details.py) — `ValueTests::test_unknown_payment_date_is_not_faked`.
- [test_portfolio_details.py](../backend/tests/test_portfolio_details.py) — `ValueTests::test_cancelled_dividends_excluded`.
- [test_portfolio_details.py](../backend/tests/test_portfolio_details.py) — `ValueTests::test_bond_record_date_used_for_entitlement`.

**Android:** Отдельного runtime-case пока нет. HomePayoutTimeline/AccountPayments: настоящие announced/expected/received, дата/UID/account/source. Право на будущую выплату и налоги не домысливаются.

**Сервер:** announced/expected/received различаются. Expected условен по текущему количеству до даты фиксации; право после фиксации не выводится из нынешнего владения. Received требует исполненной операции и её источника.

## 3D029

**Цель и резерв.** Текущий капитал против явной пользовательской цели; будущая прибыль не учитывается.

Код: [HomeWorkspaceSections.kt](../app/src/main/java/ru/omnicio/app/ui/home/HomeWorkspaceSections.kt), [PersonalWorkspaceScreens.kt](../app/src/main/java/ru/omnicio/app/ui/workspace/PersonalWorkspaceScreens.kt), [volume_state.py](../backend/volume_state.py), [volume_contract.py](../backend/volume_contract.py).

Проверки:

- [test_volume_workspace.py](../backend/tests/test_volume_workspace.py) — `test_goal_uses_actual_same_currency_capital_and_reserved_amount`.

**Android:** Отдельного runtime-case пока нет. HomeGoalProgress использует target/reserve/current от сервера; root goal editor. Будущая прибыль и возможность вывода не предполагаются.

**Сервер:** Прогресс цели использует наблюдаемый капитал за вычетом явно заданного резерва в той же валюте. Будущая прибыль и прогнозная дата достижения не добавляются.

## 3D030

**Без сети.** Зашифрованный сохранённый снимок открывается с датой и ограничением свежести.

Код: [EncryptedWorkspaceStore.kt](../app/src/main/java/ru/omnicio/app/data/workspace/EncryptedWorkspaceStore.kt), [PersonalWorkspaceStore.kt](../app/src/main/java/ru/omnicio/app/data/workspace/PersonalWorkspaceStore.kt), [MainActivity.kt](../app/src/main/java/ru/omnicio/app/MainActivity.kt).

Отдельный сценарий для этого пункта ещё не выполнен; приёмка остаётся открытой.

**Android:** Отдельного runtime-case пока нет. AES-GCM Keystore, AtomicFile, user-hash, noBackup; deactivateUser блокирует новые записи после logout. Root offline snapshot показывает as-of; исследований чужого пользователя нет. Instrumented logout/process-death evidence отсутствует.

## 3D031

**Структура.** Ортографические объёмные сегменты выбираются жестом и текстовой легендой.

Код: [PortfolioComponents.kt](../app/src/main/java/ru/omnicio/app/ui/portfolio/PortfolioComponents.kt), [VerifiedExposurePanel.kt](../app/src/main/java/ru/omnicio/app/ui/portfolio/VerifiedExposurePanel.kt), [SpatialComponents.kt](../app/src/main/java/ru/omnicio/app/ui/spatial/SpatialComponents.kt), [volume_state.py](../backend/volume_state.py), [volume_workspace.py](../backend/volume_workspace.py).

Проверки:

- [SpatialChartGeometryTest.kt](../app/src/test/java/ru/omnicio/app/ui/spatial/SpatialChartGeometryTest.kt).
- [profile_ui_probe.py](../.github/scripts/profile_ui_probe.py) — `dashboards/allocation`.
- [test_volume_workspace.py](../backend/tests/test_volume_workspace.py) — `test_verified_issuer_group_identity_is_used_without_ticker_guessing`.
- [test_volume_workspace.py](../backend/tests/test_volume_workspace.py) — `test_incomplete_broker_positions_cannot_resolve_risk_or_claim_complete_scenario`.

**Android:** JVM geometry passed publish-2. SpatialRing с реальными долями, ортопроекцией, angle hit и native legend→filter; точный pick/filter device-flow ещё не проверен.

**Сервер:** Сервер отдаёт структуру с точными суммами, идентификаторами и покрытием. Нажатие на сегмент и фильтр позиций реализованы на Android; неизвестная оценка не заменяется нулём.

## 3D032

**Компании и группы.** Агрегация по проверенным отношениям, без догадок по названию.

Код: [VerifiedExposurePanel.kt](../app/src/main/java/ru/omnicio/app/ui/portfolio/VerifiedExposurePanel.kt), [PortfolioAssetBrowser.kt](../app/src/main/java/ru/omnicio/app/ui/portfolio/PortfolioAssetBrowser.kt), [volume_state.py](../backend/volume_state.py), [volume_workspace.py](../backend/volume_workspace.py), [research_store.py](../backend/research_store.py), [credit_evidence.py](../backend/credit_evidence.py).

Проверки:

- [test_volume_workspace.py](../backend/tests/test_volume_workspace.py) — `test_verified_issuer_group_identity_is_used_without_ticker_guessing`.

**Android:** Отдельного runtime-case пока нет. VerifiedExposurePanel получает проверенные issuer/group IDs и source IDs. Группировка по названиям подписана отдельно и не выдаётся за подтверждённое владение.

**Сервер:** Агрегация компаний/групп использует проверенные issuer_identity с действительным Source, включая счета пользователя. Сходство названий или тикеров не создаёт связь; без источника часть остаётся неизвестной.

## 3D033

**Перегруппировка.** Позиции сохраняют идентичность при смене группировки.

Код: [PortfolioAssetBrowser.kt](../app/src/main/java/ru/omnicio/app/ui/portfolio/PortfolioAssetBrowser.kt), [PortfolioComponents.kt](../app/src/main/java/ru/omnicio/app/ui/portfolio/PortfolioComponents.kt).

Проверки:

- [WorkspaceFinancialSemanticsTest.kt](../app/src/test/java/ru/omnicio/app/ui/portfolio/WorkspaceFinancialSemanticsTest.kt) — `equalValuationsSortByStableIdentityAndForeignCurrencyIsNotRankedAsRubles`.
- [WorkspaceFinancialSemanticsTest.kt](../app/src/test/java/ru/omnicio/app/ui/portfolio/WorkspaceFinancialSemanticsTest.kt) — `selectedPositionResolvesTheCurrentAccountAndRefusesAmbiguousOrRemovedRows`.

**Android:** JVM passed publish-2. Stable account:UID keys, animateItem и текущее разрешение объекта. Сам переход между группами ещё требует device capture.

## 3D034

**Сравнение.** 2–3 инструмента: сопоставимые единицы, периоды и свежесть.

Код: [AssetComparisonScreen.kt](../app/src/main/java/ru/omnicio/app/ui/portfolio/AssetComparisonScreen.kt), [CommonPeriodComparison.kt](../app/src/main/java/ru/omnicio/app/ui/portfolio/CommonPeriodComparison.kt), [MarketModels.kt](../app/src/main/java/ru/omnicio/app/data/market/MarketModels.kt).

Проверки:

- [WorkspaceFinancialSemanticsTest.kt](../app/src/test/java/ru/omnicio/app/ui/portfolio/WorkspaceFinancialSemanticsTest.kt) — `comparisonUsesOnlySharedCompleteClosings`.
- [WorkspaceFinancialSemanticsTest.kt](../app/src/test/java/ru/omnicio/app/ui/portfolio/WorkspaceFinancialSemanticsTest.kt) — `priceUnitsCurrenciesAndIntervalsMustBeVerifiedAndCompatible`.
- [WorkspaceFinancialSemanticsTest.kt](../app/src/test/java/ru/omnicio/app/ui/portfolio/WorkspaceFinancialSemanticsTest.kt) — `unavailableOrInsufficientCommonObservationsNeverProduceAComparison`.

**Android:** JVM passed publish-2. 2–3 серии сравниваются только по общим полным закрытиям, одинаковым проверенным unit/currency/interval; недостаток/несовместимость блокируют результат. Полный UI flow пока без device pass.

## 3D035

**Все счета.** Один инструмент раскрывается по всем счетам пользователя.

Код: [InstrumentDossierPanel.kt](../app/src/main/java/ru/omnicio/app/ui/portfolio/InstrumentDossierPanel.kt), [DossierFactSheet.kt](../app/src/main/java/ru/omnicio/app/ui/portfolio/DossierFactSheet.kt), [DiscoveryWorkspaceScreen.kt](../app/src/main/java/ru/omnicio/app/ui/workspace/DiscoveryWorkspaceScreen.kt), [ResearchLibraryScreen.kt](../app/src/main/java/ru/omnicio/app/ui/workspace/ResearchLibraryScreen.kt), [volume_market.py](../backend/volume_market.py), [volume_state.py](../backend/volume_state.py).

Проверки:

- [WorkspaceFinancialSemanticsTest.kt](../app/src/test/java/ru/omnicio/app/ui/portfolio/WorkspaceFinancialSemanticsTest.kt) — `selectedPositionResolvesTheCurrentAccountAndRefusesAmbiguousOrRemovedRows`.

**Android:** JVM identity passed publish-2. DossierHoldingsPanel и сохранённые/watch действия раскрывают все счета; нет произвольного first-account. Dossier API/device flow ещё не проверен.

**Сервер:** load_dossier возвращает holdings отдельно по account_id/account_name для instrument_uid. Суммы разных валют не объединяются. Отдельного backend-теста сценария одной бумаги на нескольких счетах в текущем наборе нет; экран подтверждается Android evidence.

## 3D036

**Наблюдение.** Список с причиной: отчёт, выплата или изменение показателя.

Код: [PortfolioQuickPreview.kt](../app/src/main/java/ru/omnicio/app/ui/portfolio/PortfolioQuickPreview.kt), [PortfolioAssetBrowser.kt](../app/src/main/java/ru/omnicio/app/ui/portfolio/PortfolioAssetBrowser.kt), [DiscoveryWorkspaceScreen.kt](../app/src/main/java/ru/omnicio/app/ui/workspace/DiscoveryWorkspaceScreen.kt), [PersonalWorkspaceStore.kt](../app/src/main/java/ru/omnicio/app/data/workspace/PersonalWorkspaceStore.kt).

Отдельный сценарий для этого пункта ещё не выполнен; приёмка остаётся открытой.

**Android:** Отдельного runtime-case пока нет. WatchPositionAction/batch требуют reason/note и хранят UID. Причина видна в поиске; это ещё не подписка на автоматическую доставку событий.

## 3D037

**Сохранённые фильтры.** Именованные запросы, условия и группировки.

Код: [PortfolioAssetBrowser.kt](../app/src/main/java/ru/omnicio/app/ui/portfolio/PortfolioAssetBrowser.kt), [PersonalWorkspaceStore.kt](../app/src/main/java/ru/omnicio/app/data/workspace/PersonalWorkspaceStore.kt).

Отдельный сценарий для этого пункта ещё не выполнен; приёмка остаётся открытой.

**Android:** Отдельного runtime-case пока нет. SavedPortfolioFilter: имя, query, account, class, sector, group/order, watch/exposure; явное применение и удаление.

## 3D038

**Устойчивый порядок.** Свежие значения появляются сразу, порядок меняется по явному действию.

Код: [PortfolioAssetBrowser.kt](../app/src/main/java/ru/omnicio/app/ui/portfolio/PortfolioAssetBrowser.kt).

Проверки:

- [WorkspaceFinancialSemanticsTest.kt](../app/src/test/java/ru/omnicio/app/ui/portfolio/WorkspaceFinancialSemanticsTest.kt) — `equalValuationsSortByStableIdentityAndForeignCurrencyIsNotRankedAsRubles`.

**Android:** JVM passed publish-2. Значения обновляются по стабильным ключам, frozen order меняется только явным действием. Чужая/неизвестная валюта не ранжируется как RUB. Refresh interaction pending.

## 3D039

**Множественный выбор.** Состав, сопоставимые суммы и действия исследования/сравнения.

Код: [PortfolioAssetBrowser.kt](../app/src/main/java/ru/omnicio/app/ui/portfolio/PortfolioAssetBrowser.kt), [AssetComparisonScreen.kt](../app/src/main/java/ru/omnicio/app/ui/portfolio/AssetComparisonScreen.kt), [DiscoveryWorkspaceScreen.kt](../app/src/main/java/ru/omnicio/app/ui/workspace/DiscoveryWorkspaceScreen.kt).

Отдельный сценарий для этого пункта ещё не выполнен; приёмка остаётся открытой.

**Android:** Отдельного runtime-case пока нет. Tray показывает состав/количество, суммы раздельно по валютам, missing valuations/shares; сохранение исследования, watch-reason и compare 2–3. Межвалютной суммы нет.

## 3D040

**Операция и позиция.** Подтверждённая связь операции, счёта и инструмента.

Код: [AccountOperations.kt](../app/src/main/java/ru/omnicio/app/ui/portfolio/AccountOperations.kt), [PortfolioScreen.kt](../app/src/main/java/ru/omnicio/app/ui/portfolio/PortfolioScreen.kt), [WorkspaceUi.kt](../app/src/main/java/ru/omnicio/app/ui/workspace/WorkspaceUi.kt), [MainActivity.kt](../app/src/main/java/ru/omnicio/app/MainActivity.kt), [volume_workspace.py](../backend/volume_workspace.py), [volume_state.py](../backend/volume_state.py), [portfolio_details.py](../backend/portfolio_details.py).

Проверки:

- [test_volume_workspace.py](../backend/tests/test_volume_workspace.py) — `test_collected_payouts_and_operation_links_keep_actual_status_account_and_source`.
- [test_volume_workspace.py](../backend/tests/test_volume_workspace.py) — `test_operation_collection_rejects_conflicting_source_rows_without_replacing_snapshot`.

**Android:** Отдельного runtime-case пока нет. Exact operationId/date/account, автопоиск по страницам до подтверждённого ID, ограничение10k с объяснением неполноты; переход в UID-позицию/историю. Не поиск похожей строки.

**Сервер:** Связь операции со счётом и позицией идёт по брокерскому instrumentUid. Чужой пользователь/счёт не получает запись; закрытая позиция не становится текущим владением. Противоречащий дубль не проходит сбор.

## 3D041

**История в 3D.** Реальные меши столбиков, единая глубина, нули, отрицательные значения и пропуски.

Код: [HistoryChart.kt](../app/src/main/java/ru/omnicio/app/ui/portfolio/HistoryChart.kt), [HistoryBars.kt](../app/src/main/java/ru/omnicio/app/ui/portfolio/HistoryBars.kt), [SpatialComponents.kt](../app/src/main/java/ru/omnicio/app/ui/spatial/SpatialComponents.kt), [SpatialChartGuides.kt](../app/src/main/java/ru/omnicio/app/ui/spatial/SpatialChartGuides.kt), [portfolio_details.py](../backend/portfolio_details.py), [volume_contract.py](../backend/volume_contract.py).

Проверки:

- [WorkspaceFinancialSemanticsTest.kt](../app/src/test/java/ru/omnicio/app/ui/portfolio/WorkspaceFinancialSemanticsTest.kt) — `dailyHistoryKeepsAnUnobservedDateSelectableWithoutInventingZero`.
- [WorkspaceFinancialSemanticsTest.kt](../app/src/test/java/ru/omnicio/app/ui/portfolio/WorkspaceFinancialSemanticsTest.kt) — `monthlyBalanceUsesTheLastObservationRatherThanAddingBalances`.
- [SpatialChartGeometryTest.kt](../app/src/test/java/ru/omnicio/app/ui/spatial/SpatialChartGeometryTest.kt).
- [test_portfolio_details.py](../backend/tests/test_portfolio_details.py) — `DashboardApiTests::test_analytics_does_not_invent_prior_history`.
- [test_portfolio_details.py](../backend/tests/test_portfolio_details.py) — `DashboardApiTests::test_recorded_history_is_user_and_currency_scoped`.
- [test_portfolio_details.py](../backend/tests/test_portfolio_details.py) — `ValueTests::test_missing_value_is_not_zero`.

**Android:** Финансовые JVM/initial geometry passed publish-2. Mesh bars, реальные нули/отрицательные значения, null gaps. Последний Canvas удалён; новые mesh guides ожидают следующую compile/runtime проверку.

**Сервер:** История содержит реальные сохранённые наблюдения стоимости счёта, отдельно от котировочных свечей. Меши, глубина, отрицательные значения и выбор столбика проверяются на Android.

## 3D042

**Выбор столбика.** Сдвиг по Z без изменения денежной высоты.

Код: [SpatialComponents.kt](../app/src/main/java/ru/omnicio/app/ui/spatial/SpatialComponents.kt), [SpatialGeometry.kt](../app/src/main/java/ru/omnicio/app/ui/spatial/SpatialGeometry.kt), [HistoryChart.kt](../app/src/main/java/ru/omnicio/app/ui/portfolio/HistoryChart.kt).

Проверки:

- [SpatialChartGeometryTest.kt](../app/src/test/java/ru/omnicio/app/ui/spatial/SpatialChartGeometryTest.kt).

**Android:** JVM geometry passed publish-2. Выбор меняет только Z/material, не финансовую высоту. Native/renderer device evidence остаётся у renderer agent.

## 3D043

**Дата выбора.** Выбор сохраняется при смене дня, недели и месяца.

Код: [HistoryBars.kt](../app/src/main/java/ru/omnicio/app/ui/portfolio/HistoryBars.kt), [HistoryChart.kt](../app/src/main/java/ru/omnicio/app/ui/portfolio/HistoryChart.kt).

Проверки:

- [WorkspaceFinancialSemanticsTest.kt](../app/src/test/java/ru/omnicio/app/ui/portfolio/WorkspaceFinancialSemanticsTest.kt) — `aSelectedCalendarDateRemainsInsideItsDayWeekAndMonthBuckets`.
- [WorkspaceFinancialSemanticsTest.kt](../app/src/test/java/ru/omnicio/app/ui/portfolio/WorkspaceFinancialSemanticsTest.kt) — `anEvidenceInstantResolvesTheObservationAndNeverAnotherBalanceOnTheSameDay`.

**Android:** Date-bucket JVM passed publish-2; exact-Instant assertion NEW/pending. Выбранная дата сохраняется при day/week/month; точное исходное Instant отдельно в таблице, не последнее наблюдение суток.

## 3D044

**Сравнение периодов.** Две подтверждённые оценки; изменение капитала не выдаётся за доходность.

Код: [AccountPeriodComparison.kt](../app/src/main/java/ru/omnicio/app/ui/portfolio/AccountPeriodComparison.kt), [AccountAnalytics.kt](../app/src/main/java/ru/omnicio/app/ui/portfolio/AccountAnalytics.kt), [portfolio_details.py](../backend/portfolio_details.py), [volume_workspace.py](../backend/volume_workspace.py).

Проверки:

- [test_volume_workspace.py](../backend/tests/test_volume_workspace.py) — `test_attribution_uses_synchronized_boundaries_and_excludes_duplicate_external_flows`.
- [test_volume_workspace.py](../backend/tests/test_volume_workspace.py) — `test_attribution_does_not_invent_unobservable_fx_or_incomplete_flow_remainders`.

**Android:** Отдельного runtime-case пока нет. AccountPeriodComparison запрашивает оба настоящих интервала; opening/closing/change/flows раздельны. Изменение капитала не называется доходностью.

**Сервер:** Сопоставляются две реальные оценки. Изменение капитала включает внешние потоки и переоценку; отсутствующая синхронная граница не заменяется предположением.

## 3D045

**Диапазон.** Два ограничителя и точные даты; запрос после завершения выбора.

Код: [HistoryChart.kt](../app/src/main/java/ru/omnicio/app/ui/portfolio/HistoryChart.kt), [HistoryBars.kt](../app/src/main/java/ru/omnicio/app/ui/portfolio/HistoryBars.kt), [AccountAnalytics.kt](../app/src/main/java/ru/omnicio/app/ui/portfolio/AccountAnalytics.kt), [AccountDataState.kt](../app/src/main/java/ru/omnicio/app/ui/portfolio/AccountDataState.kt), [SpectrumRangeSlider.kt](../app/src/main/java/ru/omnicio/app/ui/spectrum/SpectrumRangeSlider.kt).

Проверки:

- [WorkspaceFinancialSemanticsTest.kt](../app/src/test/java/ru/omnicio/app/ui/portfolio/WorkspaceFinancialSemanticsTest.kt) — `restoredRangeDatesStayInsideTheSelectedBucketsAfterGroupingChanges`.
- [WorkspaceFinancialSemanticsTest.kt](../app/src/test/java/ru/omnicio/app/ui/portfolio/WorkspaceFinancialSemanticsTest.kt) — `rangeDatesOutsideTheReceivedSeriesClampWithoutInventingObservations`.

**Android:** NEW JVM assertions pending. Два native thumb с mesh, saveable drafts точных дат, календарь, onFinish→settled interval fetch. Drag-кадры не делают сетевые запросы. Двухручечный gesture/accessibility runtime-case ещё отсутствует.

## 3D046

**Лупа графика.** Плотные фактические данные доступны крупно.

Код: [HistoryChart.kt](../app/src/main/java/ru/omnicio/app/ui/portfolio/HistoryChart.kt), [InstrumentQuotesPanel.kt](../app/src/main/java/ru/omnicio/app/ui/portfolio/InstrumentQuotesPanel.kt).

Проверки:

- [profile_ui_probe.py](../.github/scripts/profile_ui_probe.py) — `workspace/ux100 history selection (not magnifier gesture)`.

**Android:** Runtime-сценарий написан только для обычного выбора history; подтверждённого device pass пока нет. History magnifier сохраняет исходную шкалу; OHLC magnifier имеет явно подписанную локальную шкалу цены и собственные min/max. Точные числа и кнопочные альтернативы доступны; отдельный magnifier runtime-case ещё нужен.

## 3D047

**Пропуски.** Выбираемые даты с известной причиной либо явной неизвестностью.

Код: [HistoryChart.kt](../app/src/main/java/ru/omnicio/app/ui/portfolio/HistoryChart.kt), [HistoryBars.kt](../app/src/main/java/ru/omnicio/app/ui/portfolio/HistoryBars.kt), [portfolio_details.py](../backend/portfolio_details.py).

Проверки:

- [WorkspaceFinancialSemanticsTest.kt](../app/src/test/java/ru/omnicio/app/ui/portfolio/WorkspaceFinancialSemanticsTest.kt) — `dailyHistoryKeepsAnUnobservedDateSelectableWithoutInventingZero`.
- [WorkspaceFinancialSemanticsTest.kt](../app/src/test/java/ru/omnicio/app/ui/portfolio/WorkspaceFinancialSemanticsTest.kt) — `conflictingValuesAtTheSameInstantStopHistoryEvenWithDifferentOffsets`.
- [test_portfolio_details.py](../backend/tests/test_portfolio_details.py) — `DashboardApiTests::test_analytics_does_not_invent_prior_history`.
- [test_portfolio_details.py](../backend/tests/test_portfolio_details.py) — `DashboardApiTests::test_recorded_history_is_user_and_currency_scoped`.

**Android:** JVM passed publish-2. Пропущенные даты остаются null/selectable с явной неизвестностью; zero только реальный. Конфликт значений одного Instant останавливает серию.

**Сервер:** Сервер не интерполирует отсутствующую историю и не записывает пропуск как ноль. Причина конкретного отсутствия может быть неизвестна; выбираемая дата и пояснение проверяются на Android.

## 3D048

**Свечи.** Настоящие OHLC брокера, отдельно от истории баланса, с правильными единицами.

Код: [InstrumentQuotesPanel.kt](../app/src/main/java/ru/omnicio/app/ui/portfolio/InstrumentQuotesPanel.kt), [MarketModels.kt](../app/src/main/java/ru/omnicio/app/data/market/MarketModels.kt), [WorkspaceClient.kt](../app/src/main/java/ru/omnicio/app/data/market/WorkspaceClient.kt), [volume_market.py](../backend/volume_market.py), [volume_contract.py](../backend/volume_contract.py).

Проверки:

- [WorkspaceFinancialSemanticsTest.kt](../app/src/test/java/ru/omnicio/app/ui/portfolio/WorkspaceFinancialSemanticsTest.kt) — `priceUnitsCurrenciesAndIntervalsMustBeVerifiedAndCompatible`.
- [WorkspaceFinancialSemanticsTest.kt](../app/src/test/java/ru/omnicio/app/ui/portfolio/WorkspaceFinancialSemanticsTest.kt) — `unavailableOrInsufficientCommonObservationsNeverProduceAComparison`.
- [test_volume_workspace.py](../backend/tests/test_volume_workspace.py) — `test_actual_ohlc_units_missing_intervals_and_conflict_validation`.

**Android:** JVM passed publish-2. Реальные candles API, exact decimals O/H/L/C/time/volume/source, quote-currency/%номинала/futures points; native таблица полной точности. Реальных authenticated broker/device OHLC evidence пока нет.

**Сервер:** GetCandles содержит настоящие OHLC, volume_lots и is_complete. Облигации измеряются в процентах номинала, фьючерсы — в пунктах; это не история баланса. Пустые интервалы не заполняются.

## 3D049

**Маркеры событий.** Реальные даты и источники; совпадение не выдаётся за причину цены.

Код: [InstrumentQuotesPanel.kt](../app/src/main/java/ru/omnicio/app/ui/portfolio/InstrumentQuotesPanel.kt), [DossierNewsPanel.kt](../app/src/main/java/ru/omnicio/app/ui/portfolio/DossierNewsPanel.kt), [MarketModels.kt](../app/src/main/java/ru/omnicio/app/data/market/MarketModels.kt), [volume_market.py](../backend/volume_market.py), [volume_news.py](../backend/volume_news.py), [volume_workspace.py](../backend/volume_workspace.py).

Проверки:

- [test_volume_workspace.py](../backend/tests/test_volume_workspace.py) — `test_report_calendar_uses_one_instrument_and_never_infers_publication`.
- [test_volume_workspace.py](../backend/tests/test_volume_workspace.py) — `test_news_does_not_infer_original_or_same_event_from_equal_headlines`.
- [test_volume_workspace.py](../backend/tests/test_volume_workspace.py) — `test_collected_payouts_and_operation_links_keep_actual_status_account_and_source`.

**Android:** Отдельного runtime-case пока нет. Выбираемые реальные даты/источники events; совпадение события и цены не выдается за причинность. Нет придуманных дат или исполнения.

**Сервер:** Маркеры используют фактические даты выплат, планов отчётности и новостей со своими источниками. Совпадение даты с движением цены не доказывает причинное влияние.

## 3D050

**Таблица и график.** Двусторонне связанный выбор одного наблюдения.

Код: [HistoryChart.kt](../app/src/main/java/ru/omnicio/app/ui/portfolio/HistoryChart.kt), [InstrumentQuotesPanel.kt](../app/src/main/java/ru/omnicio/app/ui/portfolio/InstrumentQuotesPanel.kt).

Проверки:

- [WorkspaceFinancialSemanticsTest.kt](../app/src/test/java/ru/omnicio/app/ui/portfolio/WorkspaceFinancialSemanticsTest.kt) — `anEvidenceInstantResolvesTheObservationAndNeverAnotherBalanceOnTheSameDay`.
- [profile_ui_probe.py](../.github/scripts/profile_ui_probe.py) — `workspace/ux100 history selection`.

**Android:** Exact-Instant JVM NEW/pending. Таблица/bar и candle/table используют общий выбор; текущий runner выбирает дату/reset, но ещё не доказывает все двусторонние связи.

## 3D051

**Досье.** Общий контекст позиции, паспорта, исследования и выплат.

Код: [InstrumentDetailsScreen.kt](../app/src/main/java/ru/omnicio/app/ui/portfolio/InstrumentDetailsScreen.kt), [InstrumentDossierPanel.kt](../app/src/main/java/ru/omnicio/app/ui/portfolio/InstrumentDossierPanel.kt), [InstrumentQuotesPanel.kt](../app/src/main/java/ru/omnicio/app/ui/portfolio/InstrumentQuotesPanel.kt), [volume_market.py](../backend/volume_market.py), [volume_state.py](../backend/volume_state.py), [research_store.py](../backend/research_store.py).

Проверки:

- [test_volume_workspace.py](../backend/tests/test_volume_workspace.py) — `test_broker_fundamental_zero_is_absent_while_negative_value_is_real`.
- [test_volume_workspace.py](../backend/tests/test_volume_workspace.py) — `test_report_calendar_uses_one_instrument_and_never_infers_publication`.
- [test_volume_workspace.py](../backend/tests/test_volume_workspace.py) — `test_reviewed_rating_change_updates_risk_history_sources_and_coverage`.

**Android:** Отдельного runtime-case пока нет. Общий UID/account для позиции, рейтингов, котировок, research, payouts/events. Объект заново разрешается в текущем снимке.

**Сервер:** load_dossier соединяет паспорт, holdings и независимо обозначенные разделы источников. Тесты проверяют финансовые/рейтинговые/отчётные разделы; полнота данных зависит от брокера и проверенных записей, live-провайдеры ими не подтверждены.

## 3D052

**Паспорт рейтинга.** Агентство, шкала, объект, дата и история; выпуск отличается от эмитента.

Код: [InstrumentDossierPanel.kt](../app/src/main/java/ru/omnicio/app/ui/portfolio/InstrumentDossierPanel.kt), [volume_market.py](../backend/volume_market.py), [volume_credit.py](../backend/volume_credit.py), [credit_evidence.py](../backend/credit_evidence.py), [research_store.py](../backend/research_store.py).

Проверки:

- [test_volume_workspace.py](../backend/tests/test_volume_workspace.py) — `test_reviewed_rating_change_updates_risk_history_sources_and_coverage`.
- [test_volume_workspace.py](../backend/tests/test_volume_workspace.py) — `test_supported_national_rating_notations_are_kept_per_agency`.

**Android:** Отдельного runtime-case пока нет. DossierRatingsPanel/DossierRatingRecord: agency, scale, subject issue/issuer+ID, grade/status/outlook, sources/history. Отсутствие рейтинга не безопасность.

**Сервер:** Рейтинг содержит агентство, национальную шкалу, объект, статус, даты и историю; выпуск не смешивается с эмитентом. Актуальное доказательство требует действующих reviewed records, включая отдельные шкалы НКР/НРА.

## 3D053

**Происхождение чисел.** Значимые показатели содержат источник, единицы, период и дату получения.

Код: [InstrumentDossierPanel.kt](../app/src/main/java/ru/omnicio/app/ui/portfolio/InstrumentDossierPanel.kt), [DossierFactSheet.kt](../app/src/main/java/ru/omnicio/app/ui/portfolio/DossierFactSheet.kt), [ResearchLibraryScreen.kt](../app/src/main/java/ru/omnicio/app/ui/workspace/ResearchLibraryScreen.kt), [volume_contract.py](../backend/volume_contract.py), [volume_market.py](../backend/volume_market.py), [portfolio_research.py](../backend/portfolio_research.py).

Проверки:

- [test_volume_workspace.py](../backend/tests/test_volume_workspace.py) — `test_broker_fundamental_zero_is_absent_while_negative_value_is_real`.
- [test_volume_workspace.py](../backend/tests/test_volume_workspace.py) — `test_fundamental_conflicts_preserve_basis_and_do_not_turn_missing_zero_into_money`.

**Android:** Отдельного runtime-case пока нет. DossierMetricsPanel/SourceProvenance раскрывают единицы, валюту, период и даты; broker_zero_means_unavailable не показан как ноль. Native quote values без округления.

**Сервер:** Метрики сохраняют Source, валюту, единицы, период и дату получения. Официальный ноль GetAssetFundamentals означает отсутствие данных. Брокерские показатели не объявляются аудированной отчётностью.

## 3D054

**Конфликты.** Различия определений, валют и периодов видимы без ложного объединения.

Код: [InstrumentDossierPanel.kt](../app/src/main/java/ru/omnicio/app/ui/portfolio/InstrumentDossierPanel.kt), [CommonPeriodComparison.kt](../app/src/main/java/ru/omnicio/app/ui/portfolio/CommonPeriodComparison.kt), [volume_market.py](../backend/volume_market.py), [volume_contract.py](../backend/volume_contract.py).

Проверки:

- [WorkspaceFinancialSemanticsTest.kt](../app/src/test/java/ru/omnicio/app/ui/portfolio/WorkspaceFinancialSemanticsTest.kt) — `priceUnitsCurrenciesAndIntervalsMustBeVerifiedAndCompatible`.
- [test_volume_workspace.py](../backend/tests/test_volume_workspace.py) — `test_fundamental_conflicts_preserve_basis_and_do_not_turn_missing_zero_into_money`.

**Android:** JVM units passed publish-2. DossierMetricConflicts показывает независимые values/period/source IDs, без ложного объединения. UI конфликтов ещё не device-verified.

**Сервер:** Конфликтующие наблюдения остаются раздельными; сравнивается основание периода/валюты. Неизвестный ноль не превращается в денежный факт, записи другого assetUid исключаются.

## 3D055

**Календарь отчётов.** Планы публикаций отличаются от уже полученных документов.

Код: [DossierReportsPanel.kt](../app/src/main/java/ru/omnicio/app/ui/portfolio/DossierReportsPanel.kt), [InstrumentDossierPanel.kt](../app/src/main/java/ru/omnicio/app/ui/portfolio/InstrumentDossierPanel.kt), [volume_market.py](../backend/volume_market.py), [research_store.py](../backend/research_store.py), [credit_evidence.py](../backend/credit_evidence.py).

Проверки:

- [WorkspaceFinancialSemanticsTest.kt](../app/src/test/java/ru/omnicio/app/ui/portfolio/WorkspaceFinancialSemanticsTest.kt) — `reportPublicationRequiresASeparateDatedSourceAndHonorsAnExplicitUnconfirmedFlag`.
- [WorkspaceFinancialSemanticsTest.kt](../app/src/test/java/ru/omnicio/app/ui/portfolio/WorkspaceFinancialSemanticsTest.kt) — `reportDatesUseMoscowCalendarForInstantsAndPreserveSourceCalendarDates`.
- [test_volume_workspace.py](../backend/tests/test_volume_workspace.py) — `test_report_calendar_uses_one_instrument_and_never_infers_publication`.

**Android:** NEW JVM pending. Месяц/status/calendar, source period и created-time отдельно. Прошедшая объявленная дата не становится опубликованным отчётом; published требует отдельного датированного источника. Календарь по конкретному инструменту, не всем бумагам сразу.

**Сервер:** GetAssetReports запрашивается с одним instrumentId. Прошедшая дата плана не подтверждает публикацию; published требует проверенного документа и датированного Source. Автоматического получения всех отчётов эмитентов не заявлено.

## 3D056

**Новости.** Дедупликация события с различением первоисточника и повторов.

Код: [DossierNewsPanel.kt](../app/src/main/java/ru/omnicio/app/ui/portfolio/DossierNewsPanel.kt), [InstrumentDossierPanel.kt](../app/src/main/java/ru/omnicio/app/ui/portfolio/InstrumentDossierPanel.kt), [DossierFactSheet.kt](../app/src/main/java/ru/omnicio/app/ui/portfolio/DossierFactSheet.kt), [volume_news.py](../backend/volume_news.py), [volume_market.py](../backend/volume_market.py), [research_store.py](../backend/research_store.py).

Проверки:

- [test_volume_workspace.py](../backend/tests/test_volume_workspace.py) — `test_news_does_not_infer_original_or_same_event_from_equal_headlines`.
- [test_volume_workspace.py](../backend/tests/test_volume_workspace.py) — `test_reviewed_news_links_bind_exact_observations_and_expose_original_repost`.
- [test_volume_workspace.py](../backend/tests/test_volume_workspace.py) — `test_news_review_rejects_missing_or_malformed_primary_source`.

**Android:** Отдельного runtime-case пока нет. Нет клиентского объединения headline. Backend verified-event/deduplication управляет группировкой; primary/repost требуют reviewed evidence; primary_sources отдельно. Непроверенная идентичность/роль явно неизвестна.

**Сервер:** Брокерский News не предоставляет первоисточник/репост/URL как доказательство. Роль и event identity назначаются только по reviewed записи, связанной с точным отпечатком публикации; иначе unknown. Равного заголовка для объединения недостаточно.

## 3D057

**Событие и портфель.** Факт, канал влияния, компания и позиция; гипотеза подписана отдельно.

Код: [DossierFactSheet.kt](../app/src/main/java/ru/omnicio/app/ui/portfolio/DossierFactSheet.kt), [DossierNewsPanel.kt](../app/src/main/java/ru/omnicio/app/ui/portfolio/DossierNewsPanel.kt), [InstrumentDossierPanel.kt](../app/src/main/java/ru/omnicio/app/ui/portfolio/InstrumentDossierPanel.kt), [volume_workspace.py](../backend/volume_workspace.py), [volume_monitor.py](../backend/volume_monitor.py), [volume_market.py](../backend/volume_market.py), [volume_news.py](../backend/volume_news.py).

Проверки:

- [test_volume_workspace.py](../backend/tests/test_volume_workspace.py) — `test_verified_issuer_group_identity_is_used_without_ticker_guessing`.
- [test_volume_workspace.py](../backend/tests/test_volume_workspace.py) — `test_reviewed_news_links_bind_exact_observations_and_expose_original_repost`.

**Android:** Отдельного runtime-case пока нет. Факт→компания→мои позиции хранит fact key и показывает все счета. Issuer identity только с reviewed source. Неизвестный канал влияния/причина не дорисованы.

**Сервер:** News→instrument подтверждается брокерской UID-связью, holdings принадлежат пользователю, эмитент требует verified identity. Эти тесты подтверждают компоненты доказательств. Экономический канал влияния код не устанавливает: impact=null, гипотеза обозначена отдельно.

## 3D058

**География.** Глобус с явно выбранной проверенной осью и доступным списком.

Код: [GeographyWorkspacePanel.kt](../app/src/main/java/ru/omnicio/app/ui/workspace/GeographyWorkspacePanel.kt), [MarketWorkspaceScreen.kt](../app/src/main/java/ru/omnicio/app/ui/workspace/MarketWorkspaceScreen.kt), [SpatialGeography.kt](../app/src/main/java/ru/omnicio/app/ui/spatial/SpatialGeography.kt), [CountryCoordinates.kt](../app/src/main/java/ru/omnicio/app/data/market/CountryCoordinates.kt), [volume_state.py](../backend/volume_state.py), [volume_workspace.py](../backend/volume_workspace.py), [volume_market.py](../backend/volume_market.py).

Проверки:

- [SpatialGeographyGeometryTest.kt](../app/src/test/java/ru/omnicio/app/ui/spatial/SpatialGeographyGeometryTest.kt).

**Android:** 3 projection JVM passed publish-2. Ось country-of-risk брокера, реальный globe+native список/filter. Google DSPL anchors — ориентиры страны, не локация эмитента; неизвестные остаются в списке. Device pick/filter pending.

**Сервер:** Ось country использует countryOfRisk/countryOfRiskName из брокерского справочника; это страна риска, а не регистрация, биржа или география выручки. Неизвестная страна остаётся неизвестной. Отдельной backend-регрессии самой оси country нет; география проверяется Android evidence.

## 3D059

**Торговый календарь.** Подтверждённые сессии, местное и московское время.

Код: [TradingCalendarPanel.kt](../app/src/main/java/ru/omnicio/app/ui/workspace/TradingCalendarPanel.kt), [MarketWorkspaceScreen.kt](../app/src/main/java/ru/omnicio/app/ui/workspace/MarketWorkspaceScreen.kt), [WorkspaceClient.kt](../app/src/main/java/ru/omnicio/app/data/market/WorkspaceClient.kt), [volume_market.py](../backend/volume_market.py), [volume_notifications.py](../backend/volume_notifications.py), [volume_monitor.py](../backend/volume_monitor.py).

Проверки:

- [test_volume_workspace.py](../backend/tests/test_volume_workspace.py) — `test_monitor_trigger_uses_previous_real_observation_and_preserves_slot_decision`.

**Android:** Отдельного runtime-case пока нет. Реальные7дней биржевого расписания, Moscow+device local одновременно. Сессия площадки не подтверждает доступность конкретной бумаги.

**Сервер:** TradingSchedules и GetTradingStatus сохраняют реальные сессии/доступность; UTC отображается Android в местном и московском времени. Тест подтверждает календарное основание мониторинга, а не живой доступ к бирже; общий календарь не гарантирует сделку по инструменту.

## 3D060

**Возврат от брокера.** Обновление и сверка; открытие ссылки не означает исполнение.

Код: [PortfolioResearchPanel.kt](../app/src/main/java/ru/omnicio/app/ui/research/PortfolioResearchPanel.kt), [PlansWorkspaceScreen.kt](../app/src/main/java/ru/omnicio/app/ui/workspace/PlansWorkspaceScreen.kt), [AccountOperations.kt](../app/src/main/java/ru/omnicio/app/ui/portfolio/AccountOperations.kt), [volume_plans.py](../backend/volume_plans.py), [volume_jobs.py](../backend/volume_jobs.py), [portfolio_details.py](../backend/portfolio_details.py).

Проверки:

- [business_ui_probe.py](../.github/scripts/business_ui_probe.py) — `plans/ready,partial`.
- [test_volume_workspace.py](../backend/tests/test_volume_workspace.py) — `test_manual_broker_handoff_does_not_claim_execution_and_requires_operation_association`.

**Android:** Runtime-сценарий написан; подтверждённого device pass пока нет. Root broker-return refresh/reconcile. Fixture доказывает только synthetic расчёт/operation binding/incomplete-source UI, не внешнее открытие брокера и не сделку.

**Сервер:** Открытие брокера не подтверждает исполнение. Сверка read-only; пользователь явно связывает подходящие исполненные операции, а исправления источника пересматривают partial/done.

## 3D061

**Ассистент.** Настоящая объёмная модель для ожидания, проверки, готовности и ошибки.

Код: [SpectrumAnalystAvatar.kt](../app/src/main/java/ru/omnicio/app/ui/spectrum/SpectrumAnalystAvatar.kt), [SpatialComponents.kt](../app/src/main/java/ru/omnicio/app/ui/spatial/SpatialComponents.kt), [BusinessWorkspaceProbe.kt](../app/src/debug/java/ru/omnicio/app/BusinessWorkspaceProbe.kt), [AssistantWorkspaceScreen.kt](../app/src/main/java/ru/omnicio/app/ui/workspace/AssistantWorkspaceScreen.kt), [volume_jobs.py](../backend/volume_jobs.py), [volume_chat.py](../backend/volume_chat.py), [volume_workspace.py](../backend/volume_workspace.py).

Проверки:

- [business_ui_probe.py](../.github/scripts/business_ui_probe.py).
- [spatial_ui_probe.py](../.github/scripts/spatial_ui_probe.py).
- [business_ui_probe.py](../.github/scripts/business_ui_probe.py) — `assistant/ready,empty,partial,error,job`.
- [test_volume_workspace.py](../backend/tests/test_volume_workspace.py) — `test_real_guarded_chat_is_charged_once_and_recovered_by_request`.
- [test_volume_workspace.py](../backend/tests/test_volume_workspace.py) — `test_ambiguous_chat_timeout_cannot_repeat_or_fake_an_answer`.

**3D-ядро:** Настоящая модель avatar с объёмным state badge; состояние соответствует клиенту, не выдуманному прогрессу ИИ. Все assistant ready/empty/partial/error/job случаи включены; узнаваемость и чтение требуют кадров.

**Android:** Runtime-сценарий написан; подтверждённого device pass пока нет. Production Assistant composable с реальными mesh и синтетическим transport. Нет платного запроса модели или реального брокерского счёта.

**Сервер:** Ассистент получает реальные состояния задания/модели; ожидание, готовность и ошибка не имитируются таймером. Объёмная модель и анимация этих состояний принадлежат Android.

## 3D062

**Плановые анализы.** Последний и следующий утренний/вечерний запуск, причина пропуска.

Код: [AnalysisTimelineScreen.kt](../app/src/main/java/ru/omnicio/app/ui/workspace/AnalysisTimelineScreen.kt), [AnalysisMonitorPanels.kt](../app/src/main/java/ru/omnicio/app/ui/workspace/AnalysisMonitorPanels.kt), [BusinessWorkspaceProbe.kt](../app/src/debug/java/ru/omnicio/app/BusinessWorkspaceProbe.kt), [AnalysisTimelineProbeData.kt](../app/src/debug/java/ru/omnicio/app/AnalysisTimelineProbeData.kt), [volume_monitor.py](../backend/volume_monitor.py), [volume_workspace.py](../backend/volume_workspace.py), [volume_notifications.py](../backend/volume_notifications.py), [autonomous_ai.py](../backend/autonomous_ai.py).

Проверки:

- [analysis_ui_probe.py](../.github/scripts/analysis_ui_probe.py) — `exercise_analysis`.
- [business_ui_probe.py](../.github/scripts/business_ui_probe.py) — `analysis/ready,empty,partial,error`.
- [test_volume_workspace.py](../backend/tests/test_volume_workspace.py) — `test_skipped_monitor_check_is_exposed_without_a_paid_analysis_record`.
- [test_volume_workspace.py](../backend/tests/test_volume_workspace.py) — `test_monitor_trigger_uses_previous_real_observation_and_preserves_slot_decision`.

**Android:** Runtime-сценарий написан; подтверждённого device pass пока нет. Saved/skip slots, check-source, report marker, diff facts, cooldown/budget/empty/error. Все данные synthetic. Exact navigation marker не открывает сам Reports/Portfolio target.

**Сервер:** Отдельно сохраняются реальные checks, утренний/вечерний slot decision, причины пропуска и следующий график. История возникает только после действительного server check; старые пропуски не сочиняются.

## 3D063

**Внеплановый анализ.** Материальное событие и подтверждённый источник запуска.

Код: [AnalysisTimelineScreen.kt](../app/src/main/java/ru/omnicio/app/ui/workspace/AnalysisTimelineScreen.kt), [AnalysisMonitorPanels.kt](../app/src/main/java/ru/omnicio/app/ui/workspace/AnalysisMonitorPanels.kt), [BusinessWorkspaceProbe.kt](../app/src/debug/java/ru/omnicio/app/BusinessWorkspaceProbe.kt), [AnalysisTimelineProbeData.kt](../app/src/debug/java/ru/omnicio/app/AnalysisTimelineProbeData.kt), [volume_monitor.py](../backend/volume_monitor.py), [autonomous_ai.py](../backend/autonomous_ai.py), [volume_workspace.py](../backend/volume_workspace.py).

Проверки:

- [analysis_ui_probe.py](../.github/scripts/analysis_ui_probe.py) — `exercise_analysis`.
- [business_ui_probe.py](../.github/scripts/business_ui_probe.py) — `analysis/ready,empty,partial,error`.
- [test_volume_workspace.py](../backend/tests/test_volume_workspace.py) — `test_monitor_trigger_uses_previous_real_observation_and_preserves_slot_decision`.

**Android:** Runtime-сценарий написан; подтверждённого device pass пока нет. Saved/skip slots, check-source, report marker, diff facts, cooldown/budget/empty/error. Все данные synthetic. Exact navigation marker не открывает сам Reports/Portfolio target.

**Сервер:** Причина внеплановой проверки связана с предыдущим автономным наблюдением, конкретными изменениями/рисками и Source. GET истории не запускает новый брокерский fanout.

## 3D064

**Версии анализа.** Новые факты, изменения и неизменившиеся выводы.

Код: [AnalysisTimelineScreen.kt](../app/src/main/java/ru/omnicio/app/ui/workspace/AnalysisTimelineScreen.kt), [AnalysisMonitorPanels.kt](../app/src/main/java/ru/omnicio/app/ui/workspace/AnalysisMonitorPanels.kt), [BusinessWorkspaceProbe.kt](../app/src/debug/java/ru/omnicio/app/BusinessWorkspaceProbe.kt), [AnalysisTimelineProbeData.kt](../app/src/debug/java/ru/omnicio/app/AnalysisTimelineProbeData.kt), [volume_analysis.py](../backend/volume_analysis.py), [volume_workspace.py](../backend/volume_workspace.py), [autonomous_ai.py](../backend/autonomous_ai.py).

Проверки:

- [analysis_ui_probe.py](../.github/scripts/analysis_ui_probe.py) — `exercise_analysis`.
- [business_ui_probe.py](../.github/scripts/business_ui_probe.py) — `analysis/ready,empty,partial,error`.
- [test_volume_workspace.py](../backend/tests/test_volume_workspace.py) — `test_structured_fact_versions_compare_actual_values_and_keep_unchanged`.

**Android:** Runtime-сценарий написан; подтверждённого device pass пока нет. Saved/skip slots, check-source, report marker, diff facts, cooldown/budget/empty/error. Все данные synthetic. Exact navigation marker не открывает сам Reports/Portfolio target.

**Сервер:** Факты сравниваются по устойчивому ID: added/removed/changed/unchanged, отдельно provenance_changed. Для legacy-карточки без facts_blob точная фактографическая сверка недоступна; равенство текста её не заменяет.

## 3D065

**Рабочий чат.** Реальная модель через guarded gateway и ограниченные собственным пользователем инструменты.

Код: [AssistantWorkspaceScreen.kt](../app/src/main/java/ru/omnicio/app/ui/workspace/AssistantWorkspaceScreen.kt), [BusinessWorkspaceProbe.kt](../app/src/debug/java/ru/omnicio/app/BusinessWorkspaceProbe.kt), [volume_chat.py](../backend/volume_chat.py), [volume_jobs.py](../backend/volume_jobs.py), [ai_guarded_client.py](../backend/ai_guarded_client.py), [ai_budget.py](../backend/ai_budget.py).

Проверки:

- [business_ui_probe.py](../.github/scripts/business_ui_probe.py) — `assistant/ready`.
- [test_volume_workspace.py](../backend/tests/test_volume_workspace.py) — `test_real_guarded_chat_is_charged_once_and_recovered_by_request`.
- [test_volume_workspace.py](../backend/tests/test_volume_workspace.py) — `test_scoped_chat_rejects_other_accounts`.
- [test_volume_workspace.py](../backend/tests/test_volume_workspace.py) — `test_chat_cursor_paginates_identical_timestamps_and_is_bound_to_user_thread`.

**Android:** Runtime-сценарий написан; подтверждённого device pass пока нет. Fake estimate/send/poll/read проверяет запросы/ввод; не доказывает production LLM quality, реальную цену или изоляцию инструментов.

**Сервер:** Настоящий guarded gateway получает ограниченный собственными счетами/периодом пакет фактов. Request ID восстанавливает запрос без дублирования. Для рабочего подключения нужны действующие настройки gateway/моделей и разрешение внешней обработки; эти тесты используют HTTP mock.

## 3D066

**Связь объяснения.** Выделение конкретных позиций, столбиков и операций по ссылкам ответа.

Код: [PortfolioScreen.kt](../app/src/main/java/ru/omnicio/app/ui/portfolio/PortfolioScreen.kt), [AccountAnalytics.kt](../app/src/main/java/ru/omnicio/app/ui/portfolio/AccountAnalytics.kt), [HistoryChart.kt](../app/src/main/java/ru/omnicio/app/ui/portfolio/HistoryChart.kt), [AccountOperations.kt](../app/src/main/java/ru/omnicio/app/ui/portfolio/AccountOperations.kt), [WorkspaceData.kt](../app/src/main/java/ru/omnicio/app/ui/workspace/WorkspaceData.kt), [BusinessWorkspaceProbe.kt](../app/src/debug/java/ru/omnicio/app/BusinessWorkspaceProbe.kt), [volume_chat.py](../backend/volume_chat.py), [portfolio_details.py](../backend/portfolio_details.py).

Проверки:

- [WorkspaceFinancialSemanticsTest.kt](../app/src/test/java/ru/omnicio/app/ui/portfolio/WorkspaceFinancialSemanticsTest.kt) — `selectedPositionResolvesTheCurrentAccountAndRefusesAmbiguousOrRemovedRows`.
- [WorkspaceFinancialSemanticsTest.kt](../app/src/test/java/ru/omnicio/app/ui/portfolio/WorkspaceFinancialSemanticsTest.kt) — `anEvidenceInstantResolvesTheObservationAndNeverAnotherBalanceOnTheSameDay`.
- [business_ui_probe.py](../.github/scripts/business_ui_probe.py) — `assistant/ready`.
- [test_volume_workspace.py](../backend/tests/test_volume_workspace.py) — `test_chat_scope_sources_real_history_and_allowlisted_navigation`.
- [test_volume_workspace.py](../backend/tests/test_volume_workspace.py) — `test_scoped_chat_rejects_other_accounts`.

**Android:** Identity JVM passed; exact Instant NEW/pending. Fake navigator проверяет IDs, target не рисует. Start/end/history_resolution передаются, source frequency отделена от visual day/week/month.

**Сервер:** Ответ допускает только серверные allowlisted ссылки на позиции, реальные операции и сохранённые history observations. История содержит точный timestamp, Moscow calendar bounds и resolution; несуществующий столбик не подставляется.

## 3D067

**Доказательства.** Источники конкретного утверждения и явная неопределённость.

Код: [AssistantWorkspaceScreen.kt](../app/src/main/java/ru/omnicio/app/ui/workspace/AssistantWorkspaceScreen.kt), [WorkspacePanels.kt](../app/src/main/java/ru/omnicio/app/ui/workspace/WorkspacePanels.kt), [BusinessWorkspaceProbe.kt](../app/src/debug/java/ru/omnicio/app/BusinessWorkspaceProbe.kt), [volume_chat.py](../backend/volume_chat.py), [volume_contract.py](../backend/volume_contract.py), [ai_guarded_client.py](../backend/ai_guarded_client.py).

Проверки:

- [business_ui_probe.py](../.github/scripts/business_ui_probe.py) — `assistant/partial`.
- [analysis_ui_probe.py](../.github/scripts/analysis_ui_probe.py) — `exercise_analysis`.
- [test_volume_workspace.py](../backend/tests/test_volume_workspace.py) — `test_chat_scope_sources_real_history_and_allowlisted_navigation`.
- [test_volume_workspace.py](../backend/tests/test_volume_workspace.py) — `test_real_guarded_chat_is_charged_once_and_recovered_by_request`.

**Android:** Runtime-сценарий написан; подтверждённого device pass пока нет. Явные uncertainty/missing rating и собственные sources проверки. Достоверность настоящего серверного ответа требует backend evidence.

**Сервер:** Claims связываются с допустимыми facts/source IDs, проверенными metadata target, Source records и coverage. Формальная привязка не доказывает истинность каждого свободного предложения модели; неопределённость и гипотезы остаются явными.

## 3D068

**Стоимость ИИ.** Фактический расход и проверенная оценка до глубокого задания; неизвестная цена не выдумывается.

Код: [AssistantWorkspaceScreen.kt](../app/src/main/java/ru/omnicio/app/ui/workspace/AssistantWorkspaceScreen.kt), [BusinessWorkspaceProbe.kt](../app/src/debug/java/ru/omnicio/app/BusinessWorkspaceProbe.kt), [volume_chat.py](../backend/volume_chat.py), [volume_workspace.py](../backend/volume_workspace.py), [ai_budget.py](../backend/ai_budget.py), [ai_guarded_client.py](../backend/ai_guarded_client.py).

Проверки:

- [business_ui_probe.py](../.github/scripts/business_ui_probe.py) — `assistant/ready`.
- [test_volume_workspace.py](../backend/tests/test_volume_workspace.py) — `test_real_guarded_chat_is_charged_once_and_recovered_by_request`.
- [test_ai_controls.py](../backend/tests/test_ai_controls.py) — `GuardedClientTests::test_prices_bound_to_model`.
- [test_ai_controls.py](../backend/tests/test_ai_controls.py) — `GuardedClientTests::test_expired_prices_do_not_allow_a_free_estimate`.
- [test_ai_controls.py](../backend/tests/test_ai_controls.py) — `GuardedClientTests::test_missing_usage_keeps_full_reservation`.
- [test_ai_controls.py](../backend/tests/test_ai_controls.py) — `GuardedClientTests::test_timeout_has_no_free_retry`.

**Android:** Runtime-сценарий написан; подтверждённого device pass пока нет. Fixture требует estimate перед enqueue/read. Не подтверждает реальную provider price/expense.

**Сервер:** Расход берётся из денежного ledger, оценка — из действующего закреплённого тарифа модели. Неизвестная цена/usage не равны нулю; предварительный потолок не объявляется точным счётом.

## 3D069

**План действий.** Расчёт, открытие брокера, сверка, частичное/полное исполнение и устаревание по источнику.

Код: [PlansWorkspaceScreen.kt](../app/src/main/java/ru/omnicio/app/ui/workspace/PlansWorkspaceScreen.kt), [BusinessWorkspaceProbe.kt](../app/src/debug/java/ru/omnicio/app/BusinessWorkspaceProbe.kt), [volume_plans.py](../backend/volume_plans.py), [volume_jobs.py](../backend/volume_jobs.py), [volume_state.py](../backend/volume_state.py), [portfolio_details.py](../backend/portfolio_details.py).

Проверки:

- [business_ui_probe.py](../.github/scripts/business_ui_probe.py) — `plans/ready,empty,partial,error,job`.
- [test_volume_workspace.py](../backend/tests/test_volume_workspace.py) — `test_manual_broker_handoff_does_not_claim_execution_and_requires_operation_association`.
- [test_volume_workspace.py](../backend/tests/test_volume_workspace.py) — `test_manual_plan_request_recovery_survives_a_later_position_change`.

**Android:** Runtime-сценарий написан; подтверждённого device pass пока нет. Production calculation/partial quantities/operation bind по synthetic source. Ни одна торговая заявка не отправляется.

**Сервер:** Пользовательский план проверяет удерживаемую позицию и целые лоты; открытие ссылки не подтверждает исполнение, partial/done требуют связанных текущих операций, новая стратегия переводит план в obsolete. Это не общий оптимизатор F09; стоимость по снимку не является исполнимой котировкой или рассчитанной комиссией.

## 3D070

**Отмена задания.** Запрос отмены, подтверждение, продолжение и безопасное получение без двойной оплаты.

Код: [WorkspacePanels.kt](../app/src/main/java/ru/omnicio/app/ui/workspace/WorkspacePanels.kt), [AssistantWorkspaceScreen.kt](../app/src/main/java/ru/omnicio/app/ui/workspace/AssistantWorkspaceScreen.kt), [JobCheckpointStore.kt](../app/src/main/java/ru/omnicio/app/data/workspace/JobCheckpointStore.kt), [BusinessWorkspaceProbe.kt](../app/src/debug/java/ru/omnicio/app/BusinessWorkspaceProbe.kt), [volume_jobs.py](../backend/volume_jobs.py), [volume_chat.py](../backend/volume_chat.py), [ai_jobs.py](../backend/ai_jobs.py), [ai_guarded_client.py](../backend/ai_guarded_client.py), [ai_budget.py](../backend/ai_budget.py).

Проверки:

- [business_ui_probe.py](../.github/scripts/business_ui_probe.py) — `assistant/job,plans/job`.
- [test_volume_workspace.py](../backend/tests/test_volume_workspace.py) — `test_request_id_conflict_recovery_and_user_isolation`.
- [test_volume_workspace.py](../backend/tests/test_volume_workspace.py) — `test_checkpoint_retry_and_queue_selection_do_not_starve_other_users`.
- [test_volume_workspace.py](../backend/tests/test_volume_workspace.py) — `test_cancelled_worker_cannot_commit_and_paid_expiry_cannot_retry`.
- [test_volume_workspace.py](../backend/tests/test_volume_workspace.py) — `test_ambiguous_chat_timeout_cannot_repeat_or_fake_an_answer`.
- [test_volume_workspace.py](../backend/tests/test_volume_workspace.py) — `test_guarded_cancellation_before_send_refunds_known_unsent_only`.

**Android:** Runtime-сценарий написан; подтверждённого device pass пока нет. Сохранённый unknown job восстанавливается без unsafe repeat. Все cancellation races и process-death ещё не покрыты.

**Сервер:** Запрос отмены отличается от подтверждённого результата. Сбор продолжает подтверждённый checkpoint; неоднозначный оплаченный запрос не повторяется. Устаревший владелец задания не может зафиксировать результат.

## 3D071

**Влияние стратегии.** Проверенный preview по версии правил и снимку, затем подтверждение.

Код: [LiveStrategyScreen.kt](../app/src/main/java/ru/omnicio/app/ui/workspace/LiveStrategyScreen.kt), [BusinessWorkspaceProbe.kt](../app/src/debug/java/ru/omnicio/app/BusinessWorkspaceProbe.kt), [volume_state.py](../backend/volume_state.py), [autonomous_ai.py](../backend/autonomous_ai.py), [volume_notifications.py](../backend/volume_notifications.py).

Проверки:

- [business_ui_probe.py](../.github/scripts/business_ui_probe.py) — `strategy/ready,partial`.
- [test_volume_workspace.py](../backend/tests/test_volume_workspace.py) — `test_strategy_confirmation_is_cas_idempotent_and_applied_to_monitor`.
- [test_volume_workspace.py](../backend/tests/test_volume_workspace.py) — `test_strategy_preview_detects_snapshot_change_and_rollback_creates_new_version`.

**Android:** Runtime-сценарий написан; подтверждённого device pass пока нет. Версионированный preview до confirm, incomplete блокирует применение. Fake transport rejects config+rollback одновременно.

**Сервер:** Preview привязан к версии и свежему снимку, имеет срок действия; confirm проверяет CAS и подключение. Подтверждённые правила действительно читает monitor. Preview не выполняет сделок и не доказывает withdrawable cash.

## 3D072

**История стратегии.** Сравнение версий и подготовка заново проверенного возврата.

Код: [LiveStrategyScreen.kt](../app/src/main/java/ru/omnicio/app/ui/workspace/LiveStrategyScreen.kt), [BusinessWorkspaceProbe.kt](../app/src/debug/java/ru/omnicio/app/BusinessWorkspaceProbe.kt), [volume_state.py](../backend/volume_state.py).

Проверки:

- [business_ui_probe.py](../.github/scripts/business_ui_probe.py) — `strategy/ready`.
- [test_volume_workspace.py](../backend/tests/test_volume_workspace.py) — `test_strategy_preview_detects_snapshot_change_and_rollback_creates_new_version`.
- [test_volume_workspace.py](../backend/tests/test_volume_workspace.py) — `test_strategy_confirmation_is_cas_idempotent_and_applied_to_monitor`.

**Android:** Runtime-сценарий написан; подтверждённого device pass пока нет. Rollback проходит новый preview и создаёт новую подтверждённую версию. Production concurrency — backend tests.

**Сервер:** История неизменяемых версий сохраняется. Возврат создаёт новую версию через заново проверенный preview; прежние данные и версии не перезаписываются.

## 3D073

**Покрытие рисков.** По направлениям и позициям, с возрастом данных; неизвестно не означает безопасно.

Код: [RiskWorkspaceScreen.kt](../app/src/main/java/ru/omnicio/app/ui/workspace/RiskWorkspaceScreen.kt), [BusinessWorkspaceProbe.kt](../app/src/debug/java/ru/omnicio/app/BusinessWorkspaceProbe.kt), [volume_state.py](../backend/volume_state.py), [volume_credit.py](../backend/volume_credit.py), [volume_market.py](../backend/volume_market.py), [volume_workspace.py](../backend/volume_workspace.py), [tinvest_portfolio.py](../backend/tinvest_portfolio.py).

Проверки:

- [business_ui_probe.py](../.github/scripts/business_ui_probe.py) — `risk/ready,empty,partial,error`.
- [test_volume_workspace.py](../backend/tests/test_volume_workspace.py) — `test_verified_issuer_group_identity_is_used_without_ticker_guessing`.
- [test_volume_workspace.py](../backend/tests/test_volume_workspace.py) — `test_reviewed_rating_change_updates_risk_history_sources_and_coverage`.
- [test_volume_workspace.py](../backend/tests/test_volume_workspace.py) — `test_incomplete_broker_positions_cannot_resolve_risk_or_claim_complete_scenario`.

**Android:** Runtime-сценарий написан; подтверждённого device pass пока нет. Native known/total positions и missing coverage; coverage не вероятность потери, unknown share не ноль.

**Сервер:** Покрытие относится к position/issuer/group/sector/currency/country/ratings/trading/liquidity и актуальности источника. Полная вероятность дефолта/процентного риска не заявляется; загрузка лимитов и виртуальные позиции делают покрытие неполным.

## 3D074

**Концентрации.** Компания, группа и сектор против действительных пользовательских лимитов.

Код: [RiskWorkspaceScreen.kt](../app/src/main/java/ru/omnicio/app/ui/workspace/RiskWorkspaceScreen.kt), [BusinessWorkspaceProbe.kt](../app/src/debug/java/ru/omnicio/app/BusinessWorkspaceProbe.kt), [volume_state.py](../backend/volume_state.py), [volume_workspace.py](../backend/volume_workspace.py), [research_store.py](../backend/research_store.py).

Проверки:

- [business_ui_probe.py](../.github/scripts/business_ui_probe.py) — `risk/ready,partial`.
- [test_volume_workspace.py](../backend/tests/test_volume_workspace.py) — `test_verified_issuer_group_identity_is_used_without_ticker_guessing`.
- [test_volume_workspace.py](../backend/tests/test_volume_workspace.py) — `test_strategy_confirmation_is_cas_idempotent_and_applied_to_monitor`.
- [test_volume_workspace.py](../backend/tests/test_volume_workspace.py) — `test_missing_risk_basis_is_not_recorded_as_resolved`.

**Android:** Runtime-сценарий написан; подтверждённого device pass пока нет. Лимит превышен отличается от отсутствующей доли/лимита. Verified issuer/group source проверяется backend отдельно.

**Сервер:** Концентрации сравниваются с действительными подтверждёнными лимитами. Компания/группа требует проверенной связи; неизвестная доля или оценка не означает безопасную концентрацию.

## 3D075

**Стресс.** Сравнение сценариев с явно указанными предположениями и ограничениями.

Код: [RiskWorkspaceScreen.kt](../app/src/main/java/ru/omnicio/app/ui/workspace/RiskWorkspaceScreen.kt), [BusinessWorkspaceProbe.kt](../app/src/debug/java/ru/omnicio/app/BusinessWorkspaceProbe.kt), [volume_state.py](../backend/volume_state.py), [volume_contract.py](../backend/volume_contract.py).

Проверки:

- [test_volume_workspace.py](../backend/tests/test_volume_workspace.py) — `test_quotation_and_scenario_arithmetic_ignore_ambient_decimal_precision`.
- [test_volume_workspace.py](../backend/tests/test_volume_workspace.py) — `test_scenarios_reject_unknown_selectors_and_implicit_overlap`.
- [test_volume_workspace.py](../backend/tests/test_volume_workspace.py) — `test_unknown_sector_cannot_be_assumed_unaffected`.
- [test_volume_workspace.py](../backend/tests/test_volume_workspace.py) — `test_compared_scenarios_share_one_real_baseline_without_forecast`.
- [test_volume_workspace.py](../backend/tests/test_volume_workspace.py) — `test_incomplete_broker_positions_cannot_resolve_risk_or_claim_complete_scenario`.

**Android:** Отдельного runtime-case пока нет. Transport валидирует 2–4 сценария одного snapshot/currency; текущий business runner ещё не проходит UI сравнения стрессов.

**Сервер:** Две–четыре пользовательские гипотезы используют один фактический baseline. Линейная переоценка не является прогнозом/FX/деривативной моделью; пересекающиеся shocks отклоняются, неполное покрытие не получает estimated_after.

## 3D076

**Проверка риска.** Подтверждённые факты и затронутые позиции; просмотр не означает финансовую сделку.

Код: [RiskWorkspaceScreen.kt](../app/src/main/java/ru/omnicio/app/ui/workspace/RiskWorkspaceScreen.kt), [BusinessWorkspaceProbe.kt](../app/src/debug/java/ru/omnicio/app/BusinessWorkspaceProbe.kt), [volume_state.py](../backend/volume_state.py).

Проверки:

- [business_ui_probe.py](../.github/scripts/business_ui_probe.py) — `risk/ready`.
- [test_volume_workspace.py](../backend/tests/test_volume_workspace.py) — `test_risk_check_freezes_owned_evidence_and_survives_a_closed_position`.

**Android:** Runtime-сценарий написан; подтверждённого device pass пока нет. Создание checklist и native unchecked→server-confirmed checked. Проверенный пункт не означает сделку.

**Сервер:** План проверки замораживает owned событие, снимок, позиции, Source и подтверждённую стратегию. Закрытая позднее позиция остаётся в историческом основании. Выполненная проверка не означает финансовую сделку.

## 3D077

**История риска.** Возникновение, изменение, закрытие и устаревание с основанием.

Код: [RiskWorkspaceScreen.kt](../app/src/main/java/ru/omnicio/app/ui/workspace/RiskWorkspaceScreen.kt), [BusinessWorkspaceProbe.kt](../app/src/debug/java/ru/omnicio/app/BusinessWorkspaceProbe.kt), [volume_workspace.py](../backend/volume_workspace.py), [volume_state.py](../backend/volume_state.py), [volume_credit.py](../backend/volume_credit.py).

Проверки:

- [business_ui_probe.py](../.github/scripts/business_ui_probe.py) — `risk/partial`.
- [test_volume_workspace.py](../backend/tests/test_volume_workspace.py) — `test_missing_risk_basis_is_not_recorded_as_resolved`.
- [test_volume_workspace.py](../backend/tests/test_volume_workspace.py) — `test_reviewed_rating_change_updates_risk_history_sources_and_coverage`.
- [test_volume_workspace.py](../backend/tests/test_volume_workspace.py) — `test_incomplete_broker_positions_cannot_resolve_risk_or_claim_complete_scenario`.

**Android:** Runtime-сценарий написан; подтверждённого device pass пока нет. Stale rating не показывается как устранённый риск; другие варианты событий остаются за backend тестами.

**Сервер:** История хранит наблюдённое превышение/изменение/устранение/устаревание и основание. Утрата оценки или источника ведёт к stale, а не ложному resolved.

## 3D078

**Уведомления.** Серверные тихие часы, часовой пояс, график и реальные стадии доставки.

Код: [NotificationWorkspaceScreens.kt](../app/src/main/java/ru/omnicio/app/ui/workspace/NotificationWorkspaceScreens.kt), [BusinessWorkspaceProbe.kt](../app/src/debug/java/ru/omnicio/app/BusinessWorkspaceProbe.kt), [volume_notifications.py](../backend/volume_notifications.py), [volume_state.py](../backend/volume_state.py), [volume_workspace.py](../backend/volume_workspace.py), [autonomous_ai.py](../backend/autonomous_ai.py).

Проверки:

- [business_ui_probe.py](../.github/scripts/business_ui_probe.py) — `notifications/ready,empty,partial,error`.
- [test_volume_workspace.py](../backend/tests/test_volume_workspace.py) — `test_notification_quiet_hours_and_read_ack_without_claim`.
- [test_volume_workspace.py](../backend/tests/test_volume_workspace.py) — `test_notification_preferences_are_applied_to_monitor_and_preview_sends_nothing`.

**Android:** Runtime-сценарий написан; подтверждённого device pass пока нет. Только event list pending/presented/read и exact ack. Не проверены WorkManager, quiet-hours, Android permission и реальная доставка.

**Сервер:** Правила timezone/quiet hours/version применяются сервером; outbox сохраняется с событием. Claimed не равно доставке, presented/read требуют клиентского подтверждения. Канал app_poll допускает задержки Android, мгновенный push не обещается.

## 3D079

**Контекст события.** Панель уведомления сохраняет состояние открытого графика.

Код: [NotificationWorkspaceScreens.kt](../app/src/main/java/ru/omnicio/app/ui/workspace/NotificationWorkspaceScreens.kt), [WorkspaceUi.kt](../app/src/main/java/ru/omnicio/app/ui/workspace/WorkspaceUi.kt).

Проверки:

- [business_ui_probe.py](../.github/scripts/business_ui_probe.py) — `notifications/ready`.

**Android:** Runtime-сценарий написан; подтверждённого device pass пока нет. Root overlay сохраняет контекст; fixture проверяет read ack, но не выбранную history date до/после overlay.

## 3D080

**Проверка правила.** Предпросмотр на прошлых фактических событиях без рассылки и обещаний будущего.

Код: [NotificationWorkspaceScreens.kt](../app/src/main/java/ru/omnicio/app/ui/workspace/NotificationWorkspaceScreens.kt), [volume_notifications.py](../backend/volume_notifications.py).

Проверки:

- [test_volume_workspace.py](../backend/tests/test_volume_workspace.py) — `test_notification_preferences_are_applied_to_monitor_and_preview_sends_nothing`.
- [test_volume_workspace.py](../backend/tests/test_volume_workspace.py) — `test_notification_quiet_hours_and_read_ack_without_claim`.

**Android:** Отдельного runtime-case пока нет. Rule retrospective preview root/backend owned; отдельного production visual-case этого workflow пока нет.

**Сервер:** Предпросмотр применяет новые правила к сохранённым фактическим событиям пользователя и ничего не отправляет. Это ретроспектива имеющегося периода, а не обещание будущей доставки.

## 3D081

**Вход Telegram.** Связные состояния ожидания, отмены, истечения и успешного возврата.

Код: [TelegramLoginScreen.kt](../app/src/main/java/ru/omnicio/app/ui/auth/TelegramLoginScreen.kt), [MainActivity.kt](../app/src/main/java/ru/omnicio/app/MainActivity.kt), [app.py](../backend/app.py).

Проверки:

- [test_telegram_login.py](../backend/tests/test_telegram_login.py) — `TelegramLoginTests::test_successful_browser_login_code_can_be_exchanged_once`.
- [test_telegram_login.py](../backend/tests/test_telegram_login.py) — `TelegramLoginTests::test_expired_token_is_rejected`.
- [test_volume_workspace.py](../backend/tests/test_volume_workspace.py) — `test_one_time_login_exchange_is_atomic_and_legacy_sessions_survive`.

**Android:** Отдельного runtime-case пока нет. Реальные состояния opening/waiting/expired/cancelled/exchanged/error. Нужен auth/browser-return runtime, fixture вход не подменяет.

**Интеграция:** Серверные тесты подтверждают одноразовый код, истечение, подпись и конкурентный обмен. Они не доказывают прохождение пользователем реального браузера Telegram.

## 3D082

**Повторный вход.** Контекст восстанавливается только для того же подтверждённого пользователя.

Код: [SessionExpiryObserver.kt](../app/src/main/java/ru/omnicio/app/ui/workspace/SessionExpiryObserver.kt), [PortfolioScreen.kt](../app/src/main/java/ru/omnicio/app/ui/portfolio/PortfolioScreen.kt), [DiscoveryWorkspaceScreen.kt](../app/src/main/java/ru/omnicio/app/ui/workspace/DiscoveryWorkspaceScreen.kt), [SessionExpiry.kt](../app/src/main/java/ru/omnicio/app/data/backend/SessionExpiry.kt), [WorkspaceClient.kt](../app/src/main/java/ru/omnicio/app/data/market/WorkspaceClient.kt), [MainActivity.kt](../app/src/main/java/ru/omnicio/app/MainActivity.kt), [app.py](../backend/app.py), [EncryptedWorkspaceStore.kt](../app/src/main/java/ru/omnicio/app/data/workspace/EncryptedWorkspaceStore.kt).

Проверки:

- [test_volume_workspace.py](../backend/tests/test_volume_workspace.py) — `test_one_time_login_exchange_is_atomic_and_legacy_sessions_survive`.

**Android:** Отдельного runtime-case пока нет. WorkspaceClient→SessionExpiry(status,token); root восстанавливает encrypted route только подтверждённому same user. IDs/period/frequency saveable, rotation не считается auth-expiry тестом.

**Интеграция:** Вход и чтение сохранённого состояния привязаны к подтверждённому Telegram ID; смена пользователя пересоздаёт область SignedInAppContent. Проверка серверной сессии не заменяет проверку восстановления Android после истечения входа.

## 3D083

**Подключение брокера.** Проверка токена, прав, счетов и портфеля; исправимые ошибки имеют продолжение.

Код: [TApiScreen.kt](../app/src/main/java/ru/omnicio/app/ui/profile/TApiScreen.kt), [MainActivity.kt](../app/src/main/java/ru/omnicio/app/MainActivity.kt), [app.py](../backend/app.py).

Проверки:

- [test_tinvest_token.py](../backend/tests/test_tinvest_token.py) — `TInvestTokenTests::test_validated_token_is_stored_encrypted`.
- [test_tinvest_token.py](../backend/tests/test_tinvest_token.py) — `TInvestTokenTests::test_tinvest_errors_do_not_destroy_previously_saved_token`.
- [test_tinvest_token.py](../backend/tests/test_tinvest_token.py) — `TInvestTokenTests::test_rejected_tinvest_token_is_not_confused_with_session_expiry`.

**Android:** Отдельного runtime-case пока нет. ConnectionStages соответствуют actual checking/saving/removing/configured/error без fake %. Подэтапы прав/счетов/портфеля только при подтверждении backend.

**Интеграция:** Проверяются read-only GetAccounts, шифрование токена, различение ошибок брокера/сессии и сохранение прежнего подключения при ошибке. Реальный брокерский токен в тестах не используется.

## 3D084

**Устройства.** Список сеансов, активность и отзыв после ответа сервера.

Код: [PersonalWorkspaceScreens.kt](../app/src/main/java/ru/omnicio/app/ui/workspace/PersonalWorkspaceScreens.kt), [MainActivity.kt](../app/src/main/java/ru/omnicio/app/MainActivity.kt), [volume_devices.py](../backend/volume_devices.py), [app.py](../backend/app.py).

Проверки:

- [test_volume_workspace.py](../backend/tests/test_volume_workspace.py) — `test_one_time_login_exchange_is_atomic_and_legacy_sessions_survive`.

**Android:** Отдельного runtime-case пока нет. Root devices/session list/revocation после ответа сервера; dedicated fixture в моём scope нет.

**Интеграция:** Список включает текущую и прежнюю сессии. Чужой пользователь не отзывает сеанс; отзыв владельцем действительно удаляет токен. Проверяется серверный результат, а не только текст успешного уведомления.

## 3D085

**Предпросмотр оформления.** Настоящий UI показывает материалы, глубину и движение до сохранения.

Код: [AppearanceScreen.kt](../app/src/main/java/ru/omnicio/app/ui/workspace/AppearanceScreen.kt), [SpatialMaterial.kt](../app/src/main/java/ru/omnicio/app/ui/spatial/SpatialMaterial.kt), [SpatialScene.kt](../app/src/main/java/ru/omnicio/app/ui/spatial/SpatialScene.kt), [WorkspaceVisualProbe.kt](../app/src/debug/java/ru/omnicio/app/WorkspaceVisualProbe.kt).

Проверки:

- [profile_ui_probe.py](../.github/scripts/profile_ui_probe.py).
- [SpatialMaterialTest.kt](../app/src/test/java/ru/omnicio/app/ui/spatial/SpatialMaterialTest.kt).
- [profile_ui_probe.py](../.github/scripts/profile_ui_probe.py) — `workspace/appearance`.

**3D-ядро:** Предпросмотр использует рабочие компоненты, тему и mesh-параметры до сохранения. Полная проверка persistence и внешнего вида на новой сборке ещё не выполнена.

**Android:** Runtime-сценарий написан; подтверждённого device pass пока нет. Настоящий UI preview с saveable theme/preferences draft, Apply/Cancel/back. Старый runner только motion/reset/back; полный persistence assertion пока отсутствует.

## 3D086

**Яркое освещение.** Непрозрачные материалы и усиленная читаемость сохраняют 3D.

Код: [SpatialMaterial.kt](../app/src/main/java/ru/omnicio/app/ui/spatial/SpatialMaterial.kt), [SpatialRenderer.kt](../app/src/main/java/ru/omnicio/app/ui/spatial/SpatialRenderer.kt), [AppearanceScreen.kt](../app/src/main/java/ru/omnicio/app/ui/workspace/AppearanceScreen.kt), [SpatialComponents.kt](../app/src/main/java/ru/omnicio/app/ui/spatial/SpatialComponents.kt), [SpectrumDesignSystem.kt](../app/src/main/java/ru/omnicio/app/ui/spectrum/SpectrumDesignSystem.kt), [AnalystTheme.kt](../app/src/main/java/ru/omnicio/app/ui/theme/AnalystTheme.kt).

Проверки:

- [SpatialMaterialTest.kt](../app/src/test/java/ru/omnicio/app/ui/spatial/SpatialMaterialTest.kt).
- [test_spectrum_contrast.py](../.github/scripts/tests/test_spectrum_contrast.py).

**3D-ядро:** Матовый режим сохраняет геометрию, уменьшает металл/блеск, повышает roughness и снимает clearcoat. Настоящий яркий солнечный свет и восприятие на физическом телефоне не измерены.

**Android:** Отдельного runtime-case пока нет. Bright light включает реальные opaque/high-contrast материалы, сохраняя объём. Читаемость при ярком физическом свете эмулятором не подтверждена.

## 3D087

**Восстановление операции.** Возврат к подтверждённой стадии, без повтора неизвестного платного запроса.

Код: [JobCheckpointStore.kt](../app/src/main/java/ru/omnicio/app/data/workspace/JobCheckpointStore.kt), [WorkspacePanels.kt](../app/src/main/java/ru/omnicio/app/ui/workspace/WorkspacePanels.kt), [BusinessWorkspaceProbe.kt](../app/src/debug/java/ru/omnicio/app/BusinessWorkspaceProbe.kt).

Проверки:

- [business_ui_probe.py](../.github/scripts/business_ui_probe.py) — `assistant/job,plans/job`.

**Android:** Runtime-сценарий написан; подтверждённого device pass пока нет. Encrypted checkpoint/unknown outcome; enqueue не повторяется автоматически. Симулированный сервер переживает Activity recreation, не доказывает process-death.

## 3D088

**Обновление ресурсов.** Модели и материалы версионированы вместе с APK; контекст обновления сохранён.

Код: [generate_spectrum_meshes.py](../tools/generate_spectrum_meshes.py), [catalogue.json](../app/src/main/assets/spectrum3d/catalogue.json), [SpatialRenderer.kt](../app/src/main/java/ru/omnicio/app/ui/spatial/SpatialRenderer.kt), [RequiredUpdateScreen.kt](../app/src/main/java/ru/omnicio/app/ui/spectrum/RequiredUpdateScreen.kt), [MainActivity.kt](../app/src/main/java/ru/omnicio/app/MainActivity.kt), [build.gradle.kts](../app/build.gradle.kts), [SpatialComponents.kt](../app/src/main/java/ru/omnicio/app/ui/spatial/SpatialComponents.kt).

Проверки:

- [test_spectrum_meshes.py](../tools/test_spectrum_meshes.py).
- [verify_apk.py](../.github/scripts/verify_apk.py).
- [test_apk_installation.py](../.github/scripts/test_apk_installation.py).

**3D-ядро:** Каталог v1 содержит SHA256/bytes/triangles/material; loader проверяет GLB до gltfio. Канонические float32 и +0 обеспечивают воспроизводимость; Linux и libm-perturbation tests прошли, настоящий Windows --check нового head ещё ожидается.

**Android:** Отдельного runtime-case пока нет. Root/renderer bundled versioned assets и обязательное обновление; мои экраны сохраняют безопасные route IDs. Device update-install из моего scope отсутствует.

## 3D089

**Что нового.** Отключаемый обзор реально внедрённых возможностей.

Код: [HomeScreen.kt](../app/src/main/java/ru/omnicio/app/ui/home/HomeScreen.kt), [PersonalWorkspaceScreens.kt](../app/src/main/java/ru/omnicio/app/ui/workspace/PersonalWorkspaceScreens.kt).

Отдельный сценарий для этого пункта ещё не выполнен; приёмка остаётся открытой.

**Android:** Отдельного runtime-case пока нет. Home version-keyed Что нового в0.11→NewFeatures и Больше не показывать. Карточка после финансового attention, не вместо главного действия.

## 3D090

**Жесты.** Короткое обучение на первом использовании с обычными альтернативами.

Код: [PersonalWorkspaceScreens.kt](../app/src/main/java/ru/omnicio/app/ui/workspace/PersonalWorkspaceScreens.kt), [HomeScreen.kt](../app/src/main/java/ru/omnicio/app/ui/home/HomeScreen.kt), [DashboardOrderEditor.kt](../app/src/main/java/ru/omnicio/app/ui/home/DashboardOrderEditor.kt), [PortfolioQuickPreview.kt](../app/src/main/java/ru/omnicio/app/ui/portfolio/PortfolioQuickPreview.kt), [HistoryChart.kt](../app/src/main/java/ru/omnicio/app/ui/portfolio/HistoryChart.kt), [InstrumentQuotesPanel.kt](../app/src/main/java/ru/omnicio/app/ui/portfolio/InstrumentQuotesPanel.kt).

Отдельный сценарий для этого пункта ещё не выполнен; приёмка остаётся открытой.

**Android:** Отдельного runtime-case пока нет. Persisted WorkspaceGestureHint: currency/hold, preview, drag, range и magnifiers. Обычные кнопки, exact dates/list доступны; first-use/dismiss device evidence пока нет.

## 3D091

**Тактильный отклик.** Различаются действия, выбор, результат и ошибка; нет вибрации на тиках цены.

Код: [SpatialInteraction.kt](../app/src/main/java/ru/omnicio/app/ui/spatial/SpatialInteraction.kt), [WorkspaceData.kt](../app/src/main/java/ru/omnicio/app/ui/workspace/WorkspaceData.kt).

Проверки:

- [spatial_ui_probe.py](../.github/scripts/spatial_ui_probe.py).
- [business_ui_probe.py](../.github/scripts/business_ui_probe.py).

**3D-ядро:** Действие/выбор/подтверждение/ошибка используют разные публичные haptic constants с системными настройками. Исход mutation даёт отклик после фактического ответа; GET/poll не вибрируют. Физический отклик не проверен эмулятором.

## 3D092

**Области касания.** Не меньше 48dp и не двигаются вместе с декоративной геометрией.

Код: [SpectrumDesignSystem.kt](../app/src/main/java/ru/omnicio/app/ui/spectrum/SpectrumDesignSystem.kt), [SpectrumSelectionControls.kt](../app/src/main/java/ru/omnicio/app/ui/spectrum/SpectrumSelectionControls.kt), [SpectrumRangeSlider.kt](../app/src/main/java/ru/omnicio/app/ui/spectrum/SpectrumRangeSlider.kt), [SpatialComponents.kt](../app/src/main/java/ru/omnicio/app/ui/spatial/SpatialComponents.kt).

Проверки:

- [spatial_ui_probe.py](../.github/scripts/spatial_ui_probe.py).

**3D-ядро:** Нативные hit-area отделены от декоративного движения. Gate измеряет >=47.5dp (пиксельный допуск к48dp), clickable/enabled и реальный click result. Не заявлена проверка каждого target до runtime.

## 3D093

**Доступность.** Семантика, TalkBack, фокус и шрифт 200% для всех сценариев.

Код: [SpectrumTextField.kt](../app/src/main/java/ru/omnicio/app/ui/spectrum/SpectrumTextField.kt), [SpectrumSelectionControls.kt](../app/src/main/java/ru/omnicio/app/ui/spectrum/SpectrumSelectionControls.kt), [FrameInstrumentation.java](../ci-ui-driver/src/main/java/ru/omnicio/ciframe/FrameInstrumentation.java).

Проверки:

- [native_input_evidence.py](../.github/scripts/native_input_evidence.py).
- [business_ui_probe.py](../.github/scripts/business_ui_probe.py).
- [profile_ui_probe.py](../.github/scripts/profile_ui_probe.py).
- [spatial_ui_probe.py](../.github/scripts/spatial_ui_probe.py).

**3D-ядро:** Нативные semantics, editable/focus/caret, проверяемые controls и26×2 business cases +profile/education200%. Input focus не равен TalkBack traversal: произношение, screen-reader восприятие и проверка всех растров остаются неподтверждёнными.

## 3D094

**Уровни движения.** Живое, сдержанное, отключено; системное отключение имеет приоритет.

Код: [SpatialModels.kt](../app/src/main/java/ru/omnicio/app/ui/spatial/SpatialModels.kt), [SpatialRenderer.kt](../app/src/main/java/ru/omnicio/app/ui/spatial/SpatialRenderer.kt), [SpatialRendererProbe.kt](../app/src/debug/java/ru/omnicio/app/SpatialRendererProbe.kt).

Проверки:

- [spatial_policy_probe.py](../.github/scripts/spatial_policy_probe.py).
- [test_spatial_policy_probe.py](../.github/scripts/tests/test_spatial_policy_probe.py).
- [spatial_ui_probe.py](../.github/scripts/spatial_ui_probe.py).

**3D-ядро:** Live/Subdued/Off сохраняют меши; системное отключение animator и severe thermal приоритетны. Реальный DurationScaleChangeListener будит idle-сцену. Gate меняет Android setting и требует effective state/остановку кадров; исполнение ожидается.

## 3D095

**Общие ресурсы.** Один Engine, пулы моделей/материалов и кадры по требованию.

Код: [SpatialRenderer.kt](../app/src/main/java/ru/omnicio/app/ui/spatial/SpatialRenderer.kt), [SpatialScene.kt](../app/src/main/java/ru/omnicio/app/ui/spatial/SpatialScene.kt).

Проверки:

- [spatial_ui_probe.py](../.github/scripts/spatial_ui_probe.py).
- [spatial_performance_evidence.py](../.github/scripts/spatial_performance_evidence.py).

**3D-ядро:** Один Engine на Activity, отдельные окна используют общий asset/instance/material pool; конечные анимации и кадры по требованию. Gate требует1Engine при2окнах, остановку idle и ограниченный рост warmed pool; реальные результаты ещё отсутствуют.

## 3D096

**Данные первыми.** Резервирование места и асинхронная загрузка 3D без задержки содержимого.

Код: [SpatialScene.kt](../app/src/main/java/ru/omnicio/app/ui/spatial/SpatialScene.kt), [SpatialComponents.kt](../app/src/main/java/ru/omnicio/app/ui/spatial/SpatialComponents.kt), [SpatialRenderer.kt](../app/src/main/java/ru/omnicio/app/ui/spatial/SpatialRenderer.kt).

Проверки:

- [profile_launch.py](../.github/scripts/profile_launch.py).
- [spatial_ui_probe.py](../.github/scripts/spatial_ui_probe.py).

**3D-ядро:** Текст/ввод/место доступны с первого кадра; engine после первого frame, локальные bytes/hash/geometry на IO. При задержке/сбое mesh остаётся читаемая нативная заливка, которая не объявляется успешным3D. Production cold-start target не доказан.

## 3D097

**Качество.** LOD, свет и частота учитывают температуру и энергосбережение.

Код: [SpatialRenderer.kt](../app/src/main/java/ru/omnicio/app/ui/spatial/SpatialRenderer.kt), [generate_spectrum_meshes.py](../tools/generate_spectrum_meshes.py), [SpatialRendererProbe.kt](../app/src/debug/java/ru/omnicio/app/SpatialRendererProbe.kt).

Проверки:

- [test_spectrum_meshes.py](../tools/test_spectrum_meshes.py) — `MeshCatalogueTest.test_low_detail_reduces_the_real_triangle_budget`.
- [spatial_policy_probe.py](../.github/scripts/spatial_policy_probe.py).

**3D-ядро:** PowerManager thermal/power-save ведут к lowGLB, отключению теней и30Hz; severe останавливает движение. Проверка реального OS override0/2/3/0 включена; физическая температура и расход батареи не измерены.

## 3D098

**Разделение кадров и данных.** Кадры никогда не запускают сеть, ИИ или финансовые расчёты.

Код: [SpatialRenderer.kt](../app/src/main/java/ru/omnicio/app/ui/spatial/SpatialRenderer.kt), [SpatialGeometry.kt](../app/src/main/java/ru/omnicio/app/ui/spatial/SpatialGeometry.kt), [SpatialComponents.kt](../app/src/main/java/ru/omnicio/app/ui/spatial/SpatialComponents.kt).

Проверки:

- [spatial_ui_probe.py](../.github/scripts/spatial_ui_probe.py).
- [business_ui_probe.py](../.github/scripts/business_ui_probe.py).

**3D-ядро:** В frame callback только локальная геометрия/матрицы/Filament и политика; HTTP/ИИ/бизнес-расчётов нет. Геометрия данных пересоздаётся от изменённых входов. Это подтверждено source review; сетевой runtime trace не выдуман.

## 3D099

**Измерения.** Проверка времени отклика, кадров, запуска, памяти и длинной сессии.

Код: [SpatialRenderer.kt](../app/src/main/java/ru/omnicio/app/ui/spatial/SpatialRenderer.kt), [SpatialRendererProbe.kt](../app/src/debug/java/ru/omnicio/app/SpatialRendererProbe.kt).

Проверки:

- [spatial_ui_probe.py](../.github/scripts/spatial_ui_probe.py).
- [spatial_performance_evidence.py](../.github/scripts/spatial_performance_evidence.py).
- [test_spatial_performance_evidence.py](../.github/scripts/tests/test_spatial_performance_evidence.py).

**3D-ядро:** Gate измеряет debug fixture startup, >=120s/120scroll/>=30rows, реальный PSS/HWUI/CPU-submit; growth<=64MiB,pool<=48,p95<=250ms ловят stall/leak эмулятора. Это не доказательство60fps/GPUtime/productioncoldstart/телефона; runtime пока отсутствует.

## 3D100

**Совместимость.** Surface/lifecycle/restart/rotation/update, Android15+, native16KB и честная граница физической проверки.

Код: [SpatialScene.kt](../app/src/main/java/ru/omnicio/app/ui/spatial/SpatialScene.kt), [SpatialRenderer.kt](../app/src/main/java/ru/omnicio/app/ui/spatial/SpatialRenderer.kt), [check_native_alignment.py](../tools/check_native_alignment.py), [action.yml](../.github/actions/check-apk/action.yml), [installation_evidence.py](../backend/installation_evidence.py), [release_publication.py](../backend/release_publication.py), [deploy-moscow-telegram-auth.yml](../.github/workflows/deploy-moscow-telegram-auth.yml), [deploy_moscow_telegram_browser_auth.py](../.github/scripts/deploy_moscow_telegram_browser_auth.py), [deploy_moscow_telegram_browser_auth_remote.sh](../.github/scripts/deploy_moscow_telegram_browser_auth_remote.sh).

Проверки:

- [test_native_alignment.py](../tools/test_native_alignment.py).
- [kernel_page_size.py](../.github/scripts/kernel_page_size.py).
- [test_apk_installation.py](../.github/scripts/test_apk_installation.py).
- [spatial_ui_probe.py](../.github/scripts/spatial_ui_probe.py).
- [test_installation_evidence.py](../backend/tests/test_installation_evidence.py).
- [test_release_runtime_publication.py](../backend/tests/test_release_runtime_publication.py) — `test_version34_transcript_remains_publishable_without_runtime_page_measurement`.
- [test_release_runtime_publication.py](../backend/tests/test_release_runtime_publication.py) — `test_version35_requires_and_accepts_both_exact_runtime_installations`.
- [test_release_runtime_publication.py](../backend/tests/test_release_runtime_publication.py) — `test_runtime_evidence_failure_preserves_previously_published_version`.
- [test_installation_evidence.py](../backend/tests/test_installation_evidence.py) — `EvidenceTests::test_new_release_requires_real_16kb_and_4kb_full_matrix`.
- [test_installation_evidence.py](../backend/tests/test_installation_evidence.py) — `EvidenceTests::test_new_release_cannot_omit_kernel_upgrade_or_profile_on_either_api`.
- [test_installation_evidence.py](../backend/tests/test_installation_evidence.py) — `EvidenceTests::test_kernel_measurement_is_bound_to_exact_platform_and_candidate`.
- [test_installation_evidence.py](../backend/tests/test_installation_evidence.py) — `EvidenceTests::test_new_release_requires_all_six_routes_and_both_native_font_sizes`.
- [test_installation_evidence.py](../backend/tests/test_installation_evidence.py) — `EvidenceTests::test_duplicate_case_or_missing_receipt_cannot_replace_a_full_run`.
- [test_deploy_moscow_telegram_auth.py](../backend/tests/test_deploy_moscow_telegram_auth.py) — `TelegramAuthDeploymentTests::test_staged_preflight_initializes_workspace_and_preserves_existing_user`.
- [test_deploy_moscow_telegram_auth.py](../backend/tests/test_deploy_moscow_telegram_auth.py) — `TelegramAuthDeploymentTests::test_workspace_probe_requires_authentication_for_every_read_route`.

**3D-ядро:** API35 official google_apis_ps16k требует getconf PAGE_SIZE=16384; API36=4096. ОбеAPI требуют clean+0.10upgrade+launch+полные52UIcase/font, привязанные кdebugAPK. Static PT_LOAD/ZIP не заменяют запуск. Lifecycle/rotation/window gates включены, runtime16KB ещё не выполнен.

**Сервер:** Публикация versionCode ≥ 35 требует transcripts API 35/16384 и API 36/4096 с измерением, точным APK, clean/upgrade/launch/profile; на каждой API нужен receipt всех 52 business case/font IDs набора spectrum-3d-100-v1, связанный с установленным debug UI fixture. Legacy v34 совместим. Это проверка CI evidence, не самостоятельное доказательство установки на физическом телефоне; Surface/lifecycle/renderer проверяет Android.

**Интеграция:** Развёртывание сначала инициализирует все таблицы в отдельной базе без scheduler, проверяет сохранение записей и требует авторизацию на новых маршрутах. Подтверждение фактической установки сервера и канала будет записано после выполнения workflow.

