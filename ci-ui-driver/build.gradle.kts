// Test-lab APK only. No dependency from :app and no published variant.
plugins { alias(libs.plugins.android.application) }
android {
    namespace = "ru.omnicio.ciframe"
    compileSdk = 36
    defaultConfig {
        applicationId = "ru.omnicio.ciframe"
        minSdk = 36
        targetSdk = 36
        versionCode = 1
        versionName = "1"
    }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    lint { abortOnError = true }
}
androidComponents.beforeVariants(androidComponents.selector().withBuildType("release")) {
    it.enable = false
}
