import asyncio

import pytest
from fastapi.testclient import TestClient

from app import providers
from app.metadata_index import MetadataIndex


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("MUSIC_INDEX_PATH", str(tmp_path / "index.sqlite3"))
    from app.main import app
    # No `with`: skips lifespan, which can only start the MCP session manager once per process.
    return TestClient(app)


def test_health_ok(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_search_rejects_unknown_provider(client):
    response = client.get("/api/search", params={"q": "piano", "providers": "nope"})
    assert response.status_code == 422
    assert "nope" in response.json()["detail"]


def test_discover_rejects_unknown_provider(client):
    response = client.get("/api/discover", params={"brief": "hopeful piano", "providers": "nope"})
    assert response.status_code == 422


def test_index_search_survives_fts_syntax_characters(client):
    for query in ['"unbalanced', "piano AND (", "a*b", "'"]:
        response = client.get("/api/index/search", params={"q": query})
        assert response.status_code == 200, query
        assert response.json()["results"] == []


def test_validate_providers_normalises_and_rejects():
    assert providers.validate_providers(None) is None
    assert providers.validate_providers([" OpenVerse "]) == ["openverse"]
    with pytest.raises(ValueError):
        providers.validate_providers(["openverse", "bogus"])


def test_metadata_index_search_handles_quotes(tmp_path):
    index = MetadataIndex(tmp_path / "catalogue.sqlite3")
    index.upsert_many([{"provider": "test", "id": "1", "title": "Hopeful Piano", "source_url": "https://example.org/1"}])
    assert index.search('"piano')[0]["id"] == "1"
    assert index.search("") == []
    assert index.search('""') == []


def test_discover_never_returns_more_than_limit(monkeypatch):
    async def fake_search_all(query, limit=8, providers=None):
        tracks = [{"provider": "openverse", "id": str(i), "title": "Piano", "source_url": f"https://example.org/{i}"} for i in range(5)]
        return {"results": tracks, "provider_errors": {}}

    monkeypatch.setattr(providers, "search_all", fake_search_all)
    result = asyncio.run(providers.discover_for_brief("hopeful piano", 2))
    assert len(result["results"]) == 2
