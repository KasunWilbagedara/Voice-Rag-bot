import os
import sys

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

if __name__ == "__main__":
    import uvicorn
    from backend_with_tools.config import PORT
    print(f"🚀 Starting Voice-RAG with Tools Backend on http://0.0.0.0:{PORT} (RAG + Databases + Live Tools)")
    uvicorn.run("backend_with_tools.main:app", host="0.0.0.0", port=PORT, reload=True)
