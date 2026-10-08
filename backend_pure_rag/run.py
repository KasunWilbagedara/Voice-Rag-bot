import os
import sys

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

if __name__ == "__main__":
    import uvicorn
    from backend_pure_rag.config import PORT
    print(f"🚀 Starting Pure Voice-RAG Backend on http://0.0.0.0:{PORT} (No Tools, Pure RAG)")
    uvicorn.run("backend_pure_rag.main:app", host="0.0.0.0", port=PORT, reload=True)
