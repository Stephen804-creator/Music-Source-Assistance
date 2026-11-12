# Music Source Assistant

A music and sound discovery workspace for creative projects. Search provider catalogues, interpret project briefs with a transparent rules-based engine, inspect track provenance and licence metadata, and connect discovery through MCP.

## Features in this version
- Responsive **Discover Music** and **AI Studio** workspaces.
- Search across Free To Use and Openverse; Freesound is enabled when `FREESOUND_API_KEY` is configured.
- Project-brief parsing for moods, genres, instruments, use cases, duration, BPM, key and production constraints.
- Explainable metadata ranking and provider failure reporting.
- Track preview when a provider supplies a preview URL, original-source links and licence reminders.
- Optional audio upload analysis (requires `requirements-audio.txt`).
- FastAPI API and Streamable HTTP MCP endpoint at `/mcp`.

## Important product truth
AI Studio currently uses deterministic ontology rules and catalogue discovery. It is **not yet connected to a generative LLM**. Chat history and saved tracks are browser-session state only. Accounts, persistent collections, a hosted PostgreSQL repository, full download management, live autocomplete and waveform rendering are not implemented in this baseline. The PostgreSQL migration is a starting schema, not an active runtime integration.

Provider licence metadata is informational, can be incomplete or stale, and is not legal clearance. Always inspect the original work page and confirm permissions, attribution, commercial use and modification rights for the intended project.

## Run locally
```bash
python -m venv .venv
# Windows PowerShell: .venv\Scripts\Activate.ps1
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```
Open `http://127.0.0.1:8000`.

Optional audio analysis: `pip install -r requirements-audio.txt`.

Optional Freesound search: set `FREESOUND_API_KEY` in the environment.

The local metadata index is a SQLite file (default `data/music_index.sqlite3`, ignored by git). Override the location with `MUSIC_INDEX_PATH`. On Render's free plan the disk is ephemeral, so the index is rebuilt from searches after each restart.

## HTTP API
- `GET /health`
- `GET /api/search?q=cinematic%20piano&limit=8`
- `GET /api/discover?brief=hopeful%20African%20documentary%20piano&limit=8`
- `GET /api/index/search?q=piano&limit=20`
- `POST /api/analyze-audio` with raw audio bytes and an `audio/*` content type (max 20 MB).

The optional `providers` query parameter takes a comma-separated list of `freetouse`, `openverse` and `freesound`. Unknown names return `422`. `limit` is the maximum number of results returned.

## MCP
Streamable HTTP endpoint: `https://YOUR-HOST/mcp`

Tools:
- `search_music(query, limit, providers)`
- `discover_music_for_project(brief, limit, providers)`
- `explain_music_licence(provider, licence)`

The `mcp[cli]` dependency is included in `requirements.txt`; Render installs it as part of the normal build.

## Deploy on Render
The included `render.yaml` describes a Python web service:
- Branch: `main`
- Python: 3.12 (`PYTHON_VERSION`)
- Build: `pip install -r requirements.txt`
- Start: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- Health: `/health`

If the service was created before `render.yaml` was added, also check in the Render dashboard that it deploys from `main`.

## Tests
```bash
pip install -r requirements-dev.txt
python -m pytest -q
```
GitHub Actions runs the same checks on every push to `main` and on pull requests.
