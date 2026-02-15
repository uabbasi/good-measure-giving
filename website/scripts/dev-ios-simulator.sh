#!/usr/bin/env bash
set -euo pipefail

HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-3000}"
URL="http://${HOST}:${PORT}"

cleanup() {
  if [ -n "${DEV_PID:-}" ] && kill -0 "$DEV_PID" >/dev/null 2>&1; then
    kill "$DEV_PID"
  fi
}

trap cleanup EXIT INT TERM

npm run dev -- --host "$HOST" --port "$PORT" --strictPort &
DEV_PID=$!

for _ in $(seq 1 60); do
  if curl -fsS "$URL" >/dev/null 2>&1; then
    break
  fi
  sleep 1
done

if ! curl -fsS "$URL" >/dev/null 2>&1; then
  echo "Dev server did not become reachable at $URL"
  exit 1
fi

bash scripts/open-ios-simulator.sh "$URL"
wait "$DEV_PID"
