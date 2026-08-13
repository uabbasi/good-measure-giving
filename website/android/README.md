# Good Measure Giving — Android App

A native Android wrapper around the Good Measure Giving web app, built with
[Capacitor](https://capacitorjs.com/). The React/Vite frontend in `website/` is
bundled into the app; charity data (JSON under `/data`) ships inside the APK, so
browsing works offline. Firebase auth and live nisab (gold/silver) prices still
require a network connection.

- **App name:** Good Measure Giving
- **Package / applicationId:** `com.goodmeasuregiving.app`
- **minSdk:** 24 (Android 7.0) · **target/compileSdk:** 36
- **Version:** 1.0.0 (versionCode 1)

## How it fits together

```
website/            React + Vite source
  dist/             `npm run build` output (git-ignored)
  capacitor.config.ts
  android/          native Android project (this directory)
    app/src/main/assets/public/   ← copied from dist/ by `cap sync` (git-ignored)
```

The web build is **not** committed. After cloning you must build the web app and
sync it into the native project before compiling.

## Prerequisites

- Node 20+ and `npm`
- JDK 21
- Android SDK with **platform 36** and **build-tools 36**, plus platform-tools
  (install via Android Studio or `sdkmanager`)
- `ANDROID_HOME` / `ANDROID_SDK_ROOT` set, or an `android/local.properties` with
  `sdk.dir=/path/to/Android/sdk`

> Building requires network access to Google's Maven repository
> (`dl.google.com`) for the Android Gradle Plugin, AndroidX, and the SDK. In
> network-restricted environments where that host is blocked, the build must be
> run on a machine or CI runner that can reach it.

## Build

From `website/`:

```bash
npm ci                 # install JS deps (first time)
npm run android:sync   # build web app + copy assets into android/
```

Then produce an artifact:

```bash
# Debug APK (installable for testing)
npm run android:apk
#   → android/app/build/outputs/apk/debug/app-debug.apk

# Release AAB (for Google Play upload)
npm run android:aab
#   → android/app/build/outputs/bundle/release/app-release.aab
```

Or open the project in Android Studio:

```bash
npm run android:open
```

## Release signing

Release builds are signed with the debug key unless you provide an upload key.
To sign for the Play Store, create `android/keystore.properties` (git-ignored):

```properties
storeFile=/absolute/path/to/upload-keystore.jks
storePassword=********
keyAlias=upload
keyPassword=********
```

Generate an upload keystore with:

```bash
keytool -genkey -v -keystore upload-keystore.jks -keyalg RSA -keysize 2048 \
  -validity 10000 -alias upload
```

Then `npm run android:aab` produces a signed release bundle. Never commit the
keystore or `keystore.properties`.

## Regenerating icons / splash

Source art lives in `website/assets/` (brand mark, generated from
`website/public/favicon.svg`). To regenerate every density:

```bash
npm run android:assets
```

## Updating the app after web changes

Any change to the React app is picked up by re-running:

```bash
npm run android:sync
```

This rebuilds `dist/` and re-copies it into the native project.
