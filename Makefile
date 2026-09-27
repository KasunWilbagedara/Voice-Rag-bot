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

dev-tools:
	$(PYTHON) -m backend.tool_server

dev-rag:
	$(PYTHON) -m backend.main

dev:
	start "Tool Service :8001" $(PYTHON) -m backend.tool_server
	$(PYTHON) -m backend.main
