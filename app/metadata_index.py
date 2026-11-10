"""Small local SQLite metadata index with FTS5 when available.

The index stores provider metadata only, not copyrighted audio files. It is a
local/dev fallback; PostgreSQL schema for hosted multi-user deployment is in
migrations/001_music_catalogue.sql.
"""
from __future__ import annotations
import json, sqlite3
from pathlib import Path
from typing import Any

class MetadataIndex:
    def __init__(self, path: str | Path = "data/music_index.sqlite3"):
        self.path = str(path)
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self._init()

    def _connect(self):
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init(self):
        with self._connect() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS tracks (
                provider TEXT NOT NULL, provider_id TEXT NOT NULL, title TEXT NOT NULL,
                creator TEXT, description TEXT, tags TEXT, duration REAL, license TEXT,
                source_url TEXT, payload TEXT NOT NULL, updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY(provider, provider_id))""")
            try:
                db.execute("""CREATE VIRTUAL TABLE IF NOT EXISTS tracks_fts USING fts5(
                    provider UNINDEXED, provider_id UNINDEXED, title, creator, description, tags)""")
            except sqlite3.OperationalError:
                pass

    def upsert_many(self, tracks: list[dict[str, Any]]) -> int:
        count = 0
        with self._connect() as db:
            for t in tracks:
                provider, pid = str(t.get("provider") or ""), str(t.get("id") or "")
                if not provider or not pid:
                    continue
                values = (provider, pid, str(t.get("title") or "Untitled"), str(t.get("creator") or ""),
                          str(t.get("description") or ""), " ".join(map(str, t.get("tags") or [])),
                          t.get("duration"), str(t.get("license") or ""), t.get("source_url"),
                          json.dumps(t, ensure_ascii=False))
                db.execute("""INSERT INTO tracks(provider,provider_id,title,creator,description,tags,duration,license,source_url,payload,updated_at)
                    VALUES(?,?,?,?,?,?,?,?,?,?,CURRENT_TIMESTAMP) ON CONFLICT(provider,provider_id) DO UPDATE SET
                    title=excluded.title,creator=excluded.creator,description=excluded.description,tags=excluded.tags,
                    duration=excluded.duration,license=excluded.license,source_url=excluded.source_url,payload=excluded.payload,updated_at=CURRENT_TIMESTAMP""", values)
                try:
                    db.execute("DELETE FROM tracks_fts WHERE provider=? AND provider_id=?", (provider, pid))
                    db.execute("INSERT INTO tracks_fts(provider,provider_id,title,creator,description,tags) VALUES(?,?,?,?,?,?)", values[:6])
                except sqlite3.OperationalError:
                    pass
                count += 1
        return count

    def search(self, query: str, limit: int = 30) -> list[dict[str, Any]]:
        with self._connect() as db:
            try:
                rows = db.execute("SELECT t.payload FROM tracks_fts f JOIN tracks t USING(provider,provider_id) WHERE tracks_fts MATCH ? LIMIT ?", (query, limit)).fetchall()
            except sqlite3.OperationalError:
                like = f"%{query}%"
                rows = db.execute("SELECT payload FROM tracks WHERE title LIKE ? OR creator LIKE ? OR description LIKE ? OR tags LIKE ? LIMIT ?", (like, like, like, like, limit)).fetchall()
        return [json.loads(row[0]) for row in rows]
