# Подготовка выдачи45 — административные исходники

Сохранено26.10.2026 для продолжения без потери подготовленных файлов. Этот каталог сам ничего не публикует и не выполняет код приложения. Генератор ещё не использован для выпуска45; его необходимо сверить с фактическими receipts завершившегося native run.

Существующий publisher44 сохранён как исходная основа. Генератор45 принимает оригинальные Windows build/controller/export receipts, распакованный native artifact, запись N00_RUNTIME_EXPORT, номер native run и exact-source backup commit. Он отказывается готовить workflow без navigation.complete=true и ожидаемого диагностического sentinel. Отдельный серверный guard повторно проверяет исходный native archive, все34 записи навигации, baseline44, upgrade, чистую установку и источник APK до изменения канала. Это preview, full15/phone остаются false.

Запуск административного генератора из корня checkout транспортной ветки:

```bash
python ops/pending-preview45/prepare-preview45-publisher.py \
  --build /absolute/original-build-receipts \
  --native /absolute/original-native-artifact \
  --native-export /absolute/native-export.json \
  --native-run ACTUAL_COMPLETED_RUN_ID \
  --source-commit ACTUAL_WINDOWS_SOURCE_BACKUP
```

Результат — локальные publisher45.py и deliver-preview45.yml рядом с генератором; автоматической отправки в GitHub или публикации нет. До переноса workflow в .github/workflows/deliver-preview45.yml проверить реальный исход native, параметры APK, diff операционных guards и сохранение опубликованного44. Прежний failure нельзя подменять ожидаемым sentinel. Прямое указание владельца на выдачу текущей проверенной preview уже действует; дополнительное разрешение не запрашивать.

Разработка/тесты приложения выполняются только на LAPTOP-NPSGA016. Timeweb — действующий runtime и хранилище архивов. Существующие секреты не печатать, БД/owner/session/signing binding не изменять.
