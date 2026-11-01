"""Regression tests for the bugs fixed in the dual-backend RAG pipeline."""

import json
import sqlite3

import pytest
from fastapi.testclient import TestClient

import backend.security as security
from backend import db
from backend.rag import save_chat_history
from backend.services.db_query.manager import db_manager, validate_read_only_sql


# ---------------------------------------------------------------------------
# SQL safety
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("sql", [
    "SELECT created_at, updated_at FROM rag_documents",
    "SELECT * FROM orders WHERE status = 'Deleted; DROP TABLE x'",
    "WITH t AS (SELECT 1 AS n) SELECT n FROM t;",
])
def test_read_only_sql_allows_legitimate_queries(sql):
    assert validate_read_only_sql(sql)


@pytest.mark.parametrize("sql", [
    "DROP TABLE orders",
    "SELECT 1; DELETE FROM orders",
    "SELECT * FROM orders WHERE 1=1 UNION SELECT * FROM x; UPDATE orders SET amount = 0",
    "PRAGMA table_info(orders)",
])
def test_read_only_sql_blocks_writes_and_stacked_statements(sql):
    with pytest.raises(ValueError):
        validate_read_only_sql(sql)


def test_sqlite_queries_run_on_read_only_connection():
    # Even if validation were bypassed, the connection itself refuses writes.
    from backend.services.db_query.manager import _sqlite_read_only_connect

    conn = _sqlite_read_only_connect(db_manager.sqlite_db_path)
    with pytest.raises(sqlite3.OperationalError):
        conn.execute("DELETE FROM orders")
    conn.close()


def test_order_tracking_is_parameterized():
    from backend.tools.db_tools import track_customer_order

    assert track_customer_order("ORD-9021")["status"] == "found"
    # With string formatting this became `... = 'X' OR '1'='1'` and returned an
    # arbitrary order; as a bound parameter it is just a non-matching ID.
    assert track_customer_order("X' OR '1'='1")["status"] == "not_found"


def test_internal_tables_hidden_from_schema():
    tables = {s["table_name"] for s in db_manager.get_database_schema("customer_support_db")}
    assert "orders" in tables
    assert not tables & {"rag_documents", "rag_document_chunks", "rag_chat_history", "rag_user_memories"}


def test_reset_keeps_knowledge_base_and_memories(isolated_store):
    db.save_or_update_memory("s1", "user_name", "Kasun")
    save_chat_history("q", [], "a", "s1")
    db_manager.reset_all_data()

    conn = sqlite3.connect(isolated_store)
    assert conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM rag_user_memories").fetchone()[0] == 1
    assert conn.execute("SELECT COUNT(*) FROM rag_chat_history").fetchone()[0] == 1
    conn.close()


def test_unsupported_db_type_rejected():
    with pytest.raises(ValueError):
        db_manager.register_connection("x", "mysql", "mysql://localhost/x")


# ---------------------------------------------------------------------------
# Memory & history
# ---------------------------------------------------------------------------

def test_save_session_memory_tool_persists_and_updates():
    from backend.tools.db_tools import save_session_memory

    assert save_session_memory(session_id="s1", key="user_name", value="Kasun") is True
    assert save_session_memory(session_id="s1", key="user_name", value="Nimal") is True
    memories = db.get_user_memories("s1")
    assert [(m["key"], m["value"]) for m in memories] == [("user_name", "Nimal")]


def test_chat_history_is_scoped_per_session():
    save_chat_history("q1", [], "a1", "alice")
    save_chat_history("q2", [], "a2", "bob")
    assert [h["userQuery"] for h in db.get_saved_chat_history(10, session_id="alice")] == ["q1"]
    assert len(db.get_saved_chat_history(10)) == 2

    db.clear_saved_chat_history("alice")
    assert db.get_saved_chat_history(10, session_id="alice") == []
    assert len(db.get_saved_chat_history(10, session_id="bob")) == 1


# ---------------------------------------------------------------------------
# Text-to-SQL parsing
# ---------------------------------------------------------------------------

def test_text_to_sql_parses_model_output(monkeypatch):
    import backend.rag.sql_gen as sg

    class _Resp:
        text = "DB_ID: customer_support_db\nSQL: SELECT * FROM orders WHERE order_id = 'ORD-9021'"

    class _Client:
        def __init__(self, **_):
            self.models = self

        def generate_content(self, **_):
            return _Resp()

    monkeypatch.setattr(sg.genai, "Client", _Client)
    assert sg.generate_llm_sql_query("status?", "schema", custom_api_key="AIzaTEST") == (
        "customer_support_db",
        "SELECT * FROM orders WHERE order_id = 'ORD-9021';",
    )


# ---------------------------------------------------------------------------
# RAG modes
# ---------------------------------------------------------------------------

@pytest.fixture
def no_llm(monkeypatch):
    """Stub embeddings + LLM; record whether tool enrichment ran."""
    import backend.rag.generator as gen
    import backend.rag.pipeline as pipeline

    calls = {"enrich": 0}

    def fake_enrich(query, chunks):
        calls["enrich"] += 1
        return [], list(chunks)

    monkeypatch.setattr(pipeline, "safe_query_embedding", lambda *a, **k: [])
    monkeypatch.setattr(gen, "_enrich_with_tools", fake_enrich)
    monkeypatch.setattr(gen, "_call_llm", lambda **kw: "Grounded answer.")
    return calls


