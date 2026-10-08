import sqlite3
import logging
from typing import Optional
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Query
from pydantic import BaseModel

from backend_pure_rag.db import get_db_connection, is_db_connected, in_memory_store, SQLITE_DB_PATH
from backend_pure_rag.document_parser import parse_document
from backend_pure_rag.rag_service import ingest_document

router = APIRouter(prefix="/api/documents", tags=["Documents (Pure RAG)"])
logger = logging.getLogger("pure_rag.documents")


class SeedRequest(BaseModel):
    apiKey: Optional[str] = None


SAMPLE_DOC_TITLE = "SLT_Enterprise_Services_Overview.txt"
SAMPLE_DOC_CONTENT = """
Sri Lanka Telecom (SLT-MOBITEL) Enterprise Solutions Overview:
SLT-MOBITEL provides high-speed optical fiber Connectivity, Enterprise Cloud Platforms, Data Center Hosting, Managed Security, and SD-WAN networks for financial institutions, government departments, and multinational enterprises across Sri Lanka.

Key Capabilities:
1. Akaza Cloud & Enterprise Data Centers: ISO 27001 certified cloud infrastructure offering IaaS, PaaS, Disaster Recovery, and Automated Storage.
2. High-Speed Optical Fiber: Dedicated symmetrical bandwidth up to 10 Gbps with 99.99% uptime SLA.
3. Voice & Unified Communications: SIP Trunking, Hosted PABX, Smart Interactive Voice Response (IVR), and Omnichannel Contact Center solutions.
4. Cybersecurity Managed Services: Next-Generation Firewall (NGFW), Distributed Denial of Service (DDoS) mitigation, Security Operations Center (SOC) monitoring, and Zero-Trust Network Access (ZTNA).

Customer Support & Contacts:
Enterprise Hotline: 1717 or +94 11 2381717
Enterprise Email: enterprise@slt.lk
Official Portal: https://www.slt.lk/enterprise
"""


