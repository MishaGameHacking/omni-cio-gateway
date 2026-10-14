package ru.omnicio.app.data.updates

internal enum class InstallFailureReason { ABORTED, BLOCKED, CONFLICT, INCOMPATIBLE, INVALID, STORAGE, OTHER }

/** Whitelisted messages: never display raw installer extras, paths or package names. */
internal fun installFailureMessage(reason: InstallFailureReason): String = when (reason) {
    InstallFailureReason.ABORTED -> "Установка отменена или установочная сессия закрыта. Можно повторить обновление, когда будете готовы."
    InstallFailureReason.BLOCKED -> "Android запретил установку. Проверьте разрешение установки для Analyst AI; при ограничениях организации обратитесь к администратору. Не отключайте защиту телефона."
    InstallFailureReason.CONFLICT -> "Android обнаружил конфликт с установленным приложением. Не удаляйте Analyst AI: сообщите разработчику, чтобы проверить подпись и совместимость выпуска."
    InstallFailureReason.INCOMPATIBLE -> "Эта сборка несовместима с устройством. Нужен подходящий выпуск Analyst AI; повторная установка того же файла может не помочь."
    InstallFailureReason.INVALID -> "Android отклонил файл обновления. Сообщите разработчику о некорректном APK. Не удаляйте приложение и не заменяйте файл сборкой из неизвестного источника."
    InstallFailureReason.STORAGE -> "Android не смог использовать память устройства для установки. Проверьте свободное место и доступность хранилища, затем повторите обновление."
    InstallFailureReason.OTHER -> "Android не установил обновление. Можно повторить попытку; при повторном отказе сообщите разработчику. Причина не определена системным статусом."
}
