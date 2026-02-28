# AGENTS.md

## Cursor Cloud specific instructions

### Overview

Agentic CXO is a Python FastAPI application — an AI-driven C-suite agent platform. It uses embedded SQLite and ChromaDB (no external database services needed). The app works fully without an `OPENAI_API_KEY` by falling back to rule-based/extractive mode.

### Quick reference

| Task | Command |
|------|---------|
| Install deps | `pip install -e ".[dev]"` |
| Lint | `ruff check src/ tests/` |
| Test | `pytest tests/ -v` |
| Run server | `uvicorn agentic_cxo.api.server:app --host 0.0.0.0 --port 8000 --reload` |
| CLI entry | `cxo serve`, `cxo scenarios`, `cxo run <id>` |

See `README.md` for full CLI and REST API usage.

### Non-obvious caveats

- The `cxo` CLI and other pip-installed scripts land in `~/.local/bin`. Ensure `PATH` includes `$HOME/.local/bin` (or use `uvicorn` / `pytest` via full path).
- Data directories `.cxo_data/` (SQLite) and `.vault/` (ChromaDB) are auto-created at runtime — no manual setup needed.
- The `passlib` library logs a benign `bcrypt` version-detection error at startup (`AttributeError: module 'bcrypt' has no attribute '__about__'`). This does not affect functionality.
- Scenarios are exposed via the REST API at `POST /scenarios/<id>/run` and the CLI (`cxo run <id>`). The web dashboard is chat-first; use API/CLI to trigger specific scenarios.
- `POST /seed` loads 9 sample business documents into the vault for testing/demo purposes.
- `asyncio_mode = "auto"` is configured in `pyproject.toml`, so async test functions are handled automatically by `pytest-asyncio`.
