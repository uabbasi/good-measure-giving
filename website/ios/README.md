# Good Measure Giving — iOS App

A native iOS wrapper around the Good Measure Giving web app, built with
[Capacitor](https://capacitorjs.com/) — the same web build that powers the
Android app. Charity data (JSON under `/data`) ships inside the app, so browsing
works offline; Firebase auth and live nisab prices require a network connection.

- **App name:** Good Measure Giving
- **Bundle identifier:** `com.goodmeasuregiving.app`
- **Min iOS:** 15.0
- **Dependencies:** Swift Package Manager (Capacitor 8) — **no CocoaPods / no `pod install`**. Xcode resolves packages automatically on first open.

## Requirements (macOS only)

iOS apps can only be compiled on **macOS with Xcode** — there is no Linux/Windows
path, and CI must use a `macos-*` runner. You need:

- macOS with **Xcode** (from the App Store) + Command Line Tools
- **Node 22+** and `npm` (Capacitor 8's CLI requires Node >= 22)
- An Apple ID for signing (a free account works for Simulator + your own device;
  a paid Apple Developer account is needed for TestFlight / App Store)

## Build & run

From `website/`:

```bash
npm ci                 # install JS deps (first time)
npm run ios:sync       # build the web app + copy it into ios/
npm run ios:xcode      # open ios/App in Xcode
```

In Xcode: pick a Simulator (or a connected device) in the toolbar and press
**▶ Run**. For a device build, set your Team under **Signing & Capabilities**
first (Xcode auto-manages the provisioning profile).

Prefer the command line? With a Simulator/device available:

```bash
npx cap run ios
```

## Web assets are not committed

Like Android, the built web app (`ios/App/App/public`) and the generated
`capacitor.config.json` are git-ignored. Re-run `npm run ios:sync` after any web
change to rebuild and re-copy them before building in Xcode.

## Icons / splash

App icon and splash (light + dark) live in
`ios/App/App/Assets.xcassets/`. Regenerate them from `website/assets/` with:

```bash
npm run ios:assets
```

## Release (App Store / TestFlight)

In Xcode: **Product → Archive**, then distribute via the Organizer (App Store
Connect). This requires a paid Apple Developer account and an App Store Connect
app record for `com.goodmeasuregiving.app`.
