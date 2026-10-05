# Calculator backend

Python 3.10+ HTTP JSON API. It uses only the Python standard library: `http.server` for HTTP, `decimal` plus a handwritten recursive-descent parser for safe arithmetic, and SQLite for persistent history. There are no runtime package-install steps.

## Run locally

From the standalone backend repository root:

```powershell
python server.py
```

The API listens at `http://127.0.0.1:8000`; the database is created at `data/calculator.sqlite3` on first start from this standalone repository (`backend/data/calculator.sqlite3` in the combined project). To override settings:

```powershell
$env:CALCULATOR_HOST = "127.0.0.1"
$env:CALCULATOR_PORT = "8000"
$env:CALCULATOR_DB_PATH = "./data/calculator.sqlite3"
$env:CALCULATOR_ALLOWED_ORIGINS = "http://127.0.0.1:5173,http://localhost:5173"
python server.py
```

When using the combined project instead of the standalone backend repository, start it from the combined root with `python -m backend.server`.

`PORT` is also honored by common hosting platforms. Set `CALCULATOR_HOST=0.0.0.0` when running inside a container. Configure the exact deployed front-end origin in `CALCULATOR_ALLOWED_ORIGINS` when the front end is hosted on a separate origin. The provided Compose setup keeps the backend private to the container network and uses a same-origin Nginx proxy. On first start the backend creates the parent directory and `calculation_history` table automatically. Its columns are `id` (primary key), `expression`, `result` (decimal text), and `created_at` (UTC timestamp).

## API

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/api/health` | Health check |
| `POST` | `/api/calculate` | Validate, parse, calculate and persist an expression |
| `GET` | `/api/history?limit=100&offset=0` | Query persisted history, newest first |
| `DELETE` | `/api/history/{id}` | Delete one record by database ID |
| `DELETE` | `/api/history` | Optional extension: delete all records |

Example request: `{"expression":"(1+2)*3"}`. A successful calculation returns `success`, the submitted expression, a JSON numeric `result`, exact display `result_text`, and the persisted `history` row. The scientific allowlist includes `sin`, `cos`, `tan`, `sqrt`, `log` (base 10), `ln`, `abs`, constants `pi`/`e`, integer powers with `^`, and factorial `!`; functions require parentheses and angles use radians. Errors return HTTP 400 with `{"success":false,"message":"..."}`. Invalid requests are never saved.

## Tests

From the standalone backend repository root:

```powershell
python -m unittest discover -s tests -v
```

The backend folder can also be used inside the combined project: run `python -m backend.server` and `python -m unittest discover -s backend/tests -v` from the combined project root. To build this repository's Docker image, run `docker build -t separated-calculator-api .` from this repository; publish it locally with `docker run --rm -p 8000:8000 -v calculator_data:/app/data separated-calculator-api`.

## Database backup

Create a consistent SQLite snapshot with the standard-library backup API:

```powershell
python -m backup --directory ./backups
```

For a combined-project checkout, use `python -m backend.backup`. Restore only while the API is stopped:

```powershell
python -m backup --restore ./backups/calculator-history-<timestamp>.sqlite3
```
