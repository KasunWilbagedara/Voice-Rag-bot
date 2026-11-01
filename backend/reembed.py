"""
Re-embed stored document chunks with the current embedding model.

Run this once after upgrading (old chunks have 1536/3072-dim vectors and no
model name), or after switching between a Gemini and an OpenAI key:

    python -m backend.reembed
"""

import json
import sqlite3

from backend.db import SQLITE_DB_PATH, get_db_connection, init_db_schema, init_sqlite_rag_tables
from backend.rag.embedder import embedding_model_name, get_embeddings_batch

BATCH = 50


def main() -> None:
    init_sqlite_rag_tables()
    model = embedding_model_name()

    conn = sqlite3.connect(SQLITE_DB_PATH)
    rows = conn.execute(
        "SELECT id, document_id, chunk_index, content FROM rag_document_chunks "
        "WHERE embedding_model IS NULL OR embedding_model != ?;",
        (model,),
    ).fetchall()
    print(f"{len(rows)} chunk(s) to re-embed with {model}")

    for start in range(0, len(rows), BATCH):
        batch = rows[start:start + BATCH]
        vectors = get_embeddings_batch([r[3] for r in batch])

        for (chunk_id, _, _, _), vec in zip(batch, vectors):
            conn.execute(
                "UPDATE rag_document_chunks SET embedding = ?, embedding_model = ? WHERE id = ?;",
                (json.dumps(vec), model, chunk_id),
            )
        conn.commit()

        # Mirror to PostgreSQL. Older versions gave PostgreSQL rows different
        # IDs, so match on (document, position) instead.
        with get_db_connection() as pg:
            if pg:
                with pg.cursor() as cur:
                    for (_, doc_id, idx, _), vec in zip(batch, vectors):
                        cur.execute(
                            "UPDATE document_chunks SET embedding = %s::vector, embedding_model = %s "
                            "WHERE document_id::text = %s AND chunk_index = %s;",
                            (str(vec), model, doc_id, idx),
                        )
                pg.commit()

        print(f"  {min(start + BATCH, len(rows))}/{len(rows)}")

    conn.close()
    # With every vector now 768-dim, the column can be typed and indexed.
    init_db_schema()
    print("Done.")


if __name__ == "__main__":
    main()
