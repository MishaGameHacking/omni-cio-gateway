plugins {
    alias(libs.plugins.android.application)
    alias(libs.plugins.compose.compiler)
}

android {
    namespace = "ru.omnicio.app"
    compileSdk = 37

    defaultConfig {
        applicationId = "ru.omnicio.app"
        minSdk = 37
        targetSdk = 37
        // Preserve the installed preview identity; each published update has a new code.
        versionCode = 35
        versionName = "0.11.0"
    }

    buildTypes {
        debug {
            applicationIdSuffix = ".debug"
            versionNameSuffix = "-debug"
        }
        release {
            isMinifyEnabled = true
            proguardFiles(
                getDefaultProguardFile("proguard-android-optimize.txt"),
                "proguard-rules.pro",
            )
        }
        create("preview") {
            initWith(getByName("release"))
            // Preserve identity of the installed test line without shipping debugger/tooling code.
            applicationIdSuffix = ".debug"
            versionNameSuffix = "-preview"
            signingConfig = signingConfigs.getByName("debug")
            isDebuggable = false
            matchingFallbacks += "release"
        }
    }

    buildFeatures {
        compose = true
        buildConfig = true
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

dependencies {
    val composeBom = platform(libs.compose.bom)

    implementation(composeBom)
    implementation(libs.activity.compose)
    implementation(libs.coroutines.android)
    implementation(libs.browser)
    implementation(libs.compose.material3)
    implementation(libs.compose.ui)
    implementation(libs.compose.ui.tooling.preview)
    implementation(libs.filament.android)
    implementation(libs.filament.gltfio)

    debugImplementation(libs.compose.ui.tooling)
    testImplementation(libs.junit)
}

