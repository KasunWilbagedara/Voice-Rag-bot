"""
Test isolation: every test gets a fresh temporary SQLite store, PostgreSQL is
treated as offline, and no real LLM / embedding calls are made.
"""

import pytest

import backend.auth as auth
import backend.db as db
import backend.rag.ingester as ingester
import backend.rag.retriever as retriever
import backend.rag.sql_gen as sql_gen
import backend.routers.documents as documents_router
from backend.services.db_query import manager as manager_mod


@pytest.fixture(autouse=True)
def isolated_store(tmp_path, monkeypatch):
    db_path = str(tmp_path / "test_datasets.db")

    # Modules that imported SQLITE_DB_PATH by value
    for mod in (db, ingester, retriever, sql_gen, documents_router):
        monkeypatch.setattr(mod, "SQLITE_DB_PATH", db_path, raising=False)

    # Login off by default; auth tests turn it on
    monkeypatch.setattr(auth, "AUTH_REQUIRED", False)

    # PostgreSQL offline
    monkeypatch.setattr(db, "_db_pool", None)
    monkeypatch.setattr(db, "_db_pool_checked", True)

    db.init_sqlite_rag_tables()

    # Point the DatabaseManager singleton at the temp file and seed demo tables
    dm = manager_mod.db_manager
    monkeypatch.setattr(dm, "sqlite_db_path", db_path)
    monkeypatch.setattr(dm, "databases", {})
    dm._init_customer_datasets_sqlite()

    yield db_path
