"""SQLite persistence for calculation history."""

from pathlib import Path
import sqlite3
from contextlib import closing


def connect(db_path: str | Path) -> sqlite3.Connection:
    connection = sqlite3.connect(str(db_path), timeout=10)
    connection.row_factory = sqlite3.Row
    return connection


def initialize(db_path: str | Path) -> None:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with closing(connect(path)) as database:
        with database:
            database.execute("PRAGMA journal_mode=WAL")
            database.execute(
                """CREATE TABLE IF NOT EXISTS calculation_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    expression TEXT NOT NULL,
                    result TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
                )"""
            )


def check_ready(db_path: str | Path) -> bool:
    """Return whether the history database is readable and ready for requests."""
    with closing(connect(db_path)) as database:
        return database.execute("SELECT 1").fetchone()[0] == 1


def add_record(db_path: str | Path, expression: str, result: str) -> dict:
    with closing(connect(db_path)) as database:
        with database:
            cursor = database.execute(
                "INSERT INTO calculation_history(expression, result) VALUES (?, ?)",
                (expression, result),
            )
            row = database.execute(
                "SELECT id, expression, result, created_at FROM calculation_history WHERE id = ?",
                (cursor.lastrowid,),
            ).fetchone()
            return dict(row)


def get_records(db_path: str | Path, limit: int = 100, offset: int = 0) -> tuple[list[dict], int]:
    with closing(connect(db_path)) as database:
        total = database.execute("SELECT COUNT(*) FROM calculation_history").fetchone()[0]
        rows = database.execute(
            "SELECT id, expression, result, created_at FROM calculation_history "
            "ORDER BY id DESC LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()
        return [dict(row) for row in rows], total


def delete_record(db_path: str | Path, record_id: int) -> bool:
    with closing(connect(db_path)) as database:
        with database:
            cursor = database.execute("DELETE FROM calculation_history WHERE id = ?", (record_id,))
            return cursor.rowcount > 0


def clear_records(db_path: str | Path) -> int:
    with closing(connect(db_path)) as database:
        with database:
            cursor = database.execute("DELETE FROM calculation_history")
            return cursor.rowcount
