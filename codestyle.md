# Backend code style

Source: [PEP 8 — Style Guide for Python Code](https://peps.python.org/pep-0008/), the official Python style guide.

- Follow PEP 8; use four spaces, descriptive `snake_case` names and focused modules.
- Keep expression parsing/calculation, persistence and HTTP transport separate (`calculator.py`, `storage.py`, `server.py`).
- Type public function inputs and outputs where useful; document non-obvious constraints.
- Parameterize every SQL value. Never concatenate user input into SQL.
- Never use `eval`, `exec`, or a general-purpose interpreter for calculator input.
- Return predictable JSON errors and do not write failed expressions to history.
- Add unit tests for parser boundaries and API integration when behavior changes.
- Keep generated databases, secrets and environment-specific configuration out of Git.