def test_pure_mode_text_query_works_without_tools(no_llm):
    from backend.main import app

    res = TestClient(app).post(
        "/api/rag",
        json={"query": "What is the refund policy?", "apiKey": "AIzaTEST", "sessionId": "s1"},
        headers={"x-backend-mode": "pure"},
    )
    assert res.status_code == 200, res.text
    assert res.json()["answer"] == "Grounded answer."
    assert res.json()["mode"] == "pure-rag"
    assert no_llm["enrich"] == 0
    assert db.get_saved_chat_history(5, session_id="s1")[0]["userQuery"] == "What is the refund policy?"


def test_standard_mode_uses_tool_enrichment(no_llm):
    from backend.main import app

    res = TestClient(app).post("/api/rag", json={"query": "hello", "apiKey": "AIzaTEST"})
    assert res.status_code == 200, res.text
    assert no_llm["enrich"] == 1


def test_agentic_query_retrieves_documents(monkeypatch):
    from backend.rag import agentic_generator as ag

    seen = {}

    def fake_embedding(text, **kwargs):
        seen["kwargs"] = kwargs
        return [0.1, 0.2]

    monkeypatch.setattr(ag, "get_embedding", fake_embedding)
    monkeypatch.setattr(ag, "search_similar_chunks", lambda **kw: [{"documentTitle": "Doc", "content": "Fact"}])
    monkeypatch.setattr(ag, "_run_agentic_loop", lambda **kw: (kw["context_text"], []))

    result = ag.agentic_query("question", custom_api_key="AIzaTEST")
    assert seen["kwargs"] == {"custom_api_key": "AIzaTEST"}
    assert "Fact" in result["answer"]


def test_tool_server_starts():
    import backend.tool_server  # noqa: F401  (used to fail with ImportError)


# ---------------------------------------------------------------------------
# Admin key
# ---------------------------------------------------------------------------

def test_destructive_endpoints_require_admin_key_when_configured(monkeypatch):
    from backend.main import app

    monkeypatch.setattr(security, "ADMIN_API_KEY", "secret")
    client = TestClient(app)
    assert client.delete("/api/documents", params={"id": "x"}).status_code == 401
    ok = client.delete("/api/documents", params={"id": "x"}, headers={"x-admin-key": "secret"})
    assert ok.status_code == 200


def test_admin_key_optional_in_development(monkeypatch):
    from backend.main import app

    monkeypatch.setattr(security, "ADMIN_API_KEY", "")
    assert TestClient(app).delete("/api/documents", params={"id": "x"}).status_code == 200


# ---------------------------------------------------------------------------
# Embeddings: fixed size + model tracking
# ---------------------------------------------------------------------------

def test_ingested_chunks_record_model_and_search_matches_model(monkeypatch):
    import backend.rag.ingester as ingester
    from backend.rag.retriever import search_similar_chunks

    monkeypatch.setattr(ingester, "get_embeddings_batch", lambda texts, key=None: [[1.0, 0.0]] * len(texts))
    ingester.ingest_document("Refunds.txt", "text/plain", "Refunds take 14 business days.", "AIzaTEST")

    conn = sqlite3.connect(db.SQLITE_DB_PATH)
    assert conn.execute("SELECT embedding_model FROM rag_document_chunks").fetchone()[0] == "gemini-embedding-001"
    conn.close()

    # Same model (Gemini key) → found by vector search
    assert search_similar_chunks([1.0, 0.0], top_k=3, custom_api_key="AIzaTEST")
    # Different model (OpenAI key) → vectors are not comparable, so no dense matches
    assert search_similar_chunks([1.0, 0.0], top_k=3, custom_api_key="sk-test") == []


def test_reembed_updates_old_chunks(monkeypatch):
    import backend.reembed as reembed

    conn = sqlite3.connect(db.SQLITE_DB_PATH)
    conn.execute("INSERT INTO rag_documents VALUES ('d1', 'Old', 'txt', '2026-01-01')")
    conn.execute(
        "INSERT INTO rag_document_chunks (id, document_id, content, chunk_index, embedding, created_at) "
        "VALUES ('c1', 'd1', 'old text', 0, '[0.5, 0.5, 0.5]', '2026-01-01')"
    )
    conn.commit()

    monkeypatch.setattr(reembed, "embedding_model_name", lambda key=None: "gemini-embedding-001")
    monkeypatch.setattr(reembed, "get_embeddings_batch", lambda texts, key=None: [[0.1] * 768 for _ in texts])
    monkeypatch.setattr(reembed, "init_db_schema", lambda: None)
    reembed.main()

    model, emb = conn.execute("SELECT embedding_model, embedding FROM rag_document_chunks WHERE id='c1'").fetchone()
    assert model == "gemini-embedding-001" and len(json.loads(emb)) == 768
    conn.close()
