#!/bin/bash
# Development server launcher - starts the website frontend

set -e

PROJECT_ROOT="$(cd "$(dirname "$0")" && pwd)"

echo "========================================"
echo "  Good Measure Giving Development Server"
echo "========================================"
echo ""

# Kill any existing processes on our port
echo "Cleaning up existing processes..."
lsof -ti:5173 2>/dev/null | xargs kill -9 2>/dev/null || true

# Convert data and start website frontend (Vite on port 5173)
echo ""
echo "Converting charity data..."
cd "$PROJECT_ROOT/website"
npm run convert-data

echo ""
echo "Starting Website Frontend (Vite)..."
npm run dev &
FRONTEND_PID=$!
echo "  PID: $FRONTEND_PID"

# Wait a moment for server to start
sleep 3

echo ""
echo "========================================"
echo "  Server Running"
echo "========================================"
echo ""
echo "  Website: http://localhost:5173"
echo ""
echo "  Press Ctrl+C to stop"
echo "========================================"
echo ""

# Handle cleanup on exit
cleanup() {
    echo ""
    echo "Shutting down server..."
    kill $FRONTEND_PID 2>/dev/null || true
    echo "Done."
    exit 0
}

trap cleanup SIGINT SIGTERM

# Wait for process to exit
wait
