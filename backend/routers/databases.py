import logging
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from pydantic import BaseModel

from backend.db_query_service import db_manager

router = APIRouter(prefix="/api/databases", tags=["Databases"])
logger = logging.getLogger("voicerag.databases_router")

class ConnectDbRequest(BaseModel):
    name: str
    dbType: str  # postgresql, mysql, sqlite
    connectionString: str

class QueryDbRequest(BaseModel):
    sqlQuery: str
    dbId: Optional[str] = "customer_support_db"

@router.get("")
def list_databases():
    try:
        databases = db_manager.list_databases()
        return {"databases": databases, "count": len(databases)}
    except Exception as e:
        logger.error(f"Error listing databases: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/schemas")
def get_all_schemas():
    try:
        databases = db_manager.list_databases()
        full_schemas = {}
        for db in databases:
            full_schemas[db["id"]] = db_manager.get_database_schema(db["id"])
        return {"schemas": full_schemas}
    except Exception as e:
        logger.error(f"Error getting schemas: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/connect")
def connect_database(req: ConnectDbRequest):
    if not req.name or not req.connectionString:
        raise HTTPException(status_code=400, detail="Database name and connection string are required.")
    try:
        result = db_manager.register_connection(
            name=req.name,
            db_type=req.dbType.lower(),
            uri_or_path=req.connectionString,
        )
        return {"message": "Database registered successfully", "database": result}
    except Exception as e:
        logger.error(f"Error connecting database: {e}")
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/upload-csv")
async def upload_csv_table(
    file: UploadFile = File(...),
    tableName: Optional[str] = Form(None)
):
    if not file.filename.endswith((".csv", ".json")):
        raise HTTPException(status_code=400, detail="Only CSV and JSON dataset files are supported.")
    try:
        content = await file.read()
        target_name = tableName or file.filename.rsplit(".", 1)[0]
        result = db_manager.ingest_csv_as_table(
            table_name=target_name,
            csv_filename=file.filename,
            csv_bytes=content
        )
        return {
            "message": f"Dataset '{file.filename}' ingested into table '{result['tableName']}' successfully.",
            "dataset": result
        }
    except Exception as e:
        logger.error(f"Error uploading CSV dataset: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/query")
def execute_test_query(req: QueryDbRequest):
    if not req.sqlQuery or not req.sqlQuery.strip():
        raise HTTPException(status_code=400, detail="SQL query text is required.")
    try:
        res = db_manager.execute_safe_sql(sql_query=req.sqlQuery, db_id=req.dbId)
        if "error" in res and res["error"]:
            raise HTTPException(status_code=400, detail=res["error"])
        return res
    except Exception as e:
        logger.error(f"Query execution error: {e}")
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/seed")
def seed_sample_database_records():
    try:
        res = db_manager.reseed_sample_data()
        return res
    except Exception as e:
        logger.error(f"Error seeding sample databases: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/reset")
def reset_all_database_records():
    try:
        res = db_manager.reset_all_data()
        return res
    except Exception as e:
        logger.error(f"Error resetting database records: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/{db_id}")
def remove_database(db_id: str):
    try:
        removed = db_manager.remove_database(db_id)
        if not removed:
            raise HTTPException(status_code=404, detail="Database not found or is built-in.")
        return {"message": f"Database '{db_id}' removed successfully."}
    except Exception as e:
        logger.error(f"Error removing database: {e}")
        raise HTTPException(status_code=400, detail=str(e))
