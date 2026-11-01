"""
services/db_query/csv_importer.py — CSV / JSON Table Builder
=============================================================
Exposes ``import_csv_to_sqlite()`` — the public function used by the
databases router to upload tabular datasets into the built-in
``customer_support_db`` SQLite file.
"""

import logging
from typing import Any, Dict

from backend.services.db_query.manager import db_manager

logger = logging.getLogger("voicerag.db_query.csv_importer")


def import_csv_to_sqlite(
    table_name: str,
    csv_filename: str,
    csv_bytes: bytes,
) -> Dict[str, Any]:
    """
    Ingests a CSV or JSON file into the Customer SQLite database as a new
    queryable table, replacing any existing table with the same name.

    Column names are sanitised (lowercase, non-alphanumeric chars → ``_``).

    Args:
        table_name:   Desired SQL table name (will be sanitised).
        csv_filename: Original filename — used to detect ``.json`` extension.
        csv_bytes:    Raw file bytes of the uploaded CSV or JSON file.

    Returns:
        Dict with ``tableName``, ``rowCount``, ``columns``, ``db_id``.

    Raises:
        RuntimeError: If pandas cannot parse the file.
    """
    return db_manager.ingest_csv_as_table(
        table_name=table_name,
        csv_filename=csv_filename,
        csv_bytes=csv_bytes,
    )
