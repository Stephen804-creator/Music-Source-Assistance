from app.query_understanding import understand_brief
from app.ranking import rank_tracks
from app.metadata_index import MetadataIndex


def test_ranker_explains_matches():
    intent = understand_brief("emotional African documentary with piano, no vocals")
    tracks = [
        {"provider":"openverse", "id":"1", "title":"Emotional African Piano", "genre":"documentary instrumental", "duration":580, "license":"BY", "source_url":"https://example.org/1"},
        {"provider":"openverse", "id":"2", "title":"Fast techno club", "genre":"electronic", "duration":180, "license":"unknown"},
    ]
    ranked = rank_tracks(tracks, intent)
    assert ranked[0]["id"] == "1"
    assert ranked[0]["relevance_score"] > ranked[1]["relevance_score"]
    assert ranked[0]["match_reasons"]


def test_metadata_index_upserts_and_searches(tmp_path):
    index = MetadataIndex(tmp_path / "catalogue.sqlite3")
    track = {"provider":"test", "id":"x1", "title":"Hopeful Piano Journey", "creator":"A Creator", "tags":["cinematic"], "source_url":"https://example.org/x1"}
    assert index.upsert_many([track]) == 1
    results = index.search("Hopeful")
    assert results and results[0]["id"] == "x1"
    track["title"] = "Hopeful Piano Journey Updated"
    assert index.upsert_many([track]) == 1
    assert "Updated" in index.search("Updated")[0]["title"]


def test_metadata_index_selects_postgres_for_hosted_environment(monkeypatch):
    from app.metadata_index import PostgresMetadataIndex, get_metadata_index

    monkeypatch.setenv("DATABASE_URL", "postgresql://music:secret@example.test:5432/catalogue")
    assert isinstance(get_metadata_index(), PostgresMetadataIndex)


def test_metadata_index_keeps_sqlite_for_local_development(monkeypatch, tmp_path):
    from app.metadata_index import MetadataIndex, get_metadata_index

    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("MUSIC_INDEX_PATH", str(tmp_path / "local.sqlite3"))
    assert isinstance(get_metadata_index(), MetadataIndex)


def test_postgres_index_rejects_non_postgres_database_url():
    import pytest
    from app.metadata_index import PostgresMetadataIndex

    with pytest.raises(ValueError, match="PostgreSQL"):
        PostgresMetadataIndex("sqlite:///not-postgres.db")
