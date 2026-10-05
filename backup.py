"""Create and restore consistent SQLite snapshots of calculation history."""

import argparse
from contextlib import closing
from datetime import datetime, timezone
import os
from pathlib import Path
import sqlite3

try:
    from .server import DEFAULT_DB
except ImportError:  # Also support execution from a standalone backend checkout.
    from server import DEFAULT_DB


def _integrity_check(database: sqlite3.Connection) -> None:
    result = database.execute("PRAGMA integrity_check").fetchone()[0]
    if result != "ok":
        raise sqlite3.DatabaseError(f"SQLite integrity check failed: {result}")


def backup_database(source_path: str | Path, backup_dir: str | Path) -> Path:
    source = Path(source_path)
    if not source.is_file():
        raise FileNotFoundError(f"Database does not exist: {source}")
    destination_dir = Path(backup_dir)
    destination_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    destination = destination_dir / f"calculator-history-{stamp}.sqlite3"
    with closing(sqlite3.connect(source, timeout=10)) as original:
        with closing(sqlite3.connect(destination, timeout=10)) as snapshot:
            original.backup(snapshot)
            _integrity_check(snapshot)
    return destination


def restore_database(backup_path: str | Path, destination_path: str | Path) -> None:
    """Restore a verified snapshot; stop the API service before calling this."""
    source = Path(backup_path)
    if not source.is_file():
        raise FileNotFoundError(f"Backup does not exist: {source}")
    destination = Path(destination_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(source, timeout=10)) as snapshot:
        _integrity_check(snapshot)
        with closing(sqlite3.connect(destination, timeout=10)) as database:
            snapshot.backup(database)
            _integrity_check(database)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", default=os.environ.get("CALCULATOR_DB_PATH", str(DEFAULT_DB)))
    parser.add_argument("--directory", default=str(Path(__file__).resolve().parent.parent / "backups"))
    parser.add_argument("--restore", metavar="BACKUP_FILE", help="restore a backup (stop the backend first)")
    args = parser.parse_args()
    if args.restore:
        restore_database(args.restore, args.database)
        print(f"Restored database from {args.restore}")
    else:
        print(backup_database(args.database, args.directory))


if __name__ == "__main__":
    main()
