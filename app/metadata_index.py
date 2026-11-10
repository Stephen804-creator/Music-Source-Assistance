from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


class MetadataIndex:
    """SQLite index for local development when DATABASE_URL is not configured."""
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
            for track in tracks:
                provider, pid = str(track.get("provider") or ""), str(track.get("id") or "")
                if not provider or not pid:
                    continue
                values = (provider, pid, str(track.get("title") or "Untitled"), str(track.get("creator") or ""),
                          str(track.get("description") or ""), " ".join(map(str, track.get("tags") or [])),
                          track.get("duration"), str(track.get("license") or ""), track.get("source_url"),
                          json.dumps(track, ensure_ascii=False))
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


class PostgresMetadataIndex:
    """Persistent hosted catalogue using Render PostgreSQL."""
    def __init__(self, database_url: str):
        parsed = urlparse(database_url)
        if parsed.scheme not in {"postgres", "postgresql"} or not parsed.hostname:
            raise ValueError("DATABASE_URL must be a PostgreSQL connection URL")
        self.database_url = database_url

    def _connect(self):
        import psycopg
        return psycopg.connect(self.database_url, connect_timeout=8)

    def initialize(self):
        migration = Path(__file__).resolve().parent.parent / "migrations" / "001_music_catalogue.sql"
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(migration.read_text(encoding="utf-8"))

    def ping(self) -> bool:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
                return cur.fetchone()[0] == 1

    def upsert_many(self, tracks: list[dict[str, Any]]) -> int:
        from psycopg.types.json import Jsonb
        rows = []
        for track in tracks:
            provider, pid = str(track.get("provider") or ""), str(track.get("id") or "")
            if not provider or not pid:
                continue
            tags = track.get("tags") or []
            if isinstance(tags, str):
                tags = [tags]
            rows.append((provider, pid, str(track.get("title") or "Untitled"),
                str(track.get("creator") or ""), str(track.get("description") or ""),
                [str(tag) for tag in tags], track.get("duration"), track.get("bpm"),
                track.get("key"), track.get("energy"), str(track.get("license") or ""),
                track.get("license_url"), track.get("source_url"), track.get("preview_url"), Jsonb(track)))
        if not rows:
            return 0
        sql = """INSERT INTO catalogue_tracks
            (provider,provider_track_id,title,creator,description,tags,duration_seconds,bpm,musical_key,energy,
             licence_code,licence_url,source_url,preview_url,raw_metadata)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT(provider,provider_track_id) DO UPDATE SET
             title=EXCLUDED.title,creator=EXCLUDED.creator,description=EXCLUDED.description,tags=EXCLUDED.tags,
             duration_seconds=EXCLUDED.duration_seconds,bpm=EXCLUDED.bpm,musical_key=EXCLUDED.musical_key,
             energy=EXCLUDED.energy,licence_code=EXCLUDED.licence_code,licence_url=EXCLUDED.licence_url,
             source_url=EXCLUDED.source_url,preview_url=EXCLUDED.preview_url,raw_metadata=EXCLUDED.raw_metadata,
             indexed_at=NOW()"""
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.executemany(sql, rows)
        return len(rows)

    def search(self, query: str, limit: int = 30) -> list[dict[str, Any]]:
        sql = """SELECT raw_metadata FROM catalogue_tracks
            WHERE to_tsvector('simple', coalesce(title,'') || ' ' || coalesce(creator,'') || ' ' ||
                  coalesce(description,'') || ' ' || array_to_string(tags,' '))
                  @@ plainto_tsquery('simple', %s)
               OR title ILIKE %s OR creator ILIKE %s OR description ILIKE %s
               OR array_to_string(tags,' ') ILIKE %s
            ORDER BY indexed_at DESC LIMIT %s"""
        pattern = f"%{query}%"
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (query, pattern, pattern, pattern, pattern, limit))
                return [row[0] for row in cur.fetchall()]


def get_metadata_index():
    database_url = os.getenv("DATABASE_URL")
    return PostgresMetadataIndex(database_url) if database_url else MetadataIndex(
        os.getenv("MUSIC_INDEX_PATH", "data/music_index.sqlite3"))
