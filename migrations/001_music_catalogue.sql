-- PostgreSQL catalogue schema for hosted deployment. Provider metadata only.
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE TABLE IF NOT EXISTS catalogue_tracks (
  id BIGSERIAL PRIMARY KEY,
  provider TEXT NOT NULL,
  provider_track_id TEXT NOT NULL,
  title TEXT NOT NULL,
  creator TEXT,
  description TEXT,
  tags TEXT[] NOT NULL DEFAULT '{}',
  duration_seconds DOUBLE PRECISION,
  bpm DOUBLE PRECISION,
  musical_key TEXT,
  energy DOUBLE PRECISION,
  licence_code TEXT,
  licence_url TEXT,
  source_url TEXT,
  preview_url TEXT,
  raw_metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  indexed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE(provider, provider_track_id)
);
CREATE INDEX IF NOT EXISTS catalogue_tracks_title_trgm ON catalogue_tracks USING gin (title gin_trgm_ops);
CREATE INDEX IF NOT EXISTS catalogue_tracks_search ON catalogue_tracks USING gin (to_tsvector('simple', coalesce(title,'') || ' ' || coalesce(creator,'') || ' ' || coalesce(description,'')));
CREATE INDEX IF NOT EXISTS catalogue_tracks_tags ON catalogue_tracks USING gin (tags);
