# MARS Recommender API

Lightweight FastAPI backend for the MARS course recommendation product.

This repo provides a minimal, runnable API scaffold implementing the serving
surface described in the design docs (see `/context`). Endpoints are
implemented as placeholders and are ready to be wired to database, artifact,
and inference services.

## What’s included

- `app.py` — FastAPI application and router registration
- `core/` — configuration and simple JWT-based security helpers
- `api/` — route modules:
	- `auth.py` — token endpoint + current user
	- `courses.py` — catalog list/detail (placeholder)
	- `history.py` — user history CRUD (placeholder)
	- `recommendations.py` — recommendation rails (placeholder)
	- `admin.py` — admin operations (placeholder)
	- `debug.py` — debug inference endpoint (`/api/v1/debug/infer`)
- `inference.py` — lightweight model loader / predict helpers (used by debug)

## Quickstart (dev)

This project can be managed with the `uv` CLI (configured via `pyproject.toml`).
Use `uv` to sync dependencies and run commands in a reproducible environment
instead of manually creating a virtualenv.

1. Install or verify `uv` CLI is available (if not installed):

```bash
# If you don't have `uv`, install it (example, use pip in your system/python env):
pip install uv-cli
```

2. Sync dependencies from `pyproject.toml`:

```bash
uv sync
```

1. Run the app:

```bash
uv run python -m uvicorn app:app --reload --port 8000
```

5. Test the debug inference endpoint (returns sample prediction or error):

```bash
curl -sS http://127.0.0.1:8000/api/v1/debug/infer | jq
```


## Development notes

- All endpoints are intentionally simple placeholders to be wired to real
	services (DB, MLflow/Artifact loader, recommendation services). Use
	`api/debug.py` to validate inference wiring before integrating into other
	endpoints.
- `core/security.py` uses JWT for demonstration. Replace with your auth
	backend and secure secret management for production.
- `core/config.py` reads env vars via a small `Settings` dataclass; set
	environment variables (or replace with Pydantic `BaseSettings` if desired).

## Commit checklist

- [ ] Run unit tests (if any)
- [ ] Verify `python -m uvicorn app:app` works inside the project venv
- [ ] Add/integrate real database + artifact loader before serving real traffic

## Next steps I can help with

- Wire endpoints to database/repositories
- Add artifact loader to serve promoted BERT4Rec artifacts
- Implement recommendation orchestration and logging

Happy to update this README further for packaging or deployment notes.
