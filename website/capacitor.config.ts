import type { CapacitorConfig } from '@capacitor/cli';

const config: CapacitorConfig = {
  appId: 'com.goodmeasuregiving.app',
  appName: 'Good Measure Giving',
  webDir: 'dist',
  android: {
    // Charity data JSON is bundled into the app under /data and served from
    // the local Capacitor origin, so the app works without a network for
    // browsing. Firebase auth and live nisab prices still require network.
    allowMixedContent: false,
  },
  ios: {
    // Match Android: bundled charity data works offline; auth/nisab need network.
    contentInset: 'automatic',
  },
  server: {
    androidScheme: 'https',
    iosScheme: 'https',
  },
};

export default config;
