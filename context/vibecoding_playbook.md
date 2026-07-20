# MARS RecSys - Vibe-Coding Playbook

This playbook is a condensed reference guide designed for AI agents and developers to quickly understand, extend, and vibe with the `mars-rec-sys` API server.

## Project Structure Overview

- [app.py](file:///home/michael/Documents/workspace/thesis/resys-api/app.py) - FastAPI entry point. Serves the SPA frontend at root `/` and mounts routers at `/api/v1`.
- [core/database.py](file:///home/michael/Documents/workspace/thesis/resys-api/core/database.py) - SQLite layer (`data/db.sqlite3`). Tracks users, history sequences, and recommender request logs.
- [inference.py](file:///home/michael/Documents/workspace/thesis/resys-api/inference.py) - Loads PyTorch models, computes sequence predictions, and returns rank metrics.
- [models/embeddings.py](file:///home/michael/Documents/workspace/thesis/resys-api/models/embeddings.py) - Performs cosine-similarity text-based search using locally saved Camembert vectors.
- [assets/](file:///home/michael/Documents/workspace/thesis/resys-api/assets/) - Single Page Application files (HTML, CSS, JS, and mock video assets).

## Essential API Reference

| Method | Endpoint | Description | Auth Required |
|---|---|---|---|
| `POST` | `/api/v1/auth/register` | Register a new learner account | No |
| `POST` | `/api/v1/auth/token` | Log in and get JWT Bearer token | No |
| `GET` | `/api/v1/courses/` | Search courses catalog | Yes |
| `GET` | `/api/v1/history/` | Get user sequence history | Yes |
| `POST` | `/api/v1/history/` | Append course to history | Yes |
| `DELETE` | `/api/v1/history/{item_idx}` | Remove course from history | Yes |
| `POST` | `/api/v1/recommendations/for-you` | Predict next items using BERT4Rec | Yes |
| `POST` | `/api/v1/recommendations/you-may-also-like` | Vector content recommendations | Yes |
| `GET` | `/api/v1/admin/recommendation-logs` | Auditing request log list | Yes (Admin) |

## Quick Database Inspection (SQLite)

The local database can be queried directly via sqlite3 CLI:
```bash
sqlite3 data/db.sqlite3
```
Useful verification queries:
```sql
-- Check user histories
SELECT u.username, h.item_idx FROM user_history h JOIN users u ON h.user_id = u.id;

-- View top latent request latencies
SELECT strategy, latency_ms, timestamp FROM recommendation_logs ORDER BY latency_ms DESC;
```

## Troubleshooting & Verification

If the PyTorch model fails to load, check that:
1. `models/checkpoints/bert4rec.pt` is present.
2. `models/sentence-camembert-base.pt` exists for text matching.
3. Verify inference directly by running the CLI checker:
   ```bash
   uv run python inference.py
   ```