@router.get("")
def list_documents():
    try:
        # 1. Check PostgreSQL if connected
        with get_db_connection() as conn:
            if conn:
                try:
                    with conn.cursor() as cur:
                        query = """
                            SELECT 
                                d.id,
                                d.title,
                                d.file_type,
                                d.created_at,
                                COUNT(c.id)::int AS chunk_count
                            FROM documents d
                            LEFT JOIN document_chunks c ON d.id = c.document_id
                            GROUP BY d.id
                            ORDER BY d.created_at DESC;
                        """
                        cur.execute(query)
                        rows = cur.fetchall()
                        if rows:
                            docs = []
                            for row in rows:
                                docs.append({
                                    "id": str(row[0]),
                                    "title": row[1],
                                    "file_type": row[2],
                                    "created_at": row[3].isoformat() if hasattr(row[3], "isoformat") else str(row[3]),
                                    "chunk_count": row[4],
                                })
                            return {"documents": docs, "dbActive": True, "source": "PostgreSQL"}
                except Exception as e:
                    logger.debug(f"PostgreSQL list docs note: {e}")

        # 2. Check SQLite pure_rag.db
        try:
            conn = sqlite3.connect(SQLITE_DB_PATH)
            cur = conn.cursor()
            cur.execute("""
                SELECT 
                    d.id,
                    d.title,
                    d.file_type,
                    d.created_at,
                    COUNT(c.id) AS chunk_count
                FROM rag_documents d
                LEFT JOIN rag_document_chunks c ON d.id = c.document_id
                GROUP BY d.id
                ORDER BY d.created_at DESC;
            """)
            rows = cur.fetchall()
            conn.close()
            if rows:
                docs = []
                for row in rows:
                    docs.append({
                        "id": row[0],
                        "title": row[1],
                        "file_type": row[2],
                        "created_at": row[3],
                        "chunk_count": row[4],
                    })
                return {"documents": docs, "dbActive": True, "source": "SQLite (pure_rag.db)"}
        except Exception as e:
            logger.debug(f"SQLite list docs note: {e}")

        # 3. Fallback to in-memory store
        docs = []
        for d in in_memory_store.documents:
            c_count = sum(1 for c in in_memory_store.chunks if c["document_id"] == d["id"])
            docs.append({
                "id": d["id"],
                "title": d["title"],
                "file_type": d["file_type"],
                "created_at": d["created_at"],
                "chunk_count": c_count,
            })
        return {"documents": docs, "dbActive": False, "source": "In-Memory"}
    except Exception as e:
        logger.error(f"Failed to list documents: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
    apiKey: Optional[str] = Form(None),
):
    try:
        content_bytes = await file.read()
        if not content_bytes:
            raise HTTPException(status_code=400, detail="Uploaded file is empty.")

        max_upload_size = 50 * 1024 * 1024  # 50 MB
        if len(content_bytes) > max_upload_size:
            raise HTTPException(status_code=413, detail="File size exceeds maximum allowed limit of 50MB.")

        # Parse document purely as text
        raw_text = parse_document(content_bytes, file.filename, custom_api_key=apiKey)
        if not raw_text or not raw_text.strip():
            raise HTTPException(status_code=422, detail="Could not extract any readable text from document.")

        result = ingest_document(
            title=file.filename,
            raw_text=raw_text,
            file_type=file.content_type or "text/plain",
            custom_api_key=apiKey,
        )

        return {
            "success": True,
            "message": f"Successfully ingested {file.filename} into Pure RAG knowledge base.",
            "document": result,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Document upload error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/seed")
def seed_default_knowledge_base(req: SeedRequest = None):
    try:
        api_key = req.apiKey if req else None
        result = ingest_document(
            title=SAMPLE_DOC_TITLE,
            raw_text=SAMPLE_DOC_CONTENT,
            file_type="text/plain",
            custom_api_key=api_key,
        )
        return {
            "success": True,
            "message": "Pure RAG default document seeded successfully.",
            "document": result,
        }
    except Exception as e:
        logger.error(f"Error seeding default knowledge: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("")
def delete_document(id: str = Query(...)):
    try:
        # Delete from PostgreSQL if connected
        with get_db_connection() as conn:
            if conn:
                try:
                    with conn.cursor() as cur:
                        cur.execute("DELETE FROM documents WHERE id = %s;", (id,))
                        conn.commit()
                except Exception as e:
                    logger.debug(f"PostgreSQL delete doc note: {e}")

        # Delete from SQLite pure_rag.db
        try:
            conn = sqlite3.connect(SQLITE_DB_PATH)
            cur = conn.cursor()
            cur.execute("DELETE FROM rag_documents WHERE id = ?;", (id,))
            cur.execute("DELETE FROM rag_document_chunks WHERE document_id = ?;", (id,))
            conn.commit()
            conn.close()
        except Exception as e:
            logger.debug(f"SQLite delete doc note: {e}")

        # Delete from in-memory store
        in_memory_store.documents = [d for d in in_memory_store.documents if d["id"] != id]
        in_memory_store.chunks = [c for c in in_memory_store.chunks if c["document_id"] != id]

        return {"success": True, "message": f"Document {id} deleted successfully from Pure RAG."}
    except Exception as e:
        logger.error(f"Delete document error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/clear")
def clear_all_documents():
    try:
        # Clear PostgreSQL
        with get_db_connection() as conn:
            if conn:
                try:
                    with conn.cursor() as cur:
                        cur.execute("DELETE FROM document_chunks;")
                        cur.execute("DELETE FROM documents;")
                        conn.commit()
                except Exception as e:
                    logger.debug(f"PostgreSQL clear docs note: {e}")

        # Clear SQLite pure_rag.db
        try:
            conn = sqlite3.connect(SQLITE_DB_PATH)
            cur = conn.cursor()
            cur.execute("DELETE FROM rag_document_chunks;")
            cur.execute("DELETE FROM rag_documents;")
            conn.commit()
            conn.close()
        except Exception as e:
            logger.debug(f"SQLite clear docs note: {e}")

        in_memory_store.documents.clear()
        in_memory_store.chunks.clear()

        return {"success": True, "message": "All documents cleared from Pure RAG."}
    except Exception as e:
        logger.error(f"Clear all documents error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
