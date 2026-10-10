plugins {
    alias(libs.plugins.android.application) apply false
    alias(libs.plugins.compose.compiler) apply false
}

allprojects {
    dependencyLocking {
        lockAllConfigurations()
        // Android Studio creates transient copied configurations during project sync
        // (for example debugRuntimeClasspathCopy). DEFAULT still validates every
        // configuration with committed lock state without rejecting those IDE-only copies.
        lockMode.set(org.gradle.api.artifacts.dsl.LockMode.DEFAULT)
    }
}
