#!/usr/bin/env bash
set -e

# Voice-RAG Bot - All-in-One Service Launcher
# Launches:
# 1. Pure RAG Backend (Port 8000)
# 2. RAG with Tools Backend (Port 8001)
# 3. Next.js Frontend UI (Port 3000)

PYTHON_BIN="./venv/bin/python"
if [ ! -f "$PYTHON_BIN" ]; then
    PYTHON_BIN="python3"
fi

echo "=========================================================="
echo "  🎙️  Starting Voice-RAG Bot Services"
echo "=========================================================="

# Trap SIGINT and SIGTERM to kill all background subprocesses cleanly
cleanup() {
    echo ""
    echo "🛑 Shutting down all Voice-RAG services..."
    kill $(jobs -p) 2>/dev/null || true
    wait 2>/dev/null || true
    echo "✅ All services stopped."
    exit 0
}
trap cleanup SIGINT SIGTERM EXIT

# Free lingering processes on ports 8000, 8001, 3000 if any
for port in 8000 8001 3000; do
    pids=$(lsof -ti :$port 2>/dev/null || true)
    if [ -n "$pids" ]; then
        echo "🧹 Freeing port $port (stopping stale process: $pids)..."
        kill -9 $pids 2>/dev/null || true
    fi
done
sleep 1

# 1. Start Pure RAG Backend (Port 8000)
echo "🚀 [1/3] Starting Pure RAG Backend on http://localhost:8000 ..."
$PYTHON_BIN -m backend_pure_rag.main &
PID_PURE=$!

# 2. Start RAG with Tools Backend (Port 8001)
echo "🚀 [2/3] Starting RAG with Tools Backend on http://localhost:8001 ..."
$PYTHON_BIN -m backend_with_tools.main &
PID_TOOLS=$!

# 3. Wait briefly for backends to initialize
sleep 2

# 4. Start Next.js Frontend (Port 3000)
echo "🚀 [3/3] Starting Next.js Frontend on http://localhost:3000 ..."
echo ""
echo "✨ Open your browser at: http://localhost:3000"
echo "Press Ctrl+C to stop all services."
echo "=========================================================="

npm run dev
