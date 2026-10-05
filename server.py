"""HTTP JSON API for the separated calculator front end."""

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import math
import os
from pathlib import Path
import sqlite3
from urllib.parse import parse_qs, urlparse

try:
    from .calculator import calculate, format_decimal, ExpressionError
    from . import storage
except ImportError:  # Support `python backend/server.py` as well.
    from calculator import calculate, format_decimal, ExpressionError
    import storage


ROOT = Path(__file__).resolve().parent
DEFAULT_DB = ROOT / "data" / "calculator.sqlite3"


class CalculatorHTTPServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, address, handler, db_path, allowed_origins):
        super().__init__(address, handler)
        self.db_path = Path(db_path)
        self.allowed_origins = allowed_origins
        storage.initialize(self.db_path)


class APIHandler(BaseHTTPRequestHandler):
    server_version = "SeparatedCalculator/1.0"

    def log_message(self, format_string, *args):
        print(f"[{self.log_date_time_string()}] {format_string % args}")

    def _send(self, status, payload):
        body = json.dumps(payload, ensure_ascii=False, allow_nan=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def _cors(self):
        origin = self.headers.get("Origin")
        allowed = self.server.allowed_origins
        if origin and ("*" in allowed or origin in allowed):
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def end_headers(self):
        self._cors()
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/health":
            try:
                storage.check_ready(self.server.db_path)
                return self._send(200, {"success": True, "status": "ok", "database": "ready"})
            except (OSError, sqlite3.Error):
                return self._send(503, {"success": False, "status": "unavailable", "message": "History database is unavailable."})
        if parsed.path == "/api/history":
            query = parse_qs(parsed.query)
            try:
                limit = int(query.get("limit", ["100"])[0])
                offset = int(query.get("offset", ["0"])[0])
                if not 1 <= limit <= 100 or offset < 0:
                    raise ValueError
            except ValueError:
                return self._send(400, {"success": False, "message": "limit must be 1–100 and offset must be non-negative."})
            try:
                records, total = storage.get_records(self.server.db_path, limit, offset)
            except (OSError, sqlite3.Error):
                return self._send(503, {"success": False, "message": "History database is unavailable."})
            return self._send(200, {"success": True, "items": records, "total": total, "limit": limit, "offset": offset})
        return self._send(404, {"success": False, "message": "API endpoint not found."})

    def do_POST(self):
        if urlparse(self.path).path != "/api/calculate":
            return self._send(404, {"success": False, "message": "API endpoint not found."})
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0 or length > 8192:
                raise ValueError("Request body must be between 1 and 8192 bytes.")
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
            expression = payload.get("expression") if isinstance(payload, dict) else None
            if not isinstance(expression, str):
                raise ValueError("The 'expression' field must be a string.")
            result = calculate(expression)
            try:
                numeric_result = float(result)
            except OverflowError:
                numeric_result = math.inf
            if not math.isfinite(numeric_result) or (result != 0 and numeric_result == 0):
                raise ValueError("The result is outside the supported display range.")
            result_text = format_decimal(result)
            record = storage.add_record(self.server.db_path, expression.strip(), result_text)
            return self._send(200, {
                "success": True,
                "expression": record["expression"],
                "result": numeric_result,
                "result_text": result_text,
                "history": record,
            })
        except ExpressionError as error:
            return self._send(400, {"success": False, "message": str(error)})
        except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as error:
            return self._send(400, {"success": False, "message": str(error) or "Invalid request."})
        except (OSError, sqlite3.Error):
            return self._send(500, {"success": False, "message": "The calculation service could not save the result."})

    def do_DELETE(self):
        path = urlparse(self.path).path
        if path == "/api/history":
            try:
                deleted = storage.clear_records(self.server.db_path)
            except (OSError, sqlite3.Error):
                return self._send(503, {"success": False, "message": "History database is unavailable."})
            return self._send(200, {"success": True, "deleted": deleted})
        prefix = "/api/history/"
        if path.startswith(prefix):
            suffix = path[len(prefix):]
            if len(suffix) > 18 or not suffix.isdigit() or int(suffix) < 1:
                return self._send(400, {"success": False, "message": "History ID must be a positive integer."})
            try:
                deleted = storage.delete_record(self.server.db_path, int(suffix))
            except (OSError, sqlite3.Error):
                return self._send(503, {"success": False, "message": "History database is unavailable."})
            if not deleted:
                return self._send(404, {"success": False, "message": "History record not found."})
            return self._send(200, {"success": True, "deleted": 1})
        return self._send(404, {"success": False, "message": "API endpoint not found."})


def create_server(host="127.0.0.1", port=8000, db_path=DEFAULT_DB, allowed_origins=None):
    if allowed_origins is None:
        raw = os.environ.get("CALCULATOR_ALLOWED_ORIGINS", "http://127.0.0.1:5173,http://localhost:5173")
        allowed_origins = {item.strip() for item in raw.split(",") if item.strip()}
    return CalculatorHTTPServer((host, port), APIHandler, db_path, set(allowed_origins))


def main():
    host = os.environ.get("CALCULATOR_HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", os.environ.get("CALCULATOR_PORT", "8000")))
    database = os.environ.get("CALCULATOR_DB_PATH", str(DEFAULT_DB))
    server = create_server(host, port, database)
    print(f"Calculator API listening on http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping calculator API...")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
