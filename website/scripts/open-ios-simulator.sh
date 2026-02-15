#!/usr/bin/env bash
set -euo pipefail

URL="${1:-http://127.0.0.1:3000}"

if ! command -v xcrun >/dev/null 2>&1; then
  echo "xcrun is unavailable. Install Xcode and command line tools first."
  exit 1
fi

if ! DEVICE_LIST="$(xcrun simctl list devices available 2>&1)"; then
  echo "Unable to query iOS simulators via CoreSimulatorService."
  echo "Try opening Xcode once, then run this command again."
  echo ""
  echo "$DEVICE_LIST"
  exit 1
fi

if ! grep -q "iPhone" <<<"$DEVICE_LIST"; then
  echo "No available iPhone simulator found."
  echo "Create one in Xcode -> Settings -> Platforms, then try again."
  exit 1
fi

BOOTED_LIST="$(xcrun simctl list devices booted 2>/dev/null || true)"
BOOTED_DEVICE="$(awk -F '[()]' '/iPhone/ {print $2; exit}' <<<"$BOOTED_LIST")"
TARGET_DEVICE="${IOS_SIM_DEVICE:-${BOOTED_DEVICE}}"

if [ -z "$TARGET_DEVICE" ]; then
  TARGET_DEVICE="$(awk -F '[()]' '/iPhone/ {print $2; exit}' <<<"$DEVICE_LIST")"
fi

if [ -z "$TARGET_DEVICE" ]; then
  echo "Could not resolve an iPhone simulator device."
  exit 1
fi

open -a Simulator >/dev/null 2>&1 || true
xcrun simctl boot "$TARGET_DEVICE" >/dev/null 2>&1 || true
xcrun simctl bootstatus "$TARGET_DEVICE" -b
xcrun simctl openurl "$TARGET_DEVICE" "$URL"

echo "Opened $URL in iOS Simulator device: $TARGET_DEVICE"
