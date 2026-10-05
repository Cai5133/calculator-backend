import json
from pathlib import Path
import tempfile
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

try:
    from backend import storage
    from backend.backup import backup_database, restore_database
except ImportError:  # Also run when this directory is a standalone repository root.
    import storage
    from backup import backup_database, restore_database

try:
    from backend.server import create_server
except ImportError:  # Also run when this directory is a standalone repository root.
    from server import create_server


class APITests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        database = Path(self.tempdir.name) / "history.sqlite3"
        self.server = create_server("127.0.0.1", 0, database, {"http://localhost:5173"})
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = f"http://127.0.0.1:{self.server.server_port}"

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        self.tempdir.cleanup()

    def request(self, path, method="GET", payload=None):
        data = json.dumps(payload).encode("utf-8") if payload is not None else None
        req = Request(self.base + path, data=data, method=method, headers={"Content-Type": "application/json", "Origin": "http://localhost:5173"})
        try:
            response = urlopen(req, timeout=2)
        except HTTPError as error:
            response = error
        return response.status, json.loads(response.read().decode("utf-8")), response.headers

    def test_calculate_persists_then_delete_by_id(self):
        status, result, _ = self.request("/api/calculate", "POST", {"expression": "(2 + 3) * 4"})
        self.assertEqual(status, 200)
        self.assertEqual(result["result"], 20)
        self.assertEqual(result["result_text"], "20")
        record_id = result["history"]["id"]

        status, history, headers = self.request("/api/history")
        self.assertEqual(status, 200)
        self.assertEqual(history["total"], 1)
        self.assertEqual(history["items"][0]["expression"], "(2 + 3) * 4")
        self.assertEqual(headers.get("Access-Control-Allow-Origin"), "http://localhost:5173")

        status, deleted, _ = self.request(f"/api/history/{record_id}", "DELETE")
        self.assertEqual(status, 200)
        self.assertEqual(deleted["deleted"], 1)
        self.assertEqual(self.request("/api/history")[1]["total"], 0)

    def test_errors_are_structured_and_not_saved(self):
        status, error, _ = self.request("/api/calculate", "POST", {"expression": "7 / 0"})
        self.assertEqual(status, 400)
        self.assertFalse(error["success"])
        self.assertIn("zero", error["message"])
        self.assertEqual(self.request("/api/history")[1]["total"], 0)

    def test_health_and_clear_all(self):
        self.request("/api/calculate", "POST", {"expression": "1+1"})
        self.request("/api/calculate", "POST", {"expression": "2+2"})
        status, payload, _ = self.request("/api/history", "DELETE")
        self.assertEqual(status, 200)
        self.assertEqual(payload["deleted"], 2)
        health = self.request("/api/health")[1]
        self.assertEqual(health["status"], "ok")
        self.assertEqual(health["database"], "ready")

    def test_history_survives_backend_restart(self):
        self.request("/api/calculate", "POST", {"expression": "9 / 3"})
        database_path = self.server.db_path
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)

        self.server = create_server("127.0.0.1", 0, database_path, {"http://localhost:5173"})
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = f"http://127.0.0.1:{self.server.server_port}"

        status, history, _ = self.request("/api/history")
        self.assertEqual(status, 200)
        self.assertEqual(history["total"], 1)
        self.assertEqual(history["items"][0]["result"], "3")

    def test_database_backup_and_restore(self):
        storage.add_record(self.server.db_path, "6 * 7", "42")
        backup = backup_database(self.server.db_path, Path(self.tempdir.name) / "backups")
        storage.clear_records(self.server.db_path)
        self.assertEqual(storage.get_records(self.server.db_path)[1], 0)

        restore_database(backup, self.server.db_path)
        records, total = storage.get_records(self.server.db_path)
        self.assertEqual(total, 1)
        self.assertEqual(records[0]["result"], "42")


if __name__ == "__main__":
    unittest.main()
