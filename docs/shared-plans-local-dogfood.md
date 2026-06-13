# Shared Household Giving Plans — Local Dogfood & Testing

The shared-plan / "Family Giving Night" feature is entirely Firestore-backed, so it
needs a live Firestore + Auth to run. Locally that's the **Firebase Emulator Suite**
(no production impact, the real `firestore.rules` active). Requires Java (for the
Firestore emulator) and `firebase-tools` (already installed).

## Automated test (CI-ready)

```bash
cd website && npm run test:e2e:shared
```

Wraps `firebase emulators:exec` (auth :9099 + firestore :8080), boots the app in
emulator mode on :5180, and drives **two real test users** through Chrome:
create plan → add charity → invite → open link → money-free preview → join.
It **asserts zero console/page errors** throughout, and suppresses first-visit
onboarding overlays. Spec: `website/tests/e2e/shared-plan-emulator.spec.ts`.

## Try it by hand (two browser windows)

```bash
# terminal 1 — emulators (auth + firestore + a data viewer UI)
cd website && npm run emulators        # data viewer: http://localhost:4000

# terminal 2 — the app, pointed at the emulators
cd website && npm run dev:emulator     # http://localhost:5173
```

Then:

1. Open http://localhost:5173, click **Sign in → Google**. The emulator shows a fake
   account chooser — **Add new account**, type any name/email. You're in (no real
   Google account needed).
2. **Profile → Your Giving → "+ Shared plan"**, name it (e.g. "Khan Family").
3. Add a charity (search by name), set weights.
4. **"Start giving session"** to walk the gather → explore → decide → recap ritual,
   or stay on the plan view. Hit **"Invite family"** (copies the join link).
5. Open the join link in an **incognito window**, sign in as a *different* fake
   account → money-free preview → **Join**.
6. Watch everything land live in the emulator data viewer at
   http://localhost:4000/firestore (`shared_plans`, `members`, your `sharedPlanIds`).

Keep Chrome DevTools open (⌥⌘J) to confirm a clean console.

## Family on phones (same WiFi, still no production)

`localhost` isn't reachable from a phone, so:

1. In `firebase.json`, add `"host": "0.0.0.0"` to each emulator (auth/firestore) so
   they accept LAN connections.
2. Start the app with your laptop's LAN IP as the emulator host and bind vite to the
   network:
   ```bash
   VITE_USE_FIREBASE_EMULATOR=true VITE_EMULATOR_HOST=<laptop-LAN-IP> \
     npx vite --host --port 5173
   ```
3. Family opens `http://<laptop-LAN-IP>:5173` on the same WiFi.

For truly-anywhere access you'd deploy the `firestore.rules` (and the app) to the real
project — a separate, deliberate deploy step.

## How the local seam works

- `website/src/auth/firebase.ts`: when `VITE_USE_FIREBASE_EMULATOR=true`, it uses a
  demo config, connects auth/firestore to the emulators (`VITE_EMULATOR_HOST` overrides
  `localhost`), and exposes `window.__TEST_AUTH__` (email/password) for Playwright. This
  whole block is dead-stripped from production bundles — the flag is never set in prod.
- `firebase.json`: emulator ports.
- npm scripts: `emulators`, `dev:emulator`, `test:e2e:shared`.
