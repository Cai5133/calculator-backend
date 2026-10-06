"""PythonAnywhere WSGI entry point for the unified calculator site.

Place this file in a PythonAnywhere web app and set PROJECT_ROOT to the
directory containing sibling `backend/` and `frontend/` folders.
"""

import json
import mimetypes
import os
from pathlib import Path
from urllib.parse import parse_qs

from backend import storage
from backend.calculator import calculate, format_decimal, ExpressionError


PROJECT_ROOT = Path(os.environ.get("CALCULATOR_PROJECT_ROOT", Path(__file__).resolve().parent.parent))
FRONTEND_ROOT = PROJECT_ROOT / "frontend"
DB_PATH = Path(os.environ.get("CALCULATOR_DB_PATH", str(PROJECT_ROOT / "data" / "calculator.sqlite3")))
storage.initialize(DB_PATH)


def response(start_response, status, payload, content_type="application/json; charset=utf-8"):
    body = payload if isinstance(payload, bytes) else json.dumps(payload, ensure_ascii=False).encode("utf-8")
    start_response(status, [("Content-Type", content_type), ("Content-Length", str(len(body))), ("Cache-Control", "no-store")])
    return [body]


def application(environ, start_response):
    method = environ.get("REQUEST_METHOD", "GET")
    path = environ.get("PATH_INFO", "/")

    if method == "GET" and path == "/api/health":
        try:
            storage.check_ready(DB_PATH)
            return response(start_response, "200 OK", {"success": True, "status": "ok", "database": "ready"})
        except Exception:
            return response(start_response, "503 Service Unavailable", {"success": False, "status": "unavailable"})

    if method == "GET" and path == "/api/history":
        query = parse_qs(environ.get("QUERY_STRING", ""))
        try:
            limit = int(query.get("limit", ["100"])[0]); offset = int(query.get("offset", ["0"])[0])
            if not 1 <= limit <= 100 or offset < 0: raise ValueError
            items, total = storage.get_records(DB_PATH, limit, offset)
            return response(start_response, "200 OK", {"success": True, "items": items, "total": total, "limit": limit, "offset": offset})
        except ValueError:
            return response(start_response, "400 Bad Request", {"success": False, "message": "Invalid history pagination."})

    if method == "POST" and path == "/api/calculate":
        try:
            length = int(environ.get("CONTENT_LENGTH") or "0")
            payload = json.loads(environ["wsgi.input"].read(length).decode("utf-8"))
            expression = payload.get("expression") if isinstance(payload, dict) else None
            if not isinstance(expression, str): raise ValueError("The expression field must be a string.")
            result = calculate(expression); result_text = format_decimal(result)
            record = storage.add_record(DB_PATH, expression.strip(), result_text)
            return response(start_response, "200 OK", {"success": True, "expression": record["expression"], "result": float(result), "result_text": result_text, "history": record})
        except ExpressionError as error:
            return response(start_response, "400 Bad Request", {"success": False, "message": str(error)})
        except (ValueError, json.JSONDecodeError, UnicodeDecodeError) as error:
            return response(start_response, "400 Bad Request", {"success": False, "message": str(error)})
        except Exception:
            return response(start_response, "500 Internal Server Error", {"success": False, "message": "The calculator service could not save the result."})

    if method == "DELETE" and path == "/api/history":
        return response(start_response, "200 OK", {"success": True, "deleted": storage.clear_records(DB_PATH)})

    if method == "DELETE" and path.startswith("/api/history/"):
        suffix = path.rsplit("/", 1)[-1]
        if not suffix.isdigit() or int(suffix) < 1:
            return response(start_response, "400 Bad Request", {"success": False, "message": "History ID must be a positive integer."})
        if not storage.delete_record(DB_PATH, int(suffix)):
            return response(start_response, "404 Not Found", {"success": False, "message": "History record not found."})
        return response(start_response, "200 OK", {"success": True, "deleted": 1})

    if method == "GET":
        relative = "index.html" if path in ("", "/") else path.lstrip("/")
        requested = (FRONTEND_ROOT / relative).resolve()
        if FRONTEND_ROOT not in requested.parents and requested != FRONTEND_ROOT or not requested.is_file():
            return response(start_response, "404 Not Found", b"Not found", "text/plain; charset=utf-8")
        return response(start_response, "200 OK", requested.read_bytes(), mimetypes.guess_type(str(requested))[0] or "application/octet-stream")

    return response(start_response, "404 Not Found", {"success": False, "message": "API endpoint not found."})
