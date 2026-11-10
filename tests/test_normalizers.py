from app.providers import normalize_freetouse, normalize_openverse, normalize_freesound


def test_freetouse_normalizer_extracts_mp3_and_metadata():
    result = normalize_freetouse({"id": 12, "title": "Hope", "artist_name": "Ari", "files": {"mp3": "https://cdn.freetouse.com/hope.mp3"}})
    assert result["provider"] == "freetouse"
    assert result["title"] == "Hope"
    assert result["creator"] == "Ari"
    assert result["download_url"].endswith("hope.mp3")


def test_openverse_normalizer_keeps_licence_and_source():
    result = normalize_openverse({"id": "abc", "title": "Rain", "creator": "Lee", "license": "by", "license_url": "https://creativecommons.org/licenses/by/4.0/", "url": "https://cdn.example.org/rain.mp3", "foreign_landing_url": "https://example.org/rain"})
    assert result["license"] == "BY"
    assert result["creator"] == "Lee"
    assert result["source_url"] == "https://example.org/rain"


def test_freesound_normalizer_does_not_invent_download_url():
    result = normalize_freesound({"id": 42, "name": "Door", "username": "sam", "license": "Attribution"})
    assert result["source_url"] == "https://freesound.org/s/42/"
    assert result["download_url"] is None
