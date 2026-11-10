import pytest
from app.query_understanding import understand_brief


def test_understands_documentary_brief_without_model():
    result = understand_brief("I am making a 10-minute African documentary, emotional piano and strings, no vocals, for YouTube monetization")
    assert "emotional" in result["attributes"]["moods"]
    assert "african" in result["attributes"]["genres"]
    assert "piano" in result["attributes"]["instruments"]
    assert result["duration_target_seconds"] == 600
    assert "youtube" in result["use_cases"]
    assert result["constraints"]["instrumental_only"] is True
    assert result["constraints"]["commercial_use_requested"] is True
    assert result["interpretation_method"] == "ontology_rules_v1"
    assert len(result["search_queries"]) >= 2


def test_synonyms_expand_to_canonical_concepts():
    result = understand_brief("A hopeful, touching film score with cello and felt piano")
    assert "uplifting" in result["attributes"]["moods"]
    assert "emotional" in result["attributes"]["moods"]
    assert "cinematic" in result["attributes"]["genres"]
    assert "strings" in result["attributes"]["instruments"]
    assert "piano" in result["attributes"]["instruments"]
    assert "hopeful" in result["expanded_terms"]


def test_parses_duration_bpm_and_key():
    result = understand_brief("Need calm ambient piano, 2:30 long, 80 BPM, in C minor")
    assert result["duration_target_seconds"] == 150
    assert result["bpm_target"] == 80
    assert result["key_target"] == "c minor"


def test_unknown_brief_is_preserved():
    result = understand_brief("A quiet soundscape for a scene at dawn")
    assert result["brief"] == "A quiet soundscape for a scene at dawn"
    assert result["search_queries"][0] == result["brief"]


def test_rejects_empty_and_oversized_briefs():
    with pytest.raises(ValueError): understand_brief("  ")
    with pytest.raises(ValueError): understand_brief("x" * 2001)
