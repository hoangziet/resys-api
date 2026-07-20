# MARS Recommender API

Fully functional FastAPI-based serving layer for the MARS course recommendation product. 

This repository implements sequence-based personalization powered by the **BERT4Rec PyTorch model**, content similarity matches using **Camembert text embeddings**, and a local **SQLite database** for session and audit logging. It features a premium, responsive Single Page Application (SPA) dashboard interface.

---

## Key Features

1. **Multi-Model Recommendation Strategy**:
   - **Personalized Rails (BERT4Rec)**: Predicts a user's next course using sequential interaction sequences.
   - **You May Also Like**: Recommends similar items using cosine similarity of French sentence-Camembert embeddings.
   - **Trending Fallback**: Popularity-based backup rails for cold-start (new user) scenarios.
2. **SQLite Database Layer**: Persists user registration, history sequences, and latency audit logs.
3. **Premium SPA Client Dashboard**: Implements login/registration cards, course grids, details drawer with HTML5 video player previews, search filters, and an admin console with live latency chart logs.
4. **Reproducible Docker Stack**: Configured with Astro-UV builder caching to run multi-stage light containers.

---

## Quickstart (Local Development)

This project is managed with the `uv` CLI (configured via `pyproject.toml`).

1. **Install uv** (if not already installed):
   ```bash
   pip install uv
   ```

2. **Sync dependencies and initialize virtual environment**:
   ```bash
   uv sync
   ```

3. **Start the API server**:
   ```bash
   uv run python -m uvicorn app:app --port 8000 --reload
   ```

4. **Access the application**:
   Open [http://127.0.0.1:8000/](http://127.0.0.1:8000/) in your browser.

---

## Deployment (Docker Compose)

The application is pre-configured with a persistent SQLite storage volume.

1. **Start the docker container**:
   ```bash
   docker compose up --build
   ```

2. **Access the application**:
   Open [http://127.0.0.1:8000/](http://127.0.0.1:8000/).

---

## Technical Documentation & Playbook

For deep dives on model configuration, SQL CLI audits, and future code extensions, refer to the files in the `context/` folder:
- [vibecoding_playbook.md](file:///home/michael/Documents/workspace/thesis/resys-api/context/vibecoding_playbook.md) - Site maps, sqlite3 tables, and test guidelines.
- [architecture.md](file:///home/michael/Documents/workspace/thesis/resys-api/context/architecture.md) - Detailed PyTorch model layers and fallback workflows.
