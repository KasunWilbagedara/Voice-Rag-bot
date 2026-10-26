up:
	docker-compose up -d --build

down:
	docker-compose down

logs:
	docker-compose logs -f

# ── Local development ─────────────────────────────────────────────────────────
# IMPORTANT: Always run make from the project root: d:\SLT\Voice-Rag-bot
# Python venv: D:\SLT\Voice-Rag-bot\venv\Scripts\python.exe
PYTHON = D:\SLT\Voice-Rag-bot\venv\Scripts\python.exe

# Backend 1: Pure RAG (Port 8000)
dev-rag:
	$(PYTHON) -m backend.main

# Backend 2: RAG + Tools (Port 8001)
dev-tools:
	$(PYTHON) -m backend.tool_server

# MCP Server (Port 8005) — for Claude Desktop / Cursor
dev-mcp:
	$(PYTHON) -m backend.mcp_server

# All backends + frontend (3 separate windows)
dev:
	start "Backend 1 — Pure RAG :8000"    $(PYTHON) -m backend.main
	start "Backend 2 — RAG + Tools :8001" $(PYTHON) -m backend.tool_server
	start "MCP Server :8005"              $(PYTHON) -m backend.mcp_server
	npm run dev
