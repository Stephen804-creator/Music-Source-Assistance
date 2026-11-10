"""Transparent, model-free interpretation and query expansion for music briefs."""
from __future__ import annotations
import json, re
from functools import lru_cache
from pathlib import Path
from typing import Any

ONTOLOGY_PATH = Path(__file__).with_name("music_ontology.json")

@lru_cache(maxsize=1)
def load_ontology() -> dict[str, Any]:
    return json.loads(ONTOLOGY_PATH.read_text(encoding="utf-8"))

def _normalise(value: str) -> str:
    value = value.casefold().replace("’", "'")
    return re.sub(r"\s+", " ", value).strip()

def _contains(text: str, phrase: str) -> bool:
    return bool(re.search(rf"(?<![\w]){re.escape(phrase)}(?![\w])", text))

def _extract_groups(text: str, ontology: dict[str, Any]) -> dict[str, list[str]]:
    found: dict[str, list[str]] = {}
    for group, concepts in ontology["concepts"].items():
        matches = []
        for canonical, synonyms in concepts.items():
            if any(_contains(text, _normalise(p)) for p in [canonical, *synonyms]):
                matches.append(canonical)
        found[group] = matches
    return found

def _duration_seconds(text: str) -> int | None:
    clock = re.search(r"\b(\d{1,2}):(\d{2})\b", text)
    if clock:
        return int(clock.group(1)) * 60 + int(clock.group(2))
    compact = re.search(r"\b(\d{1,3})\s*(?:m|min|mins|minutes?)\s*(\d{1,2})\s*(?:s|sec|secs|seconds?)?\b", text)
    if compact:
        return int(compact.group(1)) * 60 + int(compact.group(2))
    match = re.search(r"\b(\d{1,3})\s*[- ]?\s*(minutes?|mins?|min|seconds?|secs?|sec)\b", text)
    if match:
        amount = int(match.group(1))
        return amount * (60 if match.group(2).startswith("m") else 1)
    return None

def understand_brief(brief: str) -> dict[str, Any]:
    if not isinstance(brief, str) or not brief.strip() or len(brief) > 2000:
        raise ValueError("brief must contain 1 to 2000 characters")
    text = _normalise(brief)
    ontology = load_ontology()
    attributes = _extract_groups(text, ontology)
    use_cases = [name for name, terms in ontology["use_cases"].items() if any(_contains(text, _normalise(t)) for t in [name, *terms])]
    duration = _duration_seconds(text)
    bpm = None
    bpm_match = re.search(r"\b(\d{2,3})\s*bpm\b", text)
    if bpm_match and 30 <= int(bpm_match.group(1)) <= 300:
        bpm = int(bpm_match.group(1))
    key_match = re.search(r"\b(?:in|key of)\s+([a-g](?:#|b)?\s*(?:major|minor))\b", text)
    constraints = {
        "instrumental_only": any(_contains(text, x) for x in ("no vocals", "without vocals", "instrumental", "no singing")),
        "vocals_requested": any(_contains(text, x) for x in ("with vocals", "singing", "vocal track", "lyrics")),
        "commercial_use_requested": any(_contains(text, x) for x in ("commercial", "monetised", "monetized", "monetisation", "monetization", "client project", "advertisement")),
        "youtube_monetisation_requested": any(_contains(text, x) for x in ("monetised youtube", "monetized youtube", "monetise youtube", "monetize youtube", "youtube monetisation", "youtube monetization")),
        "attribution_required_avoided": any(_contains(text, x) for x in ("no attribution", "without attribution", "no credit required")),
        "loopable_requested": "loopable" in attributes.get("production", []),
    }
    expanded: list[str] = []
    for group, names in attributes.items():
        for name in names:
            expanded.append(name)
            expanded.extend(ontology["concepts"][group].get(name, [])[:3])
    expanded.extend(use_cases)
    if constraints["instrumental_only"]:
        expanded.extend(["instrumental", "no vocals"])
    if constraints["vocals_requested"]:
        expanded.append("vocals")
    if bpm:
        expanded.append(f"{bpm} BPM")
    if key_match:
        expanded.append(f"key {key_match.group(1)}")
    tokens = list(dict.fromkeys(expanded))
    queries = [brief.strip()]
    if tokens:
        queries.append(" ".join(tokens[:14]))
    mood, genre, instruments = attributes.get("moods", []), attributes.get("genres", []), attributes.get("instruments", [])
    if mood and (genre or instruments):
        queries.append(" ".join([*mood[:2], *genre[:2], *instruments[:3], "instrumental" if constraints["instrumental_only"] else ""]))
    queries = list(dict.fromkeys(q.strip()[:240] for q in queries if q.strip()))
    return {
        "brief": brief.strip(), "attributes": attributes, "use_cases": use_cases,
        "duration_target_seconds": duration, "bpm_target": bpm,
        "key_target": key_match.group(1) if key_match else None,
        "constraints": constraints, "expanded_terms": tokens[:40], "search_queries": queries,
        "interpretation_method": "ontology_rules_v1", "ontology_version": ontology.get("version", "unknown"),
        "limitations": "Rule-based interpretation recognises curated concepts and synonyms. Nuanced intent may require clarification; unknown wording is retained in the original query.",
    }
