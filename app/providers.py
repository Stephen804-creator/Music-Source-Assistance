from __future__ import annotations

import os
from typing import Any
from urllib.parse import urlparse
import httpx

FREETOUSE_API = "https://api.freetouse.com/v3"
OPENVERSE_API = "https://api.openverse.org/v1/audio/"
FREESOUND_API = "https://freesound.org/apiv2/search/text/"
TIMEOUT = httpx.Timeout(12.0, connect=5.0)


def _first(mapping: dict[str, Any], *keys: str, default: Any = None) -> Any:
    for key in keys:
        value = mapping.get(key)
        if value not in (None, ""):
            return value
    return default


def _safe_http_url(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    parsed = urlparse(value)
    return value if parsed.scheme == "https" and parsed.hostname else None


def normalize_freetouse(item: dict[str, Any]) -> dict[str, Any]:
    files = item.get("files") if isinstance(item.get("files"), dict) else {}
    artist = item.get("artist") if isinstance(item.get("artist"), dict) else {}
    return {
        "provider": "freetouse", "id": str(_first(item, "id", "_id", default="")),
        "title": _first(item, "title", "name", default="Untitled track"),
        "creator": _first(item, "artist_name", "artist", default=artist.get("name", "Unknown creator")),
        "duration": _first(item, "duration", "duration_seconds"), "genre": _first(item, "genre", "category"),
        "preview_url": _safe_http_url(_first(item, "preview_url", "preview", default=files.get("mp3"))),
        "download_url": _safe_http_url(_first(item, "download_url", default=files.get("mp3"))),
        "source_url": _safe_http_url(_first(item, "url", "permalink", "source_url")),
        "license": "Free To Use License — check the track and intended-use restrictions",
        "license_url": "https://freetouse.com/license", "attribution": True,
    }


def normalize_openverse(item: dict[str, Any]) -> dict[str, Any]:
    license_code = _first(item, "license", default="unknown")
    return {
        "provider": "openverse", "id": str(_first(item, "id", default="")),
        "title": _first(item, "title", default="Untitled audio"),
        "creator": _first(item, "creator", default="Unknown creator"),
        "duration": _first(item, "duration"), "genre": None,
        "preview_url": _safe_http_url(item.get("previews", {}).get("preview-lq-mp3") if isinstance(item.get("previews"), dict) else None),
        "download_url": _safe_http_url(_first(item, "url", "file")),
        "source_url": _safe_http_url(_first(item, "foreign_landing_url", "detail_url")),
        "license": str(license_code).upper(), "license_url": _safe_http_url(item.get("license_url")),
        "attribution": bool(item.get("attribution")) or bool(item.get("creator")),
    }


def normalize_freesound(item: dict[str, Any]) -> dict[str, Any]:
    sound_id = str(_first(item, "id", default=""))
    previews = item.get("previews") if isinstance(item.get("previews"), dict) else {}
    return {
        "provider": "freesound", "id": sound_id, "title": _first(item, "name", default="Untitled sound"),
        "creator": _first(item, "username", default="Unknown creator"), "duration": _first(item, "duration"),
        "genre": None, "preview_url": _safe_http_url(previews.get("preview-hq-mp3")),
        "download_url": None, "source_url": f"https://freesound.org/s/{sound_id}/" if sound_id else None,
        "license": _first(item, "license", default="See Freesound sound page"), "license_url": None, "attribution": True,
    }


async def _get_json(url: str, params: dict[str, Any] | None = None, headers: dict[str, str] | None = None) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=TIMEOUT, follow_redirects=True, headers={"User-Agent": "MusicAssistant/0.1"}) as client:
        response = await client.get(url, params=params, headers=headers)
        response.raise_for_status()
        data = response.json()
        return data if isinstance(data, dict) else {"results": data}


async def search_freetouse(query: str, limit: int) -> list[dict[str, Any]]:
    data = await _get_json(f"{FREETOUSE_API}/music/tracks/search", {"query": query, "limit": limit})
    rows = data.get("results", data.get("tracks", data.get("data", [])))
    if isinstance(rows, dict):
        rows = rows.get("results", [])
    return [normalize_freetouse(row) for row in rows if isinstance(row, dict)][:limit] if isinstance(rows, list) else []


async def search_openverse(query: str, limit: int) -> list[dict[str, Any]]:
    data = await _get_json(OPENVERSE_API, {"q": query, "page_size": limit, "mature": "false"})
    rows = data.get("results", [])
    return [normalize_openverse(row) for row in rows if isinstance(row, dict)][:limit] if isinstance(rows, list) else []


async def search_freesound(query: str, limit: int) -> list[dict[str, Any]]:
    token = os.getenv("FREESOUND_API_KEY")
    if not token:
        return []
    data = await _get_json(FREESOUND_API, {"query": query, "page_size": limit, "fields": "id,name,username,duration,license,previews"}, {"Authorization": f"Token {token}"})
    rows = data.get("results", [])
    return [normalize_freesound(row) for row in rows if isinstance(row, dict)][:limit] if isinstance(rows, list) else []


async def search_all(query: str, limit: int = 8, providers: list[str] | None = None) -> dict[str, Any]:
    import asyncio
    selected = providers or ["freetouse", "openverse", "freesound"]
    allowed = {"freetouse": search_freetouse, "openverse": search_openverse, "freesound": search_freesound}
    tasks = {name: fn(query, limit) for name, fn in allowed.items() if name in selected}
    names = list(tasks)
    results = await asyncio.gather(*tasks.values(), return_exceptions=True)
    tracks: list[dict[str, Any]] = []
    errors: dict[str, str] = {}
    for name, result in zip(names, results):
        if isinstance(result, Exception):
            errors[name] = type(result).__name__
        else:
            tracks.extend(result)
    try:
        from app.metadata_index import MetadataIndex
        MetadataIndex(os.getenv("MUSIC_INDEX_PATH", "data/music_index.sqlite3")).upsert_many(tracks)
    except Exception:
        pass
    return {"query": query, "results": tracks, "provider_errors": errors, "note": "Always verify the individual track licence and intended use before publishing."}


async def discover_for_brief(brief: str, limit: int = 8, providers: list[str] | None = None) -> dict[str, Any]:
    from app.query_understanding import understand_brief
    from app.ranking import rank_tracks
    interpretation = understand_brief(brief)
    import asyncio
    queries = interpretation["search_queries"]
    batches = await asyncio.gather(*(search_all(q[:240], limit, providers) for q in queries), return_exceptions=True)
    combined: list[dict[str, Any]] = []
    errors: dict[str, str] = {}
    seen: set[tuple[str, str]] = set()
    for batch in batches:
        if isinstance(batch, Exception):
            errors["discovery"] = type(batch).__name__
            continue
        errors.update(batch.get("provider_errors", {}))
        for track in batch.get("results", []):
            key = (str(track.get("provider")), str(track.get("id") or track.get("source_url")))
            if key not in seen:
                seen.add(key)
                combined.append(track)
    ranked = rank_tracks(combined, interpretation)
    return {
        "interpretation": interpretation, "queries_used": queries,
        "results": ranked[:limit * max(1, len(providers or ["freetouse", "openverse", "freesound"]))],
        "provider_errors": errors, "ranking_method": "explainable_weighted_metadata_v1",
        "licence_notice": "A relevance match is not licence clearance. Verify the individual source page and current terms for the exact project and use.",
    }
