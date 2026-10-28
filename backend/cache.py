"""Small SQLite cache for development-time Gemini responses."""

import json
import sqlite3
from pathlib import Path
from typing import Any


class ResponseCache:
    """Persist validated Gemini responses by SHA-256 file hash."""

    def __init__(self, database_path: str) -> None:
        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.database_path) as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS gemini_cache (
                    file_hash TEXT PRIMARY KEY,
                    response_json TEXT NOT NULL
                )
                """
            )

    def get(self, file_hash: str) -> dict[str, Any] | None:
        """Return a cached response, if present."""
        with sqlite3.connect(self.database_path) as connection:
            row = connection.execute(
                "SELECT response_json FROM gemini_cache WHERE file_hash = ?",
                (file_hash,),
            ).fetchone()
        return json.loads(row[0]) if row else None

    def set(self, file_hash: str, response: dict[str, Any]) -> None:
        """Store or replace a response."""
        with sqlite3.connect(self.database_path) as connection:
            connection.execute(
                """
                INSERT INTO gemini_cache (file_hash, response_json) VALUES (?, ?)
                ON CONFLICT(file_hash) DO UPDATE SET response_json = excluded.response_json
                """,
                (file_hash, json.dumps(response)),
            )
