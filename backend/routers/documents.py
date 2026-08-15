import re
import sqlite3
import logging
from typing import Optional
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Query
from pydantic import BaseModel

from backend.db import get_db_connection, is_db_connected, in_memory_store, SQLITE_DB_PATH
from backend.document_parser import parse_document
from backend.rag_service import ingest_document
from backend.db_query_service import db_manager

router = APIRouter(prefix="/api/documents", tags=["Documents"])
logger = logging.getLogger("voicerag.documents")

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
        # 1. Try PostgreSQL if connected
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
                            return {"documents": docs, "dbActive": True}
                except Exception as e:
                    logger.debug(f"PostgreSQL list docs note: {e}")

        # 2. Read from SQLite persistent database
        try:
            conn = sqlite3.connect(SQLITE_DB_PATH)
            cur = conn.cursor()
            cur.execute("""
                SELECT d.id, d.title, d.file_type, d.created_at, COUNT(c.id) AS chunk_count
                FROM rag_documents d
                LEFT JOIN rag_document_chunks c ON d.id = c.document_id
                GROUP BY d.id
                ORDER BY d.created_at DESC;
            """)
            rows = cur.fetchall()
            conn.close()

            docs = []
            for row in rows:
                docs.append({
                    "id": str(row[0]),
                    "title": row[1],
                    "file_type": row[2],
                    "created_at": str(row[3]),
                    "chunk_count": row[4],
                })
            return {"documents": docs, "dbActive": True}
        except Exception as e:
            logger.error(f"SQLite document list error: {e}")

        # 3. In-memory fallback
        docs = []
        for doc in in_memory_store.documents:
            chunk_count = sum(1 for c in in_memory_store.chunks if c["document_id"] == doc["id"])
            docs.append({
                "id": doc["id"],
                "title": doc["title"],
                "file_type": doc["file_type"],
                "created_at": doc["created_at"],
                "chunk_count": chunk_count,
            })
        return {"documents": docs, "dbActive": False}
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
        
        max_file_size = 35 * 1024 * 1024  # 35 MB
        if len(content_bytes) > max_file_size:
            raise HTTPException(status_code=413, detail="File size exceeds maximum allowed limit of 35MB.")

        # 1. Parse document text content
        extracted_text = parse_document(
            file_bytes=content_bytes,
            filename=file.filename,
            mime_type=file.content_type or "",
            custom_api_key=apiKey,
        )
        
        if not extracted_text or not extracted_text.strip():
            raise HTTPException(status_code=422, detail="Could not extract readable text from document.")

        # 2. Ingest document into Database & Vector Store
        result = ingest_document(
            title=file.filename,
            file_type=file.content_type or "text/plain",
            content=extracted_text,
            custom_api_key=apiKey,
        )

        # 3. If file is a tabular dataset (CSV or JSON), also auto-register it as a SQL Database Table
        ext = file.filename.split(".")[-1].lower() if "." in file.filename else ""
        if ext in ["csv", "json", "tsv"]:
            try:
                base_name = re.sub(r"\.[^.]+$", "", file.filename)
                clean_table = re.sub(r"[^a-zA-Z0-9_]", "_", base_name.lower())
                db_manager.ingest_csv_as_table(clean_table, file.filename, content_bytes)
                logger.info(f"Auto-registered tabular dataset '{file.filename}' as SQL table '{clean_table}'.")
            except Exception as e:
                logger.warning(f"Note: Auto SQL table creation skipped: {e}")

        return {"success": True, "document": result}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Document Upload Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/seed")
@router.post("")
def seed_sample_documents(req: Optional[SeedRequest] = None):
    try:
        api_key = req.apiKey if req else None
        result = ingest_document(
            title=SAMPLE_DOC_TITLE,
            file_type="text/plain",
            content=SAMPLE_DOC_CONTENT,
            custom_api_key=api_key,
        )
        return {"success": True, "seededDocuments": [result]}
    except Exception as e:
        logger.error(f"Seed error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("")
def delete_document(id: str = Query(...)):
    try:
        # 1. Delete from PostgreSQL
        with get_db_connection() as conn:
            if conn:
                try:
                    with conn.cursor() as cur:
                        cur.execute("DELETE FROM documents WHERE id = %s", (id,))
                        conn.commit()
                except Exception as e:
                    logger.debug(f"PostgreSQL delete doc note: {e}")

        # 2. Delete from SQLite
        try:
            conn = sqlite3.connect(SQLITE_DB_PATH)
            cur = conn.cursor()
            cur.execute("DELETE FROM rag_document_chunks WHERE document_id = ?;", (id,))
            cur.execute("DELETE FROM rag_documents WHERE id = ?;", (id,))
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"SQLite delete doc error: {e}")

        # 3. Clean in-memory store
        in_memory_store.documents = [d for d in in_memory_store.documents if d["id"] != id]
        in_memory_store.chunks = [c for c in in_memory_store.chunks if c["document_id"] != id]

        return {"success": True, "id": id}
    except Exception as e:
        logger.error(f"Delete document error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
