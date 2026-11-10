from __future__ import annotations

import os
from pathlib import Path
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from app.metadata_index import get_metadata_index, PostgresMetadataIndex
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings

from app.providers import discover_for_brief, search_all

mcp = FastMCP("Music Source Assistant", stateless_http=True)


@mcp.tool()
async def search_music(query: str, limit: int = 8, providers: list[str] | None = None) -> dict[str, Any]:
    """Search music and sound effects across Free To Use, Openverse and Freesound."""
    query = query.strip()
    if not query or len(query) > 240:
        raise ValueError("query must contain 1 to 240 characters")
    if limit < 1 or limit > 20:
        raise ValueError("limit must be between 1 and 20")
    if providers and any(p not in {"freetouse", "openverse", "freesound"} for p in providers):
        raise ValueError("Unsupported provider")
    return await search_all(query, limit, providers)


@mcp.tool()
async def discover_music_for_project(brief: str, limit: int = 8, providers: list[str] | None = None) -> dict[str, Any]:
    """Find music for a described creative project using transparent, model-free brief parsing."""
    if not brief.strip() or len(brief) > 2000:
        raise ValueError("brief must contain 1 to 2000 characters")
    if limit < 1 or limit > 20:
        raise ValueError("limit must be between 1 and 20")
    if providers and any(p not in {"freetouse", "openverse", "freesound"} for p in providers):
        raise ValueError("Unsupported provider")
    return await discover_for_brief(brief, limit, providers)


@mcp.tool()
async def explain_music_licence(provider: str, licence: str) -> dict[str, str]:
    """Explain what to verify before using a track; this is guidance, not legal advice."""
    provider = provider.lower().strip()
    licence = licence.strip()
    if provider == "freetouse":
        return {
            "summary": "Free To Use tracks are governed by the provider's Free To Use License. Free use is limited to the uses and conditions stated by that licence; commercial use may require a paid licence.",
            "check": "Check the exact track and the current licence terms for monetized user-generated content, commercial content, broadcast, digital products and attribution.",
            "licence_url": "https://freetouse.com/license",
        }
    if provider == "openverse":
        return {
            "summary": f"Openverse aggregates works under different licences. The reported licence is {licence or 'unknown'}.",
            "check": "Open the original work page and verify the licence URL, creator, attribution requirements, commercial-use permission and whether adaptations are allowed. Avoid NC works for commercial projects; check ND restrictions before editing.",
            "licence_url": "https://openverse.org/",
        }
    if provider == "freesound":
        return {
            "summary": "Freesound licences vary by sound. The sound page is authoritative.",
            "check": "Check the individual sound page for its exact Creative Commons licence, attribution requirements, commercial-use permission and modification restrictions.",
            "licence_url": "https://freesound.org/help/faq/",
        }
    raise ValueError("Unknown provider")


@asynccontextmanager
async def lifespan(app: FastAPI):
    index = get_metadata_index()
    if isinstance(index, PostgresMetadataIndex):
        index.initialize()
        index.ping()
    app.state.metadata_index = index
    async with mcp.session_manager.run():
        yield


BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = BASE_DIR / "frontend"
app = FastAPI(title="Music Source Assistant", version="0.1.0", lifespan=lifespan)


@app.get("/", include_in_schema=False)
async def home():
    return FileResponse(FRONTEND_DIR / "index.html")


app.mount("/assets", StaticFiles(directory=FRONTEND_DIR / "assets"), name="assets")


@app.get("/api/discover")
async def api_discover(brief: str = Query(min_length=1, max_length=1200), limit: int = Query(default=8, ge=1, le=20), providers: str | None = None) -> dict[str, Any]:
    selected = [p.strip().lower() for p in providers.split(",") if p.strip()] if providers else None
    try:
        return await discover_for_brief(brief, limit, selected)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail="Music provider request failed") from exc


@app.get("/health")
async def health(request: Request) -> dict[str, Any]:
    index = getattr(request.app.state, "metadata_index", None)
    database = "postgresql" if isinstance(index, PostgresMetadataIndex) else "sqlite-local"
    if isinstance(index, PostgresMetadataIndex):
        try:
            index.ping()
        except Exception as exc:
            raise HTTPException(status_code=503, detail="PostgreSQL database unavailable") from exc
    return {"status": "ok", "service": "music-source-assistant", "database": database,
            "features": ["direct-search", "project-discovery", "persistent-metadata-catalogue",
                         "explainable-ranking", "optional-audio-analysis", "mcp-streamable-http"]}


@app.get("/api/search")
async def api_search(q: str = Query(min_length=1, max_length=240), limit: int = Query(default=8, ge=1, le=20), providers: str | None = None) -> dict[str, Any]:
    selected = [p.strip().lower() for p in providers.split(",") if p.strip()] if providers else None
    try:
        return await search_all(q.strip(), limit, selected)
    except Exception as exc:
        raise HTTPException(status_code=502, detail="Music provider request failed") from exc


@app.get("/api/index/search")
async def api_index_search(q: str = Query(min_length=1, max_length=240), limit: int = Query(default=20, ge=1, le=100)):
    try:
        return {"query": q, "results": get_metadata_index().search(q, limit)}
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Metadata index search failed") from exc


@app.post("/api/analyze-audio")
async def api_analyze_audio(request: Request):
    content_type = request.headers.get("content-type", "")
    if not content_type.startswith("audio/") and content_type not in {"application/octet-stream", "application/x-wav"}:
        raise HTTPException(status_code=415, detail="Send an audio/* or application/octet-stream request body")
    data = await request.body()
    if len(data) > 20 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Audio upload exceeds 20 MB")
    try:
        from app.audio_features import analyze_audio_bytes
        return analyze_audio_bytes(data, request.headers.get("x-filename", "audio"))
    except RuntimeError as exc:
        raise HTTPException(status_code=501, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


allowed_hosts = [item.strip() for item in os.getenv("MCP_ALLOWED_HOSTS", "localhost:*,127.0.0.1:*,[::1]:*").split(",") if item.strip()]
security = TransportSecuritySettings(enable_dns_rebinding_protection=True, allowed_hosts=allowed_hosts)
# FastMCP in the supported MCP SDK exposes the default /mcp route. Mount the
# sub-application at the ASGI root so that its endpoint remains /mcp externally.
# Keep this catch-all mount last so the FastAPI routes above retain precedence.
mcp_app = mcp.streamable_http_app(host="0.0.0.0", transport_security=security)
app.mount("/", mcp_app)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=int(os.getenv("PORT", "8000")))
