plugins {
    alias(libs.plugins.android.application)
    alias(libs.plugins.compose.compiler)
}

val releaseStorePath = providers.environmentVariable("OMNICIO_RELEASE_STORE_FILE")
val releaseStorePassword = providers.environmentVariable("OMNICIO_RELEASE_STORE_PASSWORD")
val releaseKeyAlias = providers.environmentVariable("OMNICIO_RELEASE_KEY_ALIAS")
val releaseKeyPassword = providers.environmentVariable("OMNICIO_RELEASE_KEY_PASSWORD")
val releaseSigningReady = listOf(
    releaseStorePath,
    releaseStorePassword,
    releaseKeyAlias,
    releaseKeyPassword,
).all { !it.orNull.isNullOrBlank() }

android {
    namespace = "ru.omnicio.app"
    compileSdk = 36

    defaultConfig {
        applicationId = "ru.omnicio.app"
        minSdk = 26
        targetSdk = 36
        versionCode = 6
        versionName = "2.5.0"
    }

    signingConfigs {
        if (releaseSigningReady) {
            create("release") {
                storeFile = file(requireNotNull(releaseStorePath.orNull))
                storePassword = releaseStorePassword.orNull
                keyAlias = releaseKeyAlias.orNull
                keyPassword = releaseKeyPassword.orNull
            }
        }
    }

    buildTypes {
        debug {
            applicationIdSuffix = ".debug"
            versionNameSuffix = "-debug"
        }
        release {
            isMinifyEnabled = true
            signingConfigs.findByName("release")?.let { signingConfig = it }
            proguardFiles(
                getDefaultProguardFile("proguard-android-optimize.txt"),
                "proguard-rules.pro",
            )
        }
    }

    buildFeatures {
        buildConfig = true
        compose = true
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    lint {
        abortOnError = true
        checkReleaseBuilds = true
    }
}

val releasePackagingRequested = gradle.startParameter.taskNames.any { requestedTask ->
    requestedTask.substringAfterLast(':') in setOf(
        "assembleRelease",
        "bundleRelease",
        "packageRelease",
        "assemble",
        "bundle",
        "build",
    )
}
check(!releasePackagingRequested || releaseSigningReady) {
    "Release packaging requires OMNICIO release signing credentials from protected local/CI custody."
}

dependencies {
    val composeBom = platform(libs.compose.bom)

    implementation(composeBom)
    implementation(libs.activity.compose)
    implementation(libs.compose.material3)
    implementation(libs.compose.ui)
    implementation(libs.compose.ui.tooling.preview)
    implementation(libs.core.splashscreen)
    implementation(libs.lifecycle.runtime.compose)
    implementation(libs.lifecycle.viewmodel.compose)
    implementation(libs.navigation.compose)

    debugImplementation(libs.compose.ui.tooling)

    testImplementation(libs.junit)
}
