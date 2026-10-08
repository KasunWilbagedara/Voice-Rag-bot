up:
	docker-compose up -d --build

down:
	docker-compose down

logs:
	docker-compose logs -f

# Run all services together (Pure RAG, Tools RAG, Frontend)
run-all:
	./start_all.sh

# Run Pure RAG Backend locally (Port 8000)
run-pure-rag:
	./venv/bin/python -m backend_pure_rag.main

# Run RAG with Tools Backend locally (Port 8001)
run-tools-rag:
	./venv/bin/python -m backend_with_tools.main

# Run Next.js Frontend UI (Port 3000)
run-frontend:
	npm run dev

# Run Voice-RAG MCP Server via stdio (for Claude Desktop / Cursor)
run-mcp-server:
	./venv/bin/python -m backend_with_tools.mcp_server

# Run Voice-RAG MCP Server via SSE on port 8005
run-mcp-sse:
	./venv/bin/python -m backend_with_tools.mcp_server --transport sse --port 8005
