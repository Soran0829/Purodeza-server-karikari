pluginManagement {
    val flutterSdkPath =
        run {
            // Read local.properties as UTF-8: java.util.Properties.load(InputStream)
            // assumes ISO-8859-1 and mangles non-ASCII SDK paths (e.g. Japanese
            // user directories), which breaks the Gradle build.
            val properties =
                java.util.Properties().apply {
                    load(java.io.StringReader(file("local.properties").readText(Charsets.UTF_8)))
                }
            val path = properties.getProperty("flutter.sdk")
            require(path != null) { "flutter.sdk not set in local.properties" }
            path
        }

    // Flutter's plugin loader otherwise re-reads local.properties with
    // ISO-8859-1 and mangles the same non-ASCII path. Publishing the decoded
    // value here makes it skip that fallback.
    settings.extensions.extraProperties.set("flutterSdkPath", flutterSdkPath)

    includeBuild("$flutterSdkPath/packages/flutter_tools/gradle")

    repositories {
        google()
        mavenCentral()
        gradlePluginPortal()
    }
}

plugins {
    id("dev.flutter.flutter-plugin-loader") version "1.0.0"
    id("com.android.application") version "8.11.1" apply false
    id("org.jetbrains.kotlin.android") version "2.2.20" apply false
}

include(":app")
